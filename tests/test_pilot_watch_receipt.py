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
            with self.assertRaisesRegex(ValueError, "latest retained receipt"):
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

    def test_skipping_an_intervening_review_receipt_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            first = evaluate_and_retain(
                self.baseline, self.case, checked_at=NOW + timedelta(minutes=10),
                receipt_dir=folder,
            )
            first_body = json.loads(Path(first["receipt_path"]).read_text())
            second = evaluate_and_retain(
                self.baseline, self.case, checked_at=NOW + timedelta(minutes=20),
                receipt_dir=folder, previous_observation=first_body,
            )
            second_body = json.loads(Path(second["receipt_path"]).read_text())

            # A predecessor may have a valid digest yet be too old for the
            # next check. Skipping the intermediate REVIEW_REQUIRED receipt
            # must fail before writing new content.
            with self.assertRaisesRegex(ValueError, "latest retained receipt"):
                evaluate_and_retain(
                    self.baseline, self.case,
                    checked_at=NOW + timedelta(minutes=30),
                    receipt_dir=folder, previous_observation=first_body,
                )
            third = evaluate_and_retain(
                self.baseline, self.case,
                checked_at=NOW + timedelta(minutes=30),
                receipt_dir=folder, previous_observation=second_body,
            )
            body = json.loads(Path(third["receipt_path"]).read_text())
            self.assertEqual(body["previous_observation_sha256"],
                             second["observation_sha256"])
            self.assertEqual(len(list(Path(folder).glob("watch-*.json"))), 3)
            self.assertTrue(third["requires_human_review"])
            self.assertFalse(third["external_send_authorized"])

    def test_receipt_history_rejects_deleted_intermediate_link(self):
        with tempfile.TemporaryDirectory() as folder:
            first = evaluate_and_retain(
                self.baseline, self.case, checked_at=NOW + timedelta(minutes=10),
                receipt_dir=folder,
            )
            first_body = json.loads(Path(first["receipt_path"]).read_text())
            second = evaluate_and_retain(
                self.baseline, self.case, checked_at=NOW + timedelta(minutes=20),
                receipt_dir=folder, previous_observation=first_body,
            )
            Path(first["receipt_path"]).unlink()
            second_body = json.loads(Path(second["receipt_path"]).read_text())
            with self.assertRaisesRegex(ValueError, "broken predecessor chain"):
                evaluate_and_retain(
                    self.baseline, self.case,
                    checked_at=NOW + timedelta(minutes=30),
                    receipt_dir=folder, previous_observation=second_body,
                )

    def test_tampered_saved_receipt_is_blocked_even_with_other_valid_case(self):
        with tempfile.TemporaryDirectory() as folder:
            saved = evaluate_and_retain(
                self.baseline, self.case,
                checked_at=NOW + timedelta(minutes=10), receipt_dir=folder,
            )
            original = Path(saved["receipt_path"])
            body = json.loads(original.read_text())
            body["requires_human_review"] = False
            original.write_text(json.dumps(body), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "content hash mismatch"):
                evaluate_and_retain(
                    self.baseline, self.case,
                    checked_at=NOW + timedelta(minutes=10), receipt_dir=folder,
                )

    def test_same_clock_time_fork_is_rejected(self):
        import copy
        with tempfile.TemporaryDirectory() as folder:
            original = evaluate_and_retain(
                self.baseline, self.case,
                checked_at=NOW + timedelta(minutes=10), receipt_dir=folder,
            )
            changed = copy.deepcopy(self.case)
            changed["packet"]["current_action_id"] = "different"
            with self.assertRaises(ValueError):
                evaluate_and_retain(
                    self.baseline, changed,
                    checked_at=NOW + timedelta(minutes=10), receipt_dir=folder,
                )
            self.assertEqual(len(list(Path(folder).glob("watch-*.json"))), 1)
            self.assertTrue(Path(original["receipt_path"]).exists())

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
            at_deadline_receipt = json.loads(Path(at_deadline["receipt_path"]).read_text())
            expired = evaluate_and_retain(
                self.baseline, self.case,
                checked_at=NOW + timedelta(days=14, seconds=1), receipt_dir=folder,
                previous_observation=at_deadline_receipt,
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
