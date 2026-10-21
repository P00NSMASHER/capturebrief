"""Only fictional Stripe records. No charges, refunds, accounts, API keys or email sent."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from capturebrief_core.payment_reconciliation import (
    ACCOUNT_ID, PAYMENT_LINK_ID, reconcile_capturebrief_payment,
)
from scripts.reconcile_stripe_checkout import check_live_payment, REPO


def fixtures():
    session = {
        "object": "checkout.session", "id": "cs_live_TESTONLYONE",
        "livemode": True, "payment_link": PAYMENT_LINK_ID,
        "mode": "payment", "status": "complete",
        "payment_status": "paid", "currency": "usd", "amount_total": 14900,
        "customer_details": {"email": "buyer@example.com"},
        "payment_intent": "pi_TESTONLYONE",
    }
    pi = {
        "object": "payment_intent", "id": "pi_TESTONLYONE",
        "livemode": True, "status": "succeeded", "capture_method": "automatic",
        "currency": "usd", "amount": 14900, "amount_received": 14900,
        "latest_charge": "ch_TESTONLYONE",
    }
    charge = {
        "object": "charge", "id": "ch_TESTONLYONE",
        "payment_intent": "pi_TESTONLYONE", "livemode": True,
        "paid": True, "captured": True, "status": "succeeded",
        "currency": "usd", "amount": 14900, "amount_refunded": 0,
        "refunded": False, "disputed": False, "failure_code": None,
    }
    return session, pi, charge


class StripeReconciliationTests(unittest.TestCase):
    def test_fictional_three_record_paid_flow_is_consistent_not_send_authority(self):
        session, pi, charge = fixtures()
        r = reconcile_capturebrief_payment(
            session, pi, charge, account_id=ACCOUNT_ID, buyer_email="Buyer@Example.com",
        )
        self.assertEqual(r["status"], "PROCESSOR_RECORDS_CONSISTENT_REVIEW_REQUIRED")
        self.assertTrue(r["payment_verified_by_matching_records"])
        self.assertFalse(r["case_release_authorized"])
        self.assertFalse(r["external_send_authorized"])
        self.assertFalse(r["processor_records_authenticated_by_caller"])
        self.assertNotIn("buyer@example.com", json.dumps(r))
        self.assertNotIn("card", json.dumps(r).lower())

    def test_test_mode_cannot_confirm_live_customer_even_if_paid(self):
        a, b, c = fixtures()
        a["id"] = "cs_test_testonlyone"
        a["livemode"] = False
        b["livemode"] = False
        c["livemode"] = False
        out = reconcile_capturebrief_payment(
            a, b, c, account_id=ACCOUNT_ID, buyer_email="buyer@example.com"
        )
        self.assertEqual(out["status"], "PAYMENT_RECONCILIATION_BLOCKED")
        self.assertIn("SESSION_NOT_LIVE", out["error_codes"])
        self.assertFalse(out["payment_verified_by_matching_records"])

    def test_refunded_partial_or_disputed_charge_is_not_accepted(self):
        for key, value in (
            ("refunded", True),
            ("amount_refunded", 1),
            ("disputed", True),
            ("disputed", None),
            ("paid", False),
            ("captured", False),
        ):
            a, b, c = fixtures()
            c[key] = value
            with self.subTest(key=key):
                out = reconcile_capturebrief_payment(
                    a, b, c, account_id=ACCOUNT_ID, buyer_email="buyer@example.com"
                )
                self.assertFalse(out["payment_verified_by_matching_records"])
                self.assertTrue(out["error_codes"])

    def test_mismatched_customer_amount_link_account_and_intent_rejected(self):
        defects = [
            lambda a, b, c: a.update(payment_link="plink_OTHER"),
            lambda a, b, c: a.update(amount_total=1),
            lambda a, b, c: a.update(payment_status="unpaid"),
            lambda a, b, c: a.update(mode="subscription"),
            lambda a, b, c: a.update(status="expired"),
            lambda a, b, c: b.update(amount_received=0),
            lambda a, b, c: b.update(status="requires_payment_method"),
            lambda a, b, c: c.update(payment_intent="pi_OTHER"),
            lambda a, b, c: c.update(amount=999),
            lambda a, b, c: c.update(refunded=None),
        ]
        for change in defects:
            a, b, c = fixtures()
            change(a, b, c)
            out = reconcile_capturebrief_payment(
                a, b, c, account_id=ACCOUNT_ID, buyer_email="buyer@example.com"
            )
            self.assertFalse(out["payment_verified_by_matching_records"], out)

        a, b, c = fixtures()
        for account, email in (
            ("acct_wrong", "buyer@example.com"),
            (ACCOUNT_ID, "imposter@example.com"),
            (ACCOUNT_ID, ""),
        ):
            with self.subTest(account=account, email=email):
                out = reconcile_capturebrief_payment(
                    a, b, c, account_id=account, buyer_email=email,
                )
                self.assertFalse(out["payment_verified_by_matching_records"])

    def test_read_only_live_api_sequence_and_account_pin(self):
        a, b, c = fixtures()
        case = {"case_id": "CB-FICTIONAL", "intake": {"email": "buyer@example.com"}}
        calls = []

        def provider(path, key):
            self.assertEqual(key, "sk_live_FAKEONLY")
            calls.append(path)
            return copy.deepcopy({
                "/v1/account": {"object": "account", "id": ACCOUNT_ID},
                "/v1/checkout/sessions/" + a["id"]: a,
                "/v1/payment_intents/" + b["id"]: b,
                "/v1/charges/" + c["id"]: c,
            }[path])

        result = check_live_payment(
            case=case, session_id=a["id"], api_key="sk_live_FAKEONLY", fetcher=provider
        )
        self.assertEqual(len(calls), 4)
        self.assertTrue(result["payment_verified_by_matching_records"])
        self.assertEqual(result["source"], "STRIPE_DIRECT_LIVE_READ_ONLY_API")
        self.assertFalse(result["scope_approved"])
        self.assertFalse(result["sender_verified"])
        self.assertNotIn("sk_live_FAKEONLY", json.dumps(result))
        self.assertNotIn("buyer@example.com", json.dumps(result))

    def test_account_mismatch_stops_before_any_checkout_read(self):
        case = {"case_id": "CB-FICTIONAL", "intake": {"email": "buyer@example.com"}}
        calls = []

        def provider(path, key):
            calls.append(path)
            return {"object": "account", "id": "acct_OTHER"}
        with self.assertRaisesRegex(ValueError, "not scoped"):
            check_live_payment(case=case, session_id="cs_live_FAKEONE",
                               api_key="sk_live_FAKEONLY", fetcher=provider)
        self.assertEqual(calls, ["/v1/account"])

    def test_sandbox_key_and_fake_checkout_rejected_before_network(self):
        case = {"case_id": "CB-FICTIONAL", "intake": {"email": "buyer@example.com"}}
        def no_network(path, key):
            self.fail("Unexpected provider access")
        with self.assertRaisesRegex(ValueError, "Live Stripe credential"):
            check_live_payment(case=case, session_id="cs_live_FAKEONE",
                               api_key="sk_test_NOTREAL", fetcher=no_network)
        with self.assertRaisesRegex(ValueError, "live Stripe Checkout"):
            check_live_payment(case=case, session_id="cs_test_FAKEONE",
                               api_key="sk_live_FAKEONLY", fetcher=no_network)

    def test_cli_missing_key_is_redacted_without_writing(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            private_case = p / "case.json"
            private_case.write_text(json.dumps({
                "case_id": "CB-FICTIONAL",
                "intake": {"email": "buyer@example.com"}
            }))
            target = p / "receipt.json"
            env = dict(os.environ)
            env.pop("STRIPE_CAPTUREBRIEF_SECRET_KEY", None)
            call = subprocess.run([
                sys.executable, "scripts/reconcile_stripe_checkout.py",
                str(private_case), "cs_live_FAKETEST",
                "--receipt-output", str(target),
            ], cwd=REPO, env=env, text=True, capture_output=True)
            self.assertEqual(call.returncode, 3)
            self.assertFalse(target.exists())
            self.assertNotIn("buyer@example.com", call.stdout)
            self.assertNotIn("sk_live_", call.stdout)

    def test_reject_public_input_paths_without_access(self):
        from scripts.reconcile_stripe_checkout import _private_file
        with self.assertRaisesRegex(ValueError, "outside the public repository"):
            _private_file(REPO / "buyer-sensitive.json", existing=True)


if __name__ == "__main__":
    unittest.main()
