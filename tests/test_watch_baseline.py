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
        self.assertIn("RESOURCE:resource-current",result["reopened_assumptions"][0]["matched_dependencies"])
        event=next(e for e in result["events"] if e["key"]=="ARTIFACT:resource-current")
        self.assertIn("RESOURCE:resource-current",event["alias_keys"])
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


    def test_second_check_needs_each_source_newer_than_previous_not_just_delivery(self):
        from datetime import timedelta
        case = ready_case()
        baseline = build_watch_baseline(case, now=NOW)
        day_one = NOW + timedelta(minutes=20)
        day_two = NOW + timedelta(minutes=40)
        once = copy.deepcopy(case)
        for source in once["sources"]:
            source["observed_at"] = day_one.isoformat()
        first = compare_watch_baseline(baseline, once, now=day_one)
        self.assertEqual(first["source_checks"]["trace-source"]["observed_at"],
                         day_one.isoformat())
        # A second comparison with only the delivered baseline could
        # mistakenly treat yesterday's timestamps as fresh.
        repeated = compare_watch_baseline(
            baseline, once, now=day_two, previous_observation=first,
        )
        self.assertIn("WATCH_SOURCE_NOT_REFRESHED_SINCE_PREVIOUS_CHECK",
                      {event["type"] for event in repeated["events"]})
        self.assertFalse(repeated["fresh_observation_evidenced"])
        self.assertTrue(repeated["requires_human_review"])
        self.assertEqual(repeated["previous_observation_sha256"],
                         first["observation_sha256"])
        self.assertFalse(repeated["automatic_decision_change"])

    def test_previous_watch_receipt_must_be_untampered_and_chronologically_before(self):
        from datetime import timedelta
        case = ready_case()
        baseline = build_watch_baseline(case, now=NOW)
        newer = NOW + timedelta(minutes=15)
        first = compare_watch_baseline(baseline, case, now=newer)
        forged = copy.deepcopy(first)
        forged["source_checks"]["trace-source"]["observed_at"] = (
            newer + timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            compare_watch_baseline(baseline, case,
                                   now=newer + timedelta(minutes=2),
                                   previous_observation=forged)
        with self.assertRaisesRegex(ValueError, "not earlier"):
            compare_watch_baseline(baseline, case, now=newer,
                                   previous_observation=first)
        wrong = copy.deepcopy(first)
        wrong["baseline_sha256"] = "0"*64
        wrong["observation_sha256"] = digest(canonical({
            k:v for k,v in wrong.items() if k!="observation_sha256"
        }))
        with self.assertRaisesRegex(ValueError, "different pursuit/baseline"):
            compare_watch_baseline(baseline, case,
                                   now=newer + timedelta(minutes=2),
                                   previous_observation=wrong)

    def test_one_fresh_source_does_not_clear_other_stale_sources(self):
        from datetime import timedelta
        case=ready_case()
        baseline=build_watch_baseline(case,now=NOW)
        after=copy.deepcopy(case)
        later=NOW+timedelta(minutes=20)
        after["sources"][0]["observed_at"]=later.isoformat()
        result=compare_watch_baseline(baseline,after,now=later)
        stale={e["source_id"] for e in result["events"] if e["type"]=="WATCH_SOURCE_NOT_REFRESHED"}
        self.assertIn("trace-source",stale)
        self.assertNotIn("sam-current",stale)
        # An assumption citing the unrefreshed source cannot keep its
        # prior reviewed state without reopening to human inspection.
        reopen = next(item for item in result["reopened_assumptions"]
                      if item["assumption_id"] == "A1")
        self.assertIn("SOURCE_CHECK:trace-source", reopen["matched_dependencies"])
        self.assertTrue(reopen["previous_decision_preserved"])
        self.assertTrue(result["requires_human_review"])
        self.assertNotEqual(result["watch_status"],"NO_CHANGE_OBSERVED")

    def test_raw_source_fingerprint_change_reopens_trace_dependency(self):
        case=ready_case()
        baseline=build_watch_baseline(case,now=NOW)
        after=copy.deepcopy(case)
        for source in after["sources"]:
            if source["source_id"]=="trace-source":
                source["content_sha256"]="f"*64
        result=compare_watch_baseline(baseline,after,now=NOW)
        self.assertIn("SOURCE_RECORD:trace-source",{e["key"] for e in result["events"]})
        reopened=next(r for r in result["reopened_assumptions"] if r["assumption_id"]=="A1")
        self.assertIn("SOURCE_RECORD:trace-source",reopened["matched_dependencies"])
        self.assertTrue(result["requires_human_review"])
        self.assertFalse(result["automatic_decision_change"])

    def test_future_dated_source_refresh_is_not_valid_freshness(self):
        from datetime import timedelta
        case=ready_case()
        baseline=build_watch_baseline(case,now=NOW)
        after=copy.deepcopy(case)
        later=NOW+timedelta(minutes=1)
        for source in after["sources"]:
            source["observed_at"]=(later+timedelta(days=1)).isoformat()
        result=compare_watch_baseline(baseline,after,now=later)
        self.assertEqual(sum(e["type"]=="WATCH_SOURCE_NOT_REFRESHED" for e in result["events"]),len(after["sources"]))
        self.assertTrue(result["requires_human_review"])

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
