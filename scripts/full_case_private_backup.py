"""Offline encrypted full-case evidence backup candidate (NO external transport).

Pre-approval operator tool: backs up the complete *pre-release* case inventory
except the as-yet-uncreated encrypted backup and independent restore receipt.
All inputs must be in a restricted private location OUTSIDE Git/Pages/CI.
Never asserts complete SAM history, customer identity, source authenticity,
actual off-device recovery, human authorization, or customer release.

Cryptography: cryptography==46.0.4, AES-256-GCM / scrypt.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import io
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from capturebrief_core.accepted_case_release import (
    AcceptedCaseBlocked, REQUIRED_KINDS, SAFE_ID, HEX64,
    _file, _json_file, _reject_private_path_links, _root,
    canonical, sha256,
)
from capturebrief_core.atomic_io import atomic_write_bytes, exclusive_path_lock
from scripts.scoped_private_backup import (
    _bytes, _canon, _crypto, _key, _unique,
    KDF_N, KDF_R, KDF_P, MAX_HEADER,
)

# Avoid a cyclic self-reference: the final encrypted backup and external
# independently produced recovery receipt exist only AFTER this snapshot.
SCHEMA = "capturebrief-complete-private-case-snapshot-v1"
MAGIC = b"CAPTUREBRIEF-COMPLETE-CASE-AESGCM-V1\x00"
NEEDED = REQUIRED_KINDS - {"OFFDEVICE_BACKUP", "RECOVERY_RECEIPT"}
OTHER = {"ACTION_ORIGINAL", "RESOURCE_ORIGINAL", "INCORPORATED_RULE"}
MAX_FILES = 100
MAX_BYTES = 96 * 1024 * 1024
MAX_SINGLE = 50 * 1024 * 1024
MAX_ARCHIVE = 100 * 1024 * 1024
MAX_INPUT = 512 * 1024
SAFE_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
WINDOWS_RESERVED = re.compile(
    r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:[.]|$)", re.I,
)


def _safe_relative(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 240:
        raise ValueError("An owner-reviewed bounded relative file path is required")
    parts = value.split("/")
    if (PurePosixPath(value).is_absolute() or "\\" in value or ":" in value
            or value != PurePosixPath(value).as_posix()
            or not all(SAFE_PART.fullmatch(p) and not p.endswith(".")
                       and not WINDOWS_RESERVED.match(p) for p in parts)
            or any(p in {".", "..", ".git", "gh-pages"} for p in parts)):
        raise ValueError("Snapshot file path is unsafe on a private Windows/Unix host")
    return value


def _rows(inv: dict[str, Any]) -> list[dict[str, str]]:
    if not isinstance(inv, dict) or set(inv) != {"schema", "case_sha256", "files"}:
        raise ValueError("Unexpected full-case snapshot inventory schema")
    if inv["schema"] != SCHEMA or not isinstance(inv["case_sha256"], str) or (
        not HEX64.fullmatch(inv["case_sha256"])
    ):
        raise ValueError("Snapshot cannot be identified with an exact reviewed case")
    rows = inv["files"]
    if not isinstance(rows, list) or not 11 <= len(rows) <= MAX_FILES:
        raise ValueError("Complete, bounded pre-release case inventory required")
    kinds: dict[str, int] = {}
    ids: set[str] = set()
    paths: set[str] = set()
    canonical: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "kind", "path", "sha256"}:
            raise ValueError("No extra authority claims or missing source metadata allowed")
        fid, kind, rel, digest = (
            row["id"], row["kind"], _safe_relative(row["path"]), row["sha256"]
        )
        if (not isinstance(fid, str) or not SAFE_ID.fullmatch(fid)
                or not isinstance(kind, str) or kind not in NEEDED | OTHER
                or not isinstance(digest, str) or not HEX64.fullmatch(digest)
                or fid.casefold() in ids or rel.casefold() in paths):
            raise ValueError("Case inventory contains duplicate or forbidden evidence")
        ids.add(fid.casefold())
        paths.add(rel.casefold())
        kinds[kind] = kinds.get(kind, 0) + 1
        canonical.append(dict(id=fid, kind=kind, path=rel, sha256=digest))
    if (any(kinds.get(k) != 1 for k in NEEDED)
            or kinds.get("ACTION_ORIGINAL", 0) == 0):
        raise ValueError("Pre-release complete-case backup is missing mandatory kinds")
    return canonical


def _collect(source_root: str | Path, inventory_path: str | Path
             ) -> tuple[list[dict[str, Any]], dict[str, bytes], str]:
    root = _root(source_root)
    path = Path(inventory_path).expanduser().absolute()
    _reject_private_path_links(path)
    if not path.is_relative_to(root) or path.stat().st_size > MAX_INPUT:
        raise ValueError("Snapshot inventory must be an owner-only file inside the case root")
    inv = _json_file(path)
    records = _rows(inv)
    files: dict[str, bytes] = {}
    manifest_rows: list[dict[str, Any]] = []
    total = 0
    for row in records:
        raw = _file(root, row["path"], row["sha256"], limit=MAX_SINGLE)
        total += len(raw)
        if total > MAX_BYTES:
            raise ValueError("Complete source inventory exceeds bounded memory-only encryption")
        files[row["id"]] = raw
        manifest_rows.append({**row, "bytes": len(raw)})
    case_id = next(x["id"] for x in records if x["kind"] == "CASE")
    try:
        case = json.loads(files[case_id].decode("utf-8"), object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise ValueError("Complete case original is not valid unique-key JSON") from None
    if not isinstance(case, dict) or sha256(canonical(case)) != inv["case_sha256"]:
        raise ValueError("Reviewed case identity differs from case original")
    return manifest_rows, files, inv["case_sha256"]


def _package(rows: list[dict[str, Any]], files: dict[str, bytes],
             case_sha: str) -> bytes:
    manifest = {
        "schema": SCHEMA,
        "case_sha256": case_sha,
        "files": rows,
        "customer_release_authorized": False,
        "external_send_authorized": False,
        "offdevice_recovery_verified": False,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=False) as archive:
        archive.writestr("manifest.json", _canon(manifest))
        for row in rows:
            archive.writestr("evidence/" + row["id"] + ".bin", files[row["id"]])
    data = buffer.getvalue()
    if not 0 < len(data) <= MAX_ARCHIVE:
        raise ValueError("Compressed case snapshot exceeds bounded archive size")
    return data


def _target_file(value: str | Path) -> Path:
    target = Path(value).expanduser().absolute()
    _reject_private_path_links(target)
    if target.suffix != ".cbak" or target.exists():
        raise ValueError("Create a NEW encrypted .cbak backup, never overwrite an existing one")
    _root(target.parent)
    return target


def create_backup(source_root: str | Path, inventory_path: str | Path,
                  output: str | Path, passphrase: bytes) -> dict[str, Any]:
    destination = _target_file(output)
    records, files, case_sha = _collect(source_root, inventory_path)
    plaintext = _package(records, files, case_sha)
    AESGCM, _ = _crypto()
    salt, nonce = os.urandom(16), os.urandom(12)
    header = _canon({
        "schema": SCHEMA, "cipher": "AES-256-GCM", "kdf": "scrypt",
        "n": KDF_N, "r": KDF_R, "p": KDF_P,
        "salt_b64": base64.b64encode(salt).decode(),
        "nonce_b64": base64.b64encode(nonce).decode(),
        "plaintext_sha256": sha256(plaintext),
        "plaintext_bytes": len(plaintext),
    })
    if len(header) > MAX_HEADER:
        raise ValueError("Authenticated encrypted-case header exceeds bound")
    prefix = MAGIC + struct.pack(">I", len(header)) + header
    encrypted = AESGCM(_key(passphrase, salt)).encrypt(nonce, plaintext, prefix)
    atomic_write_bytes(destination, prefix + encrypted, overwrite=False, mode=0o600)
    return {
        "status": "FULL_CASE_LOCAL_ENCRYPTED_SNAPSHOT_CREATED",
        "case_tag": case_sha[:12],
        "file_count": len(records),
        "backup_sha256": sha256(destination.read_bytes()),
        "offdevice_restore_verified": False,
        "independent_key_custody_verified": False,
        "complete_source_history_verified": False,
        "internal_report_review_verified": False,
        "customer_release_authorized": False,
        "external_send_performed": False,
    }


def _decrypt(path: str | Path, passphrase: bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    source = Path(path).expanduser().absolute()
    _reject_private_path_links(source)
    _root(source.parent)
    raw = _bytes(source, MAX_ARCHIVE + MAX_HEADER + len(MAGIC) + 64)
    base = len(MAGIC)
    if not raw.startswith(MAGIC) or len(raw) < base + 4:
        raise ValueError("Unsupported complete-case encrypted backup")
    count = struct.unpack(">I", raw[base:base + 4])[0]
    if not 0 < count <= MAX_HEADER or len(raw) < base + 4 + count + 16:
        raise ValueError("Complete-case backup header length invalid")
    head = raw[base + 4:base + 4 + count]
    meta = json.loads(head.decode("utf-8"), object_pairs_hook=_unique)
    if (not isinstance(meta, dict) or set(meta) != {
        "schema", "cipher", "kdf", "n", "r", "p", "salt_b64", "nonce_b64",
        "plaintext_sha256", "plaintext_bytes",
    } or _canon(meta) != head or meta["schema"] != SCHEMA
            or meta["cipher"] != "AES-256-GCM" or meta["kdf"] != "scrypt"
            or (meta["n"], meta["r"], meta["p"]) != (KDF_N, KDF_R, KDF_P)
            or type(meta["plaintext_bytes"]) is not int
            or not 0 < meta["plaintext_bytes"] <= MAX_ARCHIVE
            or not isinstance(meta["plaintext_sha256"], str)
            or not HEX64.fullmatch(meta["plaintext_sha256"])):
        raise ValueError("Encrypted-case header policy malformed")
    try:
        salt = base64.b64decode(meta["salt_b64"], validate=True)
        nonce = base64.b64decode(meta["nonce_b64"], validate=True)
    except (ValueError, TypeError):
        raise ValueError("Encrypted-case salt/nonce encoding invalid") from None
    if len(salt) != 16 or len(nonce) != 12:
        raise ValueError("Encrypted-case key derivation parameters invalid")
    AESGCM, _ = _crypto()
    start = base + 4 + count
    decrypted = AESGCM(_key(passphrase, salt)).decrypt(
        nonce, raw[start:], raw[:start]
    )
    if len(decrypted) != meta["plaintext_bytes"] or sha256(decrypted) != meta["plaintext_sha256"]:
        raise ValueError("Full-case encrypted plaintext integrity mismatch")

    with zipfile.ZipFile(io.BytesIO(decrypted)) as archive:
        names = archive.namelist()
        if ("manifest.json" not in names or len(names) != len(set(names))
                or len(names) > MAX_FILES + 1
                or archive.getinfo("manifest.json").file_size > MAX_INPUT):
            raise ValueError("Unsafe or incomplete encrypted-case archive")
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"),
                              object_pairs_hook=_unique)
        if (not isinstance(manifest, dict) or set(manifest) != {
            "schema", "case_sha256", "files", "customer_release_authorized",
            "external_send_authorized", "offdevice_recovery_verified",
        } or any(manifest[k] is not False for k in (
            "customer_release_authorized", "external_send_authorized",
            "offdevice_recovery_verified"
        ))):
            raise ValueError("Authenticated case manifest has unsupported authority")
        selected = {"schema": manifest["schema"],
                    "case_sha256": manifest["case_sha256"],
                    "files": [{k: row[k] for k in ("id", "kind", "path", "sha256")}
                              for row in manifest["files"]]}
        records = _rows(selected)
        if len(records) != len(manifest["files"]):
            raise ValueError("Encrypted case file count inconsistent")
        total = 0
        files: dict[str, bytes] = {}
        for row, meta_row in zip(records, manifest["files"]):
            if set(meta_row) != {"id", "kind", "path", "sha256", "bytes"}:
                raise ValueError("Encrypted case file entry contains an extra field")
            name = "evidence/" + row["id"] + ".bin"
            if (name not in names or type(meta_row["bytes"]) is not int
                    or not 0 < meta_row["bytes"] <= MAX_SINGLE
                    or archive.getinfo(name).file_size != meta_row["bytes"]):
                raise ValueError("Encrypted case file missing or inconsistent")
            total += meta_row["bytes"]
            if total > MAX_BYTES:
                raise ValueError("Decompressed case exceeds memory bound")
            data = archive.read(name)
            if len(data) != meta_row["bytes"] or sha256(data) != row["sha256"]:
                raise ValueError("Encrypted case file differs from retained original")
            files[row["id"]] = data
        expected = {"manifest.json"} | {
            "evidence/" + row["id"] + ".bin" for row in records
        }
        if set(names) != expected:
            raise ValueError("Encrypted case archive has additional unknown files")
        case_row = next(row for row in records if row["kind"] == "CASE")
        try:
            case = json.loads(files[case_row["id"]].decode("utf-8"),
                              object_pairs_hook=_unique)
        except (ValueError, UnicodeError):
            raise ValueError("Decrypted case original is not valid JSON") from None
        if not isinstance(case, dict) or sha256(canonical(case)) != manifest["case_sha256"]:
            raise ValueError("Decrypted case identity was modified")
    return manifest, files


def verify_backup(path: str | Path, passphrase: bytes) -> dict[str, Any]:
    manifest, _ = _decrypt(path, passphrase)
    return {
        "status": "FULL_CASE_ENCRYPTED_LOCAL_INTEGRITY_VERIFIED",
        "case_tag": manifest["case_sha256"][:12],
        "file_count": len(manifest["files"]),
        "offdevice_restore_verified": False,
        "customer_release_authorized": False,
        "external_send_performed": False,
    }


def restore_backup(path: str | Path, output_dir: str | Path,
                   passphrase: bytes) -> dict[str, Any]:
    manifest, files = _decrypt(path, passphrase)
    output = Path(output_dir).expanduser().absolute()
    _reject_private_path_links(output)
    if output.exists():
        raise ValueError("Restoration requires a NEW private destination")
    parent = _root(output.parent)
    with exclusive_path_lock(output, suffix=".case-restore.lock", timeout_seconds=5):
        if output.exists():
            raise ValueError("A concurrent restoration already owns this destination")
        temp = Path(tempfile.mkdtemp(prefix=".capturebrief-case-restore-", dir=parent))
        try:
            for row in manifest["files"]:
                path_parts = _safe_relative(row["path"]).split("/")
                target = temp.joinpath(*path_parts)
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                atomic_write_bytes(target, files[row["id"]], overwrite=False, mode=0o600)
            if output.exists():
                raise ValueError("Restore destination was claimed concurrently")
            os.rename(temp, output)
        finally:
            if temp.exists():
                shutil.rmtree(temp)
    return {
        "status": "FULL_CASE_LOCALLY_RESTORED_RECONCILIATION_REQUIRED",
        "case_tag": manifest["case_sha256"][:12],
        "file_count": len(manifest["files"]),
        "independent_offdevice_restore_proven": False,
        "reconciliation_required_before_use": True,
        "customer_release_authorized": False,
        "external_send_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="action", required=True)
    for action in ("create", "verify", "restore"):
        command = modes.add_parser(action)
        command.add_argument("--backup-file", required=True)
        if action == "create":
            command.add_argument("--private-root", required=True)
            command.add_argument("--inventory", required=True)
        if action == "restore":
            command.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        secret = getpass.getpass("Recovery phrase (never stored or printed): ").encode()
        if args.action == "create":
            result = create_backup(
                args.private_root, args.inventory, args.backup_file, secret
            )
        elif args.action == "verify":
            result = verify_backup(args.backup_file, secret)
        else:
            result = restore_backup(args.backup_file, args.output_dir, secret)
    except Exception as exc:
        print(json.dumps({
            "status": "FULL_CASE_ENCRYPTED_RECOVERY_BLOCKED",
            "error_type": type(exc).__name__,
            "customer_release_authorized": False,
            "external_send_performed": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
