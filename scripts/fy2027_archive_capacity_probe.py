"""Metadata-only SAM FY2027 archive budget reconnaissance. NEVER authorizes release.

No catalog changes, archive ingestion, source-index creation, original-file
retention, customer information, external sends, payments or deployments.
An official documented PUBLIC Data Services extract URL is the only entry.
Every redirect is guarded by PR #53's exact host+object+SigV4 policy.
Use only to scope an independent operator's storage plan, not attest source.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request

from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from capturebrief_core.data_services import ARCHIVE_DOWNLOAD
from capturebrief_core.source_policy import (
    open_approved_extract, require_approved_extract_delivery,
)

CANDIDATE_YEARS = (1969, 1970, 1980, 1981, *range(1998, 2028))
assert len(CANDIDATE_YEARS) == 34
TOTAL_MAX_BYTES = 100_000_000_000
CONTENT_RANGE = re.compile(r"^bytes 0-0/([1-9][0-9]*)$")


def inspect_archive_header(year: int, *, opener=None, timeout: float = 15.0) -> dict[str, Any]:
    """Request just byte 0 from one pinned, PUBLIC SAM original transport.

    The observation is explicitly NOT publisher attestation or full bytes.
    A server that ignores Range is rejected before any full-body read.
    """
    if type(year) is not int or year not in CANDIDATE_YEARS:
        raise ValueError("Fiscal year is outside the frozen unapproved review candidate")
    source = ARCHIVE_DOWNLOAD.format(fy=year)
    req = Request(source, headers={"User-Agent": "CaptureBrief/0.3", "Range": "bytes=0-0"})
    response = open_approved_extract(req, source_url=source, timeout=timeout, opener=opener)
    with response:
        delivered = response.geturl() if hasattr(response, "geturl") else source
        host = require_approved_extract_delivery(source, delivered)
        status = getattr(response, "status", None)
        if status is None and hasattr(response, "getcode"):
            status = response.getcode()
        if status != 206:
            return {
                "fiscal_year": year, "status": "RANGE_NOT_PROVEN",
                "http_status": status if type(status) is int else None,
                "origin_object_bytes": None, "transport_host": host,
                "bytes_downloaded": 0, "publisher_original_verified": False,
                "catalog_approved": False,
            }
        headers = getattr(response, "headers", None)
        if headers is None:
            raise ValueError("Partial response missing source headers")
        match = CONTENT_RANGE.fullmatch(str(headers.get("Content-Range", "")).strip())
        if match is None:
            raise ValueError("Partial response lacks exact one-byte Content-Range")
        total_bytes = int(match.group(1))
        if total_bytes <= 0 or total_bytes > TOTAL_MAX_BYTES:
            raise ValueError("Archive original size is implausible or outside budget bound")
        declared_length = headers.get("Content-Length")
        if declared_length is not None and str(declared_length).strip() != "1":
            raise ValueError("Partial origin Content-Length not one byte")
        one_byte = response.read(2)
        if not isinstance(one_byte, bytes) or len(one_byte) != 1:
            raise ValueError("Partial origin response delivered unexpected byte count")
    return {
        "fiscal_year": year, "status": "ONE_BYTE_RANGE_AND_SIZE_DECLARED_UNREVIEWED",
        "http_status": 206, "origin_object_bytes": total_bytes,
        "transport_host": host, "bytes_downloaded": 1,
        "publisher_original_verified": False, "catalog_approved": False,
    }


def probe_many(years: list[int], *, opener=None, sleep_seconds: float = 0.0) -> dict[str, Any]:
    """Read ONLY pinned metadata and a single byte per annual source."""
    if (not isinstance(years, list) or not years or len(years) > len(CANDIDATE_YEARS)
            or any(type(y) is not int or y not in CANDIDATE_YEARS for y in years)
            or len(set(years)) != len(years)):
        raise ValueError("Explicit probe fiscal years must be unique approved candidates")
    records = []
    for position, year in enumerate(years):
        if position and sleep_seconds:
            time.sleep(sleep_seconds)
        try:
            record = inspect_archive_header(year, opener=opener)
        except Exception as exc:
            # Never print the full HTTPError/URL/redirect query; its text may
            # contain a short-lived SigV4 token or destination path.
            record = {
                "fiscal_year": year, "status": "SOURCE_METADATA_UNAVAILABLE",
                "http_status": None, "origin_object_bytes": None,
                "transport_host": None, "bytes_downloaded": 0,
                "error_type": type(exc).__name__,
                "publisher_original_verified": False, "catalog_approved": False,
            }
        records.append(record)
    proven = [r for r in records if r["status"] == "ONE_BYTE_RANGE_AND_SIZE_DECLARED_UNREVIEWED"]
    total = sum(r["origin_object_bytes"] for r in proven)
    return {
        "schema": "capturebrief-fy2027-unapproved-capacity-observation-v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "requested_year_count": len(years),
        "frozen_candidate_year_count": len(CANDIDATE_YEARS),
        "confirmed_one_byte_metadata_count": len(proven),
        "complete_metadata_coverage": len(years) == len(CANDIDATE_YEARS) == len(proven),
        "confirmed_metadata_years_sum_bytes": total,
        "total_archive_bytes_only_if_all_metadata_confirmed": total if len(years) == len(CANDIDATE_YEARS) == len(proven) else None,
        "single_byte_observations": records,
        "original_bytes_retained": False,
        "independent_human_catalog_reviewed": False,
        "publisher_originals_verified": False,
        "active_extract_budget_included": False,
        "disk_space_checked": False,
        "source_index_updated": False,
        "FY2027_full_catalog_certified": False,
        "external_send_authorized": False,
        "customer_release_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-public-metadata", action="store_true", required=True,
                        help="Explicit opt-in to one byte per listed public archive")
    parser.add_argument("--years", default="all",
                        help="all or comma-separated strict subset of frozen candidate fiscal years")
    args = parser.parse_args(argv)
    try:
        if args.years == "all":
            years = list(CANDIDATE_YEARS)
        else:
            years = [int(part) for part in args.years.split(",")]
        output = probe_many(years, sleep_seconds=0.25)
    except (ValueError, TypeError, OverflowError) as exc:
        print(json.dumps({"status": "METADATA_OBSERVATION_BLOCKED",
                          "error_type": type(exc).__name__,
                          "FY2027_full_catalog_certified": False,
                          "customer_release_authorized": False}, sort_keys=True))
        return 2
    print(json.dumps(output, indent=2, sort_keys=True))
    # Failed individual observations are explicitly reported; no source/catalog
    # or customer release flag ever becomes true merely from metadata.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
