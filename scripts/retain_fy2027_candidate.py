"""Privately retain ONLY the exact FY2027 public SAM CSV verified 2026-10-19.

This is a one-off, approved SAM Data Services entrypoint -> guarded exact
official S3 object transfer. It does not certify publisher identity, approve
the FY2027 catalog, update an indexed source slot, or grant buyer release.
The complete original is never stored in the public GitHub repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from capturebrief_core.atomic_io import ensure_exact_bytes, ensure_exact_file
from capturebrief_core.data_services import ARCHIVE_DOWNLOAD
from capturebrief_core.history_index import download_extract_to_file

FISCAL_YEAR = 2027
KNOWN_ORIGINAL_SHA256 = "7b4e00e3156248db9dcca767431bb6c5d4168aeeb2abc707ab12c0f9e61d71ce"
KNOWN_ORIGINAL_BYTES = 1607260
MAX_TRANSFER_BYTES = 2_000_000
PROVENANCE_RUN = "https://github.com/P00NSMASHER/capturebrief/actions/runs/39205786451"
PUBLIC_LISTING = (
    "https://sam.gov/data-services/Contract%20Opportunities/Archived%20Data?privacy=Public"
)
SOURCE_URL = ARCHIVE_DOWNLOAD.format(fy=FISCAL_YEAR)
SHA = re.compile(r"^[0-9a-f]{64}$")


def _private_root(directory: str | Path) -> Path:
    path = Path(directory).expanduser().absolute()
    if path.is_symlink() or path.is_relative_to(REPO):
        raise ValueError("Source bytes must be retained in a private, non-symlink directory")
    parent = path.parent.resolve(strict=True)
    if parent.is_relative_to(REPO):
        raise ValueError("Source bytes must be retained outside the public repo")
    resolved = path.resolve(strict=False)
    if resolved.is_relative_to(REPO):
        raise ValueError("Source bytes must be retained outside the public repo")
    if path.exists() and not path.is_dir():
        raise ValueError("Source bytes destination is not a directory")
    return resolved


def retain_exact_fy2027(
    directory: str | Path,
    *,
    opener=None,
    expected_sha256: str = KNOWN_ORIGINAL_SHA256,
    expected_bytes: int = KNOWN_ORIGINAL_BYTES,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Make a private immutable retained source file; never update catalog.

    The explicit expected override is for deterministic fake-byte tests ONLY.
    The CLI hardcodes the immutable verified public-source SHA and byte count.
    """
    if not isinstance(expected_sha256, str) or SHA.fullmatch(expected_sha256) is None:
        raise ValueError("expected SHA must be a 64-character lowercase hex digest")
    if type(expected_bytes) is not int or not (0 < expected_bytes <= MAX_TRANSFER_BYTES):
        raise ValueError("expected size is not within the public FY2027 transfer bound")
    stamp = observed_at or datetime.now(timezone.utc)
    if not isinstance(stamp, datetime) or stamp.utcoffset() is None:
        raise ValueError("observation must have timezone")
    stamp = stamp.astimezone(timezone.utc)
    root = _private_root(directory)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Use an isolated temporary directory. If the authoritative original
    # changes, do NOT overwrite a previous file or publish an unverified copy.
    with tempfile.TemporaryDirectory(prefix=".fy2027-transfer-", dir=root) as work:
        temporary = Path(work) / "FY2027_archived_opportunities.csv"
        args = {
            "source_url": SOURCE_URL,
            "max_bytes": MAX_TRANSFER_BYTES,
        }
        if opener is not None:
            args["opener"] = opener
        fetched = download_extract_to_file(temporary, **args)
        digest = fetched.get("sha256")
        size = fetched.get("size_bytes")
        if digest != expected_sha256 or size != expected_bytes:
            raise ValueError("SAM original changed from independently observed exact FY2027 bytes")
        if fetched.get("source_url") != SOURCE_URL:
            raise ValueError("Downloaded source is not the approved public SAM entrypoint")
        # Host is transport evidence, not independent publisher approval.
        if fetched.get("final_delivery_host") not in {
            "sam.gov", "s3.amazonaws.com", "falextracts.s3.amazonaws.com",
        }:
            # This is the final constrained transport host returned by the
            # source-policy validator, NEVER a blanket acceptance of S3.
            raise ValueError("Downloaded source did not use approved first-party transport")
        final_path = root / f"FY2027-{digest}.csv"
        retention = ensure_exact_file(
            temporary, final_path,
            expected_sha256=expected_sha256,
            expected_size=expected_bytes,
            mode=0o444,
        )

    receipt = {
        "schema": "capturebrief-fy2027-private-candidate-retention-v1",
        "source_listing": PUBLIC_LISTING,
        "source_url": SOURCE_URL,
        "prior_ci_sha256": KNOWN_ORIGINAL_SHA256,
        "prior_ci_run": PROVENANCE_RUN,
        "observed_at": stamp.isoformat().replace("+00:00", "Z"),
        "downloaded_sha256": digest,
        "downloaded_bytes": size,
        "retained_original_file": True,
        "local_file_sha256_verified": retention["sha256"] == digest,
        "official_delivery_host": fetched.get("final_delivery_host"),
        "redirect_used": fetched.get("redirect_used"),
        "source_etag": fetched.get("source_etag"),
        "source_last_modified": fetched.get("source_last_modified"),
        "operator_path": str(final_path),
        "test_override": (expected_sha256 != KNOWN_ORIGINAL_SHA256
                          or expected_bytes != KNOWN_ORIGINAL_BYTES),
        "catalog_approved": False,
        "full_archive_history_verified": False,
        "human_source_review_complete": False,
        "case_release_authorized": False,
        "external_send_authorized": False,
    }
    receipt_raw = (json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False)
                   + "\n").encode("utf-8")
    receipt_path = root / f"FY2027-{digest}.receipt.json"
    ensure_exact_bytes(receipt_path, receipt_raw)
    return {
        "status": "PRIVATE_SOURCE_OBSERVATION_REVIEW_REQUIRED",
        "sha256": digest,
        "bytes": size,
        "receipt_file": str(receipt_path),
        "original_file": str(final_path),
        "test_override": receipt["test_override"],
        "catalog_approved": False,
        "case_release_authorized": False,
        "external_send_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-dir", required=True,
                   help="A private local filesystem directory outside public GitHub/Pages")
    args = p.parse_args(argv)
    try:
        result = retain_exact_fy2027(args.private_dir)
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        # Do not log provider URLs, signed redirects or private local paths.
        print(json.dumps({"status": "SOURCE_RETENTION_BLOCKED",
                          "error_type": type(exc).__name__,
                          "catalog_approved": False,
                          "external_send_authorized": False}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
