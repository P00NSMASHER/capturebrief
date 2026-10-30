"""Create and verify a CONSISTENT private snapshot of CaptureBrief's shared nonce ledger.

Pre-first-customer operator tool. Does NOT use customer data, grant approvals,
send messages, provision cloud storage, or restore/promote an old ledger.
Snapshot only committed SQLite transactions, including uncheckpointed WAL,
then normalize in memory and publish a new 0600 copy outside Git.

A backup can be stale. Never promote it without independent reconciliation
against every later authorization and the original verified manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import stat
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from capturebrief_core.accepted_case_release import (
    AcceptedCaseBlocked, _root, _reject_private_path_links,
)
from capturebrief_core.authorization_ledger import _SCHEMA, _validate_ledger
from capturebrief_core.atomic_io import atomic_write_bytes, exclusive_path_lock

MAX_LEDGER_BYTES = 8 * 1024 * 1024


def _path(value: str | Path, *, must_exist: bool) -> Path:
    raw = Path(value).expanduser().absolute()
    _reject_private_path_links(raw)
    if raw.suffix != ".sqlite" or raw.name.startswith("."):
        raise ValueError("Authorization ledger needs a private .sqlite file")
    parent = _root(raw.parent)
    # Normalize Windows 8.3 aliases only after symlink/reparse rejection.
    path = parent / raw.name
    if must_exist:
        if not path.is_file() or path.is_symlink():
            raise ValueError("Existing private authorization ledger required")
        if os.name != "nt" and path.stat().st_mode & 0o077:
            raise ValueError("Authorization ledger must have 0600 permissions")
    elif path.exists() or path.is_symlink() or any(
        path.with_name(path.name + suffix).exists()
        for suffix in ("-wal", "-shm", "-journal")
    ):
        raise ValueError("New private ledger/snapshot destination must not overwrite data")
    return path


def initialize_empty_ledger(path: str | Path) -> dict[str, object]:
    """Establish ONE empty registry before customers; never reset existing entries."""
    target = _path(path, must_exist=False)
    with exclusive_path_lock(target, timeout_seconds=5, suffix=".nonce-init.lock"):
        _path(target, must_exist=False)
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            with closing(sqlite3.connect(target, timeout=5)) as db:
                db.execute("PRAGMA synchronous=FULL")
                db.execute(_SCHEMA)
                db.commit()
                _validate_ledger(db, datetime.now(timezone.utc))
        except Exception:
            # Roll back only the file this initializer exclusively created.
            target.unlink(missing_ok=True)
            raise
    return {
        "status": "EMPTY_AUTHORIZATION_LEDGER_INITIALIZED_NO_CUSTOMER",
        "reservation_count": 0,
        "can_reset_existing_authorizations": False,
        "customer_release_authorized": False,
        "external_send_performed": False,
    }


def _validate_bytes(data: bytes, *, now: datetime | None = None) -> int:
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_LEDGER_BYTES:
        raise ValueError("Authorization ledger snapshot is missing or oversized")
    if len(data) < 100 or data[:16] != b"SQLite format 3\x00" or data[18:20] != b"\x01\x01":
        raise ValueError("Authorization snapshot is not portable rollback-mode SQLite")
    clock = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(clock, datetime) or clock.utcoffset() is None:
        raise ValueError("Authorization inspection time must be timezone-aware")
    try:
        with closing(sqlite3.connect(":memory:")) as db:
            db.deserialize(data)
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA query_only=ON")
            _validate_ledger(db, clock.astimezone(timezone.utc))
            count = db.execute(
                "SELECT COUNT(*) FROM single_message_authorizations"
            ).fetchone()[0]
            if not isinstance(count, int) or count < 0:
                raise ValueError("Authorization ledger row count is invalid")
            return count
    except (sqlite3.DatabaseError, AcceptedCaseBlocked) as exc:
        raise ValueError("Authorization snapshot failed schema, integrity or nonce checks") from None


def _capture(source: str | Path) -> tuple[bytes, int]:
    path = _path(source, must_exist=True)
    if not 0 < path.stat().st_size <= MAX_LEDGER_BYTES:
        raise ValueError("Authorization ledger source has invalid size")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        pages = db.execute("PRAGMA page_count").fetchone()[0]
        size = db.execute("PRAGMA page_size").fetchone()[0]
        if pages * size > MAX_LEDGER_BYTES:
            raise ValueError("Authorization ledger committed pages exceed snapshot budget")
        _validate_ledger(db, datetime.now(timezone.utc))
        with closing(sqlite3.connect(":memory:")) as restored:
            restored.execute("PRAGMA temp_store=MEMORY")
            db.backup(restored)
            # Backup API can preserve a WAL-mode SQLite header (2,2).
            # Normalize IN MEMORY so an isolated restore opens on Windows.
            restored.execute("VACUUM")
            data = restored.serialize()
    return data, _validate_bytes(data)


def create_snapshot(source: str | Path, output: str | Path) -> dict[str, object]:
    path = _path(output, must_exist=False)
    data, count = _capture(source)
    # Reject source==destination, symlinks and reusing existing snapshots.
    with exclusive_path_lock(path, timeout_seconds=5, suffix=".nonce-snapshot.lock"):
        _path(path, must_exist=False)
        atomic_write_bytes(path, data, overwrite=False, mode=0o600)
    return {
        "status": "CONSISTENT_SHARED_NONCE_LEDGER_SNAPSHOT_CREATED",
        "snapshot_sha256": hashlib.sha256(data).hexdigest(),
        "reservation_count": count,
        "committed_wal_state_included": True,
        "reconciliation_required_before_any_restore": True,
        "independent_offdevice_restore_verified": False,
        "customer_release_authorized": False,
        "external_send_performed": False,
    }


def verify_snapshot(path: str | Path) -> dict[str, object]:
    item = _path(path, must_exist=True)
    # A one-time size check is insufficient: an equally sized SQLite file
    # could replace this path *during* read_bytes(), leaving a stale digest
    # reported as verification of the new file. This is a read-only guard,
    # not evidence that the file can never change after verification.
    before = item.stat()
    if not 0 < before.st_size <= MAX_LEDGER_BYTES:
        raise ValueError("Authorization snapshot source exceeds allowed size")
    data = item.read_bytes()
    _reject_private_path_links(item)
    try:
        after = item.stat()
    except OSError:
        raise ValueError("Authorization snapshot changed during read") from None
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if len(data) != before.st_size or identity_before != identity_after:
        raise ValueError("Authorization snapshot changed during read")
    # Windows' stat metadata can fail to distinguish a rapid same-size
    # replacement. Independently re-open this bounded file and compare bytes
    # before reporting a source-path digest. Still not a permanent-lock claim.
    with item.open("rb") as stream:
        confirmation = stream.read(MAX_LEDGER_BYTES + 1)
    _reject_private_path_links(item)
    latest = item.stat()
    if (confirmation != data or
            (latest.st_dev, latest.st_ino, latest.st_size, latest.st_mtime_ns)
            != identity_after):
        raise ValueError("Authorization snapshot changed during read")
    count = _validate_bytes(data)
    return {
        "status": "SHARED_NONCE_LEDGER_SNAPSHOT_INTEGRITY_VERIFIED",
        "snapshot_sha256": hashlib.sha256(data).hexdigest(),
        "reservation_count": count,
        "safe_to_promote_without_reconciliation": False,
        "customer_release_authorized": False,
        "external_send_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_subparsers(dest="command", required=True)
    init = action.add_parser("init")
    init.add_argument("--ledger", required=True)
    snapshot = action.add_parser("snapshot")
    snapshot.add_argument("--ledger", required=True)
    snapshot.add_argument("--snapshot-file", required=True)
    verify = action.add_parser("verify")
    verify.add_argument("--snapshot-file", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            output = initialize_empty_ledger(args.ledger)
        elif args.command == "snapshot":
            output = create_snapshot(args.ledger, args.snapshot_file)
        else:
            output = verify_snapshot(args.snapshot_file)
    except (ValueError, AcceptedCaseBlocked, sqlite3.DatabaseError, OSError):
        print(json.dumps({
            "status": "NONCE_LEDGER_SNAPSHOT_BLOCKED",
            "customer_release_authorized": False,
            "external_send_performed": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
