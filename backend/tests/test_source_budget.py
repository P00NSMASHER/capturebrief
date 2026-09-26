"""Tests require no source account, API key, network, or third-party packages."""

from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_budget import AttemptConflict, BudgetExceeded, BudgetNotConfigured, Ledger


NOW = datetime(2026, 9, 14, 23, 59, 59, tzinfo=timezone.utc)


class SourceBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "requests.sqlite3"
        self.ledger = Ledger(self.path)

    def test_unknown_budget_fails_closed_without_record(self):
        with self.assertRaises(BudgetNotConfigured):
            self.ledger.reserve("unconfigured", "attempt-1", NOW)
        with self.assertRaises(BudgetNotConfigured):
            self.ledger.summary("unconfigured", NOW.date())
        self.ledger.configure_budget("unconfigured", 1)
        self.assertEqual(self.ledger.summary("unconfigured", NOW.date()).used, 0)

    def test_invalid_configuration_and_zero_budget(self):
        for value in (-1, None, True, 1.5, "10", 2**63):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.ledger.configure_budget("acct", value)
        self.ledger.configure_budget("acct", 0)
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve("acct", "zero", NOW)

    def test_replay_is_not_permission_to_send_twice(self):
        self.ledger.configure_budget("acct", 1)
        self.assertTrue(self.ledger.reserve("acct", "attempt", NOW).should_attempt)
        replay = self.ledger.reserve("acct", "attempt", NOW)
        self.assertFalse(replay.should_attempt)
        self.assertEqual(self.ledger.summary("acct", NOW.date()).used, 1)
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve("acct", "new-attempt", NOW)

    def test_failed_retried_and_abandoned_attempts_all_count(self):
        self.ledger.configure_budget("acct", 6)
        for index, status in enumerate(("timeout", "http_error", "network_error", "invalid_response", "success")):
            attempt = f"retry-{index}"
            self.assertTrue(self.ledger.reserve("acct", attempt, NOW).should_attempt)
            self.assertTrue(self.ledger.complete(attempt, status))
            self.assertFalse(self.ledger.complete(attempt, status))
        self.ledger.reserve("acct", "crashed-worker", NOW)
        summary = Ledger(self.path).summary("acct", NOW.date())
        self.assertEqual((summary.used, summary.remaining, summary.pending), (6, 0, 1))
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve("acct", "one-too-many", NOW)

    def test_rollover_uses_utc_and_old_replay_stays_old(self):
        self.ledger.configure_budget("acct", 1)
        self.ledger.reserve("acct", "old", NOW)
        tomorrow = NOW + timedelta(seconds=1)
        self.assertTrue(self.ledger.reserve("acct", "new", tomorrow).should_attempt)
        replay = self.ledger.reserve("acct", "old", tomorrow)
        self.assertEqual(replay.day, "2026-09-14")
        self.assertFalse(replay.should_attempt)
        self.assertEqual(self.ledger.summary("acct", "2026-09-15").used, 1)

    def test_timezone_normalization_and_naive_clock_rejected(self):
        self.ledger.configure_budget("acct", 2)
        local = datetime(2026, 9, 14, 23, tzinfo=timezone(timedelta(hours=-4)))
        self.assertEqual(self.ledger.reserve("acct", "local", local).day, "2026-09-15")
        with self.assertRaises(ValueError):
            self.ledger.reserve("acct", "naive", datetime(2026, 9, 14))

    def test_concurrent_connections_cannot_overspend(self):
        self.ledger.configure_budget("acct", 7)
        barrier = threading.Barrier(20)

        def request(index):
            ledger = Ledger(self.path)
            barrier.wait(timeout=10)
            try:
                return ledger.reserve("acct", f"parallel-{index}", NOW).should_attempt
            except BudgetExceeded:
                return False

        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(request, range(20)))
        self.assertEqual(sum(results), 7)
        self.assertEqual(self.ledger.summary("acct", NOW.date()).remaining, 0)

    def test_concurrent_replays_authorize_one_physical_attempt(self):
        self.ledger.configure_budget("acct", 10)
        barrier = threading.Barrier(12)

        def request(_):
            ledger = Ledger(self.path)
            barrier.wait(timeout=10)
            return ledger.reserve("acct", "same-attempt", NOW).should_attempt

        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(request, range(12)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.ledger.summary("acct", NOW.date()).used, 1)

    def test_account_budgets_are_independent_but_attempt_ids_global(self):
        for account in ("one", "two"):
            self.ledger.configure_budget(account, 1)
        self.ledger.reserve("one", "unique", NOW)
        with self.assertRaises(AttemptConflict):
            self.ledger.reserve("two", "unique", NOW)
        self.assertTrue(self.ledger.reserve("two", "different", NOW).should_attempt)

    def test_reconfiguration_never_clears_usage(self):
        self.ledger.configure_budget("acct", 2)
        self.ledger.reserve("acct", "first", NOW)
        self.ledger.reserve("acct", "second", NOW)
        self.ledger.configure_budget("acct", 1)
        summary = self.ledger.summary("acct", NOW.date())
        self.assertEqual((summary.used, summary.remaining), (2, 0))
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve("acct", "third", NOW)
        self.ledger.configure_budget("acct", 3)
        self.assertTrue(self.ledger.reserve("acct", "third", NOW).should_attempt)

    def test_unknown_and_conflicting_completions_are_rejected(self):
        with self.assertRaises(KeyError):
            self.ledger.complete("missing", "success")
        self.ledger.configure_budget("acct", 1)
        self.ledger.reserve("acct", "attempt", NOW)
        self.ledger.complete("attempt", "timeout")
        with self.assertRaises(AttemptConflict):
            self.ledger.complete("attempt", "success")
        with self.assertRaises(ValueError):
            self.ledger.complete("attempt", "https://sam.gov?api_key=secret")

    def test_no_url_or_freeform_error_fields(self):
        with self.assertRaises(ValueError):
            self.ledger.configure_budget("https://sam.gov?api_key=secret", 1)
        self.ledger.configure_budget("acct", 1)
        with self.assertRaises(ValueError):
            self.ledger.reserve("acct", "error message with secrets", NOW)
        with closing(sqlite3.connect(self.path)) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(source_attempts)")}
        self.assertEqual(columns, {"attempt_id", "account_id", "utc_day", "reserved_at", "status", "completed_at"})

    def test_requires_persistent_file_and_valid_summary_date(self):
        with self.assertRaises(ValueError):
            Ledger(":memory:")
        self.ledger.configure_budget("acct", 1)
        for day in ("2026-9-14", "2026-09-99", NOW):
            with self.subTest(day=day), self.assertRaises(ValueError):
                self.ledger.summary("acct", day)


if __name__ == "__main__":
    unittest.main()
