"""PermitPlate-style, REAL public-source cross-readback for one SAM.gov pursuit.

Two independent official data surfaces are consulted: complete bounded SAM
Data Services ACTIVE/FY2027 original CSVs and a fresh authenticated public
Opportunities v2 latest-active API. All source bytes are verified, parsed and
compared with the exact notice and solicitation family.

This deliberately cannot certify complete historical versions, deleted
attachments, incorporated-rule applicability, reviewer signoff, paid delivery
or a customer. Those facts need separate first-party human-reviewed evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capturebrief_core.data_services import (
    ACTIVE_DOWNLOAD, ARCHIVE_DOWNLOAD, _family_filter, scan_extract_bytes,
)
from capturebrief_core.model import parse_dt
from scripts.verify_sam_current_access import (
    SOLICITATION, run_probe,
)

VERSION = "capturebrief-real-federal-case-crossreadback-v1"
SEED = "0d961fc227d34d4da9a895f941e48a1e"
ARCHIVE_YEAR = 2027
ACTIVE_BOUND = 320 * 1024 * 1024
ARCHIVE_BOUND = 15 * 1024 * 1024


class RealSourceBlocked(ValueError):
    """The official-source cross-check is unavailable or contradicted."""


def _read_source(path: str | Path, *, bound: int) -> bytes:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise RealSourceBlocked("A complete regular source original is required")
    size = source.stat().st_size
    if not 0 < size <= bound:
        raise RealSourceBlocked("Source byte count is missing or outside the bound")
    with source.open("rb") as handle:
        data = handle.read(bound + 1)
    if len(data) != size:
        raise RealSourceBlocked("Source original changed during read")
    return data


def _clock(value: datetime | None) -> datetime:
    now = value or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise RealSourceBlocked("Source crosscheck requires a real UTC clock")
    return now.astimezone(timezone.utc)


def _official_notice_link(value: str | None, notice_id: str) -> bool:
    if not isinstance(value, str) or not isinstance(notice_id, str):
        return False
    try:
        u = urlsplit(value)
        return (u.scheme == "https" and u.hostname == "sam.gov"
                and u.port in (None, 443)
                and not u.username and not u.password and not u.query
                and not u.fragment
                and u.path in (
                    f"/opp/{notice_id}/view",
                    f"/workspace/contract/opp/{notice_id}/view",
                ))
    except ValueError:
        return False


def evaluate_public_case(
    *,
    active_bytes: bytes,
    archive_bytes: bytes,
    probe: dict[str, Any],
    checked_at: datetime | None = None,
) -> dict[str, Any]:
    """Check official-source consistency without silently upgrading history."""
    now = _clock(checked_at)
    if not isinstance(probe, dict):
        raise RealSourceBlocked("Independent official current API probe missing")
    if (probe.get("status") != "PUBLIC_API_OBSERVATION_VERIFIED"
            or probe.get("api_access_verified") is not True
            or probe.get("latest_active_observation_verified") is not True
            or probe.get("api_key_present_in_runtime") is not True
            or probe.get("public_probe_solicitation") != SOLICITATION
            or probe.get("source_endpoint") != "https://api.sam.gov/opportunities/v2/search"
            or probe.get("full_history_verified") is not False
            or probe.get("customer_delivery_verified") is not False
            or probe.get("external_send_authorized") is not False):
        raise RealSourceBlocked("Fresh authenticated current API evidence is unavailable")
    api_at = parse_dt(probe.get("observed_at"))
    if not api_at or api_at > now or (now-api_at).total_seconds() > 300:
        raise RealSourceBlocked("API current observation is stale or future-dated")
    pages = probe.get("pagination")
    if (not isinstance(pages, dict) or pages.get("complete") is not True
            or pages.get("total_records") != 1
            or pages.get("returned_records") != 1
            or not isinstance(pages.get("offset"), int)
            or pages.get("offset") != 0):
        raise RealSourceBlocked("API current readback was ambiguous or incomplete")
    if probe.get("notice_id_sha256") != hashlib.sha256(SEED.encode()).hexdigest():
        raise RealSourceBlocked("API notice differs from source benchmark's exact seed")
    if (not isinstance(active_bytes, bytes) or not isinstance(archive_bytes, bytes)
            or not 0 < len(active_bytes) <= ACTIVE_BOUND
            or not 0 < len(archive_bytes) <= ARCHIVE_BOUND):
        raise RealSourceBlocked("Complete bounded first-party original bytes required")
    snapshots = [
        scan_extract_bytes(
            active_bytes, source_url=ACTIVE_DOWNLOAD, source_kind="ACTIVE",
            solicitation_number=SOLICITATION,
        ),
        scan_extract_bytes(
            archive_bytes, source_url=ARCHIVE_DOWNLOAD.format(fy=ARCHIVE_YEAR),
            source_kind="ARCHIVE", fiscal_year=ARCHIVE_YEAR,
            solicitation_number=SOLICITATION,
        ),
    ]
    if not all(s["rows_scanned"] > 0 and s["extract_sha256"] for s in snapshots):
        raise RealSourceBlocked("The two official original extracts were empty")
    active_rows = [r for r in snapshots[0]["matches"] if r["notice_id"].lower() == SEED]
    if len(active_rows) != 1 or str(active_rows[0].get("active", "")).strip().lower() != "yes":
        raise RealSourceBlocked("Original ACTIVE extract lacks exact active seed")
    if any(not _official_notice_link(r.get("link"), SEED) for r in active_rows):
        raise RealSourceBlocked("Source extract URL does not match exact official seed notice")
    family_rows, family = _family_filter(snapshots, seed_notice_id=SEED)
    if (not family_rows or not family.get("aac_code")
            or not family.get("office") or not family.get("solicitation_number")):
        raise RealSourceBlocked("Source-family identity cannot be independently anchored")
    expected_ids = sorted({str(r["notice_id"]).lower() for r in family_rows})
    if SEED not in expected_ids:
        raise RealSourceBlocked("Cross-source family dropped the buyer notice")
    # A shared solicitation number is not a family key by itself. Report
    # inconsistent AAgency/office as ambiguous, never filter the conflict.
    matched = [row for snap in snapshots for row in snap["matches"]]
    if any(str(row.get("aac_code") or "").strip().upper() != family["aac_code"]
           or str(row.get("office") or "").strip().upper() != family["office"]
           for row in matched):
        raise RealSourceBlocked("Same solicitation has conflicting publisher agencies/offices")
    if any(not _official_notice_link(row.get("link"), row["notice_id"])
           for row in family_rows):
        raise RealSourceBlocked("Unapproved or mismatched public notice URL")

    # This is a strict source *membership* check. Even a single observed
    # action does not prove there were no earlier/deleted amendments.
    return {
        "schema": VERSION,
        "status": "OFFICIAL_DATA_SERVICES_AND_ACTIVE_API_CORRELATED_HISTORY_REVIEW_REQUIRED",
        "observed_at": now.isoformat(),
        "public_solicitation_number": SOLICITATION,
        "notice_sha256": hashlib.sha256(SEED.encode()).hexdigest(),
        "source_slot_count": len(snapshots),
        "extracts": [
            {
                "slot": "ACTIVE" if i == 0 else f"ARCHIVE:{ARCHIVE_YEAR}",
                "sha256": s["extract_sha256"],
                "bytes": len((active_bytes, archive_bytes)[i]),
                "rows_replayed": s["rows_scanned"],
                "matching_solicitation_rows": len(s["matches"]),
            } for i,s in enumerate(snapshots)
        ],
        "candidate_action_count": len(expected_ids),
        "candidate_action_set_sha256": hashlib.sha256(
            "\n".join(expected_ids).encode("ascii")
        ).hexdigest(),
        "seed_in_official_active_original": True,
        "independent_current_api_correlated": True,
        "family_agency_and_office_consistent": True,
        "current_resource_links_count": probe.get("resource_link_count"),
        "full_historical_action_set_verified": False,
        "history_cancellations_and_deletions_verified": False,
        "full_attachment_manifest_verified": False,
        "incorporated_rules_applicability_verified": False,
        "independent_human_source_review_complete": False,
        "operator_private_storage_approved": False,
        "production_offdevice_recovery_verified": False,
        "real_customer_required_for_prelaunch_benchmark": False,
        "paid_checkout_enabled": False,
        "customer_release_authorized": False,
        "external_send_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active-original", type=Path, required=True)
    parser.add_argument("--fy2027-original", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        # Key is kept in the environment by an exact-current-main-only
        # Actions job. It is never accepted as a CLI value, printed or saved.
        result, code = run_probe(os.environ.get("SAM_API_KEY", ""))
        if code != 0:
            raise RealSourceBlocked("Official API verification is not currently available")
        output = evaluate_public_case(
            active_bytes=_read_source(args.active_original, bound=ACTIVE_BOUND),
            archive_bytes=_read_source(args.fy2027_original, bound=ARCHIVE_BOUND),
            probe=result, checked_at=datetime.now(timezone.utc),
        )
    except Exception:
        # Network errors may contain a signed GSA delivery URL or an API key.
        # Never print source exception text or a raw document.
        print(json.dumps({
            "schema": VERSION, "status": "OFFICIAL_CASE_SOURCE_CROSSREADBACK_BLOCKED",
            "history_complete": False, "customer_release_authorized": False,
            "external_send_authorized": False,
        }, sort_keys=True))
        return 2
    target = args.out.expanduser().absolute()
    if target.exists() or target.is_symlink() or not target.parent.is_dir():
        raise SystemExit("Crossreadback receipt needs a fresh existing private runner output path")
    from capturebrief_core.atomic_io import atomic_write_text
    atomic_write_text(target, json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": output["status"], "source_slot_count": output["source_slot_count"],
        "candidate_action_count": output["candidate_action_count"],
        "full_historical_action_set_verified": False,
        "customer_release_authorized": False, "external_send_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
