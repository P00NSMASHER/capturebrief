"""Encrypted, portable backup for ONE CaptureBrief scoped source workspace.

Operator-only: no Cloudflare account, external upload, checkout, mail, or source
review is performed. A backup must still be copied OFF DEVICE and independently
restored with a separately retained recovery phrase before operational approval.
Requires pinned optional dependency: cryptography==46.0.4.
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
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from capturebrief_core.atomic_io import atomic_write_bytes, exclusive_path_lock
from capturebrief_core.scoped_source import (
    _intake_identity, _private_path, private_root, read_private_case,
    ScopedSourceBlocked,
)

MAGIC = b"CAPTUREBRIEF-SCOPED-AESGCM-V1\x00"
SCHEMA = "capturebrief-scoped-private-backup-v1"
KDF_N, KDF_R, KDF_P = 32768, 8, 1
MAX_FILES = 80
MAX_TOTAL = 128 * 1024 * 1024
MAX_BUNDLE = 132 * 1024 * 1024
MAX_HEADER = 2048
FILE_NAME = re.compile(
    r"^(?:sam-current-[0-9a-f]{64}\.json|"
    r"case-current-[0-9a-f]{64}\.json|"
    r"public-source-[0-9a-f]{64}\.bin(?:\.receipt\.json)?)$"
)


def _crypto():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    return AESGCM, Scrypt


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate authenticated backup metadata key")
        result[key] = value
    return result


def _key(passphrase: bytes, salt: bytes) -> bytes:
    if not isinstance(passphrase, bytes) or len(passphrase) < 20:
        raise ValueError("A strong independently retained recovery phrase is required")
    _, Scrypt = _crypto()
    return Scrypt(salt=salt, length=32, n=KDF_N, r=KDF_R, p=KDF_P).derive(passphrase)


def _new_file(value: str | Path) -> Path:
    raw = Path(value).expanduser().absolute()
    for component in (raw, *raw.parents):
        junction = getattr(component, "is_junction", None)
        if component.is_symlink() or (junction is not None and junction()):
            raise ValueError("Encrypted backup destination must not follow links")
    path = raw.resolve(strict=False)
    if path.suffix != ".cbak" or path.exists():
        raise ValueError("Backup needs a new .cbak path outside Git")
    private_root(path.parent)
    return path


def _bytes(path: Path, bound: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Backup source is not a regular file")
    size = path.stat().st_size
    if not 0 < size <= bound:
        raise ValueError("Backup source exceeds file bound")
    with path.open("rb") as handle:
        data = handle.read(bound + 1)
    if len(data) != size:
        raise ValueError("Backup source changed during read")
    return data




def _validate_source_set(case: dict[str, Any], files: dict[str, bytes]) -> None:
    """Refuse to encrypt forged release assertions or mismatched source bytes."""
    from capturebrief_core.scoped_source import verify_scoped_capture, _time
    from capturebrief_core.model import canonical_json, sha256_hex
    identity = _intake_identity(case)
    for name, content in files.items():
        if name == "intake-case.json":
            continue
        if not name.startswith("evidence/") or not FILE_NAME.fullmatch(name[9:]):
            raise ValueError("Scoped source contains a forbidden file name")
        leaf = name[9:]
        if leaf.startswith("sam-current-"):
            capture = json.loads(content.decode("utf-8"), object_pairs_hook=_unique)
            if (capture.get("capture_sha256") != leaf[len("sam-current-"):-len(".json")]
                    or content != (json.dumps(capture, sort_keys=True, indent=2,
                                              ensure_ascii=False) + "\n").encode()):
                raise ValueError("Scoped API receipt content address is invalid")
            observed = (capture.get("api_observation") or {}).get("observed_at")
            verify_scoped_capture(case, capture, now=_time(observed))
        elif leaf.startswith("case-current-"):
            saved = json.loads(content.decode("utf-8"), object_pairs_hook=_unique)
            if (sha256_hex(canonical_json(saved)) !=
                    leaf[len("case-current-"):-len(".json")]):
                raise ValueError("Bound reviewed case content address is invalid")
            if _intake_identity(saved)["identity"] != identity["identity"]:
                raise ValueError("Reviewed case belongs to a different intake")
        elif leaf.endswith(".bin"):
            expected_sha = leaf[len("public-source-"):-len(".bin")]
            if hashlib.sha256(content).hexdigest() != expected_sha:
                raise ValueError("Retained original no longer matches its source digest")
            if "evidence/" + leaf + ".receipt.json" not in files:
                raise ValueError("Retained original has no matching source receipt")
        elif leaf.endswith(".bin.receipt.json"):
            receipt = json.loads(content.decode("utf-8"), object_pairs_hook=_unique)
            source_name = receipt.get("retained_filename")
            if (receipt.get("schema") != "capturebrief-scoped-review-source-v1"
                    or not isinstance(source_name, str)
                    or source_name + ".receipt.json" != leaf
                    or receipt.get("case_identity_sha256") != identity["identity"]
                    or receipt.get("source_sha256") !=
                       source_name[len("public-source-"):-len(".bin")]
                    or receipt.get("capture_mode") != "OPERATOR_SUPPLIED_FOR_INDEPENDENT_REVIEW"
                    or any(receipt.get(flag) is not False for flag in (
                        "publisher_authenticity_verified", "history_completeness_verified",
                        "customer_release_authorized", "external_send_authorized"
                    ))):
                raise ValueError("Retained public-source receipt is inconsistent or claims release")
            original = files.get("evidence/" + source_name)
            if original is None or len(original) != receipt.get("source_bytes"):
                raise ValueError("Retained source bytes no longer match its receipt")

def _contents(case_path: str | Path, root: str | Path) -> tuple[str, dict[str, bytes]]:
    case = read_private_case(case_path)
    identity = _intake_identity(case)
    private = private_root(root)
    folder = private_root(private / ("case-" + identity["case_tag"]))
    case_bytes = _bytes(_private_path(case_path, directory=False), 256 * 1024)
    files = {"intake-case.json": case_bytes}
    total = len(case_bytes)
    for item in sorted(folder.iterdir()):
        if (item.is_symlink() or not item.is_file() or
                not FILE_NAME.fullmatch(item.name)):
            raise ValueError("Unexpected private scoped source file; refuse partial backup")
        data = _bytes(item, 50 * 1024 * 1024 if item.name.endswith(".bin") else 1024 * 1024)
        total += len(data)
        if total > MAX_TOTAL or len(files) >= MAX_FILES:
            raise ValueError("Case source data exceeds bounded encrypted backup")
        files["evidence/" + item.name] = data
    if len(files) == 1:
        raise ValueError("No retained source data to protect")
    _validate_source_set(case, files)
    return identity["case_tag"], files


def _archive(case_tag: str, files: dict[str, bytes]) -> bytes:
    manifest = {
        "schema": SCHEMA,
        "case_tag": case_tag,
        "files": [
            {"name": key, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for key, data in sorted(files.items())
        ],
        "source_review_verified": False,
        "external_send_authorized": False,
        "customer_release_authorized": False,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED,
                         allowZip64=False, compresslevel=6) as out:
        out.writestr("manifest.json", _canon(manifest))
        for name, data in sorted(files.items()):
            out.writestr(name, data)
    return buf.getvalue()


def create_backup(case_path: str | Path, private_dir: str | Path,
                  output: str | Path, passphrase: bytes) -> dict[str, Any]:
    path = _new_file(output)
    case_tag, files = _contents(case_path, private_dir)
    plain = _archive(case_tag, files)
    if len(plain) > MAX_BUNDLE:
        raise ValueError("Compressed scoped evidence exceeds backup bound")
    AESGCM, _ = _crypto()
    salt, nonce = os.urandom(16), os.urandom(12)
    header = {
        "schema": SCHEMA,
        "cipher": "AES-256-GCM",
        "kdf": "scrypt",
        "n": KDF_N, "r": KDF_R, "p": KDF_P,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "plaintext_sha256": hashlib.sha256(plain).hexdigest(),
        "plaintext_bytes": len(plain),
    }
    head = _canon(header)
    if len(head) > MAX_HEADER:
        raise ValueError("Encrypted backup header exceeds bound")
    prefix = MAGIC + struct.pack(">I", len(head)) + head
    ciphertext = AESGCM(_key(passphrase, salt)).encrypt(nonce, plain, prefix)
    atomic_write_bytes(path, prefix + ciphertext, overwrite=False, mode=0o600)
    return {
        "status": "SCOPED_LOCAL_ENCRYPTED_BACKUP_CREATED",
        "backup_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "case_tag": case_tag, "file_count": len(files),
        "offdevice_copy_verified": False, "independent_restore_verified": False,
        "recovery_key_independently_retained": False,
        "customer_release_authorized": False, "external_send_authorized": False,
    }


def _open_backup(backup: str | Path, passphrase: bytes) -> tuple[str, dict[str, bytes]]:
    source = _private_path(backup, directory=False)
    raw = _bytes(source, MAX_BUNDLE + MAX_HEADER + len(MAGIC) + 64)
    marker = len(MAGIC)
    if not raw.startswith(MAGIC) or len(raw) < marker + 4:
        raise ValueError("Unsupported or truncated scoped encrypted backup")
    count = struct.unpack(">I", raw[marker:marker + 4])[0]
    if not 0 < count <= MAX_HEADER or len(raw) < marker + 4 + count + 16:
        raise ValueError("Scoped encrypted backup header bound is invalid")
    head = raw[marker + 4:marker + 4 + count]
    header = json.loads(head.decode("utf-8"), object_pairs_hook=_unique)
    if not isinstance(header, dict) or set(header) != {
        "schema", "cipher", "kdf", "n", "r", "p", "salt_b64", "nonce_b64",
        "plaintext_sha256", "plaintext_bytes",
    } or head != _canon(header):
        raise ValueError("Scoped encrypted backup header is not canonical")
    if (header["schema"] != SCHEMA or header["cipher"] != "AES-256-GCM"
            or header["kdf"] != "scrypt"
            or (header["n"], header["r"], header["p"]) != (KDF_N, KDF_R, KDF_P)
            or not isinstance(header["plaintext_bytes"], int)
            or not 0 < header["plaintext_bytes"] <= MAX_BUNDLE):
        raise ValueError("Scoped encryption policy is invalid")
    try:
        salt = base64.b64decode(header["salt_b64"], validate=True)
        nonce = base64.b64decode(header["nonce_b64"], validate=True)
    except (ValueError, TypeError):
        raise ValueError("Scoped encryption parameters are invalid") from None
    if len(salt) != 16 or len(nonce) != 12:
        raise ValueError("Scoped encrypted salt or nonce length is invalid")
    AESGCM, _ = _crypto()
    start = marker + 4 + count
    plain = AESGCM(_key(passphrase, salt)).decrypt(nonce, raw[start:], raw[:start])
    if (len(plain) != header["plaintext_bytes"]
            or hashlib.sha256(plain).hexdigest() != header["plaintext_sha256"]):
        raise ValueError("Scoped encrypted payload digest is inconsistent")

    files: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(plain), "r") as archive:
        names = archive.namelist()
        if (len(names) != len(set(names)) or len(names) > MAX_FILES + 1
                or "manifest.json" not in names):
            raise ValueError("Encrypted ZIP contains duplicate/unexpected entries")
        if archive.getinfo("manifest.json").file_size > 64 * 1024:
            raise ValueError("Encrypted manifest exceeds bounded metadata allowance")
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"), object_pairs_hook=_unique)
        if (not isinstance(manifest, dict)
                or set(manifest) != {
                    "schema", "case_tag", "files", "source_review_verified",
                    "customer_release_authorized", "external_send_authorized"
                }
                or manifest["schema"] != SCHEMA
                or manifest["source_review_verified"] is not False
                or manifest["customer_release_authorized"] is not False
                or manifest["external_send_authorized"] is not False
                or not re.fullmatch(r"[0-9a-f]{24}", str(manifest["case_tag"]))):
            raise ValueError("Authenticated manifest makes unsupported authority claims")
        entries = manifest["files"]
        if not isinstance(entries, list) or len(entries) != len(names) - 1:
            raise ValueError("Authenticated file list is incomplete")
        total = 0
        for item in entries:
            if not isinstance(item, dict) or set(item) != {"name", "sha256", "size"}:
                raise ValueError("Backup file manifest is malformed")
            name = item["name"]
            if (not isinstance(name, str) or
                    (name != "intake-case.json" and
                     not (name.startswith("evidence/") and FILE_NAME.fullmatch(name[9:]))) or
                    name not in names or name in files or
                    not isinstance(item["size"], int) or
                    not 0 < item["size"] <= 50 * 1024 * 1024):
                raise ValueError("Backup has a forbidden, duplicate or oversized file")
            total += item["size"]
            if total > MAX_TOTAL or archive.getinfo(name).file_size != item["size"]:
                raise ValueError("Backup extraction exceeds bounded source data")
            data = archive.read(name)
            if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError("Backup file failed exact-byte verification")
            files[name] = data
        if set(names) != set(files) | {"manifest.json"} or "intake-case.json" not in files:
            raise ValueError("Authenticated backup has missing or unexpected files")
        restored_case = json.loads(files["intake-case.json"].decode("utf-8"), object_pairs_hook=_unique)
        if _intake_identity(restored_case)["case_tag"] != manifest["case_tag"]:
            raise ValueError("Backup case identity does not match source manifest")
        _validate_source_set(restored_case, files)
    return manifest["case_tag"], files


def verify_backup(backup: str | Path, passphrase: bytes) -> dict[str, Any]:
    case_tag, files = _open_backup(backup, passphrase)
    return {
        "status": "SCOPED_ENCRYPTED_BACKUP_INTEGRITY_VERIFIED",
        "case_tag": case_tag, "file_count": len(files),
        "independent_offdevice_restore_proven": False,
        "customer_release_authorized": False, "external_send_authorized": False,
    }


def restore_backup(backup: str | Path, output_dir: str | Path,
                   passphrase: bytes) -> dict[str, Any]:
    tag, files = _open_backup(backup, passphrase)
    requested = Path(output_dir).expanduser().absolute()
    if requested.exists() or requested.is_symlink():
        raise ValueError("Restoration needs a new, empty private destination")
    parent = private_root(requested.parent)
    with exclusive_path_lock(requested, timeout_seconds=5, suffix=".restore.lock"):
        if requested.exists():
            raise ValueError("Restore destination became occupied")
        tmp = Path(tempfile.mkdtemp(prefix=".scoped-restore-", dir=parent))
        try:
            for name, data in files.items():
                relative = Path(name)
                dest = tmp / relative
                dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                atomic_write_bytes(dest, data, overwrite=False, mode=0o600)
            if requested.exists():
                raise ValueError("Restore destination became occupied")
            os.rename(tmp, requested)
        finally:
            if tmp.exists():
                shutil.rmtree(tmp)
    return {
        "status": "SCOPED_BACKUP_LOCALLY_RESTORED_AND_REHASHED",
        "case_tag": tag, "file_count": len(files),
        "independent_offdevice_restore_proven": False,
        "recovery_key_independently_retained": False,
        "customer_release_authorized": False, "external_send_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="command", required=True)
    create = modes.add_parser("create")
    create.add_argument("--case", required=True)
    create.add_argument("--private-dir", required=True)
    create.add_argument("--backup-file", required=True)
    verify = modes.add_parser("verify")
    verify.add_argument("--backup-file", required=True)
    restore = modes.add_parser("restore")
    restore.add_argument("--backup-file", required=True)
    restore.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        secret = getpass.getpass("Recovery phrase (never printed/stored): ").encode()
        if args.command == "create":
            result = create_backup(args.case, args.private_dir, args.backup_file, secret)
        elif args.command == "verify":
            result = verify_backup(args.backup_file, secret)
        else:
            result = restore_backup(args.backup_file, args.output_dir, secret)
    except Exception as exc:
        print(json.dumps({
            "status": "SCOPED_BACKUP_BLOCKED",
            "error_type": type(exc).__name__,
            "customer_release_authorized": False,
            "external_send_authorized": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
