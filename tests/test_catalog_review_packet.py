import copy
import json
import unittest
from pathlib import Path

from capturebrief_core.archive_catalog import catalog_snapshot, validate_catalog_snapshot
from scripts.validate_catalog_review_packet import validate

RESEARCH = Path(__file__).resolve().parents[1] / "research"


class CatalogReviewPacketTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads((RESEARCH / "sam_catalog_review_candidate_20261027.json").read_text())
        self.snapshot = (RESEARCH / "sam_archive_visible_inventory_20261027.txt").read_bytes()

    def test_current_observed_inventory_is_complete_but_not_production_catalog(self):
        before = catalog_snapshot()
        report = validate(self.packet, self.snapshot)
        self.assertEqual(report["visible_public_files"], 36)
        self.assertEqual(report["required_archive_slots"], 34)
        self.assertEqual(report["newly_listed_years"], [1969, 1981, 2027, 2029])
        self.assertEqual(report["future_listed_years"], [2029, 2030])
        self.assertFalse(report["FY2028_listed"])
        self.assertFalse(report["catalog_approved"])
        self.assertEqual(catalog_snapshot(), before)
        self.assertFalse(validate_catalog_snapshot(self.packet, fiscal_year=2027))

    def test_invented_year_dropped_year_review_claim_or_changed_source_is_rejected(self):
        changes = [
            {"filenames": self.packet["filenames"] + ["FY2028_archived_opportunities.csv"]},
            {"proposed_archive_years": self.packet["proposed_archive_years"][1:]},
            {"human_reviewed": True}, {"reviewer_identity": "simulated customer"},
            {"approved_to_update_catalog": True}, {"proposed_current_through_fy": 2028},
            {"source_page": "https://sam.gov.evil.example/catalog"},
            {"source_snapshot_sha256": "0"*64}, {"observed_at": "2026-10-28T14:14:00.860Z"},
        ]
        for change in changes:
            packet = copy.deepcopy(self.packet)
            packet.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate(packet, self.snapshot)
        with self.assertRaises(ValueError):
            validate(self.packet, self.snapshot + b"edited")


if __name__ == "__main__":
    unittest.main()
