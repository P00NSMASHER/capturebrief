"""No-spend official-source watch-cycle regression tests.

Provider replies are deterministic fakes. No API key is real and no live
provider, email, Stripe account, user data, scheduler or deployment is touched.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from capturebrief_core.decision_trace import canonical, digest
from capturebrief_core.watch_baseline import WATCH_SCHEMA, _public_state
from scripts.run_current_watch_cycle import REPOSITORY, execute
from tests.test_current_search import FakeResponse, api_payload, case as make_case


def baseline(case: dict, *, now: datetime) -> dict:
    created = now - timedelta(minutes=5)
    payload = {
        "schema_version": WATCH_SCHEMA,
        "case_id": case["case_id"],
        "family_id": case["family_id"],
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "watch_until": (created + timedelta(days=14)).isoformat().replace("+00:00", "Z"),
        "case_sha256": digest(canonical(case)),
        "state": _public_state(case, now=created),
        "contains_raw_case": False,
        "contains_source_text": False,
        "automatic_decision_change": False,
    }
    return {**payload, "baseline_sha256": digest(canonical(payload))}


class CurrentWatchCycleTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.case = make_case()
        self.baseline = baseline(self.case, now=self.now)

    @staticmethod
    def present(req, timeout=30):
        return FakeResponse(api_payload())

    @staticmethod
    def missing(req, timeout=30):
        return FakeResponse({
            "totalRecords": 0,
            "limit": 100,
            "offset": 0,
            "opportunitiesData": [],
        })

    def test_fresh_sam_api_check_produces_private_review_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            new_case = root / "case-updated.json"
            result = execute(
                self.case, self.baseline, api_key="fake-test-only",
                updated_case_path=str(new_case), receipt_dir=str(root / "receipts"),
                opener=self.present,
            )
            self.assertEqual(result["status"], "CURRENT_API_CHECK_REVIEW_REQUIRED")
            self.assertTrue(new_case.is_file())
            self.assertTrue(Path(result["watch_receipt_path"]).is_file())
            self.assertFalse(result["all_watch_sources_refreshed"])
            self.assertFalse(result["external_send_authorized"])
            updated = json.loads(new_case.read_text())
            self.assertEqual(updated["packet"]["family_status"], "ACTIVE")
            self.assertEqual(updated["assumptions"], self.case["assumptions"])
            self.assertEqual(len(updated["current_action_receipts"]), 1)
            self.assertIn("sam-current-api", {s["source_id"] for s in updated["sources"]})
            report = json.loads(Path(result["watch_receipt_path"]).read_text())
            self.assertTrue(report["requires_human_review"])
            self.assertNotEqual(report["watch_status"], "NO_CHANGE_OBSERVED")
            self.assertNotIn("fake-test-only", new_case.read_text())
            self.assertNotIn("fake-test-only", json.dumps(report))

    def test_rejected_watch_lineage_cannot_publish_refreshed_case(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            receipt_dir = root / "receipts"
            initial = root / "first-case.json"
            result = execute(
                self.case, self.baseline, api_key="fake-test-only",
                updated_case_path=str(initial), receipt_dir=str(receipt_dir),
                opener=self.present,
            )
            self.assertTrue(Path(result["watch_receipt_path"]).exists())
            subsequent = root / "second-case.json"
            # The receipt directory now contains a prior watch result. A
            # later check cannot skip it and still publish a new case file.
            with self.assertRaisesRegex(ValueError, "latest retained receipt"):
                execute(
                    self.case, self.baseline, api_key="fake-test-only",
                    updated_case_path=str(subsequent),
                    receipt_dir=str(receipt_dir),
                    checked_at=datetime.now(timezone.utc) + timedelta(minutes=1),
                    opener=self.present,
                )
            self.assertFalse(subsequent.exists())
            self.assertEqual(len(list(receipt_dir.glob("watch-*.json"))), 1)

    def test_missing_active_api_match_stays_review_required_not_terminal(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "updated.json"
            result = execute(
                self.case, self.baseline, api_key="fake-test-only",
                updated_case_path=str(output), receipt_dir=str(root / "receipts"),
                opener=self.missing,
            )
            self.assertEqual(result["status"], "CURRENT_SOURCE_REVIEW_REQUIRED")
            self.assertFalse(result["case_published_as_refreshed"])
            self.assertFalse(result["external_send_authorized"])
            self.assertFalse(output.exists())
            receipt = json.loads(Path(result["event_receipt_path"]).read_text())
            self.assertFalse(receipt["currentness_inferred"])
            self.assertEqual(receipt["reason"], "NO_VERIFIED_CURRENT_ACTION")

    def test_rejects_unsupported_forged_case_before_external_fetch(self):
        wrong_case = copy.deepcopy(self.case)
        wrong_case["packet"]["history_receipts"] = []
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(RuntimeError):
                execute(wrong_case, self.baseline, api_key="fake-test-only",
                        updated_case_path=str(root / "updated.json"),
                        receipt_dir=str(root / "receipts"), opener=self.present)
            self.assertFalse((root / "updated.json").exists())

    def test_tampered_baseline_stops_case_publication(self):
        fake = copy.deepcopy(self.baseline)
        fake["state"]["history_set_sha256"] = "0"*64
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(ValueError):
                execute(self.case, fake, api_key="fake-test-only",
                        updated_case_path=str(root / "updated.json"),
                        receipt_dir=str(root / "receipts"),
                        opener=lambda req, timeout=30: self.fail("No API fetch for invalid baseline"))
            self.assertFalse((root / "updated.json").exists())

    def test_mismatched_baseline_pursuit_blocks_before_source_fetch(self):
        unrelated = copy.deepcopy(self.baseline)
        unrelated["case_id"] = "DIFFERENT"
        payload = {k:v for k,v in unrelated.items() if k != "baseline_sha256"}
        unrelated["baseline_sha256"] = digest(canonical(payload))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaisesRegex(ValueError, "different pursuit"):
                execute(self.case, unrelated, api_key="fake-test-only",
                        updated_case_path=str(root / "updated.json"),
                        receipt_dir=str(root / "receipts"),
                        opener=lambda req, timeout=30: self.fail("No API fetch for wrong pursuit"))
            self.assertFalse((root / "updated.json").exists())

    def test_future_provider_observation_cannot_be_backdated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(ValueError):
                execute(self.case, self.baseline, api_key="fake-test-only",
                        checked_at=self.now - timedelta(minutes=20),
                        updated_case_path=str(root / "updated.json"),
                        receipt_dir=str(root / "receipts"), opener=self.present)
            self.assertFalse((root / "updated.json").exists())

    def test_no_key_and_public_repo_path_rejected_without_network(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(ValueError):
                execute(self.case, self.baseline, api_key="",
                        updated_case_path=str(root / "updated.json"),
                        receipt_dir=str(root / "receipts"), opener=self.present)
            with self.assertRaisesRegex(ValueError, "outside the public repository"):
                execute(self.case, self.baseline, api_key="fake-test-only",
                        updated_case_path=str(REPOSITORY / "customer-case.json"),
                        receipt_dir=str(root / "receipts"),
                        opener=lambda **kw: self.fail("No source fetch may occur"))

    def test_cli_missing_sam_key_fails_without_logging_sensitive_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            case_path = root / "case.json"
            baseline_path = root / "baseline.json"
            case_path.write_text(json.dumps(self.case))
            baseline_path.write_text(json.dumps(self.baseline))
            env = dict(os.environ)
            env.pop("SAM_API_KEY", None)
            result = subprocess.run(
                [sys.executable, "scripts/run_current_watch_cycle.py",
                 str(case_path), str(baseline_path),
                 "--updated-case", str(root / "out.json"),
                 "--receipt-dir", str(root / "receipts")],
                cwd=REPOSITORY, env=env, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 3)
            self.assertEqual(json.loads(result.stdout)["status"], "WATCH_CYCLE_BLOCKED")
            self.assertFalse((root / "out.json").exists())


if __name__ == "__main__":
    unittest.main()
