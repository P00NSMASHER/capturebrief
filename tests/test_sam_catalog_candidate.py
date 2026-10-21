"""Frozen official SAM listing observation QA; never authorizes FY2027 sources."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.reconcile_sam_catalog_candidate import REPO, reconcile_observation


def observed():
    return json.loads((REPO / "research" / "sam_archives_observation_20261019.json")
                      .read_text(encoding="utf-8"))


class SamCatalogCandidateTests(unittest.TestCase):
    def test_complete_36_year_inventory_is_unreviewed_and_fy2027_still_blocked(self):
        data = reconcile_observation(observed())
        self.assertEqual(data["observed_total_years"], 36)
        self.assertEqual(data["newly_listed_years"], [1969, 1981, 2027, 2029])
        self.assertEqual(data["previously_listed_but_absent_years"], [])
        self.assertEqual(data["proposed_future_listed_years"], [2029, 2030])
        self.assertIn(1969, data["proposed_required_through_fy2027"])
        self.assertIn(1981, data["proposed_required_through_fy2027"])
        self.assertIn(2027, data["proposed_required_through_fy2027"])
        self.assertNotIn(2028, data["proposed_required_through_fy2027"])
        self.assertEqual(len(data["proposed_required_through_fy2027"]), 34)
        self.assertFalse(data["FY2028_listed"])
        self.assertEqual(data["FY2027_object_partial_probe_bytes"], 1)
        self.assertEqual(data["FY2027_object_total_declared_bytes"], 1607260)
        self.assertFalse(data["FY2027_original_complete_sha256_verified"])
        self.assertEqual(data["production_current_through_fy"], 2026)
        self.assertFalse(data["approved_for_full_catalog_claims"])
        self.assertFalse(data["approved_to_update_catalog"])
        self.assertTrue(data["independent_review_required"])
        self.assertRegex(data["observation_sha256"], r"^[0-9a-f]{64}$")

    def test_later_full_byte_observation_is_not_operator_retention_or_approval(self):
        proof = json.loads((REPO / "research" /
            "fy2027_original_bytes_observation_20261019.json").read_text())
        self.assertEqual(proof["schema"], "capturebrief-sam-public-file-byte-observation-v1")
        self.assertEqual(proof["github_actions_run"],
                         "https://github.com/P00NSMASHER/capturebrief/actions/runs/39205786451")
        self.assertEqual(proof["size_bytes"], 1607260)
        self.assertEqual(proof["csv_data_rows"], 1104)
        self.assertEqual(proof["sha256"],
                         "7b4e00e3156248db9dcca767431bb6c5d4168aeeb2abc707ab12c0f9e61d71ce")
        self.assertRegex(proof["sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(proof["full_bytes_were_read"])
        self.assertFalse(proof["original_bytes_durably_retained"])
        self.assertFalse(proof["operator_approved_extract_index_updated"])
        self.assertFalse(proof["human_catalog_reviewed"])
        self.assertFalse(proof["approved_for_full_catalog_claim"])
        self.assertFalse(proof["customer_release_authorized"])
        self.assertEqual(proof["current_catalog_approved_through_fy"], 2026)

    def test_false_human_review_or_approved_flag_is_rejected(self):
        for change in (
            {"production_authority": True},
            {"independent_human_reviewed": True},
            {"evidence_class": "HUMAN_REVIEWED"},
            {"schema": "capturebrief-official-sam-catalog-v2"},
        ):
            item = observed()
            item.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                reconcile_observation(item)

    def test_inventory_cannot_invent_missing_fy2028_or_drop_early_years(self):
        for change in ("append_2028", "drop_1981", "duplicate_2027", "reorder", "rename"):
            item = observed()
            if change == "append_2028":
                item["filenames"].append("FY2028_archived_opportunities.csv")
            elif change == "drop_1981":
                item["filenames"].remove("FY1981_archived_opportunities.csv")
            elif change == "duplicate_2027":
                item["filenames"].append("FY2027_archived_opportunities.csv")
            elif change == "reorder":
                item["filenames"].reverse()
            else:
                item["filenames"][0] = "../../FY1969_archived_opportunities.csv"
            with self.subTest(change=change), self.assertRaises(ValueError):
                reconcile_observation(item)

    def test_partial_read_cannot_be_promoted_to_verified_csv(self):
        for change in ("full_sha256", "whole_file_verified", "http_status",
                       "read_bytes", "content_range", "listed_storage_url"):
            item = observed()
            if change == "full_sha256":
                item["object_probe"][change] = "0"*64
            elif change == "whole_file_verified":
                item["object_probe"][change] = True
            elif change == "http_status":
                item["object_probe"][change] = 200
            elif change == "read_bytes":
                item["object_probe"][change] = 1607260
            elif change == "content_range":
                item["object_probe"][change] = "bytes 0-1607259/1607260"
            else:
                item["object_probe"][change] = "https://untrusted.example/fy2027"
            with self.subTest(change=change), self.assertRaises(ValueError):
                reconcile_observation(item)

    def test_changed_observation_time_or_spoofed_listing_origin_is_rejected(self):
        for field, value in (
            ("started_at", "2026-10-20T04:59:14Z"),
            ("ended_at", "2026-10-19T04:59:00Z"),
            ("source_page", "https://sam.gov.evil.example/listing"),
            ("source_listing_api", "https://evil.example/api"),
        ):
            item = observed()
            item[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                reconcile_observation(item)

    def test_cli_emits_evidence_candidate_not_acceptance_or_production_change(self):
        proc = subprocess.run(
            [sys.executable, "scripts/reconcile_sam_catalog_candidate.py"],
            cwd=REPO, text=True, capture_output=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["status"], "CATALOG_CANDIDATE_REVIEW_REQUIRED")
        self.assertFalse(report["approved_to_update_catalog"])
        self.assertEqual(report["production_current_through_fy"], 2026)
        self.assertTrue(report["no_source_files_downloaded_by_this_tool"])


if __name__ == "__main__":
    unittest.main()
