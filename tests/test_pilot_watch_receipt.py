import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from capturebrief_core.watch_baseline import build_watch_baseline
from scripts.run_watch_receipt import REPO_ROOT, evaluate_and_retain

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 21, 17, 30, tzinfo=timezone.utc)


class PilotWatchReceiptTests(unittest.TestCase):
    def setUp(self):
        self.case = json.loads((ROOT / "fixtures/ready_trace_case.json").read_text())
        self.baseline = build_watch_baseline(self.case, now=NOW)

    def test_stale_case_produces_immutable_review_receipt_not_false_clean(self):
        with tempfile.TemporaryDirectory() as folder:
            result = evaluate_and_retain(
                self.baseline, self.case,
                checked_at=NOW + timedelta(minutes=5), receipt_dir=folder,
            )
            self.assertEqual(result["watch_status"], "REVIEW_REQUIRED")
            self.assertTrue(result["requires_human_review"])
            self.assertFalse(result["external_send_authorized"])
            receipt = json.loads(Path(result["receipt_path"]).read_text())
            self.assertIn("WATCH_SOURCE_NOT_REFRESHED", {e["type"] for e in receipt["events"]})
            self.assertNotIn("buyer@example.com", json.dumps(receipt))
            self.assertEqual(result["observation_sha256"], receipt["observation_sha256"])
            # Identical replay is idempotent and never silently rewrites.
            again = evaluate_and_retain(
                self.baseline, self.case,
                checked_at=NOW + timedelta(minutes=5), receipt_dir=folder,
            )
            self.assertEqual(result, again)

            # A later operator check in this private receipt directory must
            # chain to its immediate predecessor rather than silently
            # comparing unchanged sources to the old delivery baseline.
            with self.assertRaisesRegex(ValueError, "Subsequent watch check"):
                evaluate_and_retain(
                    self.baseline, self.case,
                    checked_at=NOW + timedelta(minutes=10),
                    receipt_dir=folder,
                )
            new = evaluate_and_retain(
                self.baseline, self.case,
                checked_at=NOW + timedelta(minutes=10),
                receipt_dir=folder, previous_observation=receipt,
            )
            self.assertEqual(new["previous_observation_sha256"],
                             receipt["observation_sha256"])
            latest = json.loads(Path(new["receipt_path"]).read_text())
            self.assertIn("WATCH_SOURCE_NOT_REFRESHED_SINCE_PREVIOUS_CHECK",
                          {e["type"] for e in latest["events"]})
            self.assertTrue(new["requires_human_review"])

    def test_tamper_cannot_overwrite_prior_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            result = evaluate_and_retain(self.baseline, self.case,
                                          checked_at=NOW + timedelta(minutes=5),
                                          receipt_dir=folder)
            path = Path(result["receipt_path"])
            path.write_text("tampered", encoding="utf-8")
            with self.assertRaises(ValueError):
                evaluate_and_retain(self.baseline, self.case,
                                    checked_at=NOW + timedelta(minutes=5),
                                    receipt_dir=folder)
            self.assertEqual(path.read_text(), "tampered")

    def test_rejects_public_repo_and_future_baseline(self):
        with self.assertRaisesRegex(ValueError, "outside the public repository"):
            evaluate_and_retain(self.baseline, self.case,
                                checked_at=NOW + timedelta(minutes=5),
                                receipt_dir=str(REPO_ROOT / "my-customer-watch"))
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "later independent observation"):
                evaluate_and_retain(self.baseline, self.case,
                                    checked_at=NOW, receipt_dir=folder)

    def test_exact_fourteen_day_boundary_and_expiration(self):
        with tempfile.TemporaryDirectory() as folder:
            at_deadline = evaluate_and_retain(
                self.baseline, self.case,
                checked_at=NOW + timedelta(days=14), receipt_dir=folder,
            )
            self.assertTrue(at_deadline["requires_human_review"])
            self.assertNotEqual(at_deadline["watch_status"], "NO_CHANGE_OBSERVED")
            expired = evaluate_and_retain(
                self.baseline, self.case,
                checked_at=NOW + timedelta(days=14, seconds=1), receipt_dir=folder,
            )
            self.assertEqual(expired["watch_status"], "EXPIRED")
            self.assertTrue(expired["requires_human_review"])
            self.assertFalse(expired["external_send_authorized"])

    def test_invalid_integrity_hash_produces_no_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            baseline = json.loads(json.dumps(self.baseline))
            baseline["state"]["history_set_sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                evaluate_and_retain(baseline, self.case,
                                    checked_at=NOW + timedelta(minutes=5),
                                    receipt_dir=folder)
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
