from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from capturebrief_core.decision_trace import canonical, digest
from capturebrief_core.watch_baseline import build_watch_baseline, compare_watch_baseline

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,9,21,17,30,tzinfo=timezone.utc)


def ready_case():
    return json.loads((ROOT/"fixtures"/"ready_trace_case.json").read_text(encoding="utf-8"))


class WatchBaselineTests(unittest.TestCase):
    def test_unchanged_case_has_no_watch_events(self):
        case=ready_case()
        baseline=build_watch_baseline(case,now=NOW)
        result=compare_watch_baseline(baseline,case,now=NOW)
        self.assertEqual(result["events"],[])
        self.assertEqual(result["reopened_assumptions"],[])
        self.assertFalse(result["requires_human_review"])
        self.assertFalse(result["automatic_decision_change"])
        self.assertTrue(result["previous_decision_preserved"])

    def test_artifact_change_reopens_only_triggered_assumption(self):
        case=ready_case()
        baseline=build_watch_baseline(case,now=NOW)
        after=copy.deepcopy(case)
        after["packet"]["artifacts"][0]["sha256"]="d"*64
        result=compare_watch_baseline(baseline,after,now=NOW)
        self.assertIn("ARTIFACT:resource-current",{e["key"] for e in result["events"]})
        self.assertEqual([x["assumption_id"] for x in result["reopened_assumptions"]],["A1"])
        self.assertIn("ARTIFACT:resource-current",result["reopened_assumptions"][0]["matched_dependencies"])
        self.assertTrue(result["requires_human_review"])
        self.assertFalse(result["automatic_decision_change"])

    def test_new_source_version_reopens_direct_dependency(self):
        case=ready_case()
        baseline=build_watch_baseline(case,now=NOW)
        after=copy.deepcopy(case)
        snap=copy.deepcopy(after["decision_trace"]["snapshots"][0])
        snap["version_label"]="Later observed version"
        snap["observed_at"]="2026-09-21T17:20:00+00:00"
        snap["snapshot_id"]="SNAP:"+digest(canonical({k:v for k,v in snap.items() if k!="snapshot_id"}))
        after["decision_trace"]["snapshots"].append(snap)
        result=compare_watch_baseline(baseline,after,now=NOW)
        self.assertIn("SOURCE:DEMO-FAMILY-001:CURRENT",{e["key"] for e in result["events"]})
        self.assertEqual(result["reopened_assumptions"][0]["assumption_id"],"A1")
        self.assertTrue(result["reopened_assumptions"][0]["previous_decision_preserved"])

    def test_baseline_is_minimal_and_contains_no_source_text_or_intake(self):
        case=ready_case()
        case["intake"]={"email":"buyer@example.com","company":"Buyer"}
        baseline=build_watch_baseline(case,now=NOW)
        raw=json.dumps(baseline,sort_keys=True)
        self.assertNotIn("buyer@example.com",raw)
        self.assertNotIn("Fixture current solicitation controls the working baseline.",raw)
        self.assertFalse(baseline["contains_raw_case"])
        self.assertFalse(baseline["contains_source_text"])

    def test_baseline_tamper_is_rejected(self):
        case=ready_case()
        baseline=build_watch_baseline(case,now=NOW)
        baseline["state"]["history_set_sha256"]="0"*64
        with self.assertRaises(ValueError):
            compare_watch_baseline(baseline,case,now=NOW)

    def test_different_pursuit_is_rejected(self):
        case=ready_case()
        baseline=build_watch_baseline(case,now=NOW)
        other=copy.deepcopy(case); other["case_id"]="OTHER"
        with self.assertRaises(ValueError):
            compare_watch_baseline(baseline,other,now=NOW)

    def test_trace_tamper_becomes_integrity_finding(self):
        case=ready_case()
        baseline=build_watch_baseline(case,now=NOW)
        after=copy.deepcopy(case)
        after["decision_trace"]["reviews"][0]["citations"][0]["quote"]="tampered"
        result=compare_watch_baseline(baseline,after,now=NOW)
        self.assertTrue(result["integrity_findings"])
        self.assertTrue(result["requires_human_review"])


if __name__=="__main__":
    unittest.main()
