"""Verify traceability is enforced by the real audit/render/intake/watch paths."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest
from capturebrief_core import audit_case, compare_cases, render_markdown
from capturebrief_core.intake import build_case_from_intake
from capturebrief_core.workqueue import build_work_queue
from capturebrief_core.decision_trace import PROFILE, review_input_digest
from test_audit_watch import case as packet_case
from test_decision_trace import example

NOW = datetime(2026, 9, 21, 13, tzinfo=timezone.utc)


def traced_packet():
    case = packet_case()
    trace = example()
    for key in ("sources", "assumptions", "evidence_profile", "decision_trace"):
        case[key] = trace[key]
    for s in case["sources"]:
        s["observed_at"] = "2026-09-21T12:00:00Z"
    case["decision_trace"]["decision_at"] = "2026-09-21T12:30:00Z"
    for change in case["decision_trace"]["source_changes"]:
        change["recorded_at"] = "2026-09-21T12:00:00Z"
    entry = case["decision_trace"]["assumption_traces"][0]
    entry["review"]["reviewed_at"] = "2026-09-21T12:45:00Z"
    entry["review"]["input_sha256"] = review_input_digest(case, "A1")
    return case


class TraceIntegrationTests(unittest.TestCase):
    def test_full_composed_gate(self):
        result = audit_case(traced_packet(), now=NOW)
        self.assertEqual("READY_FOR_HUMAN_RELEASE", result.release_state, result.findings)

    def test_packet_failure_not_overridden(self):
        c = traced_packet(); c["packet"]["history_receipts"] = []
        self.assertEqual("FAIL_CLOSED", audit_case(c, now=NOW).release_state)

    def test_trace_failure_not_overridden(self):
        c = traced_packet(); c["decision_trace"]["assumption_traces"][0]["review"] = None
        self.assertEqual("FAIL_CLOSED", audit_case(c, now=NOW).release_state)

    def test_main_renderer_includes_history(self):
        c = traced_packet(); result = audit_case(c, now=NOW)
        text = render_markdown(c, result)
        self.assertIn("90-second handoff", text)
        self.assertIn("Assumption source / rule / version history", text)
        self.assertIn("June 2025", text)
        self.assertIn("Reference closure", text)

    def test_existing_watch_gets_targeted_rule_change(self):
        b = traced_packet(); a = deepcopy(b)
        a["decision_trace"]["rule_versions"][0]["version_label"] = "July 2025"
        result = compare_cases(b, a)
        self.assertEqual(["A1"], [r["assumption_id"] for r in result["reopened_assumptions"]])
        self.assertTrue(result["reopened_assumptions"][0]["requires_human_review"])

    def test_work_queue_includes_trace_gaps(self):
        c = traced_packet(); c["decision_trace"]["assumption_traces"][0]["review"] = None
        queue = build_work_queue(c, now=NOW)
        tasks = [t for t in queue["tasks"] if t["task_key"].startswith("decision-trace:")]
        self.assertEqual(1, len(tasks))
        self.assertFalse(tasks[0]["can_auto_execute"])
        self.assertIn("TRACE_HUMAN_REVIEW", tasks[0]["metadata"]["finding_codes"])

    def test_new_intake_uses_trace_profile_without_approval(self):
        intake = {"public_only_confirmation": True, "public_opportunity": "https://sam.gov/opp/demo/view",
                  "current_posture": "GO", "company": "Synthetic company", "email": "reviewer@example.com",
                  "assumption_1": "Two examples suffice."}
        c = build_case_from_intake(intake, submitted_at="2026-09-21T12:00:00Z")
        self.assertEqual(PROFILE, c["evidence_profile"])
        self.assertIsNone(c["decision_trace"]["assumption_traces"][0]["review"])
        self.assertIn("PACKET_REFERENCE_CLOSURE", c["assumptions"][0]["reopen_triggers"])
        self.assertEqual("FAIL_CLOSED", audit_case(c, now=NOW).release_state)

    def test_legacy_case_remains_explicitly_legacy(self):
        c = packet_case(); result = audit_case(c, now=NOW)
        self.assertEqual("READY_FOR_HUMAN_RELEASE", result.release_state)
        self.assertIn("No exact-history claim", render_markdown(c, result))

if __name__ == "__main__":
    unittest.main()
