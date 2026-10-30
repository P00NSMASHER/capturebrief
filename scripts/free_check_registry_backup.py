"""Operator-only encrypted snapshot of the free-check ten-business registry.

A consistent SQLite backup captures committed WAL transactions. Neither a
local backup nor local restore proves off-device custody, currentness, customer
admission, source approval, delivery, or permission to contact customers.
Requires pinned optional dependency cryptography==46.0.4.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import os
import re
import sqlite3
import stat
import struct
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from capturebrief_core.atomic_io import atomic_write_bytes, exclusive_path_lock
from capturebrief_core.free_trial import MAX_COHORT_SIZE, _SCHEMA
from capturebrief_core.private_order_registry import _private_db
from capturebrief_core.scoped_source import _private_path, private_root
from scripts.scoped_private_backup import (
    _bytes, _canon, _crypto, _key, _new_file, _unique,
    KDF_N, KDF_R, KDF_P, MAX_HEADER,
)

MAGIC = b"CAPTUREBRIEF-FREE-REGISTRY-AESGCM-V1\x00"
SCHEMA = "capturebrief-free-check-registry-backup-v1"
MAX_SNAPSHOT = 2 * 1024 * 1024
SHA = re.compile(r"^[0-9a-f]{64}$")
DIGEST_COLUMNS = (
    "business_sha256", "request_sha256", "original_case_sha256",
    "scope_sha256", "identity_review_sha256",
)
ZERO_COLUMNS = (
    "amount_due_cents", "automatic_upgrade_authorized",
    "customer_release_authorized", "external_send_authorized",
)
COLUMNS = (
    *DIGEST_COLUMNS, "reserved_at", "trial_state", *ZERO_COLUMNS,
)


def _expected_sql() -> str:
    return re.sub(r"\s+", " ", _SCHEMA.strip().replace(
        "CREATE TABLE IF NOT EXISTS", "CREATE TABLE", 1,
    )).strip().casefold()


def _validate_snapshot(data: bytes) -> int:
    """Inspect authenticated snapshot structure and reservation safety."""
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_SNAPSHOT:
        raise ValueError("Registry snapshot exceeds bounded SQLite allowance")
    with closing(sqlite3.connect(":memory:")) as db:
        db.deserialize(data)
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ValueError("Registry snapshot failed SQLite integrity check")
        objects = db.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY name",
        ).fetchall()
        tables = [item for item in objects if item[0] == "table"]
        if (len(tables) != 1 or tables[0][1] != "free_check_reservations"
                or re.sub(r"\s+", " ", tables[0][2]).strip().casefold() != _expected_sql()
                or any(t != "table" and not (
                    t == "index" and name.startswith(
                        "sqlite_autoindex_free_check_reservations_"
                    ) and sql is None
                ) for t, name, sql in objects)):
            raise ValueError("Registry must contain only the exact guarded reservations schema")
        columns = tuple(row[1] for row in db.execute(
            "PRAGMA table_info(free_check_reservations)"
        ))
        if columns != COLUMNS:
            raise ValueError("Registry reservation column order differs from release schema")
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT * FROM free_check_reservations").fetchall()
        if len(rows) > MAX_COHORT_SIZE:
            raise ValueError("Registry exceeds ten-business cap")
        # Use one UTC bound for the entire recovered snapshot. A timestamp
        # arbitrarily far in the future cannot be valid historical custody.
        # Allow five minutes for ordinary workstation clock skew.
        future_limit = datetime.now(timezone.utc) + timedelta(minutes=5)
        for row in rows:
            if (any(not isinstance(row[k], str) or not SHA.fullmatch(row[k])
                    for k in DIGEST_COLUMNS)
                    or row["trial_state"] != "RESERVED_REVIEW_REQUIRED"
                    or any(type(row[k]) is not int or row[k] != 0 for k in ZERO_COLUMNS)):
                raise ValueError("Registry reservation has an invalid identity or authority flag")
            try:
                raw = row["reserved_at"]
                at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except (TypeError, AttributeError, ValueError):
                raise ValueError("Invalid registry reservation timestamp") from None
            if (at.tzinfo is None or at.utcoffset() is None
                    or at.utcoffset().total_seconds() != 0):
                raise ValueError("Reservation timestamp must be UTC")
            if at > future_limit:
                raise ValueError("Registry contains a future-dated reservation")
        return len(rows)


def _snapshot(path: str | Path) -> tuple[bytes, int]:
    source = _private_db(path)
    if (not source.is_file() or source.is_symlink()
            or (os.name != "nt" and source.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO))):
        raise ValueError("Registry must be an existing owner-only SQLite file")
    private_root(source.parent)
    if source.stat().st_size > MAX_SNAPSHOT:
        raise ValueError("Registry exceeds permitted source size")
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=5)) as db:
        pages = db.execute("PRAGMA page_count").fetchone()[0]
        size = db.execute("PRAGMA page_size").fetchone()[0]
        if pages * size > MAX_SNAPSHOT:
            raise ValueError("Registry database including WAL exceeds bounded snapshot")
        with closing(sqlite3.connect(":memory:")) as snapshot:
            snapshot.execute("PRAGMA temp_store=MEMORY")
            db.backup(snapshot)
            # SQLite backup retains the source WAL header in its in-memory
            # copy. VACUUM normalizes it to a portable rollback-mode file,
            # without staging any unencrypted temporary database on disk.
            snapshot.execute("VACUUM")
            data = snapshot.serialize()
            if data[18:20] != b"\x01\x01":
                raise ValueError("Registry snapshot journal header was not normalized")
    return data, _validate_snapshot(data)


def create_backup(registry: str | Path, output: str | Path,
                  passphrase: bytes) -> dict[str, object]:
    path = _new_file(output)
    data, count = _snapshot(registry)
    AESGCM, _ = _crypto()
    salt, nonce = os.urandom(16), os.urandom(12)
    head = _canon({
        "schema": SCHEMA, "cipher": "AES-256-GCM", "kdf": "scrypt",
        "n": KDF_N, "r": KDF_R, "p": KDF_P,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "plaintext_sha256": hashlib.sha256(data).hexdigest(),
        "plaintext_bytes": len(data), "reservation_count": count,
    })
    if len(head) > MAX_HEADER:
        raise ValueError("Registry backup header exceeds bound")
    prefix = MAGIC + struct.pack(">I", len(head)) + head
    encrypted = AESGCM(_key(passphrase, salt)).encrypt(nonce, data, prefix)
    atomic_write_bytes(path, prefix + encrypted, overwrite=False, mode=0o600)
    return {
        "status": "FREE_REGISTRY_LOCAL_ENCRYPTED_SNAPSHOT_CREATED",
        "backup_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "reservation_count": count,
        "offdevice_copy_verified": False,
        "independent_restore_verified": False,
        "reconciliation_required_before_use": True,
        "customer_release_authorized": False,
        "external_send_authorized": False,
    }


def _open_backup(backup: str | Path, passphrase: bytes) -> tuple[bytes, int]:
    raw = _bytes(_private_path(backup, directory=False),
                 MAX_SNAPSHOT + MAX_HEADER + len(MAGIC) + 64)
    marker = len(MAGIC)
    if not raw.startswith(MAGIC) or len(raw) < marker + 4:
        raise ValueError("Unsupported or truncated registry backup")
    n = struct.unpack(">I", raw[marker:marker + 4])[0]
    if not 0 < n <= MAX_HEADER or len(raw) < marker + 4 + n + 16:
        raise ValueError("Invalid registry backup header length")
    head = raw[marker + 4:marker + 4 + n]
    header = json.loads(head.decode("utf-8"), object_pairs_hook=_unique)
    keys = {
        "schema", "cipher", "kdf", "n", "r", "p", "salt_b64",
        "nonce_b64", "plaintext_sha256", "plaintext_bytes", "reservation_count",
    }
    if (not isinstance(header, dict) or set(header) != keys
            or head != _canon(header) or header["schema"] != SCHEMA
            or header["cipher"] != "AES-256-GCM" or header["kdf"] != "scrypt"
            or (header["n"], header["r"], header["p"]) != (KDF_N, KDF_R, KDF_P)
            or type(header["plaintext_bytes"]) is not int
            or not 0 < header["plaintext_bytes"] <= MAX_SNAPSHOT
            or type(header["reservation_count"]) is not int
            or not 0 <= header["reservation_count"] <= MAX_COHORT_SIZE
            or not isinstance(header["plaintext_sha256"], str)
            or not SHA.fullmatch(header["plaintext_sha256"])):
        raise ValueError("Registry backup encryption contract is invalid")
    try:
        salt = base64.b64decode(header["salt_b64"], validate=True)
        nonce = base64.b64decode(header["nonce_b64"], validate=True)
    except (ValueError, TypeError):
        raise ValueError("Invalid encrypted registry salt or nonce") from None
    if len(salt) != 16 or len(nonce) != 12:
        raise ValueError("Invalid encrypted registry salt or nonce length")
    AESGCM, _ = _crypto()
    start = marker + 4 + n
    data = AESGCM(_key(passphrase, salt)).decrypt(nonce, raw[start:], raw[:start])
    if (len(data) != header["plaintext_bytes"]
            or hashlib.sha256(data).hexdigest() != header["plaintext_sha256"]):
        raise ValueError("Registry payload does not match authenticated bytes")
    count = _validate_snapshot(data)
    if count != header["reservation_count"]:
        raise ValueError("Registry reservation count disagrees with encrypted header")
    return data, count


def verify_backup(backup: str | Path, passphrase: bytes) -> dict[str, object]:
    _, count = _open_backup(backup, passphrase)
    return {
        "status": "FREE_REGISTRY_LOCAL_BACKUP_INTEGRITY_VERIFIED",
        "reservation_count": count,
        "offdevice_copy_verified": False,
        "reconciliation_required_before_use": True,
        "customer_release_authorized": False,
        "external_send_authorized": False,
    }


def restore_backup(backup: str | Path, output: str | Path,
                   passphrase: bytes) -> dict[str, object]:
    data, count = _open_backup(backup, passphrase)
    dest = _private_db(output)
    private_root(dest.parent)
    if (dest.exists() or dest.is_symlink()
            or any(dest.with_name(dest.name + suffix).exists()
                   for suffix in ("-wal", "-shm", "-journal"))):
        raise ValueError("Restore requires a fresh SQLite destination without journal sidecars")
    with exclusive_path_lock(dest, timeout_seconds=5, suffix=".restore.lock"):
        if (dest.exists() or any(dest.with_name(dest.name + suffix).exists()
                                 for suffix in ("-wal", "-shm", "-journal"))):
            raise ValueError("Restore destination already exists or has SQLite sidecars")
        atomic_write_bytes(dest, data, overwrite=False, mode=0o600)
    return {
        "status": "FREE_REGISTRY_LOCALLY_RESTORED_RECONCILIATION_REQUIRED",
        "reservation_count": count,
        "independent_offdevice_restore_proven": False,
        "reconciliation_required_before_use": True,
        "customer_release_authorized": False,
        "external_send_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for command in ("create", "verify", "restore"):
        sub = commands.add_parser(command)
        sub.add_argument("--backup-file", required=True)
        if command == "create":
            sub.add_argument("--registry", required=True)
        if command == "restore":
            sub.add_argument("--output-registry", required=True)
    args = parser.parse_args(argv)
    try:
        secret = getpass.getpass("Recovery phrase (never printed/stored): ").encode()
        if args.action == "create":
            result = create_backup(args.registry, args.backup_file, secret)
        elif args.action == "verify":
            result = verify_backup(args.backup_file, secret)
        else:
            result = restore_backup(args.backup_file, args.output_registry, secret)
    except Exception as exc:
        print(json.dumps({
            "status": "FREE_REGISTRY_BACKUP_BLOCKED",
            "error_type": type(exc).__name__,
            "customer_release_authorized": False,
            "external_send_authorized": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
