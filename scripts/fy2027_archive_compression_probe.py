"""BOUNDED source-range compression reconnaissance, not a source importer.

Samples official PUBLIC FY archives through the exact guarded SAM.gov -> S3
redirect contract. Reads at most three 128 KiB ranges per year, never a
complete large original, never stores or prints source bytes, and never
certifies sources, compression capacity, backups or customer release.
This is advisory compression evidence ONLY; no source or customer data
is uploaded as a GitHub artifact.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from capturebrief_core.data_services import ARCHIVE_DOWNLOAD
from capturebrief_core.source_policy import (
    open_approved_extract, require_approved_extract_delivery,
)
from scripts.fy2027_archive_capacity_probe import CANDIDATE_YEARS

MAX_YEAR_COUNT = 10
MAX_WINDOW_BYTES = 128 * 1024
WINDOWS_PER_YEAR = 3
MAX_NETWORK_BYTES = MAX_YEAR_COUNT * MAX_WINDOW_BYTES * WINDOWS_PER_YEAR
OBSERVATION = REPO / "research" / "fy2027_archive_capacity_observation_20261020.json"


def _no_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Duplicate metadata key")
        out[key] = value
    return out


def frozen_unapproved_sizes() -> dict[int, int]:
    """Validate the exact previously observed metadata receipt, never approve it."""
    if not OBSERVATION.is_file() or OBSERVATION.stat().st_size > 64 * 1024:
        raise ValueError("Missing or oversized frozen source-size observation")
    obj = json.loads(OBSERVATION.read_text(encoding="utf-8"),
                     object_pairs_hook=_no_duplicate_keys)
    if (obj.get("schema") != "capturebrief-fy2027-unapproved-archive-capacity-snapshot-v1"
            or obj.get("source_actions_run") !=
            "https://github.com/P00NSMASHER/capturebrief/actions/runs/39350338311"
            or obj.get("candidate_archive_years") != 34
            or obj.get("bytes_read_per_year") != 1
            or obj.get("independent_human_catalog_approval") is not False
            or obj.get("full_catalog_claim_authorized") is not False
            or obj.get("customer_release_authorized") is not False
            or obj.get("original_source_files_retrieved") is not False):
        raise ValueError("Unapproved metadata receipt identity changed")
    raw = obj.get("year_size_bytes")
    required = {"FY" + str(year) for year in CANDIDATE_YEARS}
    if not isinstance(raw, dict) or set(raw) != required:
        raise ValueError("Frozen source metadata year inventory is inconsistent")
    if any(type(value) is not int or not (0 < value <= 100_000_000_000)
           for value in raw.values()):
        raise ValueError("Invalid observed source-byte sizes")
    if (type(obj.get("archive_size_sum_bytes")) is not int
            or sum(raw.values()) != obj["archive_size_sum_bytes"]
            or obj["archive_size_sum_bytes"] != 20_333_624_076):
        raise ValueError("Frozen metadata total changed")
    return {year: raw["FY" + str(year)] for year in CANDIDATE_YEARS}


def _windows(total: int, *, max_window: int) -> list[tuple[int, int]]:
    if (type(total) is not int or total < 1
            or type(max_window) is not int
            or not 1 <= max_window <= MAX_WINDOW_BYTES):
        raise ValueError("Invalid source range window")
    # Restrict aggregate samples to < full original, including tiny years.
    window = min(max_window, (total - 1) // 4)
    if window == 0:
        return []
    starts = (0, max(0, (total - window) // 2), total - window)
    out = list(dict.fromkeys((start, start + window - 1) for start in starts))
    if sum(end - start + 1 for start, end in out) >= total:
        raise ValueError("Range plan would sample the complete original")
    return out


def _sample_range(
    year: int, start: int, end: int, *, total: int,
    opener=None, timeout: float = 20.0,
) -> tuple[int, int, str]:
    """Read exactly the accepted byte range from a guarded first-party source."""
    if type(year) is not int or year not in CANDIDATE_YEARS:
        raise ValueError("Unapproved sample year")
    if (type(start) is not int or type(end) is not int
            or start < 0 or end < start or end >= total
            or end - start + 1 > MAX_WINDOW_BYTES):
        raise ValueError("Unsafe range boundaries")
    url = ARCHIVE_DOWNLOAD.format(fy=year)
    length = end - start + 1
    req = Request(url, headers={
        "User-Agent": "CaptureBrief/0.3",
        "Range": f"bytes={start}-{end}",
        "Accept-Encoding": "identity",
    })
    response = open_approved_extract(
        req, timeout=timeout, source_url=url, opener=opener,
    )
    with response:
        target = response.geturl() if hasattr(response, "geturl") else url
        host = require_approved_extract_delivery(url, target)
        status = getattr(response, "status", None)
        if status is None and hasattr(response, "getcode"):
            status = response.getcode()
        # Absolutely no read when the origin ignores range or returns 200.
        if status != 206:
            raise ValueError("Source did not honor the bounded range")
        headers = getattr(response, "headers", None)
        if headers is None:
            raise ValueError("No source metadata headers")
        if str(headers.get("Content-Range", "")).strip() != f"bytes {start}-{end}/{total}":
            raise ValueError("Origin changed or returned inconsistent range")
        declared_length = headers.get("Content-Length")
        if declared_length is not None and str(declared_length).strip() != str(length):
            raise ValueError("Source partial Content-Length mismatch")
        if str(headers.get("Content-Encoding", "identity")).strip().lower() != "identity":
            raise ValueError("Encoded transfer cannot demonstrate original-byte range")
        data = response.read(length + 1)
        if not isinstance(data, bytes) or len(data) != length:
            raise ValueError("Sampled source did not return exactly the range length")
    # Never retain raw source samples beyond the current function. No content
    # may be returned, printed, written to disk, or surfaced in exception text.
    compressed = gzip.compress(data, compresslevel=6, mtime=0)
    return len(data), len(compressed), host


def sample_year(year: int, *, size: int, opener=None,
                max_window: int = MAX_WINDOW_BYTES) -> dict[str, Any]:
    if type(year) is not int or year not in CANDIDATE_YEARS:
        raise ValueError("Sample year outside frozen review candidate")
    spans = _windows(size, max_window=max_window)
    if not spans:
        return {
            "fiscal_year": year, "status": "TOO_SMALL_TO_SAMPLE_SAFELY",
            "declared_original_bytes": size, "sampled_bytes": 0,
            "sampled_gzip_bytes": 0, "sample_range_count": 0,
            "estimated_gzip_ratio_sample_only": None,
            "publisher_original_verified": False,
        }
    total_read = total_gzip = 0
    observed_hosts = set()
    for start, end in spans:
        n, c, host = _sample_range(
            year, start, end, total=size, opener=opener,
        )
        total_read += n
        total_gzip += c
        observed_hosts.add(host)
    return {
        "fiscal_year": year,
        "status": "BOUNDED_GZIP_SAMPLE_OBSERVED_UNREVIEWED",
        "declared_original_bytes": size,
        "sampled_bytes": total_read, "sampled_gzip_bytes": total_gzip,
        "sample_range_count": len(spans),
        "sample_fraction_of_original": round(total_read / size, 8),
        "estimated_gzip_ratio_sample_only": round(total_gzip / total_read, 6),
        "transport_hosts": sorted(observed_hosts),
        "publisher_original_verified": False,
    }


def sample_many(years: list[int], *, opener=None,
                max_window: int = MAX_WINDOW_BYTES,
                sleep_seconds: float = 0.0) -> dict[str, Any]:
    if (not isinstance(years, list) or not years
            or len(years) > MAX_YEAR_COUNT
            or len(set(years)) != len(years)
            or any(type(year) is not int or year not in CANDIDATE_YEARS for year in years)):
        raise ValueError("At most 10 distinct frozen review candidate years allowed")
    if type(max_window) is not int or not (1 <= max_window <= MAX_WINDOW_BYTES):
        raise ValueError("Source sample window limit exceeded")
    sizes = frozen_unapproved_sizes()
    observations = []
    for i, year in enumerate(years):
        if i and sleep_seconds > 0:
            time.sleep(sleep_seconds)
        try:
            result = sample_year(year, size=sizes[year], opener=opener,
                                 max_window=max_window)
        except Exception as exc:
            # Signed URLs and provider exceptions can contain auth material.
            # Never print a URL, error string, request body or raw source bytes.
            result = {
                "fiscal_year": year, "status": "RANGE_SAMPLE_UNAVAILABLE",
                "error_type": type(exc).__name__,
                "declared_original_bytes": sizes[year],
                "sampled_bytes": 0, "sampled_gzip_bytes": 0,
                "estimated_gzip_ratio_sample_only": None,
                "publisher_original_verified": False,
            }
        observations.append(result)
    successful = [x for x in observations
                  if x["status"] == "BOUNDED_GZIP_SAMPLE_OBSERVED_UNREVIEWED"]
    observed_bytes = sum(x["sampled_bytes"] for x in successful)
    if observed_bytes > MAX_NETWORK_BYTES:
        raise ValueError("Global sampling byte budget exceeded")
    weighted_proxy = sum(
        round(x["declared_original_bytes"] * x["estimated_gzip_ratio_sample_only"])
        for x in successful
    )
    return {
        "schema": "capturebrief-fy2027-bounded-gzip-sampling-v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "requested_years": years,
        "selected_year_count": len(years),
        "complete_archive_coverage": False,
        "sample_max_bytes_per_range": max_window,
        "sampled_year_count": len(successful),
        "sampled_source_bytes": observed_bytes,
        "sampled_network_byte_budget": MAX_NETWORK_BYTES,
        "selected_original_metadata_bytes": sum(sizes[y] for y in years),
        "subset_sample_derived_gzip_proxy_bytes": (
            weighted_proxy if len(successful) == len(years) else None
        ),
        "subset_proxy_is_guaranteed_upper_bound": False,
        "complete_archive_compressed_bytes_proven": False,
        "fit_on_paam_l044_proven": False,
        "original_bytes_durably_retained": False,
        "source_index_updated": False,
        "human_catalog_approval": False,
        "disk_encryption_verified": False,
        "offdevice_backup_verified": False,
        "external_send_authorized": False,
        "customer_release_authorized": False,
        "year_observations": observations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-public-samples", required=True, action="store_true")
    parser.add_argument("--years", required=True,
                        help="At most 10 comma-separated archive years")
    parser.add_argument("--max-window-bytes", type=int, default=MAX_WINDOW_BYTES)
    args = parser.parse_args(argv)
    try:
        years = [int(y) for y in args.years.split(",")]
        result = sample_many(years, max_window=args.max_window_bytes,
                             sleep_seconds=0.25)
    except (ValueError, TypeError) as exc:
        print(json.dumps({
            "status": "SOURCE_COMPRESSION_PROBE_BLOCKED",
            "error_type": type(exc).__name__,
            "complete_archive_compressed_bytes_proven": False,
            "customer_release_authorized": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
