from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from capturebrief_core.decision_trace import canonical, digest, evaluate_decision_trace, freeze_rule_version, passage
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

    def test_snapshot_observed_after_decision_cannot_support_that_decision(self):
        case=ready_case()
        snapshot=case["decision_trace"]["snapshots"][0]
        source=next(x for x in case["sources"] if x["source_id"]==snapshot["source_id"])
        snapshot["observed_at"]="2026-09-21T13:10:00+00:00"
        source["observed_at"]="2026-09-21T13:10:00+00:00"
        snapshot["snapshot_id"]="SNAP:"+digest(canonical({k:v for k,v in snapshot.items() if k!="snapshot_id"}))
        case["decision_trace"]["reviews"][0]["citations"][0]["snapshot_id"]=snapshot["snapshot_id"]
        report=evaluate_decision_trace(case,now=NOW)
        self.assertIn("TRACE_LOOKAHEAD_DECISION_EVIDENCE",{x["code"] for x in report["findings"]})
        self.assertEqual(report["trace_state"],"TRACE_INCOMPLETE")

    def test_snapshot_url_must_match_its_bound_source_url(self):
        case=ready_case()
        snapshot=case["decision_trace"]["snapshots"][0]
        snapshot["url"]="https://example.org/substituted-source"
        snapshot["snapshot_id"]="SNAP:"+digest(canonical({k:v for k,v in snapshot.items() if k!="snapshot_id"}))
        case["decision_trace"]["reviews"][0]["citations"][0]["snapshot_id"]=snapshot["snapshot_id"]
        report=evaluate_decision_trace(case,now=NOW)
        self.assertIn("TRACE_SOURCE_METADATA_MISMATCH",{x["code"] for x in report["findings"]})
        self.assertEqual(report["trace_state"],"TRACE_INCOMPLETE")

    def test_review_after_declared_decision_time_is_not_historical_evidence(self):
        case=ready_case()
        case["decision_trace"]["reviews"][0]["reviewed_at"]="2026-09-21T13:10:00+00:00"
        report=evaluate_decision_trace(case,now=NOW)
        self.assertIn("TRACE_REVIEW_AFTER_DECISION",{x["code"] for x in report["findings"]})
        self.assertEqual(report["trace_state"],"TRACE_INCOMPLETE")

    def test_resolved_finding_cannot_hide_unresolved_rule_scope(self):
        case=ready_case()
        review=case["decision_trace"]["reviews"][0]
        review["rule_scope"]={"status":"UNRESOLVED","rationale":"Applicability has not been resolved."}
        report=evaluate_decision_trace(case,now=NOW)
        self.assertIn("TRACE_RESOLVED_RULE_SCOPE_UNRESOLVED",{x["code"] for x in report["findings"]})
        self.assertEqual(report["trace_state"],"TRACE_INCOMPLETE")

    def _add_rule(self,case):
        snapshot=case["decision_trace"]["snapshots"][0]
        rule=freeze_rule_version(
            namespace="FAR",citation="52.204-21",edition="2026-01",agency="FAR Council",
            text_passage=passage(snapshot,1,1,locator="fixture line 1"),
            effective_from="2026-01-01",
        )
        case["decision_trace"]["rule_versions"].append(rule)
        case["decision_trace"]["reviews"][0]["rule_scope"]={
            "status":"REQUIRED","rationale":"Red-team fixture requires a reviewed rule."
        }
        return rule

    def test_resolved_finding_cannot_hide_unresolved_rule_applicability(self):
        case=ready_case()
        rule=self._add_rule(case)
        case["decision_trace"]["reviews"][0]["rule_links"]=[{
            "rule_version_id":rule["rule_version_id"],"family_id":case["family_id"],
            "applicability":"UNRESOLVED","basis":"PENDING_REVIEW",
            "rationale":"No applicability conclusion yet."
        }]
        report=evaluate_decision_trace(case,now=NOW)
        self.assertIn("TRACE_RESOLVED_RULE_APPLICABILITY_UNRESOLVED",
                      {x["code"] for x in report["findings"]})
        self.assertEqual(report["trace_state"],"TRACE_INCOMPLETE")

    def test_resolved_rule_applicability_requires_exact_pursuit_basis(self):
        case=ready_case()
        rule=self._add_rule(case)
        case["decision_trace"]["reviews"][0]["rule_links"]=[{
            "rule_version_id":rule["rule_version_id"],"family_id":case["family_id"],
            "applicability":"APPLIES","basis":"SOLICITATION_REVIEW",
            "rationale":"Reviewer says it applies, but no exact basis passage is retained."
        }]
        report=evaluate_decision_trace(case,now=NOW)
        self.assertIn("TRACE_RULE_BASIS_PASSAGE_MISSING",
                      {x["code"] for x in report["findings"]})
        self.assertEqual(report["trace_state"],"TRACE_INCOMPLETE")

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

    def test_rule_version_text_cannot_be_backed_by_solicitation_text(self):
        case=ready_case()
        snapshot=case["decision_trace"]["snapshots"][0]
        fake_rule=freeze_rule_version(
            namespace="FAR",citation="52.999-1",edition="2026-01",agency="FAR Council",
            text_passage=passage(snapshot,1,1,locator="not actually a rule"),
            effective_from=None,
        )
        case["decision_trace"]["rule_versions"].append(fake_rule)
        report=evaluate_decision_trace(case,now=NOW)
        self.assertIn("TRACE_RULE_TEXT_SOURCE_KIND_INVALID",
                      {x["code"] for x in report["findings"]})
        self.assertEqual(report["trace_state"],"TRACE_INCOMPLETE")

    def test_version_relationship_needs_exact_authority_evidence(self):
        case=ready_case()
        old=case["decision_trace"]["snapshots"][0]
        new_text="Amendment 02 replaces the prior working baseline."
        source={
            "source_id":"trace-amendment",
            "title":"Fixture amendment",
            "url":"https://sam.gov/opp/example/amendment",
            "authority":"SUPPORTING",
            "artifact_state":"PUBLIC",
            "observed_at":"2026-09-21T13:02:00+00:00",
            "content_sha256":digest(new_text),
        }
        from capturebrief_core.decision_trace import freeze_text_snapshot
        new=freeze_text_snapshot(
            source=source,source_key=old["source_key"],kind="AMENDMENT",
            version_label="Amendment 02",text=new_text,capture_method="NATIVE_TEXT",
            captured_by="Reviewer",mapping_note="Red-team version relation fixture.",
        )
        case["sources"].append(source)
        case["assumptions"][0]["source_ids"].append(source["source_id"])
        case["decision_trace"]["snapshots"].append(new)
        case["decision_trace"]["reviews"][0]["changes"]=[{
            "from_snapshot_id":old["snapshot_id"],
            "to_snapshot_id":new["snapshot_id"],
            "relation":"AMENDS",
            "summary":"The amendment replaces the prior baseline.",
            "from_passage":passage(old,1,1,locator="prior baseline"),
            "to_passage":passage(new,1,1,locator="amendment"),
        }]
        report=evaluate_decision_trace(case,now=NOW)
        self.assertIn("TRACE_CHANGE_AUTHORITY_MISSING",
                      {x["code"] for x in report["findings"]})
        self.assertEqual(report["trace_state"],"TRACE_INCOMPLETE")

    def test_watch_cannot_claim_clean_without_a_fresh_observation(self):
        case=ready_case()
        baseline=build_watch_baseline(case,now=NOW)
        later=NOW.replace(day=22)
        from capturebrief_core.watch_baseline import compare_watch_baseline
        result=compare_watch_baseline(baseline,case,now=later)
        self.assertTrue(result["requires_human_review"])
        self.assertIn("WATCH_NO_FRESH_OBSERVATION",{x["type"] for x in result["events"]})
        self.assertEqual(result["watch_status"],"REVIEW_REQUIRED")

    def test_expired_currentness_must_be_visible_even_if_ids_do_not_change(self):
        case=ready_case()
        case["current_action_receipts"][0]["expires_at"]="2026-09-22T13:00:00+00:00"
        baseline=build_watch_baseline(case,now=NOW)
        from capturebrief_core.watch_baseline import compare_watch_baseline
        result=compare_watch_baseline(
            baseline,case,now=datetime(2026,9,23,17,30,tzinfo=timezone.utc)
        )
        kinds={x["type"] for x in result["events"]}
        self.assertIn("CURRENTNESS_VERDICT_CHANGED",kinds)
        self.assertTrue(result["requires_human_review"])

    def test_fourteen_day_watch_cannot_silently_continue_after_scope_ends(self):
        case=ready_case()
        baseline=build_watch_baseline(case,now=NOW)
        self.assertEqual(baseline["watch_until"],"2026-10-05T17:30:00Z")
        from capturebrief_core.watch_baseline import compare_watch_baseline
        result=compare_watch_baseline(
            baseline,case,now=datetime(2026,10,6,17,30,tzinfo=timezone.utc)
        )
        self.assertEqual(result["watch_status"],"EXPIRED")
        self.assertIn("WATCH_WINDOW_EXPIRED",{x["type"] for x in result["events"]})
        self.assertTrue(result["requires_human_review"])

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
