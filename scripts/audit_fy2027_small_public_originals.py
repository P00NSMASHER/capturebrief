"""Memory-only public SAM archived-original semantics for FY1999-FY2001.

Only three exact frozen candidate year/size pairs may be read. No source,
notice, signed URL, token, customer record, or raw CSV bytes are persisted
or printed. 6,334,801 bytes is the total original-data download bound.
This is neither an approved 34-year catalog nor production source retention.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import io
import json
import sys
from pathlib import Path
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from capturebrief_core.data_services import ARCHIVE_DOWNLOAD, REQUIRED_COLUMNS
from capturebrief_core.source_policy import (
    open_approved_extract, require_approved_extract_delivery,
)

YEARS = (1999, 2000, 2001)
SIZES = {1999: 2157836, 2000: 1770534, 2001: 2406431}
MAX_BYTES = 6334801
METADATA = ROOT / "research" / "fy2027_archive_capacity_observation_20261020.json"


def _strict_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate frozen source metadata key")
        obj[key] = value
    return obj


def validate_frozen_sizes() -> None:
    """Require exact earlier in-memory publisher declared header observation."""
    if not METADATA.is_file() or METADATA.stat().st_size > 65536:
        raise ValueError("Frozen public size observation unavailable")
    obj = json.loads(METADATA.read_text(encoding="utf-8"),
                     object_pairs_hook=_strict_pairs)
    if (
        obj.get("schema") != "capturebrief-fy2027-unapproved-archive-capacity-snapshot-v1"
        or obj.get("source_actions_run") !=
            "https://github.com/P00NSMASHER/capturebrief/actions/runs/39350338311"
        or obj.get("candidate_archive_years") != 34
        or obj.get("independent_human_catalog_approval") is not False
        or obj.get("full_catalog_claim_authorized") is not False
        or obj.get("customer_release_authorized") is not False
    ):
        raise ValueError("Frozen original-byte metadata contract changed")
    sizes = obj.get("year_size_bytes")
    if not isinstance(sizes, dict) or len(sizes) != 34:
        raise ValueError("Not a complete frozen year-size observation")
    if any(sizes.get("FY"+str(y)) != SIZES[y] for y in YEARS):
        raise ValueError("One of three exact public original sizes changed")
    if sum(SIZES.values()) != MAX_BYTES:
        raise ValueError("Aggregate original-source hard bound changed")


def inspect_original_memory(original: bytes) -> dict:
    """Parse genuine or fictional CSV bytes; never output raw values."""
    if not isinstance(original, bytes) or not 0 < len(original) <= 3_000_000:
        raise ValueError("Memory-only source too large or missing")
    encoding = "utf-8-sig" if original.startswith(b"\xef\xbb\xbf") else "cp1252"
    text = original.decode(encoding, errors="strict")
    count = 0
    duplicates = 0
    blank_notice = 0
    blank_sol = 0
    blank_aac = 0
    blank_office = 0
    blank_aac_and_office = 0
    grouped_solicitations = collections.defaultdict(list)
    seen: set[str] = set()
    with io.StringIO(text, newline="") as stream:
        parser = csv.DictReader(stream, restkey="_extra", strict=True)
        cols = list(parser.fieldnames or [])
        if (not REQUIRED_COLUMNS.issubset(set(cols))
                or len(cols) != len(set(cols))):
            raise ValueError("Original CSV headers incomplete or duplicated")
        for row in parser:
            count += 1
            if "_extra" in row or any(value is None for value in row.values()):
                raise ValueError("Malformed original source CSV row shape")
            notice = str(row.get("NoticeId") or "").strip()
            if not notice:
                blank_notice += 1
            elif notice in seen:
                duplicates += 1
            else:
                seen.add(notice)
            sol = " ".join(str(row.get("Sol#") or "").upper().split())
            aac = " ".join(str(row.get("AAC Code") or "").upper().split())
            office = " ".join(str(row.get("Office") or "").upper().split())
            if not sol:
                blank_sol += 1
            if not aac:
                blank_aac += 1
            if not office:
                blank_office += 1
            if not aac and not office:
                blank_aac_and_office += 1
            if sol:
                grouped_solicitations[sol].append((aac, office))
    repeated = [v for v in grouped_solicitations.values() if len(v) > 1]
    repeated_with_missing_anchors = sum(
        any(not aac or not office for aac, office in items)
        for items in repeated
    )
    repeated_with_multiple_aacs = sum(
        len({aac for aac, _ in items if aac}) > 1
        for items in repeated
    )
    repeated_with_same_aac_office_collisions = 0
    for items in repeated:
        by_aac = collections.defaultdict(set)
        for aac, office in items:
            if aac and office:
                by_aac[aac].add(office)
        if any(len(offices) > 1 for offices in by_aac.values()):
            repeated_with_same_aac_office_collisions += 1
    return {
        "rows": count, "header_columns": len(cols),
        "required_headers_present": True,
        "duplicate_notice_id_rows": duplicates,
        "blank_notice_id_rows": blank_notice,
        "blank_solicitation_rows": blank_sol,
        "blank_aac_rows": blank_aac,
        "blank_office_rows": blank_office,
        "blank_aac_and_office_rows": blank_aac_and_office,
        "repeated_nonblank_solicitation_groups": len(repeated),
        "repeated_groups_with_missing_agency_or_office": repeated_with_missing_anchors,
        "repeated_groups_with_multiple_known_aacs": repeated_with_multiple_aacs,
        "repeated_groups_with_multiple_offices_inside_known_aac": (
            repeated_with_same_aac_office_collisions
        ),
    }


def observe_public_original(year: int, *, opener=None, size_override=None) -> dict:
    if type(year) is not int or year not in YEARS:
        raise ValueError("Only the three bounded historic years are permitted")
    if size_override is not None and opener is None:
        raise ValueError("Source-size overrides require injected fake transport")
    expected = SIZES[year] if size_override is None else size_override
    if type(expected) is not int or not 0 < expected <= 3_000_000:
        raise ValueError("Original-year byte size exceeds the bound")
    url = ARCHIVE_DOWNLOAD.format(fy=year)
    req = Request(url, headers={
        "User-Agent": "CaptureBrief/0.3",
        "Accept-Encoding": "identity",
    })
    response = open_approved_extract(
        req, timeout=30, source_url=url, opener=opener,
    )
    with response:
        target = response.geturl() if hasattr(response, "geturl") else url
        host = require_approved_extract_delivery(url, target)
        status = getattr(response, "status", None)
        if status is None and hasattr(response, "getcode"):
            status = response.getcode()
        if status != 200:
            raise ValueError("Original-data response did not return HTTP 200")
        headers = getattr(response, "headers", None)
        if headers is None:
            raise ValueError("Missing source identity headers")
        length = headers.get("Content-Length")
        if length is not None and str(length).strip() != str(expected):
            raise ValueError("Source data length differs from frozen original")
        if str(headers.get("Content-Encoding", "identity")).strip().lower() != "identity":
            raise ValueError("Unexpected transfer encoding")
        data = response.read(expected + 1)
        if not isinstance(data, bytes) or len(data) != expected:
            raise ValueError("Original truncated or exceeds public size bound")
    metadata = inspect_original_memory(data)
    return {
        "fiscal_year": year, "original_bytes": expected,
        "original_sha256": hashlib.sha256(data).hexdigest(),
        "trusted_delivery_host": host,
        "status": "PUBLIC_ORIGINAL_SEMANTICS_UNAPPROVED",
        **metadata,
        "original_bytes_persisted": False,
        "publisher_review_approved": False,
        "customer_release_authorized": False,
    }


def observe_all(*, opener=None, fake_sizes=None) -> dict:
    validate_frozen_sizes()
    if fake_sizes is not None and opener is None:
        raise ValueError("Synthetic sizes must not reach live network")
    if fake_sizes is not None and set(fake_sizes) != set(YEARS):
        raise ValueError("Fake sizes must name only approved bounded years")
    report = []
    for year in YEARS:
        report.append(observe_public_original(
            year, opener=opener,
            size_override=(fake_sizes[year] if fake_sizes is not None else None),
        ))
    return {
        "schema": "capturebrief-public-small-original-semantics-v1",
        "status": "THREE_PUBLIC_ORIGINALS_BOUNDED_UNAPPROVED",
        "years": list(YEARS),
        "source_metadata_declared_bytes": MAX_BYTES,
        "source_bytes_observed": sum(x["original_bytes"] for x in report),
        "observations": report,
        "full_archive_originals_retained": False,
        "source_catalog_approved": False,
        "source_bytes_written_to_disk": False,
        "offdevice_backup_verified": False,
        "customer_release_authorized": False,
    }


def main() -> int:
    try:
        report = observe_all()
    except Exception as exc:
        # Provider HTTP failures can include signed credentials in the text.
        print(json.dumps({
            "status": "EARLY_PUBLIC_ORIGINAL_SEMANTICS_BLOCKED",
            "error_type": type(exc).__name__,
            "source_catalog_approved": False,
            "customer_release_authorized": False,
        },sort_keys=True))
        return 2
    print(json.dumps(report,sort_keys=True,indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
