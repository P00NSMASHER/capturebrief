"""Operator-only, client-side encrypted FY2027 ORIGINAL + PR #53 receipt backup.

This independent backup candidate does not download sources, authenticate
publisher provenance, update source indexes, certify FULL_CATALOG, upload to
cloud, escrow a key, contact buyers, or authorize customer release.

Requires the optional, pinned and separately installed `cryptography` package.
Only the CLI's immutable FY2027 SHA/size are production candidate inputs;
injected expected digest/size arguments are solely for synthetic offline QA.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import os
import stat
import struct
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from capturebrief_core.atomic_io import atomic_write_bytes, ensure_exact_bytes
from capturebrief_core.data_services import ARCHIVE_DOWNLOAD

FY = 2027
ORIGINAL_SHA256 = "7b4e00e3156248db9dcca767431bb6c5d4168aeeb2abc707ab12c0f9e61d71ce"
ORIGINAL_BYTES = 1_607_260
ORIGINAL_NAME = f"FY2027-{ORIGINAL_SHA256}.csv"
RECEIPT_NAME = f"FY2027-{ORIGINAL_SHA256}.receipt.json"
SOURCE_URL = ARCHIVE_DOWNLOAD.format(fy=FY)
PROVENANCE = "https://github.com/P00NSMASHER/capturebrief/actions/runs/39205786451"
LISTING = "https://sam.gov/data-services/Contract%20Opportunities/Archived%20Data?privacy=Public"

MAGIC = b"CAPTUREBRIEF-FY2027-AEAD-V1\x00"
FRAME = b"FY2027-ORIGINAL-RECEIPT-V1\x00"
MAX_RECEIPT_BYTES = 16 * 1024
MAX_HEADER_BYTES = 2048
MAX_ORIGINAL_BYTES = 2_000_000
KDF_N = 32768
KDF_R = 8
KDF_P = 1
CIPHER = "AES-256-GCM"
RECEIPT_FIELDS = frozenset({
    "schema", "source_listing", "source_url", "prior_ci_sha256", "prior_ci_run",
    "observed_at", "downloaded_sha256", "downloaded_bytes",
    "retained_original_file", "local_file_sha256_verified",
    "official_delivery_host", "redirect_used", "source_etag",
    "source_last_modified", "operator_path", "test_override",
    "catalog_approved", "full_archive_history_verified", "human_source_review_complete",
    "case_release_authorized", "external_send_authorized",
})


def _crypto():
    """Import lazily so production core does not acquire an implicit dependency."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    return AESGCM, Scrypt


def _private_path(value: str | Path, *, directory: bool) -> Path:
    raw = Path(value).expanduser().absolute()
    # Reject symlinks at every existing path component, not just the leaf.
    for part in (raw, *raw.parents):
        # Windows directory junctions are reparse points but not symlinks.
        junction = getattr(part, "is_junction", None)
        if part.is_symlink() or (junction is not None and junction()):
            raise ValueError("Backup paths cannot traverse symlinks or junctions")
    real = raw.resolve(strict=directory)
    if real == REPO or real.is_relative_to(REPO):
        raise ValueError("Private source or encrypted backup path belongs outside public Git")
    if directory and not real.is_dir():
        raise ValueError("Private source or destination directory is unavailable")
    if not directory and (not real.parent.is_dir() or real.is_dir()):
        raise ValueError("Backup output must have an existing private parent directory")
    return real


def _read_bounded(path: Path, max_size: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Expected regular source artifact missing")
    size = path.stat().st_size
    if not 0 < size <= max_size:
        raise ValueError("Unexpected source or encrypted backup size")
    with path.open("rb") as f:
        value = f.read(max_size + 1)
    if len(value) != size:
        raise ValueError("Source changed while reading")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, val in pairs:
        if name in out:
            raise ValueError("Duplicate fields in integrity protected record")
        out[name] = val
    return out


def _load_json(raw: bytes, *, max_size: int) -> dict[str, Any]:
    if len(raw) > max_size:
        raise ValueError("Record exceeds bound")
    obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    if not isinstance(obj, dict):
        raise ValueError("Record must be an object")
    return obj


def _canonical_record(obj: dict[str, Any]) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _validate_receipt(
    raw: bytes, *, original_sha256: str, original_bytes: int, synthetic_test: bool,
) -> dict[str, Any]:
    receipt = _load_json(raw, max_size=MAX_RECEIPT_BYTES)
    if set(receipt) != RECEIPT_FIELDS or raw != _canonical_record(receipt):
        raise ValueError("Receipt schema or immutable canonical bytes are invalid")
    expected = {
        "schema": "capturebrief-fy2027-private-candidate-retention-v1",
        "source_listing": LISTING, "source_url": SOURCE_URL,
        "prior_ci_sha256": ORIGINAL_SHA256, "prior_ci_run": PROVENANCE,
        "downloaded_sha256": original_sha256, "downloaded_bytes": original_bytes,
        "retained_original_file": True, "local_file_sha256_verified": True,
        "test_override": synthetic_test, "catalog_approved": False,
        "full_archive_history_verified": False, "human_source_review_complete": False,
        "case_release_authorized": False, "external_send_authorized": False,
    }
    for field, expected_value in expected.items():
        if type(receipt.get(field)) is not type(expected_value) or receipt[field] != expected_value:
            raise ValueError("Receipt source identity or release hold mismatch")
    if not isinstance(receipt["operator_path"], str) or not receipt["operator_path"].endswith(
        f"FY2027-{original_sha256}.csv"
    ):
        raise ValueError("Receipt does not identify the exact FY2027 original")
    if receipt.get("official_delivery_host") not in {
        "sam.gov", "s3.amazonaws.com", "falextracts.s3.amazonaws.com",
    }:
        raise ValueError("Unexpected original-source delivery host")
    if not isinstance(receipt.get("observed_at"), str) or not receipt["observed_at"].endswith("Z"):
        raise ValueError("Missing source-observation timestamp")
    return receipt


def _expected(original_sha256: str, original_bytes: int) -> bool:
    if (not isinstance(original_sha256, str) or len(original_sha256) != 64
            or any(c not in "0123456789abcdef" for c in original_sha256)):
        raise ValueError("Invalid expected original SHA-256")
    if type(original_bytes) is not int or not (0 < original_bytes <= MAX_ORIGINAL_BYTES):
        raise ValueError("Invalid bounded original-file size")
    return original_sha256 != ORIGINAL_SHA256 or original_bytes != ORIGINAL_BYTES


def _payload(source_dir: str | Path, *, original_sha256: str, original_bytes: int) -> bytes:
    fake = _expected(original_sha256, original_bytes)
    private = _private_path(source_dir, directory=True)
    source = _read_bounded(private / f"FY2027-{original_sha256}.csv", MAX_ORIGINAL_BYTES)
    if len(source) != original_bytes or hashlib.sha256(source).hexdigest() != original_sha256:
        raise ValueError("Original source bytes do not match independently pinned evidence")
    receipt_bytes = _read_bounded(private / f"FY2027-{original_sha256}.receipt.json", MAX_RECEIPT_BYTES)
    _validate_receipt(receipt_bytes, original_sha256=original_sha256,
                      original_bytes=original_bytes, synthetic_test=fake)
    return FRAME + struct.pack(">I", len(receipt_bytes)) + receipt_bytes + source


def _key(passphrase: bytes, salt: bytes) -> bytes:
    if (not isinstance(passphrase, bytes) or len(passphrase) < 16
            or len(passphrase) > 1024 or b"\x00" in passphrase
            or b"\r" in passphrase or b"\n" in passphrase):
        raise ValueError("Passphrase must be 16-1024 bytes without line breaks")
    _, Scrypt = _crypto()
    return Scrypt(salt=salt, length=32, n=KDF_N, r=KDF_R, p=KDF_P).derive(passphrase)


def _header(salt: bytes, nonce: bytes) -> bytes:
    obj = {
        "schema": "capturebrief-fy2027-encrypted-backup-v1",
        "cipher": CIPHER, "kdf": "scrypt", "n": KDF_N, "r": KDF_R, "p": KDF_P,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "user_key_recovery_independently_required": True,
        "source_catalog_approved": False,
        "customer_release_authorized": False,
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _parse_header(raw: bytes) -> tuple[bytes, bytes]:
    obj = _load_json(raw, max_size=MAX_HEADER_BYTES)
    if set(obj) != {
        "schema", "cipher", "kdf", "n", "r", "p", "salt_b64", "nonce_b64",
        "user_key_recovery_independently_required", "source_catalog_approved",
        "customer_release_authorized",
    }:
        raise ValueError("Unknown backup header fields")
    if (obj["schema"] != "capturebrief-fy2027-encrypted-backup-v1"
            or obj["cipher"] != CIPHER or obj["kdf"] != "scrypt"
            or type(obj["n"]) is not int or obj["n"] != KDF_N
            or type(obj["r"]) is not int or obj["r"] != KDF_R
            or type(obj["p"]) is not int or obj["p"] != KDF_P
            or obj["user_key_recovery_independently_required"] is not True
            or obj["source_catalog_approved"] is not False
            or obj["customer_release_authorized"] is not False):
        raise ValueError("Backup header security configuration does not match")
    try:
        salt = base64.b64decode(obj["salt_b64"], validate=True)
        nonce = base64.b64decode(obj["nonce_b64"], validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Corrupt salt or nonce") from exc
    if len(salt) != 16 or len(nonce) != 12 or _header(salt, nonce) != raw:
        raise ValueError("Noncanonical or invalid backup encryption header")
    return salt, nonce


def create_backup(
    source_dir: str | Path, backup_file: str | Path, passphrase: bytes, *,
    expected_sha256: str = ORIGINAL_SHA256, expected_bytes: int = ORIGINAL_BYTES,
) -> dict[str, Any]:
    plaintext = _payload(source_dir, original_sha256=expected_sha256, original_bytes=expected_bytes)
    out = _private_path(backup_file, directory=False)
    if out.exists() or out.is_symlink():
        raise FileExistsError("Backup destination already exists; never overwrite a previous copy")
    source_root = _private_path(source_dir, directory=True)
    if out.is_relative_to(source_root):
        raise ValueError("Encrypted backup belongs outside source-original directory")
    salt, nonce = os.urandom(16), os.urandom(12)
    aad = _header(salt, nonce)
    AESGCM, _ = _crypto()
    ciphertext = AESGCM(_key(passphrase, salt)).encrypt(nonce, plaintext, aad)
    raw = MAGIC + struct.pack(">I", len(aad)) + aad + ciphertext
    atomic_write_bytes(out, raw, overwrite=False, mode=0o600)
    if hashlib.sha256(_read_bounded(out, MAX_ORIGINAL_BYTES + MAX_RECEIPT_BYTES + MAX_HEADER_BYTES + 128)).digest() != hashlib.sha256(raw).digest():
        raise ValueError("Written encrypted backup differs from verified bytes")
    return {
        "status": "LOCAL_ENCRYPTED_BACKUP_CANDIDATE",
        "cipher": CIPHER, "backup_sha256": hashlib.sha256(raw).hexdigest(),
        "backup_bytes": len(raw), "original_sha256_verified": True,
        "source_receipt_integrity_verified": True,
        "offdevice_copy_verified": False, "independent_restore_test_passed": False,
        "independent_key_escrow_verified": False,
        "source_catalog_approved": False, "customer_release_authorized": False,
    }


def _decrypt(
    backup_file: str | Path, passphrase: bytes, *,
    expected_sha256: str, expected_bytes: int,
) -> tuple[bytes, bytes]:
    _expected(expected_sha256, expected_bytes)
    path = _private_path(backup_file, directory=False)
    raw = _read_bounded(path, MAX_ORIGINAL_BYTES + MAX_RECEIPT_BYTES + MAX_HEADER_BYTES + 128)
    minimum = len(MAGIC) + 4 + 1 + 16
    if not raw.startswith(MAGIC) or len(raw) < minimum:
        raise ValueError("Invalid encrypted backup file header")
    n = struct.unpack(">I", raw[len(MAGIC):len(MAGIC) + 4])[0]
    if not 1 <= n <= MAX_HEADER_BYTES or len(raw) < len(MAGIC) + 4 + n + 16:
        raise ValueError("Invalid encrypted backup header bound")
    aad = raw[len(MAGIC) + 4:len(MAGIC) + 4 + n]
    salt, nonce = _parse_header(aad)
    AESGCM, _ = _crypto()
    payload = AESGCM(_key(passphrase, salt)).decrypt(
        nonce, raw[len(MAGIC) + 4 + n:], aad,
    )
    if not payload.startswith(FRAME) or len(payload) < len(FRAME) + 4:
        raise ValueError("Invalid decrypted original-and-receipt frame")
    at = len(FRAME)
    receipt_length = struct.unpack(">I", payload[at:at + 4])[0]
    at += 4
    if not 0 < receipt_length <= MAX_RECEIPT_BYTES or len(payload) != at + receipt_length + expected_bytes:
        raise ValueError("Decrypted frame byte lengths conflict with known original")
    receipt = payload[at:at + receipt_length]
    original = payload[at + receipt_length:]
    if hashlib.sha256(original).hexdigest() != expected_sha256:
        raise ValueError("Restored original-file SHA differs from independently observed FY2027")
    _validate_receipt(receipt, original_sha256=expected_sha256,
                      original_bytes=expected_bytes,
                      synthetic_test=_expected(expected_sha256, expected_bytes))
    return original, receipt


def verify_backup(
    backup_file: str | Path, passphrase: bytes, *,
    expected_sha256: str = ORIGINAL_SHA256, expected_bytes: int = ORIGINAL_BYTES,
) -> dict[str, Any]:
    original, _ = _decrypt(backup_file, passphrase,
                           expected_sha256=expected_sha256, expected_bytes=expected_bytes)
    return {
        "status": "LOCAL_BACKUP_DECRYPTION_AND_SOURCE_HASH_PASS",
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "original_bytes": len(original), "receipt_integrity_verified": True,
        "independent_offdevice_restore_proven": False,
        "source_catalog_approved": False, "customer_release_authorized": False,
    }


def restore_backup(
    backup_file: str | Path, output_dir: str | Path, passphrase: bytes, *,
    expected_sha256: str = ORIGINAL_SHA256, expected_bytes: int = ORIGINAL_BYTES,
) -> dict[str, Any]:
    original, receipt = _decrypt(
        backup_file, passphrase, expected_sha256=expected_sha256,
        expected_bytes=expected_bytes,
    )
    out = _private_path(output_dir, directory=True)
    dest_original = out / f"FY2027-{expected_sha256}.csv"
    dest_receipt = out / f"FY2027-{expected_sha256}.receipt.json"
    for dest, value in ((dest_original, original), (dest_receipt, receipt)):
        if dest.is_symlink() or (dest.exists() and (not dest.is_file()
                or dest.read_bytes() != value)):
            raise ValueError("Restore destination contains conflicting or unsafe files")
    # All authentication and conflict checks complete before publication.
    ensure_exact_bytes(dest_original, original, mode=0o600)
    os.chmod(dest_original, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    ensure_exact_bytes(dest_receipt, receipt, mode=0o600)
    if (dest_original.read_bytes() != original or dest_receipt.read_bytes() != receipt):
        raise ValueError("Restored original and receipt failed byte-for-byte verification")
    return {
        "status": "LOCAL_ORIGINAL_AND_RECEIPT_RESTORE_PASS",
        "original_sha256": expected_sha256,
        "original_bytes": expected_bytes, "receipt_bytes_preserved": True,
        "independent_offdevice_restore_proven": False,
        "source_catalog_approved": False, "customer_release_authorized": False,
    }


def _read_secret(path: str | None) -> bytes:
    if path is None:
        if not sys.stdin.isatty():
            raise ValueError("Interactive local terminal or independently protected secret file required")
        return getpass.getpass("Private offline backup passphrase: ").encode("utf-8")
    # On Windows, simple file-mode checks do not enforce NTFS ACLs.
    # A plaintext passphrase file with inherited Users/Everyone read access
    # would compromise every off-device encrypted copy. Until a strict SID/ACL
    # verifier is available, require a trusted interactive terminal instead.
    if os.name == "nt":
        raise ValueError("Windows passphrase files are disabled until NTFS ACLs can be verified")
    secret_path = _private_path(path, directory=False)
    if secret_path.is_symlink() or not secret_path.is_file():
        raise ValueError("Secure local passphrase file not present")
    if os.name != "nt" and (secret_path.stat().st_mode & 0o077):
        raise ValueError("Passphrase file grants group/other permissions")
    raw = _read_bounded(secret_path, 1025)
    return raw.rstrip(b"\r\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="operation", required=True)
    for action in ("create", "verify", "restore"):
        p = subs.add_parser(action)
        p.add_argument("--passphrase-file", help="Operator-held protected local secret, never GitHub/chat")
        p.add_argument("--backup-file", required=True)
        if action == "create":
            p.add_argument("--source-dir", required=True)
        if action == "restore":
            p.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        secret = _read_secret(args.passphrase_file)
        if args.operation == "create":
            result = create_backup(args.source_dir, args.backup_file, secret)
        elif args.operation == "verify":
            result = verify_backup(args.backup_file, secret)
        else:
            result = restore_backup(args.backup_file, args.output_dir, secret)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, ImportError, RuntimeError) as exc:
        # Crypto/tag failures must not disclose secret, plaintext paths, or URLs.
        print(json.dumps({"status": "BACKUP_OPERATION_BLOCKED",
                          "error_type": type(exc).__name__,
                          "source_catalog_approved": False,
                          "customer_release_authorized": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
