"""Pilot release must fail closed on missing real evidence and unsigned claims."""
import json
import subprocess
import tempfile
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from capturebrief_core.intake import build_case_from_intake
from scripts.pilot_preflight import inspect, official_opportunity
from tests.test_source_coverage_audit import make_index

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
OFFICIAL = "https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view"


class PilotPreflightTests(unittest.TestCase):
    def test_only_genuine_first_party_notice_urls_pass_structural_check(self):
        self.assertTrue(official_opportunity(OFFICIAL))
        for value in (
            "http://sam.gov/opp/3127a3862fe74c0b8bf614948e89f66f/view",
            "https://sam.gov.evil.example/opp/3127a3862fe74c0b8bf614948e89f66f/view",
            "https://buyer:s3cret@sam.gov/opp/3127a3862fe74c0b8bf614948e89f66f/view",
            "https://sam.gov/opp/example/view",
            "https://sam.gov/private/buyer-brief",
            "https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view#forged",
            "https://sam.gov:444/opp/c20a138049b94add92f0f32a41856585/view",
            "https://sam.gov:badport/opp/c20a138049b94add92f0f32a41856585/view",
            "https://sam.gov/opp/c20a138049b94add92f0f32a41856585/view?api_key=SECRET",
            None,
        ):
            with self.subTest(value=value):
                self.assertFalse(official_opportunity(value))

    def test_october_fiscal_rollover_blocks_unsupported_source_catalog(self):
        out = inspect(now=NOW)
        self.assertEqual(out["fiscal_year"], 2027)
        self.assertEqual(out["gates"]["catalog"]["status"], "BLOCKED_STALE_CATALOG")
        self.assertEqual(out["status"], "PILOT_BLOCKED")
        self.assertFalse(out["technical_preflight_passed"])
        self.assertIs(out["approved_to_accept_payment_or_send_customer_material"], False)

    def test_real_public_notice_only_opens_review_not_customer_release(self):
        # This is an observed public federal IT/enterprise-services notice; buyer details are fictional.
        # A true public URL by itself supplies no verified controlling sources.
        intake = {
            "email": "buyer@example.com",
            "company": "Fictional Federal Corp",
            "public_opportunity": OFFICIAL,
            "current_posture": "HOLD",
            "assumption_1": "The proposal deadline is still May 1, 2026.",
            "assumption_2": "The original FY2026 posting has no later amendments.",
            "public_only_confirmation": "yes",
        }
        case = build_case_from_intake(intake, submitted_at=NOW.isoformat())
        out = inspect(now=NOW, case=case)
        self.assertEqual(out["gates"]["real_case"]["status"], "BLOCKED_INTAKE_NOTICE_NOT_IN_HISTORY")
        self.assertEqual(out["gates"]["release"]["status"], "BLOCKED_BY_CORE_EVIDENCE")
        self.assertEqual(out["gates"]["delivery"]["status"], "BLOCKED_UNVERIFIED_BUNDLE")
        self.assertEqual(out["gates"]["watch"]["status"], "BLOCKED_NO_FRESH_WATCH_REPLAY")
        self.assertIs(out["approved_to_accept_payment_or_send_customer_material"], False)
        self.assertEqual(case["packet"]["history_receipts"], [])
        self.assertEqual(case["current_action_receipts"], [])
        self.assertTrue(all(x["evidence_state"] == "UNPROVEN" for x in case["assumptions"]))

    def test_buyer_notice_must_match_claimed_history_even_if_sam_shaped(self):
        intake = {
            "email": "buyer@example.com",
            "company": "Fictional Federal Corp",
            "public_opportunity": OFFICIAL,
            "current_posture": "HOLD",
            "assumption_1": "The original deadline still applies.",
            "public_only_confirmation": "yes",
        }
        case = build_case_from_intake(intake, submitted_at=NOW.isoformat())
        case["packet"]["history_action_ids"] = ["f" * 32]
        mismatched = inspect(now=NOW, case=case)
        self.assertEqual(mismatched["gates"]["real_case"]["status"],
                         "BLOCKED_INTAKE_NOTICE_NOT_IN_HISTORY")
        self.assertFalse(mismatched["technical_preflight_passed"])

        # A caller can insert a matching ID in an unverified history list.
        # This removes only the *identity* failure, NEVER source/release proof.
        case["packet"]["history_action_ids"] = [OFFICIAL.split("/")[4]]
        linked = inspect(now=NOW, case=case)
        self.assertEqual(linked["gates"]["real_case"]["status"],
                         "PUBLIC_NOTICE_BOUND_TO_HISTORY")
        self.assertEqual(linked["gates"]["release"]["status"], "BLOCKED_BY_CORE_EVIDENCE")
        self.assertFalse(linked["approved_to_accept_payment_or_send_customer_material"])

    def test_unverified_digest_and_fake_payment_cannot_flip_readiness(self):
        intake = {
            "email": "buyer@example.com",
            "company": "Fictional Federal Corp",
            "public_opportunity": OFFICIAL,
            "current_posture": "UNSURE",
            "assumption_1": "Award is guaranteed.",
            "public_only_confirmation": "yes",
        }
        case = build_case_from_intake(intake, submitted_at=NOW.isoformat())
        case["intake"]["purchase_status"] = "PAID"  # buyer claim, not processor evidence
        out = inspect(now=NOW, case=case, bundle_path="does-not-exist.zip",
                      receipt={"bundle_sha256": "0" * 64, "case_sha256": "1" * 64})
        self.assertEqual(out["gates"]["delivery"]["status"], "BLOCKED_BUNDLE_INTEGRITY")
        self.assertEqual(out["gates"]["payment"]["status"], "STRIPE_LIVE_RECORD_VERIFICATION_REQUIRED")
        self.assertFalse(out["technical_preflight_passed"])

    def test_pre_pilot_admission_does_not_require_future_delivery_or_watch(self):
        # This frozen September historical clock exercises lifecycle separation,
        # not a declaration that the October FY2027 catalog is approved.
        pre_rollover = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
        out = inspect(now=pre_rollover, stage="admission")
        self.assertEqual(out["stage"], "admission")
        self.assertEqual(out["status"], "PILOT_ADMISSION_BLOCKED")
        self.assertEqual(out["gates"]["source_index"]["status"], "BLOCKED_NO_PRIVATE_INDEX")
        self.assertEqual(out["gates"]["real_case"]["status"], "POST_ADMISSION_CUSTOMER_EVIDENCE")
        self.assertEqual(out["gates"]["release"]["status"], "POST_ADMISSION_DELIVERY_REVIEW")
        self.assertEqual(out["gates"]["delivery"]["status"], "POST_ADMISSION_CUSTOMER_BUNDLE")
        self.assertEqual(out["gates"]["watch"]["status"], "POST_ADMISSION_WATCH_OBSERVATION")
        self.assertFalse(out["technical_preflight_passed"])
        self.assertIs(out["approved_to_accept_payment_or_send_customer_material"], False)
        self.assertEqual(set(out["pre_pilot_gates"]),
                         {"catalog", "source_index", "intake", "payment", "operator", "production"})

    def test_current_admission_blocks_stale_fy2027_without_circular_customer_requirements(self):
        out = inspect(now=NOW, stage="admission")
        self.assertEqual(out["status"], "PILOT_ADMISSION_BLOCKED")
        self.assertEqual(out["gates"]["catalog"]["status"], "BLOCKED_STALE_CATALOG")
        self.assertEqual(out["gates"]["source_index"]["status"], "BLOCKED_CATALOG_STALE")
        self.assertEqual(out["gates"]["delivery"]["status"], "POST_ADMISSION_CUSTOMER_BUNDLE")
        self.assertFalse(out["technical_preflight_passed"])
        self.assertFalse(out["approved_to_accept_payment_or_send_customer_material"])

    def test_private_full_index_local_hashes_allow_only_review_not_launch(self):
        # The indexed bytes below are synthetic. Local hash consistency is not
        # authentic publisher proof or an authorization to take payment.
        historical = datetime(2026, 9, 21, 15, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            index, _ = make_index(Path(td))
            out = inspect(
                now=historical, stage="admission",
                history_index=str(index), verify_source_bytes=True,
            )
            self.assertEqual(out["status"], "PILOT_ADMISSION_REVIEW_REQUIRED")
            self.assertEqual(out["gates"]["source_index"]["status"],
                             "INDEX_LOCAL_HASHES_MATCH")
            self.assertTrue(out["gates"]["source_index"]["coverage"]["file_hashes_checked"])
            self.assertFalse(out["gates"]["source_index"]["coverage"][
                "publisher_authenticity_independently_established"])
            self.assertFalse(out["technical_preflight_passed"])
            self.assertFalse(out["approved_to_accept_payment_or_send_customer_material"])

    def test_fresh_index_metadata_alone_cannot_pass_admission(self):
        historical = datetime(2026, 9, 21, 15, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            index, _ = make_index(Path(td))
            out = inspect(now=historical, stage="admission", history_index=str(index))
            self.assertEqual(out["status"], "PILOT_ADMISSION_BLOCKED")
            self.assertEqual(out["gates"]["source_index"]["status"],
                             "BLOCKED_INDEX_BYTES_UNCHECKED")

    def test_unreadable_index_fails_closed_without_creating_file(self):
        historical = datetime(2026, 9, 21, 15, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "never-created.sqlite"
            out = inspect(now=historical, stage="admission", history_index=str(path),
                          verify_source_bytes=True)
            self.assertEqual(out["status"], "PILOT_ADMISSION_BLOCKED")
            self.assertEqual(out["gates"]["source_index"]["status"],
                             "BLOCKED_UNREADABLE_INDEX")
            self.assertFalse(path.exists())

    def test_FY2027_stays_blocked_even_with_fully_hashed_old_index(self):
        with tempfile.TemporaryDirectory() as td:
            index, _ = make_index(Path(td))
            out = inspect(now=NOW, stage="admission", history_index=str(index),
                          verify_source_bytes=True)
            self.assertEqual(out["gates"]["source_index"]["status"],
                             "BLOCKED_CATALOG_STALE")
            self.assertEqual(out["status"], "PILOT_ADMISSION_BLOCKED")
            self.assertFalse(out["approved_to_accept_payment_or_send_customer_material"])

    def test_completion_retains_strict_bundle_and_watch_requirements(self):
        historical = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
        out = inspect(now=historical, stage="completion")
        self.assertEqual(out["status"], "PILOT_BLOCKED")
        self.assertEqual(out["gates"]["delivery"]["status"], "BLOCKED_UNVERIFIED_BUNDLE")
        self.assertEqual(out["gates"]["watch"]["status"], "BLOCKED_NO_FRESH_WATCH_REPLAY")
        self.assertFalse(out["technical_preflight_passed"])

    def test_bad_stage_is_rejected_not_treated_as_approved(self):
        with self.assertRaisesRegex(ValueError, "stage must"):
            inspect(now=NOW, stage="waived")

    def test_cli_is_read_only_and_exit_code_never_claims_approval(self):
        root = Path(__file__).resolve().parents[1]
        run = subprocess.run(
            [sys.executable, "scripts/pilot_preflight.py", "--as-of", "2026-10-18T12:00:00Z"],
            cwd=root, capture_output=True, text=True, check=False,
        )
        self.assertEqual(run.returncode, 2, run.stderr)
        out = json.loads(run.stdout)
        self.assertEqual(out["status"], "PILOT_BLOCKED")
        self.assertIs(out["approved_to_accept_payment_or_send_customer_material"], False)

    def test_time_must_be_timezone_aware(self):
        with self.assertRaises(ValueError):
            inspect(now=datetime(2026, 10, 18, 12, 0))


if __name__ == "__main__":
    unittest.main()
