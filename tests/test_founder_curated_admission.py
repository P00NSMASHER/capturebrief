"""Regression contract for the PermitPlate-style, inquiry-only pilot split."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from capturebrief_core.archive_catalog import ARCHIVE_CATALOG_CURRENT_THROUGH_FY
from capturebrief_core.delivery_readiness import evaluate_delivery_readiness
from capturebrief_core.intake import build_case_from_intake
from scripts.pilot_preflight import inspect

NOW = datetime(2026, 10, 27, 19, 0, tzinfo=timezone.utc)


class FounderCuratedFreeAdmissionTests(unittest.TestCase):
    def test_full_catalog_policy_stays_blocked_and_fy2027_unapproved(self):
        self.assertEqual(ARCHIVE_CATALOG_CURRENT_THROUGH_FY, 2026)
        actual = inspect(now=NOW, stage="admission", offer="free")
        self.assertEqual(actual["launch_mode"], "full_catalog")
        self.assertEqual(actual["status"], "PILOT_ADMISSION_BLOCKED")
        self.assertEqual(actual["gates"]["catalog"]["status"], "BLOCKED_STALE_CATALOG")
        self.assertEqual(actual["gates"]["source_index"]["status"], "BLOCKED_CATALOG_STALE")
        self.assertFalse(actual["technical_preflight_passed"])
        self.assertFalse(actual["approved_to_accept_payment_or_send_customer_material"])

    def test_founder_curated_is_inquiry_only_not_customer_admission(self):
        report = inspect(now=NOW, stage="admission", offer="free", launch_mode="founder_curated")
        self.assertEqual(report["launch_mode"], "founder_curated")
        self.assertEqual(report["status"], "FOUNDER_CURATED_INQUIRY_REVIEW_REQUIRED")
        self.assertTrue(report["inquiry_preparation_only"])
        self.assertFalse(report["technical_preflight_passed"])
        self.assertFalse(report["approved_to_accept_payment_or_send_customer_material"])
        self.assertEqual(report["gates"]["catalog"]["status"], "BLOCKED_STALE_CATALOG")
        self.assertEqual(report["gates"]["source_index"]["status"], "BLOCKED_CATALOG_STALE")
        self.assertEqual(report["full_catalog_diagnostic_gates"], ["catalog", "source_index"])
        self.assertNotIn("catalog", report["pre_pilot_gates"])
        self.assertNotIn("source_index", report["pre_pilot_gates"])
        self.assertIn("history_route", report["post_pilot_gates"])
        self.assertIn("current_action", report["post_pilot_gates"])
        self.assertIn("private_recovery", report["post_pilot_gates"])
        self.assertIn("release", report["post_pilot_gates"])
        self.assertIn("delivery", report["post_pilot_gates"])
        self.assertEqual(report["gates"]["payment"]["status"], "NO_PAYMENT_FOR_FREE_CHECK")
        self.assertEqual(report["gates"]["watch"]["status"], "NOT_INCLUDED_IN_FREE_CHECK")
        self.assertEqual(report["gates"]["history_route"]["status"], "CASE_SPECIFIC_FIRST_PARTY_REVIEW_REQUIRED")
        self.assertEqual(report["gates"]["current_action"]["status"], "CUSTOMER_SPECIFIC_API_OBSERVATION_REQUIRED")
        self.assertEqual(report["gates"]["private_recovery"]["status"], "ENCRYPTED_PRIVATE_RETENTION_REVIEW_REQUIRED")
        self.assertEqual(report["gates"]["intake"]["status"], "MANUAL_INBOX_RECONCILIATION_REQUIRED")
        self.assertEqual(report["gates"]["trial_identity"]["status"], "BUSINESS_ELIGIBILITY_REVIEW_REQUIRED")
        self.assertEqual(report["gates"]["operator"]["status"], "INDEPENDENT_REVIEW_AND_SEND_APPROVAL_REQUIRED")

    def test_first_customer_prelaunch_does_not_require_customer_or_customer_review(self):
        report = inspect(now=NOW, stage="admission", offer="free",
                         launch_mode="founder_curated")
        policy = report["first_customer_prelaunch_policy"]
        self.assertIs(policy["customer_required"], False)
        self.assertIs(policy["customer_feedback_required"], False)
        self.assertIs(policy["customer_report_or_customer_signoff_required"], False)
        self.assertIs(policy["real_customer_delivery_or_payment_proven"], False)
        self.assertTrue(policy["independent_internal_operator_qa_required"])
        self.assertTrue(policy["full_internal_report_review_and_explicit_send_approval_required_at_delivery"])
        self.assertTrue(policy["complete_official_history_required_per_future_case"])
        prelaunch = set(report["pre_pilot_gates"])
        per_case = set(report["post_pilot_gates"])
        self.assertEqual(prelaunch, {
            "production", "prelaunch_private_workspace",
            "prelaunch_offdevice_recovery", "prelaunch_internal_qa",
        })
        self.assertTrue({"intake", "trial_identity", "operator", "real_case",
                         "history_route", "current_action", "release", "delivery"} <= per_case)
        self.assertFalse(prelaunch.intersection(per_case))
        # A complete buyer deliverable is not invented merely because the
        # prelaunch scorecard no longer has circular customer conditions.
        self.assertFalse(report["approved_to_accept_payment_or_send_customer_material"])
        self.assertFalse(report["technical_preflight_passed"])

    def test_first_customer_policy_is_not_applied_to_paid_or_full_catalog(self):
        report = inspect(now=NOW, stage="admission", offer="free",
                         launch_mode="full_catalog")
        self.assertIsNone(report["first_customer_prelaunch_policy"])
        self.assertIn("catalog", report["pre_pilot_gates"])
        self.assertIn("source_index", report["pre_pilot_gates"])

    def test_fake_buyer_claim_cannot_become_approved_review(self):
        case = build_case_from_intake({
            "email": "buyer@example.com",
            "company": "Fictional IT Provider",
            "public_opportunity": "https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view",
            "current_posture": "HOLD",
            "assumption_1": "The response deadline has not moved.",
            "public_only_confirmation": "yes",
        }, submitted_at=NOW.isoformat())
        readiness = evaluate_delivery_readiness(case, now=NOW)
        self.assertFalse(readiness.eligible)
        self.assertIn("HISTORY_UNRESOLVED", readiness.blocker_codes)
        intake = inspect(now=NOW, stage="admission", offer="free",
                         launch_mode="founder_curated", case=case)
        self.assertFalse(intake["technical_preflight_passed"])
        self.assertFalse(intake["approved_to_accept_payment_or_send_customer_material"])
        self.assertEqual(intake["gates"]["release"]["status"], "POST_ADMISSION_DELIVERY_REVIEW")
        self.assertEqual(intake["gates"]["delivery"]["status"], "POST_ADMISSION_FREE_REPORT")
        self.assertEqual(case["packet"]["history_receipts"], [])
        self.assertEqual(case["current_action_receipts"], [])

    def test_founder_curated_rejects_paid_completion_and_invalid_modes(self):
        for stage, offer in [("completion", "free"), ("admission", "paid"), ("completion", "paid")]:
            with self.subTest(stage=stage, offer=offer), self.assertRaises(ValueError):
                inspect(now=NOW, stage=stage, offer=offer, launch_mode="founder_curated")
        with self.assertRaises(ValueError):
            inspect(now=NOW, stage="admission", offer="free", launch_mode="waived")

    def test_cli_never_returns_a_green_launch_exit(self):
        root = Path(__file__).resolve().parents[1]
        command = [sys.executable, "scripts/pilot_preflight.py", "--stage", "admission",
                   "--offer", "free", "--launch-mode", "founder_curated", "--as-of",
                   "2026-10-27T19:00:00Z"]
        run = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
        self.assertEqual(run.returncode, 2, run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual(result["status"], "FOUNDER_CURATED_INQUIRY_REVIEW_REQUIRED")
        self.assertFalse(result["technical_preflight_passed"])
        self.assertFalse(result["approved_to_accept_payment_or_send_customer_material"])


if __name__ == "__main__":
    unittest.main()
