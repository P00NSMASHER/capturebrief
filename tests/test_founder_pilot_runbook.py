"""Adversarial checks against stale paid-first-pilot operator instructions."""
import unittest
from datetime import datetime, timezone

from scripts.audit_founder_pilot_runbook import REQUIRED, RUNBOOK, violations
from scripts.pilot_preflight import inspect


class FounderPilotRunbookContractTests(unittest.TestCase):
    def test_checked_in_runbook_describes_the_current_no_card_pilot(self):
        self.assertEqual(violations(RUNBOOK.read_text(encoding="utf-8")), [])

    def test_legacy_paid_workflow_is_rejected(self):
        good = "\n".join(REQUIRED.values())
        self.assertFalse(violations(good))
        for old in (
            "## A. Source, identity, and prepayment intake",
            "## B. Payment: live account, never website assertion",
            "one-time USD 149.00",
            "## D. The 14-day targeted watch",
        ):
            with self.subTest(stale_instruction=old):
                self.assertTrue(any(x.startswith("STALE_") for x in violations(good + "\n" + old)))

    def test_no_private_backup_or_send_gate_can_silently_disappear(self):
        good = "\n".join(REQUIRED.values())
        for key in (
            "private_destination", "isolated_token", "provider_isolation",
            "complete_backup", "second_device", "separate_key",
            "signed_one_message_release", "no_messages",
        ):
            with self.subTest(missing=key):
                mutated = good.replace(REQUIRED[key], "UNVERIFIED_PLACEHOLDER")
                self.assertIn("MISSING_" + key.upper(), violations(mutated))

    def test_founder_preflight_is_not_paid_or_customer_send_authorization(self):
        result = inspect(now=datetime(2026, 10, 29, 19, 0, tzinfo=timezone.utc),
                         stage="admission", offer="free", launch_mode="founder_curated")
        self.assertFalse(result["approved_to_accept_payment_or_send_customer_material"])
        self.assertFalse(result["first_customer_prelaunch_policy"]["customer_required"])
        self.assertEqual(result["gates"]["payment"]["status"], "NO_PAYMENT_FOR_FREE_CHECK")
        self.assertEqual(result["status"], "FOUNDER_CURATED_INQUIRY_REVIEW_REQUIRED")
        self.assertIn("prelaunch_offdevice_recovery", result["pre_pilot_gates"])
        self.assertIn("history_route", result["post_pilot_gates"])


if __name__ == "__main__":
    unittest.main()
