"""Fail-closed, no-network tests for private payment-hold to original-order binding.

All buyer details and Stripe-shaped objects are explicitly fictional.
No API calls, customer contact, payments, uploads, approvals, or sends.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from capturebrief_core.private_order_registry import order_summary
from scripts.batch_import_request_drafts import batch_import
from scripts.inspect_private_order_fulfillment import inspect_fulfillment
from scripts.register_private_order import register_checkout
from tests.test_private_order_os import provider_for, stripe_records
from tests.test_request_draft import draft

NOW = datetime(2026, 10, 21, 16, 0, tzinfo=timezone.utc)


class PaymentHoldBindingTests(unittest.TestCase):
    def fixture(self, root: Path):
        inbox, cases, storage = (root / name for name in ("inbox", "cases", "private"))
        for path in (inbox, cases, storage):
            path.mkdir()
        (inbox / "request.txt").write_text(draft(), encoding="utf-8")
        imported = batch_import(inbox, cases)
        self.assertEqual(imported["created"], 1)
        case_path = next(cases.glob("*.case.json"))
        db = storage / "orders.sqlite"
        provider, calls = provider_for(stripe_records("HOLDREAD"))
        result = register_checkout(
            case_path, checkout_session_id="cs_live_HOLDREAD",
            database_path=db, api_key="sk_live_FICTIONAL_TEST_KEY",
            fetcher=provider, synthetic_test_mode=True, observed_at=NOW,
        )
        self.assertEqual(result["status"], "PRIVATE_ORDER_REGISTERED_REVIEW_REQUIRED")
        self.assertEqual(len(calls), 4)
        with closing(sqlite3.connect(db)) as conn:
            conn.row_factory = sqlite3.Row
            original = dict(conn.execute(
                "SELECT session_ref, case_sha256, request_sha256 FROM orders"
            ).fetchone())
        return cases, db, original

    def inject_hold(self, db: Path, original: dict, *, session=None,
                    case_sha=None, request_sha=None, provider=1, receipt_sha=None):
        with closing(sqlite3.connect(db)) as conn:
            # The registry's DDL names a FK, but SQLite leaves enforcement OFF
            # unless explicitly enabled. Model a damaged/restored registry.
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute(
                """INSERT INTO payment_holds(
                    session_ref, case_sha256, request_sha256, first_blocked_at,
                    blocked_reconciliation_sha256, synthetic_provider)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session if session is not None else original["session_ref"],
                 case_sha if case_sha is not None else original["case_sha256"],
                 request_sha if request_sha is not None else original["request_sha256"],
                 NOW.isoformat().replace("+00:00", "Z"),
                 receipt_sha if receipt_sha is not None else "f" * 64, provider),
            )
            conn.commit()

    def assert_both_views_fail_closed(self, cases, db):
        before = {p.name: p.read_bytes() for p in cases.iterdir()}
        summary = order_summary(db)
        self.assertEqual(summary["status"], "PRIVATE_ORDER_REGISTRY_BLOCKED")
        self.assertFalse(summary["all_customer_release_authorized"])
        view = inspect_fulfillment(cases, db, now=NOW)
        self.assertEqual(view["status"], "PRIVATE_ORDER_FULFILLMENT_BLOCKED")
        self.assertGreater(view["blocked"], 0)
        self.assertFalse(view["external_send_authorized"])
        self.assertFalse(view.get("customer_release_authorized", False))
        self.assertEqual(before, {p.name: p.read_bytes() for p in cases.iterdir()})
        text = json.dumps({"summary": summary, "view": view})
        for secret in ("buyer@example.com", "cs_live_HOLDREAD",
                       "https://sam.gov/opp/", str(cases)):
            self.assertNotIn(secret, text)

    def test_healthy_registry_remains_review_only(self):
        with tempfile.TemporaryDirectory() as temp:
            cases, db, _ = self.fixture(Path(temp))
            self.assertEqual(order_summary(db)["status"], "PRIVATE_ORDER_REVIEW_PENDING")
            view = inspect_fulfillment(cases, db, now=NOW)
            self.assertEqual(view["status"], "PRIVATE_ORDER_FULFILLMENT_REVIEW_PENDING")
            self.assertFalse(view["external_send_authorized"])
            self.assertFalse(view["delivery_verified"])

    def test_orphan_hold_must_not_disappear_from_both_read_only_views(self):
        with tempfile.TemporaryDirectory() as temp:
            cases, db, original = self.fixture(Path(temp))
            self.inject_hold(db, original, session="cs_live_ORPHANED")
            self.assert_both_views_fail_closed(cases, db)

    def test_conflicting_hold_identity_and_provenance_never_get_silently_accepted(self):
        for alteration in (
            {"case_sha": "a" * 64},
            {"request_sha": "b" * 64},
            {"provider": 0},
            {"receipt_sha": "bad"},
        ):
            with self.subTest(alteration=alteration), tempfile.TemporaryDirectory() as temp:
                cases, db, original = self.fixture(Path(temp))
                self.inject_hold(db, original, **alteration)
                self.assert_both_views_fail_closed(cases, db)

    def test_valid_hold_blocks_payment_recheck_without_approving_work(self):
        with tempfile.TemporaryDirectory() as temp:
            cases, db, original = self.fixture(Path(temp))
            self.inject_hold(db, original)
            summary = order_summary(db)
            self.assertEqual(summary["status"], "PRIVATE_ORDER_PAYMENT_RECHECK_BLOCKED")
            self.assertEqual(summary["payment_rechecks_blocked"], 1)
            view = inspect_fulfillment(cases, db, now=NOW)
            self.assertEqual(view["status"], "PRIVATE_ORDER_FULFILLMENT_BLOCKED")
            self.assertEqual(view["orders"][0]["status"], "PAYMENT_RECHECK_BLOCKED")
            self.assertFalse(view["orders"][0]["payment_currently_authenticated_for_start"])
            self.assertFalse(view["external_send_authorized"])


if __name__ == "__main__":
    unittest.main()
