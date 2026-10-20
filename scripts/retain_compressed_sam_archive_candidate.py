"""PRIVATE, ON-DEMAND gzip retention of an UNAPPROVED original SAM archive CSV.

Requires the exact FY2027 candidate-year inventory and immutable publisher-
declared sizes observed in PR #58. Uses PR #53's strict per-hop guarded public
SAM -> official signed S3 transport, never reads SAM's unapproved UI.

No uncompressed original is persisted as an intermediate file. Raw publisher
bytes are streamed through gzip while hashing, then independently decompressed
and rehashed before an immutable PRIVATE .csv.gz + receipt are published.
No private path, signed transport URL, payload, source bytes or key is printed.

This CANNOT certify source provenance or FULL_CATALOG: no catalog/index update,
customer email, checkout, deployment, scheduled bulk fetch or off-device backup.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capturebrief_core.atomic_io import (
    ensure_exact_bytes, ensure_exact_file, exclusive_path_lock,
)
from capturebrief_core.data_services import ARCHIVE_DOWNLOAD
from capturebrief_core.source_policy import (
    open_approved_extract, require_approved_extract_delivery,
)
from scripts.fy2027_archive_compression_probe import frozen_unapproved_sizes

BLOCK_BYTES = 1024 * 1024
MAX_ORIGINAL_BYTES = 1_500_000_000
MAX_MANIFEST_BYTES = 8192
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def _private_dir(directory: str | Path) -> Path:
    raw = Path(directory).expanduser().absolute()
    for item in (raw, *raw.parents):
        junction = getattr(item, "is_junction", None)
        if item.is_symlink() or (junction is not None and junction()):
            raise ValueError("Private source destination includes an unsafe reparse point")
    real = raw.resolve(strict=False)
    if real == ROOT or real.is_relative_to(ROOT):
        raise ValueError("Private source originals cannot be stored inside public Git")
    if real.exists() and not real.is_dir():
        raise ValueError("Retention root is not a directory")
    # The operator's private root is the only persistent destination.
    real.mkdir(mode=0o700, parents=True, exist_ok=True)
    return real


def _utc(value: datetime | None) -> str:
    value = value or datetime.now(timezone.utc)
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Source observation time must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_file(file: Path) -> tuple[str, int]:
    sha = hashlib.sha256()
    total = 0
    with file.open("rb") as handle:
        for data in iter(lambda: handle.read(BLOCK_BYTES), b""):
            sha.update(data)
            total += len(data)
    return sha.hexdigest(), total


def _verify_decompressed(archive: Path, expected_sha: str, expected_bytes: int) -> None:
    sha = hashlib.sha256()
    count = 0
    with gzip.open(archive, "rb") as handle:
        for part in iter(lambda: handle.read(BLOCK_BYTES), b""):
            count += len(part)
            if count > expected_bytes:
                raise ValueError("Compressed candidate expands beyond exact source bound")
            sha.update(part)
    if count != expected_bytes or sha.hexdigest() != expected_sha:
        raise ValueError("Compressed original fails independent bit-for-bit source replay")


def _decode_unique(pairs):
    result = {}
    for key, val in pairs:
        if key in result:
            raise ValueError("Duplicate source provenance receipt field")
        result[key] = val
    return result


def _canonical(obj: dict[str, Any]) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _safe_receipt(path: Path, wanted: dict[str, Any]) -> tuple[bool, str]:
    """Create or verify immutable receipt without forging a fresh observed_at."""
    raw = _canonical(wanted)
    with exclusive_path_lock(path):
        if path.exists() or path.is_symlink():
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
                raise ValueError("Existing compressed-original receipt path is unsafe")
            previous_raw = path.read_bytes()
            previous = json.loads(previous_raw.decode("utf-8"),
                                  object_pairs_hook=_decode_unique)
            if (not isinstance(previous, dict) or set(previous) != set(wanted)
                    or previous_raw != _canonical(previous)):
                raise ValueError("Compressed source manifest schema is not canonical")
            for key, val in wanted.items():
                if key != "original_observed_at" and previous[key] != val:
                    raise ValueError("Existing source manifest conflicts with immutable original")
            old_stamp = previous.get("original_observed_at")
            if not isinstance(old_stamp, str) or not old_stamp.endswith("Z"):
                raise ValueError("Existing original observation is invalid")
            ensure_exact_bytes(path, previous_raw, mode=0o600)
            return False, old_stamp
        ensure_exact_bytes(path, raw, mode=0o600)
        return True, wanted["original_observed_at"]


def retain_compressed_candidate(
    year: int, private_dir: str | Path, *,
    opener=None, expected_size: int | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """ONE FY at a time, exact original-size-bound, not source/index approval.

    Overrides exist solely for injected fake-byte offline tests; the CLI never
    passes overrides, and production transport cannot accept them.
    """
    if type(year) is not int:
        raise ValueError("Fiscal year must be a numeric frozen candidate")
    sizes = frozen_unapproved_sizes()
    if year not in sizes:
        raise ValueError("FY archive outside unapproved review inventory")
    if expected_size is not None and opener is None:
        raise ValueError("Expected file-size overrides require injected fake I/O")
    total = sizes[year] if expected_size is None else expected_size
    if type(total) is not int or not 0 < total <= MAX_ORIGINAL_BYTES:
        raise ValueError("Archive metadata byte count is outside bounded retention contract")
    observed = _utc(observed_at)
    root = _private_dir(private_dir)
    url = ARCHIVE_DOWNLOAD.format(fy=year)
    req = Request(url, headers={
        "User-Agent": "CaptureBrief/0.3",
        "Accept-Encoding": "identity",
    })
    fd, temp_name = tempfile.mkstemp(
        prefix=f".FY{year}-compressed-", suffix=".tmp", dir=str(root),
    )
    temp = Path(temp_name)
    digest = hashlib.sha256()
    total_read = 0
    host = None
    created_archive = False
    try:
        try:
            # Guard *each* redirect before opening its target; the final host
            # and exact FY object must match the documented SAM entrypoint.
            response = open_approved_extract(
                req, timeout=120.0, source_url=url, opener=opener,
            )
            with response:
                delivered = response.geturl() if hasattr(response, "geturl") else url
                host = require_approved_extract_delivery(url, delivered)
                status = getattr(response, "status", None)
                if status is None and hasattr(response, "getcode"):
                    status = response.getcode()
                if status != 200:
                    raise ValueError("Full source-original response must be HTTP 200")
                headers = getattr(response, "headers", None)
                if headers is None:
                    raise ValueError("Source response lacks trustworthy headers")
                length = headers.get("Content-Length")
                if length is not None and str(length).strip() != str(total):
                    raise ValueError("Publisher-declared source size no longer matches review candidate")
                if str(headers.get("Content-Encoding", "identity")).lower() != "identity":
                    raise ValueError("Unexpected transparent transfer compression")
                with os.fdopen(fd, "wb") as out:
                    fd = -1
                    with gzip.GzipFile(filename="", mode="wb", fileobj=out,
                                       compresslevel=6, mtime=0) as gz:
                        while total_read < total:
                            part = response.read(min(BLOCK_BYTES, total + 1 - total_read))
                            if not part:
                                break
                            total_read += len(part)
                            if total_read > total:
                                raise ValueError("Source stream exceeded exact archive bound")
                            digest.update(part)
                            gz.write(part)
                        if total_read != total or response.read(1):
                            raise ValueError("Official original ended early or exceeded expected size")
                    out.flush()
                    os.fsync(out.fileno())
        finally:
            if fd >= 0:
                os.close(fd)
                fd = -1

        raw_sha = digest.hexdigest()
        if SHA_RE.fullmatch(raw_sha) is None:
            raise ValueError("Original SHA-256 invalid")
        _verify_decompressed(temp, raw_sha, total)
        gz_sha, gz_size = _hash_file(temp)
        if gz_size <= 0 or gz_size > total + 4096:
            raise ValueError("Compressed candidate size is outside fail-closed bounds")
        dest = root / f"FY{year}-{raw_sha}.csv.gz"
        saved = ensure_exact_file(
            temp, dest, expected_sha256=gz_sha, expected_size=gz_size,
            mode=0o444,
        )
        created_archive = bool(saved["created"])
        receipt = {
            "schema": "capturebrief-private-unapproved-original-gzip-retention-v1",
            "source_entrypoint": url,
            "source_metadata_reference": "https://github.com/P00NSMASHER/capturebrief/actions/runs/39350338311",
            "metadata_class": "UNREVIEWED_PUBLIC_ORIGIN_ONE_BYTE_HEADER",
            "fiscal_year": year,
            "original_bytes": total,
            "original_sha256": raw_sha,
            "gzip_sha256": gz_sha,
            "gzip_bytes": gz_size,
            "gzip_format": "RFC1952_DETERMINISTIC_MTIME_ZERO",
            "verified_decompressed_original_sha256": True,
            "verified_decompressed_original_bytes": True,
            "original_observed_at": observed,
            "trusted_delivery_host": host,
            "synthetic_test_override": expected_size is not None,
            "original_stored_uncompressed": False,
            "catalog_approved": False,
            "private_source_index_updated": False,
            "full_catalog_history_verified": False,
            "publisher_originals_independently_reviewed": False,
            "offdevice_backup_verified": False,
            "device_encryption_verified": False,
            "customer_release_authorized": False,
            "external_send_authorized": False,
        }
        receipt_path = root / f"FY{year}-{raw_sha}.gzip-candidate.receipt.json"
        new_receipt, observed = _safe_receipt(receipt_path, receipt)
        return {
            "status": "PRIVATE_COMPRESSED_ORIGINAL_CANDIDATE_NOT_APPROVED",
            "year": year, "original_bytes": total, "original_sha256": raw_sha,
            "gzip_bytes": gz_size, "gzip_sha256": gz_sha,
            "compression_ratio": round(gz_size / total, 6),
            "archive_created": created_archive, "receipt_created": new_receipt,
            "first_original_observed_at": observed,
            "source_index_updated": False, "catalog_approved": False,
            "customer_release_authorized": False, "external_send_authorized": False,
        }
    finally:
        if fd >= 0:
            os.close(fd)
        if temp.exists():
            if os.name == "nt":
                os.chmod(temp, 0o600)
            temp.unlink()


def verify_compressed_candidate(year: int, private_dir: str | Path,
                                 *, original_sha256: str) -> dict[str, Any]:
    if type(year) is not int or year not in frozen_unapproved_sizes():
        raise ValueError("Unknown candidate archive year")
    if not isinstance(original_sha256, str) or SHA_RE.fullmatch(original_sha256) is None:
        raise ValueError("Invalid pinned original SHA-256")
    root = _private_dir(private_dir)
    archive = root / f"FY{year}-{original_sha256}.csv.gz"
    receipt_path = root / f"FY{year}-{original_sha256}.gzip-candidate.receipt.json"
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("Compressed candidate is unavailable or unsafe")
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise ValueError("Private original-source receipt is unavailable")
    raw = receipt_path.read_bytes()
    if not 0 < len(raw) <= MAX_MANIFEST_BYTES:
        raise ValueError("Private source manifest outside size bound")
    r = json.loads(raw.decode("utf-8"), object_pairs_hook=_decode_unique)
    if not isinstance(r, dict) or _canonical(r) != raw:
        raise ValueError("Private source manifest is not canonical")
    if (r.get("schema") != "capturebrief-private-unapproved-original-gzip-retention-v1"
            or r.get("fiscal_year") != year
            or r.get("original_sha256") != original_sha256
            or r.get("source_entrypoint") != ARCHIVE_DOWNLOAD.format(fy=year)
            or r.get("catalog_approved") is not False
            or r.get("customer_release_authorized") is not False
            or r.get("full_catalog_history_verified") is not False
            or r.get("private_source_index_updated") is not False
            or r.get("verified_decompressed_original_sha256") is not True
            or r.get("verified_decompressed_original_bytes") is not True):
        raise ValueError("Private source manifest validation failed")
    raw_size = r.get("original_bytes")
    if type(raw_size) is not int or raw_size < 1 or raw_size > MAX_ORIGINAL_BYTES:
        raise ValueError("Retained original size invalid")
    gzip_sha, gzip_bytes = _hash_file(archive)
    if gzip_sha != r.get("gzip_sha256") or gzip_bytes != r.get("gzip_bytes"):
        raise ValueError("Compressed original differs from immutable receipt")
    _verify_decompressed(archive, original_sha256, raw_size)
    return {
        "status": "PRIVATE_GZIP_CANDIDATE_BYTE_INTEGRITY_PASS_ONLY",
        "year": year, "original_bytes": raw_size, "original_sha256": original_sha256,
        "gzip_bytes": gzip_bytes, "gzip_sha256": gzip_sha,
        "offdevice_backup_verified": False, "catalog_approved": False,
        "source_index_updated": False, "customer_release_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    add = sub.add_parser("retain")
    add.add_argument("--year", required=True, type=int)
    add.add_argument("--private-dir", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--year", required=True, type=int)
    verify.add_argument("--private-dir", required=True)
    verify.add_argument("--original-sha256", required=True)
    args = p.parse_args(argv)
    try:
        if args.command == "retain":
            result = retain_compressed_candidate(args.year, args.private_dir)
        else:
            result = verify_compressed_candidate(
                args.year, args.private_dir,
                original_sha256=args.original_sha256,
            )
    except Exception as exc:
        # Never include signed URLs, private paths, source bytes or provider errors.
        print(json.dumps({
            "status": "PRIVATE_SOURCE_COMPRESSION_BLOCKED",
            "error_type": type(exc).__name__,
            "catalog_approved": False, "customer_release_authorized": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
