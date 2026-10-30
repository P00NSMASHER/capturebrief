"""Validate the frozen Oct27 rendered inventory and its INACTIVE catalog proposal.

No network, catalog update or approval. Reviewer identity remains absent until
a real independently supervised observation/review occurs; this artifact never
substitutes simulated customer feedback for source-catalog signoff.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from capturebrief_core.archive_catalog import catalog_snapshot

SNAPSHOT_SHA256 = "428724d4b0cfecc448994c4caa9eac4e03b73b41087b59004cb37b92a3c320b0"
SNAPSHOT_BYTES = 15140
OBSERVED_AT = "2026-10-27T14:14:00.860Z"


def validate(packet, snapshot):
    if (not isinstance(packet, dict)
            or packet.get("schema") != "capturebrief-rendered-catalog-review-candidate-v1"
            or packet.get("observation_class") != "AUTOMATED_RENDERED_ACCESSIBILITY_SNAPSHOT_UNREVIEWED"
            or packet.get("source_page") != catalog_snapshot()["source_url"]
            or packet.get("observed_at") != OBSERVED_AT
            or packet.get("source_snapshot_file") != "sam_archive_visible_inventory_20261027.txt"
            or packet.get("source_snapshot_sha256") != SNAPSHOT_SHA256
            or packet.get("source_snapshot_bytes") != SNAPSHOT_BYTES
            or len(snapshot) != SNAPSHOT_BYTES or hashlib.sha256(snapshot).hexdigest() != SNAPSHOT_SHA256):
        raise ValueError("Candidate does not match the retained first-party rendered observation")
    for field in ("human_reviewed", "production_authority", "approved_to_update_catalog",
                  "full_catalog_coverage_proven", "customer_release_authorized"):
        if packet.get(field) is not False:
            raise ValueError("Automated rendered observation cannot supply human or production approval")
    if packet.get("reviewer_identity") is not None or packet.get("review_reference") is not None:
        raise ValueError("No reviewer signoff exists for this frozen automated observation")
    names = re.findall(r"(FY\d{4}_archived_opportunities[.]csv) Item under Archived DataPublic", snapshot.decode())
    years = sorted(int(name[2:6]) for name in names)
    if (len(names) != 36 or len(set(names)) != 36 or packet.get("filenames") != names
            or packet.get("proposed_archive_years") != [y for y in years if y <= 2027]
            or packet.get("proposed_future_listed_years") != [y for y in years if y > 2027]
            or packet.get("proposed_current_through_fy") != 2027):
        raise ValueError("Candidate inventory differs from the exact rendered listing")
    current = catalog_snapshot()
    existing = set(current["archive_years"]) | set(current["future_listed_years"])
    return {"status": "EXACT_RENDERED_CATALOG_CANDIDATE_REVIEW_REQUIRED",
            "observed_at": OBSERVED_AT, "source_snapshot_sha256": SNAPSHOT_SHA256,
            "visible_public_files": len(names), "required_archive_slots": len(packet["proposed_archive_years"]),
            "newly_listed_years": sorted(set(years) - existing),
            "previously_listed_now_absent": sorted(existing - set(years)),
            "future_listed_years": packet["proposed_future_listed_years"], "FY2028_listed": 2028 in years,
            "production_current_through_fy": current["current_through_fy"],
            "production_catalog_sha256": current["catalog_sha256"],
            "catalog_approved": False, "independent_human_review_required": True,
            "full_source_index_verified": False, "customer_release_authorized": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    root = ROOT / "research"
    packet = json.loads((root / "sam_catalog_review_candidate_20261027.json").read_text())
    result = validate(packet, (root / packet["source_snapshot_file"]).read_bytes())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
