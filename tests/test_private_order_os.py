"""Hermetic CaptureBrief private-order acceptance: all buyers and Stripe data invented."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from capturebrief_core.private_order_registry import register_order, order_summary, OrderConflict
from capturebrief_core.payment_reconciliation import ACCOUNT_ID, PAYMENT_LINK_ID
from scripts.batch_import_request_drafts import batch_import
from scripts.register_private_order import register_checkout
from tests.test_request_draft import draft

NOW = datetime(2026, 10, 21, 16, 0, tzinfo=timezone.utc)


def stripe_records(suffix="TESTONLY", email="buyer@example.com"):
    session = {
        "object": "checkout.session", "id": f"cs_live_{suffix}",
        "livemode": True, "payment_link": PAYMENT_LINK_ID,
        "mode": "payment", "status": "complete",
        "payment_status": "paid", "currency": "usd", "amount_total": 14900,
        "customer_details": {"email": email},
        "payment_intent": f"pi_{suffix}",
    }
    intent = {
        "object": "payment_intent", "id": f"pi_{suffix}",
        "livemode": True, "status": "succeeded", "capture_method": "automatic",
        "currency": "usd", "amount": 14900, "amount_received": 14900,
        "latest_charge": f"ch_{suffix}",
    }
    charge = {
        "object": "charge", "id": f"ch_{suffix}",
        "payment_intent": f"pi_{suffix}", "livemode": True,
        "paid": True, "captured": True, "status": "succeeded",
        "currency": "usd", "amount": 14900, "amount_refunded": 0,
        "refunded": False, "disputed": False, "failure_code": None,
    }
    return session, intent, charge


def provider_for(records, *, account=ACCOUNT_ID):
    session, intent, charge = copy.deepcopy(records)
    resources = {
        "/v1/account": {"object": "account", "id": account},
        "/v1/checkout/sessions/" + session["id"]: session,
        "/v1/payment_intents/" + intent["id"]: intent,
        "/v1/charges/" + charge["id"]: charge,
    }
    calls = []
    def fetch(path, key):
        assert key == "sk_live_FICTIONAL_TEST_KEY"
        calls.append(path)
        return copy.deepcopy(resources[path])
    return fetch, calls


class PrivateOrderOsTests(unittest.TestCase):
    def root(self, parent):
        base = Path(parent)
        inbox, cases, orders = base/"inbox", base/"cases", base/"orders"
        for path in (inbox, cases, orders):
            path.mkdir()
        return inbox, cases, orders/"registry.sqlite"

    def create_case(self, inbox, cases, *, text=None, filename="buyer.txt"):
        (inbox/filename).write_text(text or draft(), encoding="utf-8")
        report = batch_import(inbox, cases)
        self.assertEqual(report["blocked"], 0)
        return sorted(cases.glob("*.case.json"))[-1]

    def register(self, case, db, records, *, synthetic=True):
        fetcher, calls = provider_for(records)
        result = register_checkout(
            case, checkout_session_id=records[0]["id"],
            database_path=db, api_key="sk_live_FICTIONAL_TEST_KEY",
            fetcher=fetcher, synthetic_test_mode=synthetic, observed_at=NOW,
        )
        return result, calls

    def test_synthetic_stripe_records_register_once_without_revenue_claim(self):
        with tempfile.TemporaryDirectory() as td:
            inbox, cases, db = self.root(td)
            case = self.create_case(inbox, cases)
            original = {p.name: p.read_bytes() for p in cases.iterdir()}
            r, calls = self.register(case, db, stripe_records("FIRST"))
            self.assertEqual(calls, [
                "/v1/account", "/v1/checkout/sessions/cs_live_FIRST",
                "/v1/payment_intents/pi_FIRST", "/v1/charges/ch_FIRST",
            ])
            self.assertEqual(r["status"], "PRIVATE_ORDER_REGISTERED_REVIEW_REQUIRED")
            self.assertEqual(r["payment_state"], "SYNTHETIC_CONSISTENT_NOT_LIVE_PROOF")
            self.assertFalse(r["work_authorized"])
            self.assertFalse(r["customer_release_authorized"])
            summary = order_summary(db)
            self.assertEqual(summary["status"], "PRIVATE_ORDER_REVIEW_PENDING")
            self.assertEqual(len(summary["orders"]), 1)
            self.assertEqual(summary["orders"][0]["source_state"], "SOURCE_CATALOG_NOT_ATTESTED")
            self.assertEqual(summary["orders"][0]["watch_state"], "NOT_STARTED")
            self.assertNotIn("buyer@example.com", json.dumps(summary))
            self.assertNotIn("pi_FIRST", json.dumps(summary))
            self.assertNotIn("cs_live_FIRST", json.dumps(summary))
            again, _ = self.register(case, db, stripe_records("FIRST"))
            self.assertEqual(again["status"], "ALREADY_REGISTERED_UNVERIFIED")
            self.assertEqual(len(order_summary(db)["orders"]), 1)
            self.assertEqual(original, {p.name: p.read_bytes() for p in cases.iterdir()})

    def test_one_payment_or_case_cannot_be_reassigned_to_another_buyer(self):
        with tempfile.TemporaryDirectory() as td:
            inbox, cases, db = self.root(td)
            first = self.create_case(inbox, cases)
            one, _ = self.register(first, db, stripe_records("ONE"))
            self.assertEqual(one["status"], "PRIVATE_ORDER_REGISTERED_REVIEW_REQUIRED")
            self.create_case(inbox, cases, text=draft(company="Other Fictional Buyer"),
                             filename="second.txt")
            other = next(p for p in cases.glob("*.case.json") if p != first)
            with self.assertRaises(OrderConflict):
                self.register(other, db, stripe_records("ONE"))
            with self.assertRaises(OrderConflict):
                self.register(first, db, stripe_records("TWO"))
            self.assertEqual(len(order_summary(db)["orders"]), 1)

    def test_refund_dispute_wrong_account_wrong_buyer_and_test_mode_block(self):
        for issue in ("refunded", "disputed", "unpaid", "wrong_email", "test_mode", "wrong_account"):
            with self.subTest(issue=issue), tempfile.TemporaryDirectory() as td:
                inbox, cases, db = self.root(td)
                case = self.create_case(inbox, cases)
                records = list(stripe_records("REFUSE"))
                if issue == "refunded":
                    records[2]["refunded"] = True
                    records[2]["amount_refunded"] = 14900
                elif issue == "disputed":
                    records[2]["disputed"] = True
                elif issue == "unpaid":
                    records[0]["payment_status"] = "unpaid"
                elif issue == "wrong_email":
                    records[0]["customer_details"]["email"] = "someone-else@example.com"
                elif issue == "test_mode":
                    records[0]["livemode"] = False
                if issue == "wrong_account":
                    fetcher, calls = provider_for(records, account="acct_WRONG")
                else:
                    fetcher, calls = provider_for(records)
                try:
                    result = register_checkout(
                        case, checkout_session_id=records[0]["id"],
                        database_path=db, api_key="sk_live_FICTIONAL_TEST_KEY",
                        fetcher=fetcher, synthetic_test_mode=True, observed_at=NOW,
                    )
                    self.assertEqual(result["status"], "PAYMENT_RECONCILIATION_BLOCKED")
                except ValueError:
                    # Provider-account and test-mode mismatches should throw.
                    pass
                self.assertFalse(db.exists())
                self.assertEqual(order_summary(db)["orders"], [])

    def test_refund_after_registration_persists_separate_payment_hold(self):
        with tempfile.TemporaryDirectory() as td:
            inbox, cases, db = self.root(td)
            case = self.create_case(inbox, cases)
            initial, _ = self.register(case, db, stripe_records("REVERSAL"))
            self.assertEqual(initial["status"], "PRIVATE_ORDER_REGISTERED_REVIEW_REQUIRED")
            records = list(stripe_records("REVERSAL"))
            records[2]["refunded"] = True
            records[2]["amount_refunded"] = 14900
            rejected, _ = self.register(case, db, records)
            self.assertEqual(rejected["status"], "PAYMENT_RECONCILIATION_BLOCKED")
            self.assertTrue(rejected["existing_order_recheck_marked"])
            summary = order_summary(db)
            self.assertEqual(summary["status"], "PRIVATE_ORDER_PAYMENT_RECHECK_BLOCKED")
            self.assertEqual(len(summary["orders"]), 1)
            self.assertTrue(summary["orders"][0]["payment_recheck_blocked"])
            self.assertEqual(summary["orders"][0]["payment_state"],
                             "PAYMENT_RECHECK_BLOCKED_REVIEW_REQUIRED")
            # No silent re-promotion if a later synthetic record looks paid.
            with self.assertRaises(OrderConflict):
                self.register(case, db, stripe_records("REVERSAL"))
            self.assertEqual(len(order_summary(db)["orders"]), 1)
            self.assertNotIn("buyer@example.com", json.dumps(summary))
            self.assertFalse(summary["any_external_send_authorized"])

    def test_fake_key_and_untrusted_provider_modes_block_without_io(self):
        with tempfile.TemporaryDirectory() as td:
            inbox, cases, db = self.root(td)
            case = self.create_case(inbox, cases)
            provider, calls = provider_for(stripe_records())
            for synthetic, injected in ((True, None), (False, provider)):
                with self.assertRaises(ValueError):
                    register_checkout(case, checkout_session_id="cs_live_TESTONLY",
                        database_path=db, api_key="sk_live_FICTIONAL_TEST_KEY",
                        fetcher=injected, synthetic_test_mode=synthetic)
            with self.assertRaisesRegex(ValueError, "Live Stripe credential"):
                register_checkout(case, checkout_session_id="cs_live_TESTONLY",
                    database_path=db, api_key="sk_test_FICTIONAL",
                    fetcher=provider, synthetic_test_mode=True)
            self.assertFalse(db.exists())
            self.assertFalse(calls)

    def test_tampered_case_or_receipt_prevents_provider_calls(self):
        for target in ("case", "receipt"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as td:
                inbox, cases, db = self.root(td)
                case = self.create_case(inbox, cases)
                receipt = Path(str(case).replace(".case.json", ".receipt.json"))
                p = case if target == "case" else receipt
                p.write_text("tampered private file", encoding="utf-8")
                provider, calls = provider_for(stripe_records())
                with self.assertRaises(ValueError):
                    register_checkout(
                        case, checkout_session_id="cs_live_TESTONLY",
                        database_path=db, api_key="sk_live_FICTIONAL_TEST_KEY",
                        fetcher=provider, synthetic_test_mode=True,
                    )
                self.assertFalse(db.exists())
                self.assertFalse(calls)

    def test_private_registry_creation_race_reuses_existing_file(self):
        # Another worker may create the private SQLite pathname after this
        # one tested exists(), before its exclusive create. SQLite UNIQUE and
        # BEGIN IMMEDIATE must decide the order, not a FileExistsError.
        with tempfile.TemporaryDirectory() as td:
            inbox, cases, db = self.root(td)
            case = self.create_case(inbox, cases)
            original_open = os.open
            raced = []

            def simultaneous_first_create(path, flags, mode=0o777, *args, **kwargs):
                if (Path(path).resolve() == db.resolve()
                        and flags & os.O_EXCL
                        and not raced):
                    raced.append(True)
                    fd = original_open(path, flags, mode)
                    os.close(fd)
                    raise FileExistsError("another fictional worker created registry")
                return original_open(path, flags, mode, *args, **kwargs)

            with patch("capturebrief_core.private_order_registry.os.open",
                       side_effect=simultaneous_first_create):
                r, _ = self.register(case, db, stripe_records("RACE"))
            self.assertTrue(raced)
            self.assertEqual(r["status"], "PRIVATE_ORDER_REGISTERED_REVIEW_REQUIRED")
            self.assertEqual(len(order_summary(db)["orders"]), 1)
            again, _ = self.register(case, db, stripe_records("RACE"))
            self.assertEqual(again["status"], "ALREADY_REGISTERED_UNVERIFIED")

    def test_two_simultaneous_operators_register_same_payment_only_once(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as td:
            inbox, cases, db = self.root(td)
            case = self.create_case(inbox, cases)
            def register_simultaneously(_):
                return self.register(case, db, stripe_records("PARALLEL"))[0]["status"]
            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = sorted(executor.map(register_simultaneously, range(2)))
            self.assertEqual(statuses, [
                "ALREADY_REGISTERED_UNVERIFIED",
                "PRIVATE_ORDER_REGISTERED_REVIEW_REQUIRED",
            ])
            self.assertEqual(len(order_summary(db)["orders"]), 1)

    def test_registry_read_only_summary_and_cli_no_key_no_customer_data(self):
        with tempfile.TemporaryDirectory() as td:
            inbox, cases, db = self.root(td)
            self.assertFalse(db.exists())
            self.assertEqual(order_summary(db)["status"], "PRIVATE_ORDER_REGISTRY_EMPTY")
            self.assertFalse(db.exists())
            case = self.create_case(inbox, cases)
            env = dict(os.environ)
            env.pop("STRIPE_CAPTUREBRIEF_SECRET_KEY", None)
            run = subprocess.run(
                [sys.executable,
                 str(Path(__file__).resolve().parents[1]/"scripts/register_private_order.py"),
                 str(case), "cs_live_TESTONLY", "--registry", str(db)],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(run.returncode, 3)
            self.assertFalse(db.exists())
            self.assertNotIn("buyer@example.com", run.stdout)
            self.assertNotIn(str(case), run.stdout)
            self.assertNotIn("sk_live_", run.stdout)
