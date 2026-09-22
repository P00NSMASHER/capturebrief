from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from capturebrief_core.decision_trace import evaluate_decision_trace
from capturebrief_core.outcomes import append_outcome_event, make_outcome_event, summarize_outcomes
from capturebrief_core.watch_baseline import build_watch_baseline

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,9,21,17,30,tzinfo=timezone.utc)
CASE_SHA="a"*64
OTHER_CASE_SHA="c"*64
BUNDLE_SHA="b"*64


def ready_case():
    return json.loads((ROOT/"fixtures/ready_trace_case.json").read_text())


def outcome(kind, *, case_id="CB-RT", case_sha256=CASE_SHA, bundle=BUNDLE_SHA,
            at="2026-09-21T18:00:00Z", **data):
    return make_outcome_event(
        case_id=case_id, case_sha256=case_sha256,
        delivery_bundle_sha256=bundle, event_type=kind, event_at=at, data=data,
    )


class TruthLayerRedTeamTests(unittest.TestCase):
    def test_supported_claim_cannot_be_complete_with_zero_exact_citations(self):
        case=ready_case()
        case["decision_trace"]["reviews"][0]["citations"]=[]
        report=evaluate_decision_trace(case,now=NOW)
        self.assertEqual(report["trace_state"],"TRACE_INCOMPLETE")
        self.assertIn("TRACE_RESOLVED_EVIDENCE_MISSING",
                      {x["code"] for x in report["findings"]})

    def test_supported_claim_needs_a_supporting_not_merely_context_citation(self):
        case=ready_case()
        case["decision_trace"]["reviews"][0]["citations"][0]["role"]="CONTEXT"
        report=evaluate_decision_trace(case,now=NOW)
        self.assertEqual(report["trace_state"],"TRACE_INCOMPLETE")
        self.assertIn("TRACE_RESOLVED_EVIDENCE_ROLE_MISSING",
                      {x["code"] for x in report["findings"]})

    def test_watch_cli_signals_review_required_to_automation(self):
        case=ready_case()
        baseline=build_watch_baseline(case,now=NOW)
        changed=copy.deepcopy(case)
        changed["decision_trace"]["snapshots"][0]["text"]+="\nTampered after release."
        with tempfile.TemporaryDirectory() as directory:
            baseline_path=Path(directory)/"baseline.json"
            case_path=Path(directory)/"changed.json"
            baseline_path.write_text(json.dumps(baseline))
            case_path.write_text(json.dumps(changed))
            result=subprocess.run(
                [sys.executable,"-m","capturebrief_core.trace_cli","watch-check",
                 str(baseline_path),str(case_path)],
                cwd=ROOT,capture_output=True,text=True,timeout=30,
            )
        payload=json.loads(result.stdout)
        self.assertTrue(payload["requires_human_review"])
        self.assertTrue(payload["integrity_findings"])
        self.assertEqual(result.returncode,3,
                         "watch-check must not look green to unattended automation when review is required")

    def test_outcome_case_id_cannot_mix_different_case_fingerprints(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger=Path(directory)/"outcomes.jsonl"
            append_outcome_event(ledger,outcome("PAYMENT",state="PAID",
                payment_evidence_ref="stripe:rt1"),recorded_at="2026-09-21T18:01:00Z")
            append_outcome_event(ledger,outcome("DELIVERY",case_sha256=OTHER_CASE_SHA,
                at="2026-09-21T19:00:00Z",started_at="2026-09-21T18:00:00Z",
                delivered_at="2026-09-21T19:00:00Z",delivery_evidence_ref="bundle:rt1"),
                recorded_at="2026-09-21T19:01:00Z")
            with self.assertRaisesRegex(ValueError,"case fingerprint"):
                summarize_outcomes(ledger)

    def test_feedback_cannot_count_without_a_matching_delivered_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger=Path(directory)/"outcomes.jsonl"
            append_outcome_event(ledger,outcome("FEEDBACK",
                usefulness="USEFUL",action_effect="CHANGED_ACTION",source_limited=False,
                finding_classes=["SOURCE_VERSION"],feedback_evidence_ref="feedback:rt1"),
                recorded_at="2026-09-21T18:01:00Z")
            summary=summarize_outcomes(ledger)
        self.assertEqual(summary["buyer_feedback_cases"],0)
        self.assertEqual(summary["feedback"]["changed_action"],0)
        self.assertGreater(summary["unbound_outcome_events"],0)

    def test_repeat_request_cannot_count_without_a_matching_delivered_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger=Path(directory)/"outcomes.jsonl"
            append_outcome_event(ledger,outcome("REPEAT_REQUEST",
                state="REQUESTED_REPEAT",repeat_evidence_ref="feedback:rt2"),
                recorded_at="2026-09-21T18:01:00Z")
            summary=summarize_outcomes(ledger)
        self.assertEqual(summary["repeat"]["requested_repeat"],0)
        self.assertGreater(summary["unbound_outcome_events"],0)


if __name__=="__main__":
    unittest.main()
