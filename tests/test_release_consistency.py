"""Integration regressions: real audit/trace/queue/renderers, no green stubs.

Spies retain the real functions. The only simulated behaviour is concurrent
caller/file mutation at a controlled boundary in the two race regressions.
"""
from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from capturebrief_core import delivery_bundle as bundle_module
from capturebrief_core import delivery_readiness as readiness_module
from capturebrief_core import fulfillment_plan as plan_module
from capturebrief_core.decision_trace import canonical, digest, evaluate_decision_trace
from capturebrief_core.delivery_bundle import build_delivery_bundle, build_delivery_files
from capturebrief_core.delivery_readiness import evaluate_delivery_readiness
from capturebrief_core.fulfillment_plan import build_fulfillment_plan
from capturebrief_core.render import render_markdown
from capturebrief_core.trace_render import render_trace_html, render_trace_markdown

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 21, 17, 30, tzinfo=timezone.utc)


def fixture(name: str = "ready_trace_case.json") -> dict:
    return json.loads((ROOT / "fixtures" / name).read_text(encoding="utf-8"))


class ReleaseConsistencyTests(unittest.TestCase):
    def assert_all_reject(self, case: dict, *, now: datetime = NOW) -> None:
        readiness = evaluate_delivery_readiness(case, now=now)
        self.assertFalse(readiness.eligible)
        self.assertTrue(readiness.blocker_codes)
        plan = build_fulfillment_plan(case, now=now)
        self.assertFalse(plan["delivery_bundle_eligible"])
        self.assertNotEqual(plan["fulfillment_state"], "READY_TO_BUILD_DELIVERY")
        self.assertEqual(plan["release_blocker_codes"], list(readiness.blocker_codes))
        with self.assertRaises(ValueError):
            build_delivery_files(case, now=now)

    def test_planner_and_builder_share_the_same_preflight_function(self):
        self.assertIs(plan_module.evaluate_delivery_readiness,
                      readiness_module.evaluate_delivery_readiness)
        self.assertIs(bundle_module.evaluate_delivery_readiness,
                      readiness_module.evaluate_delivery_readiness)

    def test_real_ready_case_is_eligible_and_builds(self):
        case = fixture()
        readiness = evaluate_delivery_readiness(case, now=NOW)
        self.assertTrue(readiness.eligible)
        self.assertEqual(readiness.blocker_codes, ())
        self.assertEqual(readiness.checked_at, NOW)
        plan = build_fulfillment_plan(case, now=NOW)
        self.assertTrue(plan["delivery_bundle_eligible"])
        files = build_delivery_files(case, now=NOW)
        summary = json.loads(files["decision-summary.json"])
        self.assertEqual(summary["release_state"], readiness.audit.release_state)
        self.assertEqual(summary["trace_state"], readiness.trace["trace_state"])
        self.assertEqual(summary["evaluated_at"], plan["delivery_checked_at"])

    def test_legacy_readability_does_not_make_delivery_ready(self):
        self.assert_all_reject(fixture("ready_case.json"))

    def test_missing_trace_rejected_by_every_layer(self):
        case = fixture()
        case.pop("decision_trace")
        self.assert_all_reject(case)

    def test_trace_requirement_needs_literal_true(self):
        for value in (False, None, "true", 1):
            with self.subTest(value=value):
                case = fixture()
                case["decision_trace_required"] = value
                self.assert_all_reject(case)

    def test_synthetic_trace_rejected_by_every_layer(self):
        case = fixture()
        case["decision_trace"]["synthetic"] = True
        self.assert_all_reject(case)

    def test_snapshot_edit_rejected_by_every_layer(self):
        case = fixture()
        case["decision_trace"]["snapshots"][0]["text"] += "\nAltered evidence."
        self.assert_all_reject(case)

    def test_quote_edit_rejected_by_every_layer(self):
        case = fixture()
        case["decision_trace"]["reviews"][0]["citations"][0]["quote"] = "Not retained text."
        self.assert_all_reject(case)

    def test_source_hash_mismatch_rejected_by_every_layer(self):
        case = fixture()
        source_id = case["decision_trace"]["snapshots"][0]["source_id"]
        source = next(s for s in case["sources"] if s["source_id"] == source_id)
        source["content_sha256"] = "0" * 64
        self.assert_all_reject(case)

    def test_missing_currentness_rejected_by_every_layer(self):
        case = fixture()
        case["current_action_receipts"] = []
        self.assert_all_reject(case)

    def test_missing_history_rejected_by_every_layer(self):
        case = fixture()
        case["packet"]["history_receipts"] = []
        self.assert_all_reject(case)

    def test_missing_manifests_rejected_by_every_layer(self):
        case = fixture()
        case["packet"]["manifest_receipts"] = []
        self.assert_all_reject(case)

    def test_future_evidence_rejected_relative_to_declared_clock(self):
        self.assert_all_reject(fixture(), now=datetime(2020, 1, 1, tzinfo=timezone.utc))

    def test_every_rendered_trace_uses_the_preflight_clock(self):
        case = fixture()
        # Spy calls the real evaluator; it does not supply a fabricated verdict.
        with patch("capturebrief_core.trace_render.evaluate_decision_trace",
                   wraps=evaluate_decision_trace) as spy:
            files = build_delivery_files(case, now=NOW)
        self.assertGreaterEqual(spy.call_count, 3)
        for call in spy.call_args_list:
            self.assertEqual(call.kwargs.get("now"), NOW)
        self.assertEqual(files["decision-evidence.md"].decode(),
                         render_trace_markdown(case, now=NOW))
        self.assertEqual(files["decision-evidence.html"].decode(),
                         render_trace_html(case, now=NOW))
        self.assertEqual(files["brief.md"].decode(), render_markdown(case, now=NOW))

    def test_standalone_reports_can_replay_a_declared_clock(self):
        case = fixture()
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        self.assertIn("TRACE_INCOMPLETE", render_trace_markdown(case, now=past))
        self.assertIn("Evidence still needed", render_trace_html(case, now=past))
        self.assertIn("FAIL_CLOSED", render_markdown(case, now=past))
        self.assertIn("TRACE_COMPLETE", render_trace_markdown(case, now=NOW))

    def test_equivalent_timezone_offsets_produce_identical_bundle(self):
        case = fixture()
        local = NOW.astimezone(timezone(timedelta(hours=-4)))
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "utc.zip"
            second = Path(directory) / "offset.zip"
            a = build_delivery_bundle(case, first, now=NOW)
            b = build_delivery_bundle(case, second, now=local)
            self.assertEqual(a["bundle_sha256"], b["bundle_sha256"])
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_receipt_cannot_be_rebound_to_a_later_writers_bytes(self):
        real_publish = bundle_module._publish_completed_zip
        built = {}
        def publish_then_replace(staged, target, *, overwrite):
            built["bytes"] = staged.read_bytes()
            real_publish(staged, target, overwrite=overwrite)
            target.write_bytes(b"A later writer replaced the published path.")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "delivery.zip"
            with patch("capturebrief_core.delivery_bundle._publish_completed_zip",
                       side_effect=publish_then_replace):
                receipt = build_delivery_bundle(fixture(), target, now=NOW)
            self.assertEqual(receipt["bundle_sha256"], digest(built["bytes"]))
            self.assertEqual(receipt["bundle_bytes"], len(built["bytes"]))
            self.assertNotEqual(receipt["bundle_sha256"], digest(target.read_bytes()))
            self.assertEqual(receipt["receipt_scope"], "BUILT_ARTIFACT_NOT_CURRENT_PATH_STATE")
            with zipfile.ZipFile(io.BytesIO(built["bytes"])) as archive:
                manifest = json.loads(archive.read("delivery-manifest.json"))
                self.assertEqual(receipt["case_sha256"], manifest["case_sha256"])

    def test_caller_mutation_does_not_mix_case_versions_in_one_bundle(self):
        case = fixture()
        expected_hash = digest(canonical(case))
        real_build_files = build_delivery_files
        def build_then_mutate(snapshot, *, now):
            files = real_build_files(snapshot, now=now)
            case["intake"] = {"note": "Caller changed its working copy after rendering."}
            return files
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "delivery.zip"
            with patch("capturebrief_core.delivery_bundle.build_delivery_files",
                       side_effect=build_then_mutate):
                receipt = build_delivery_bundle(case, target, now=NOW)
            with zipfile.ZipFile(target) as archive:
                manifest = json.loads(archive.read("delivery-manifest.json"))
                summary = json.loads(archive.read("decision-summary.json"))
            self.assertEqual(receipt["case_sha256"], expected_hash)
            self.assertEqual(manifest["case_sha256"], expected_hash)
            self.assertEqual(summary["case_sha256"], expected_hash)
            self.assertNotEqual(digest(canonical(case)), expected_hash)

    def test_preflight_and_bundle_do_not_modify_the_input_or_grant_send_permission(self):
        case = fixture()
        original = copy.deepcopy(case)
        evaluate_delivery_readiness(case, now=NOW)
        plan = build_fulfillment_plan(case, now=NOW)
        with tempfile.TemporaryDirectory() as directory:
            receipt = build_delivery_bundle(case, Path(directory) / "delivery.zip", now=NOW)
        self.assertEqual(case, original)
        self.assertFalse(plan["communications"]["external_send_authorized"])
        self.assertFalse(receipt["external_send_authorized"])
        self.assertFalse(json.loads(build_delivery_files(case, now=NOW)["decision-summary.json"])
                         ["external_send_authorized"])

    def test_invalid_clock_or_nonobject_case_stops(self):
        for clock in (datetime(2026, 9, 21), "2026-09-21", False):
            with self.subTest(clock=clock):
                with self.assertRaises(ValueError):
                    evaluate_delivery_readiness(fixture(), now=clock)
        with self.assertRaises(ValueError):
            evaluate_delivery_readiness([], now=NOW)


if __name__ == "__main__":
    unittest.main()
