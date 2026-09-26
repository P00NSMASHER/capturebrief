"""Offline tests for payment event idempotency and bounded credits."""

from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from entitlement_ledger import InsufficientEntitlement, Ledger, LedgerConflict, OrderNotFound

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)

def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()

class EntitlementLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "billing.sqlite3"
        self.ledger = Ledger(self.path)

    def order(self, order_id="order-1", product="pilot_149", provider="pi-1", organization="org-1"):
        return self.ledger.create_order(order_id, organization, product, {"pilot_149": 14_900}[product], provider_payment_id=provider, now=NOW)

    def paid(self, order_id="order-1", product="pilot_149", provider="pi-1", organization="org-1"):
        self.order(order_id, product, provider, organization)
        return self.ledger.apply_payment_event(f"evt-{order_id}-paid", provider, "payment_succeeded", order_id, digest(f"{order_id}-paid"), NOW)

    def test_order_price_and_replay_are_server_controlled(self):
        created = self.order()
        self.assertEqual(created.status, "pending")
        self.assertEqual(self.ledger.create_order("order-1", "org-1", "pilot_149", 14_900, provider_payment_id="pi-1", now=NOW), created)
        with self.assertRaises(ValueError): self.ledger.create_order("bad-price", "org-1", "pilot_149", 1, provider_payment_id="pi-2")
        with self.assertRaises(LedgerConflict): self.ledger.create_order("order-1", "org-2", "pilot_149", 14_900, provider_payment_id="pi-1")
        with self.assertRaises(LedgerConflict): self.order("order-2", provider="pi-1")

    def test_success_grants_bundle_once_and_late_events_do_not_regrant(self):
        result = self.paid()
        self.assertEqual((result.outcome, result.order_status), ("applied", "paid"))
        self.assertEqual(dict(result.granted), {"reviewed_pursuit": 1, "monitoring_window_14d": 1})
        self.assertEqual(self.ledger.balances("org-1"), {"reviewed_pursuit": 1, "monitoring_window_14d": 1})
        duplicate = self.ledger.apply_payment_event("evt-order-1-paid", "pi-1", "payment_succeeded", "order-1", digest("order-1-paid"), NOW)
        self.assertEqual(duplicate.outcome, "duplicate")
        late_success = self.ledger.apply_payment_event("evt-order-1-paid-late", "pi-1", "payment_succeeded", "order-1", digest("late"), NOW)
        self.assertEqual(late_success.outcome, "ignored")
        self.assertEqual(self.ledger.balances("org-1"), {"reviewed_pursuit": 1, "monitoring_window_14d": 1})

    def test_failed_and_refund_before_success_never_grant(self):
        self.order("failed", provider="pi-failed")
        failed = self.ledger.apply_payment_event("evt-failed", "pi-failed", "payment_failed", "failed", digest("failed"), NOW)
        self.assertEqual((failed.outcome, failed.order_status), ("applied", "failed"))
        late = self.ledger.apply_payment_event("evt-failed-late-success", "pi-failed", "payment_succeeded", "failed", digest("late-failed"), NOW)
        self.assertEqual(late.outcome, "ignored")
        self.order("refunded-first", provider="pi-refunded-first")
        refund = self.ledger.apply_payment_event("evt-refund-first", "pi-refunded-first", "payment_refunded", "refunded-first", digest("refund-first"), NOW)
        self.assertEqual((refund.outcome, refund.order_status), ("applied", "refunded"))
        success = self.ledger.apply_payment_event("evt-refund-first-success", "pi-refunded-first", "payment_succeeded", "refunded-first", digest("success-after-refund"), NOW)
        self.assertEqual(success.outcome, "ignored")
        self.assertEqual(self.ledger.balances("org-1"), {})

    def test_refund_revokes_only_unreserved_credits(self):
        self.paid()
        reserved = self.ledger.reserve_credit("org-1", "reviewed_pursuit", "res-review", "job-review", NOW)
        self.assertTrue(reserved.should_execute)
        self.assertEqual(self.ledger.balance("org-1", "reviewed_pursuit"), 0)
        refund = self.ledger.apply_payment_event("evt-refund", "pi-1", "payment_refunded", "order-1", digest("refund"), NOW)
        self.assertEqual(dict(refund.revoked), {"monitoring_window_14d": 1})
        self.assertEqual(self.ledger.balances("org-1"), {})
        self.assertEqual(self.ledger.complete_credit("res-review", "failed", NOW).state, "forfeited")
        self.assertEqual(self.ledger.balance("org-1", "reviewed_pursuit"), 0)

    def test_credit_reservation_replay_restore_consume_and_conflict(self):
        self.paid()
        first = self.ledger.reserve_credit("org-1", "monitoring_window_14d", "res-1", "job-1", NOW)
        replay = self.ledger.reserve_credit("org-1", "monitoring_window_14d", "res-1", "job-1", NOW)
        self.assertTrue(first.should_execute); self.assertFalse(replay.should_execute)
        self.assertEqual(self.ledger.balance("org-1", "monitoring_window_14d"), 0)
        restored = self.ledger.complete_credit("res-1", "failed", NOW)
        self.assertEqual((restored.state, restored.changed), ("restored", True))
        self.assertFalse(self.ledger.complete_credit("res-1", "failed", NOW).changed)
        self.assertEqual(self.ledger.balance("org-1", "monitoring_window_14d"), 1)
        second = self.ledger.reserve_credit("org-1", "monitoring_window_14d", "res-2", "job-2", NOW)
        self.assertTrue(second.should_execute)
        consumed = self.ledger.complete_credit("res-2", "succeeded", NOW)
        self.assertEqual((consumed.state, consumed.changed), ("consumed", True))
        with self.assertRaises(LedgerConflict): self.ledger.complete_credit("res-2", "failed", NOW)
        with self.assertRaises(LedgerConflict): self.ledger.reserve_credit("org-1", "reviewed_pursuit", "res-2", "job-2", NOW)

    def test_concurrent_reservations_cannot_overspend(self):
        self.paid(product="pilot_149")
        def reserve(index):
            ledger = Ledger(self.path)
            try: return ledger.reserve_credit("org-1", "reviewed_pursuit", f"res-{index}", f"job-{index}", NOW).should_execute
            except InsufficientEntitlement: return False
        with ThreadPoolExecutor(max_workers=20) as pool: results = list(pool.map(reserve, range(20)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.ledger.balance("org-1", "reviewed_pursuit"), 0)

    def test_tenant_checked_order_lookup_and_event_payload_conflict(self):
        self.paid()
        with self.assertRaises(OrderNotFound): self.ledger.get_order("order-1", "other-org")
        with self.assertRaises(LedgerConflict): self.ledger.apply_payment_event("evt-order-1-paid", "pi-1", "payment_succeeded", "order-1", digest("different"), NOW)

    def test_schema_has_no_raw_payload_or_secret_fields(self):
        with closing(sqlite3.connect(self.path)) as connection:
            event_columns = {row[1] for row in connection.execute("PRAGMA table_info(payment_events)")}
            ledger_columns = {row[1] for row in connection.execute("PRAGMA table_info(entitlement_ledger)")}
        self.assertNotIn("payload", event_columns)
        self.assertNotIn("api_key", event_columns | ledger_columns)
        self.assertIn("payload_sha256", event_columns)

if __name__ == "__main__":
    unittest.main()
