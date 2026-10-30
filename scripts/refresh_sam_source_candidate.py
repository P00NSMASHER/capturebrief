"""Refresh a private, explicitly UNAPPROVED SAM source/index review candidate.

Unlike the historical Oct19 checksum verifier, this records the bytes actually
served now. It never rewrites a prior source, approves the FY2027 catalog, or
uses a customer/production index. The existing guarded transport, CSV parser,
immutable retention and independent row-projection audit remain mandatory.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capturebrief_core.atomic_io import ensure_exact_bytes, ensure_exact_file, exclusive_path_lock
from capturebrief_core.data_services import ACTIVE_DOWNLOAD, ARCHIVE_DOWNLOAD
from capturebrief_core.history_index import APPROVED_FETCH, OPERATOR_FILE, download_extract_to_file, ingest_extract_file
from scripts.audit_original_index_projection import audit_row_projection
from scripts.fy2027_archive_capacity_probe import CANDIDATE_YEARS
from scripts.retain_compressed_sam_archive_candidate import _private_dir

MARKER = {
    "schema": "capturebrief-unapproved-source-candidate-workspace-v1",
    "purpose": "SOURCE_REVIEW_CANDIDATE_ONLY",
    "production_index": False,
    "catalog_approved": False,
    "customer_release_authorized": False,
}
MAX_BYTES = 2_000_000_000
RESERVE_BYTES = 4 * 1024**3


def _bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _slot(slot):
    if slot == "ACTIVE":
        return "ACTIVE", None, ACTIVE_DOWNLOAD
    if isinstance(slot, str) and slot.startswith("ARCHIVE:"):
        raw = slot.removeprefix("ARCHIVE:")
        if raw.isdecimal() and int(raw) in CANDIDATE_YEARS and raw == str(int(raw)):
            year = int(raw)
            return "ARCHIVE", year, ARCHIVE_DOWNLOAD.format(fy=year)
    raise ValueError("Slot must be ACTIVE or an explicitly observed candidate archive year")


def refresh_candidate(private_dir, *, slot, max_bytes, opener=None):
    kind, year, source_url = _slot(slot)
    if type(max_bytes) is not int or not 0 < max_bytes <= MAX_BYTES:
        raise ValueError("Explicit positive transfer bound must not exceed 2GB")
    raw = Path(private_dir).expanduser().absolute()
    if any((parent / ".git").is_file() or (parent / ".git" / "HEAD").is_file()
           for parent in (raw, *raw.parents)):
        raise ValueError("Candidate source data must be outside every Git checkout")
    root = _private_dir(raw)
    marker = root / "CANDIDATE-ONLY.json"
    # Do not adopt an arbitrary existing private/production database.
    if not marker.exists() and any(root.iterdir()):
        raise ValueError("A new candidate workspace must be empty")
    ensure_exact_bytes(marker, _bytes(MARKER), mode=0o600)
    index = root / "candidate-source-index.sqlite"
    originals = root / "originals"
    receipts = root / "observations"
    for path in (originals, receipts):
        if path.is_symlink():
            raise ValueError("Candidate directories must not follow links")
        path.mkdir(mode=0o700, exist_ok=True)
    if index.is_symlink():
        raise ValueError("Candidate index must not follow links")
    with exclusive_path_lock(root / ".candidate-refresh", timeout_seconds=0):
        # Temporary source, retained source, and a conservative one-source
        # index allowance coexist. This is not whole-catalog capacity proof.
        if shutil.disk_usage(root).free < 3 * max_bytes + RESERVE_BYTES:
            raise ValueError("Insufficient capacity for bounded candidate refresh")
        with tempfile.TemporaryDirectory(prefix="transfer-", dir=root) as temporary:
            work = Path(temporary)
            fetched = download_extract_to_file(
                work / "original.csv", source_url=source_url,
                max_bytes=max_bytes, opener=opener,
            )
            kwargs = dict(source_url=source_url, source_kind=kind, fiscal_year=year,
                          observed_at=fetched["observed_at"],
                          collection_mode=APPROVED_FETCH if opener is None else OPERATOR_FILE,
                          source_etag=fetched.get("source_etag"),
                          source_last_modified=fetched.get("source_last_modified"))
            # Reject malformed source rows before changing the persistent
            # candidate index. The validation index is temporary and isolated.
            ingest_extract_file(work / "validation.sqlite", work / "original.csv", **kwargs)
            audit_row_projection(work / "validation.sqlite", slot=slot, snapshot_root=work)
            retained = originals / (slot.replace(":", "-") + "-" + fetched["sha256"] + ".csv")
            ensure_exact_file(work / "original.csv", retained,
                              expected_sha256=fetched["sha256"],
                              expected_size=fetched["size_bytes"], mode=0o400)
            ingested = ingest_extract_file(index, retained, **kwargs)
        if os.name != "nt":
            index.chmod(0o600)
        projected = audit_row_projection(index, slot=slot, snapshot_root=originals)
        receipt = {
            "schema": "capturebrief-current-source-candidate-observation-v1",
            "slot": slot, "source_url": source_url,
            "observed_at": fetched["observed_at"],
            "source_sha256": fetched["sha256"], "source_bytes": fetched["size_bytes"],
            "source_etag": fetched.get("source_etag"),
            "source_last_modified": fetched.get("source_last_modified"),
            "official_delivery_host": fetched["final_delivery_host"],
            "signed_delivery_url_retained": False,
            "rows_indexed": ingested["rows_scanned"],
            "exact_source_projection_verified": projected["exact_row_fields_verified"],
            "original_relative_path": retained.relative_to(root).as_posix(),
            "synthetic_transport": opener is not None,
            "catalog_approved": False,
            "independent_human_source_review_complete": False,
            "production_index_updated": False,
            "offdevice_restore_verified": False,
            "customer_release_authorized": False,
            "external_send_authorized": False,
        }
        stamp = datetime.fromisoformat(fetched["observed_at"]).strftime("%Y%m%dT%H%M%S%fZ")
        name = slot.replace(":", "-") + "-" + stamp + "-" + fetched["sha256"] + ".json"
        ensure_exact_bytes(receipts / name, _bytes(receipt), mode=0o600)
    return {
        "status": "FRESH_SOURCE_CANDIDATE_INDEXED_REVIEW_REQUIRED",
        **{key: value for key, value in receipt.items() if key != "original_relative_path"},
        "candidate_snapshot_reused": ingested["reused"],
        "prior_source_bytes_and_observations_preserved": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", required=True, type=Path)
    parser.add_argument("--slot", required=True)
    parser.add_argument("--max-bytes", type=int, required=True,
                        help="Explicit full-original bound, at most 2000000000")
    args = parser.parse_args(argv)
    try:
        result = refresh_candidate(args.private_dir, slot=args.slot, max_bytes=args.max_bytes)
    except Exception as error:
        print(json.dumps({"status": "SOURCE_CANDIDATE_REFRESH_BLOCKED",
                          "error_type": type(error).__name__, "catalog_approved": False,
                          "customer_release_authorized": False}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
