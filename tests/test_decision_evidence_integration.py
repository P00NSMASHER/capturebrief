from __future__ import annotations
import copy, json, unittest
from pathlib import Path

from capturebrief_core.audit import audit_case
from capturebrief_core.intake import build_case_from_intake
from capturebrief_core.render import render_markdown
from capturebrief_core.workqueue import build_work_queue

ROOT=Path(__file__).resolve().parents[1]

class DecisionEvidenceIntegrationTests(unittest.TestCase):
    def ready(self):
        return json.loads((ROOT/"fixtures"/"ready_case.json").read_text())

    def test_new_intake_requires_decision_trace(self):
        case=build_case_from_intake({
            "public_only_confirmation": True,
            "public_opportunity": "https://sam.gov/opp/example/view",
            "current_posture": "GO",
            "company": "Example Co",
            "email": "buyer@example.com",
            "assumption_1": "The current page limit is 20 pages.",
        },submitted_at="2026-09-21T15:00:00+00:00")
        self.assertTrue(case["decision_trace_required"])
        codes={x.code for x in audit_case(case).findings}
        self.assertIn("TRACE_MISSING",codes)
        self.assertIn("DECISION_TRACE_NOT_RELEASE_READY",codes)
        tasks={x["task_key"] for x in build_work_queue(case)["tasks"]}
        self.assertIn("trace:integrity",tasks)

    def test_legacy_ready_fixture_stays_backward_compatible(self):
        self.assertEqual(audit_case(self.ready()).release_state,"READY_FOR_HUMAN_RELEASE")

    def test_ready_case_fails_closed_when_trace_is_required(self):
        case=self.ready()
        case["decision_trace_required"]=True
        result=audit_case(case)
        self.assertEqual(result.release_state,"FAIL_CLOSED")
        self.assertIn("TRACE_MISSING",{x.code for x in result.findings})

    def test_buyer_report_surfaces_missing_trace(self):
        case=self.ready()
        case["decision_trace_required"]=True
        report=render_markdown(case)
        self.assertIn("## Decision evidence",report)
        self.assertIn("TRACE_MISSING",report)

    def test_work_queue_surfaces_trace_review(self):
        case=self.ready()
        case["decision_trace_required"]=True
        queue=build_work_queue(case)
        trace=[x for x in queue["tasks"] if x["task_key"].startswith("trace:")]
        self.assertTrue(trace)
        self.assertTrue(all(x["actor"]=="HUMAN_REVIEW" for x in trace))
        self.assertTrue(all(x["can_auto_execute"] is False for x in trace))

if __name__=="__main__":
    unittest.main()
