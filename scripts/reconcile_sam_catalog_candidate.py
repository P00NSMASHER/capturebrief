"""Reconcile a FROZEN unreviewed SAM.gov archival listing with pinned production.

Never fetches, approves, upgrades, imports sources, changes the FY2027
catalog, contacts a customer, or claims publisher-original bytes. A verified
filename listing != an independently reviewed and approved source collection.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from capturebrief_core.archive_catalog import (
    ARCHIVE_CATALOG_YEARS,
    ARCHIVE_CATALOG_FUTURE_LISTED_YEARS,
    ARCHIVE_CATALOG_CURRENT_THROUGH_FY,
    ARCHIVE_CATALOG_SOURCE_PAGE,
)
from capturebrief_core.model import canonical_json, sha256_hex

RECORDED_YEARS = (1969, 1970, 1980, 1981, *range(1998, 2028), 2029, 2030)
RECORDED_FILENAME = re.compile(r"^FY(\d{4})_archived_opportunities[.]csv$")
SOURCE_API = (
    "https://sam.gov/api/prod/fileextractservices/v1/api/listfiles"
    "?domain=Contract%20Opportunities%2FArchived%20Data&privacy=Public"
)
SOURCE_ORIGINAL_FY2027 = (
    "https://s3.amazonaws.com/falextracts/Contract%20Opportunities/"
    "Archived%20Data/FY2027_archived_opportunities.csv"
)


def reconcile_observation(observation: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(observation, dict):
        raise ValueError("Catalog observation must be a structured object")
    required = {
        "schema", "evidence_class", "production_authority", "independent_human_reviewed",
        "source_page", "source_listing_api", "started_at", "ended_at",
        "filenames", "object_probe",
    }
    if set(observation) != required:
        raise ValueError("Catalog observation is missing or contains unexpected fields")
    if (observation["schema"] != "capturebrief-sam-archives-observation-v1"
            or observation["evidence_class"] !=
            "UNREVIEWED_FIRST_PARTY_BROWSER_AND_API_OBSERVATION"
            or observation["production_authority"] is not False
            or observation["independent_human_reviewed"] is not False
            or observation["source_page"] != ARCHIVE_CATALOG_SOURCE_PAGE
            or observation["source_listing_api"] != SOURCE_API):
        raise ValueError("Catalog observation identity/approval boundary invalid")

    def utc(value: Any) -> datetime:
        if not isinstance(value, str) or not value.endswith("Z"):
            raise ValueError("Observation timestamp must be explicit UTC")
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.utcoffset() is None:
            raise ValueError("Observation timestamp has no timezone")
        return dt.astimezone(timezone.utc)

    beginning = utc(observation["started_at"])
    end = utc(observation["ended_at"])
    if (beginning.isoformat() != "2026-10-19T04:59:14+00:00"
            or end.isoformat() != "2026-10-19T05:00:36+00:00"):
        raise ValueError("Frozen October 19 source observation timestamps changed")
    files = observation["filenames"]
    if not isinstance(files, list) or not files:
        raise ValueError("Catalog filenames must be an ordered nonempty list")
    observed: list[int] = []
    for name in files:
        match = RECORDED_FILENAME.fullmatch(name) if isinstance(name, str) else None
        if not match:
            raise ValueError("Unexpected SAM archive filename")
        observed.append(int(match.group(1)))
    if observed != list(RECORDED_YEARS):
        raise ValueError("Frozen first-party inventory differs from original 36 listed years")

    probe = observation["object_probe"]
    fields = {
        "filename", "listed_storage_url", "public_listing", "http_status",
        "content_range", "read_bytes", "declared_file_bytes",
        "source_last_modified", "source_etag", "full_sha256",
        "whole_file_verified",
    }
    if not isinstance(probe, dict) or set(probe) != fields:
        raise ValueError("FY2027 source probe schema incorrect")
    if (
        probe["filename"] != "FY2027_archived_opportunities.csv"
        or probe["listed_storage_url"] != SOURCE_ORIGINAL_FY2027
        or probe["public_listing"] is not True
        or type(probe["http_status"]) is not int or probe["http_status"] != 206
        or probe["content_range"] != "bytes 0-0/1607260"
        or type(probe["read_bytes"]) is not int or probe["read_bytes"] != 1
        or type(probe["declared_file_bytes"]) is not int
        or probe["declared_file_bytes"] != 1607260
        or probe["source_last_modified"] != "2026-10-18T14:51:03Z"
        or probe["source_etag"] != "342a9a79f252ba732c347376f4efa66f"
        or probe["full_sha256"] is not None
        or probe["whole_file_verified"] is not False
    ):
        raise ValueError("FY2027 partial object probe cannot be upgraded to full-byte evidence")

    pinned = set(ARCHIVE_CATALOG_YEARS) | set(ARCHIVE_CATALOG_FUTURE_LISTED_YEARS)
    observed_set = set(observed)
    currently_required = {y for y in observed if y <= 2027}
    return {
        "schema": "capturebrief-sam-catalog-candidate-reconciliation-v1",
        "observation_sha256": sha256_hex(canonical_json(observation)),
        "observation_source": "PUBLIC_SAM_BROWSER_AND_OFFICIAL_LISTING_API",
        "observation_is_human_reviewed": False,
        "newly_listed_years": sorted(observed_set - pinned),
        "previously_listed_but_absent_years": sorted(pinned - observed_set),
        "proposed_required_through_fy2027": sorted(currently_required),
        "proposed_future_listed_years": sorted(observed_set - currently_required),
        "observed_total_years": len(observed),
        "FY2028_listed": 2028 in observed_set,
        "FY2027_object_partial_probe_bytes": 1,
        "FY2027_object_total_declared_bytes": probe["declared_file_bytes"],
        "FY2027_original_complete_sha256_verified": False,
        "production_current_through_fy": ARCHIVE_CATALOG_CURRENT_THROUGH_FY,
        "approved_to_update_catalog": False,
        "approved_for_full_catalog_claims": False,
        "independent_review_required": True,
        "no_source_files_downloaded_by_this_tool": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation", default=str(
        REPO / "research" / "sam_archives_observation_20261019.json"
    ))
    args = parser.parse_args(argv)
    try:
        path = Path(args.observation)
        if not path.is_file() or path.stat().st_size > 128 * 1024:
            raise ValueError("Missing or oversized catalog observation")
        obj = json.loads(path.read_text(encoding="utf-8"))
        result = reconcile_observation(obj)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "OBSERVATION_INVALID", "error": type(exc).__name__,
                          "approved_to_update_catalog": False}))
        return 2
    print(json.dumps({"status": "CATALOG_CANDIDATE_REVIEW_REQUIRED", **result},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
