"""Offline tests for leases, retries, review gates, and tenant-safe reads."""

from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from job_queue import JobNotFound, LeaseLost, Queue, QueueConflict  # noqa: E402

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)

class JobQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "queue.sqlite3"
        self.queue = Queue(self.path, max_budget_cents=800)

    def enqueue(self, job_id="job-1", idem="org-1:src-1:profile-1:pilot:analysis-1", org="org-1", max_attempts=3):
        return self.queue.enqueue(
            job_id=job_id, idempotency_key=idem, organization_id=org,
            source_version="src-1", profile_version="profile-1", product="pilot_99",
            analysis_version="analysis-1", budget_cents=500, max_attempts=max_attempts, now=NOW,
        )

    def move_to_review(self, job_id="job-1", worker="worker-1"):
        claimed = self.queue.claim_next(worker, now=NOW)
        self.assertIsNotNone(claimed)
        for next_status in ("parsing", "analyzing", "validating"):
            self.queue.transition(job_id, worker, next_status, now=NOW)
        return self.queue.transition(job_id, worker, "review_required", now=NOW)

    def test_enqueue_is_idempotent_and_bounded(self):
        first = self.enqueue()
        replay = self.enqueue()
        self.assertTrue(first.created)
        self.assertFalse(replay.created)
        self.assertEqual(first.job, replay.job)
        with self.assertRaises(QueueConflict): self.enqueue(job_id="other", idem=first.job.idempotency_key)
        with self.assertRaises(ValueError):
            self.queue.enqueue(job_id="too-expensive", idempotency_key="too-expensive", organization_id="org-1", source_version="src", profile_version="profile", product="pilot_99", analysis_version="analysis", budget_cents=801, now=NOW)
        with self.assertRaises(ValueError):
            self.queue.enqueue(job_id="bad-attempts", idempotency_key="bad-attempts", organization_id="org-1", source_version="src", profile_version="profile", product="pilot_99", analysis_version="analysis", budget_cents=1, max_attempts=9, now=NOW)

    def test_pipeline_requires_review_before_delivery(self):
        self.enqueue()
        self.assertEqual(self.queue.claim_next("worker-1", now=NOW).status, "fetching")
        self.queue.transition("job-1", "worker-1", "parsing", now=NOW)
        self.queue.transition("job-1", "worker-1", "analyzing", now=NOW)
        self.queue.transition("job-1", "worker-1", "validating", now=NOW)
        reviewed = self.queue.transition("job-1", "worker-1", "review_required", now=NOW)
        self.assertIsNone(reviewed.worker_id)
        self.assertIsNone(self.queue.claim_next("worker-2", now=NOW))
        ready = self.queue.review_decide("job-1", "reviewer-1", approved=True, now=NOW)
        self.assertEqual(ready.status, "ready")
        delivery = self.queue.claim_next("worker-2", now=NOW)
        self.assertEqual(delivery.status, "delivering")
        delivered = self.queue.transition("job-1", "worker-2", "delivered", now=NOW)
        self.assertEqual(delivered.status, "delivered")
        self.assertEqual(self.queue.last_success_at(), delivered.delivered_at)
        self.assertEqual(self.queue.events("job-1", "org-1")[-1]["to_status"], "delivered")

    def test_killed_worker_lease_expires_and_job_is_reclaimed(self):
        self.enqueue()
        claimed = self.queue.claim_next("worker-1", now=NOW, lease_seconds=10)
        self.assertEqual(claimed.attempt_count, 1)
        recovered = self.queue.sweep_expired(NOW + timedelta(seconds=11))
        self.assertEqual(recovered, 1)
        reclaims = self.queue.claim_next("worker-2", now=NOW + timedelta(seconds=11), lease_seconds=10)
        self.assertEqual((reclaims.status, reclaims.attempt_count), ("fetching", 2))
        with self.assertRaises(LeaseLost): self.queue.transition("job-1", "worker-1", "parsing", now=NOW + timedelta(seconds=11))
        self.assertIn("lease_expired", [event["reason_code"] for event in self.queue.events("job-1", "org-1")])

    def test_retry_backoff_is_bounded_and_dead_letters_after_limit(self):
        self.enqueue(max_attempts=2)
        self.queue.claim_next("worker-1", now=NOW)
        retry = self.queue.fail("job-1", "worker-1", "source_unavailable", now=NOW)
        self.assertEqual(retry.status, "queued")
        self.assertEqual(retry.last_error_code, "source_unavailable")
        self.assertGreater(retry.next_attempt_at, NOW.isoformat())
        self.assertIsNone(self.queue.claim_next("worker-2", now=NOW + timedelta(seconds=4)))
        second = self.queue.claim_next("worker-2", now=NOW + timedelta(seconds=5))
        self.assertEqual(second.attempt_count, 2)
        final = self.queue.fail("job-1", "worker-2", "source_unavailable", now=NOW + timedelta(seconds=5))
        self.assertEqual((final.status, final.last_error_code), ("failed", "retry_exhausted"))
        self.assertIsNone(self.queue.claim_next("worker-3", now=NOW + timedelta(hours=1)))

    def test_nonretryable_source_failure_is_visible_and_not_retried(self):
        self.enqueue(); self.queue.claim_next("worker-1", now=NOW)
        blocked = self.queue.fail("job-1", "worker-1", "attachment_inaccessible", retryable=False, now=NOW)
        self.assertEqual((blocked.status, blocked.last_error_code), ("failed", "attachment_inaccessible"))
        self.assertIsNone(self.queue.claim_next("worker-2", now=NOW + timedelta(hours=1)))

    def test_wrong_worker_and_cross_tenant_reads_fail_closed(self):
        self.enqueue(); self.queue.claim_next("worker-1", now=NOW)
        with self.assertRaises(LeaseLost): self.queue.transition("job-1", "worker-2", "parsing", now=NOW)
        with self.assertRaises(JobNotFound): self.queue.get("job-1", "other-org")
        with self.assertRaises(JobNotFound): self.queue.events("job-1", "other-org")

    def test_review_rejection_blocks_and_cancel_is_idempotent(self):
        self.enqueue(); self.move_to_review()
        blocked = self.queue.review_decide("job-1", "reviewer-1", approved=False, now=NOW)
        self.assertEqual((blocked.status, blocked.last_error_code), ("blocked_source", "stale_source"))
        with self.assertRaises(QueueConflict): self.queue.review_decide("job-1", "reviewer-1", approved=False, now=NOW)
        self.enqueue(job_id="job-2", idem="job-2-idem")
        cancelled = self.queue.cancel("job-2", "admin-1", now=NOW)
        self.assertEqual((cancelled.status, cancelled.last_error_code), ("cancelled", "cancelled"))
        self.assertEqual(self.queue.cancel("job-2", "admin-1", now=NOW), cancelled)
        with self.assertRaises(QueueConflict): self.queue.cancel("job-1", "admin-1", now=NOW)

    def test_concurrent_claims_lease_each_job_once(self):
        for index in range(8): self.enqueue(job_id=f"job-{index}", idem=f"idem-{index}")
        def claim(worker):
            result = Queue(self.path).claim_next(worker, now=NOW)
            return None if result is None else result.job_id
        with ThreadPoolExecutor(max_workers=20) as pool:
            ids = [item for item in pool.map(claim, [f"worker-{i}" for i in range(20)]) if item]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 8)

    def test_schema_uses_fixed_codes_and_no_freeform_error_text(self):
        with closing(sqlite3.connect(self.path)) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
            event_columns = {row[1] for row in connection.execute("PRAGMA table_info(job_events)")}
        self.assertNotIn("error_message", columns | event_columns)
        self.assertIn("last_error_code", columns)
        self.assertIn("reason_code", event_columns)

if __name__ == "__main__":
    unittest.main()
