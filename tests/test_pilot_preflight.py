"""Pilot release must fail closed on missing real evidence and unsigned claims."""
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from capturebrief_core.intake import build_case_from_intake
from scripts.pilot_preflight import inspect, official_opportunity

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
OFFICIAL = "https://sam.gov/opp/3127a3862fe74c0b8bf614948e89f66f/view"


class PilotPreflightTests(unittest.TestCase):
    def test_only_genuine_first_party_notice_urls_pass_structural_check(self):
        self.assertTrue(official_opportunity(OFFICIAL))
        for value in (
            "http://sam.gov/opp/3127a3862fe74c0b8bf614948e89f66f/view",
            "https://sam.gov.evil.example/opp/3127a3862fe74c0b8bf614948e89f66f/view",
            "https://buyer:s3cret@sam.gov/opp/3127a3862fe74c0b8bf614948e89f66f/view",
            "https://sam.gov/opp/example/view",
            "https://sam.gov/private/buyer-brief",
            "https://sam.gov/opp/3127a3862fe74c0b8bf614948e89f66f/view#forged",
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
        # This is a real, currently visible public notice; the buyer is fictitious.
        # A true public URL by itself supplies no verified controlling sources.
        intake = {
            "email": "buyer@example.com",
            "company": "Fictional Federal Corp",
            "public_opportunity": OFFICIAL,
            "current_posture": "HOLD",
            "assumption_1": "The proposal deadline is still October 29, 2026.",
            "assumption_2": "No further amendments affect the deadline.",
            "public_only_confirmation": "yes",
        }
        case = build_case_from_intake(intake, submitted_at=NOW.isoformat())
        out = inspect(now=NOW, case=case)
        self.assertEqual(out["gates"]["real_case"]["status"], "PUBLIC_LINK_FORMAT_VERIFIED")
        self.assertEqual(out["gates"]["release"]["status"], "BLOCKED_BY_CORE_EVIDENCE")
        self.assertEqual(out["gates"]["delivery"]["status"], "BLOCKED_UNVERIFIED_BUNDLE")
        self.assertEqual(out["gates"]["watch"]["status"], "BLOCKED_NO_FRESH_WATCH_REPLAY")
        self.assertIs(out["approved_to_accept_payment_or_send_customer_material"], False)
        self.assertEqual(case["packet"]["history_receipts"], [])
        self.assertEqual(case["current_action_receipts"], [])
        self.assertTrue(all(x["evidence_state"] == "UNPROVEN" for x in case["assumptions"]))

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
