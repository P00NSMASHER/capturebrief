"""CaptureBrief 2.0 action-first buyer deliverable acceptance.

This is product-format QA, not acceptance of a real customer's source history,
private intake, provider delivery or unattended source interpretations.
"""
from __future__ import annotations

import hashlib
import html
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone

from capturebrief_core.action_brief_v2 import render_action_brief_v2
from capturebrief_core.delivery_bundle import build_delivery_files
from tests.test_delivery_bundle import ready_case

NOW = datetime(2026, 9, 21, 17, 30, tzinfo=timezone.utc)


@dataclass
class FakeAudit:
    release_state: str = "READY_FOR_HUMAN_RELEASE"
    currentness_verdict: str = "CURRENT_VERIFIED"
    current_action_id: str = "ACTION-CURRENT-01"


class ActionBriefV2Tests(unittest.TestCase):
    def test_valid_case_receives_print_ready_v2_html_and_retains_source_pack(self):
        files = build_delivery_files(ready_case(), now=NOW)
        self.assertIn("action-brief.html", files)
        text = files["action-brief.html"].decode()
        self.assertIn("CaptureBrief 2.0", text)
        self.assertIn("<!doctype html>", text.lower())
        self.assertIn("90-second decision brief", text)
        self.assertIn("A1", text)
        self.assertIn("What we found", text)
        self.assertIn("What to do", text)
        self.assertIn("Source trail", text)
        self.assertIn("decision-evidence.html", text)
        self.assertIn("@media print", text)
        self.assertIn("Not a bid decision", text)
        self.assertNotIn("customer@example.com", text)
        self.assertNotIn("https://buy.stripe.com/", text)
        self.assertTrue(files["decision-evidence.html"])
        self.assertTrue(files["brief.md"])
        self.assertTrue(files["source-version-manifest.json"])

    def test_source_and_buyer_text_are_html_escaped_no_scripts_or_trackers(self):
        case = {"case_id": "CASE-<script>alert(9)</script>",
                "family_id": "FAMILY-A", "current_posture": "HOLD"}
        cards = [{
            "assumption_id": "A1",
            "assumption": "<img src=x onerror=alert(1)>",
            "evidence_state": "CONTRADICTED",
            "decision_class": "GATE_CHANGING",
            "finding": "<script>bad()</script>",
            "next_action": "Fix quote & inspect exact record",
            "owner": "Proposal lead",
            "reviewed_by": "Reviewer",
            "citations": [{"source": {
                "title": "Agency <draft>", "url": "https://sam.gov/opp/test/view",
                "version_label": "Amendment 01", "document_sha256": "a" * 64},
                "locator": "Section L.3",
                "quote": 'Changed to 15 pages & "no exception".'}],
            "changes": [],
        }]
        txt = render_action_brief_v2(case, {"trace_state": "TRACE_COMPLETE", "assumptions": cards},
                                     FakeAudit(), now=NOW)
        self.assertNotIn("<script>", txt)
        self.assertNotIn("<img src=x", txt)
        self.assertIn("&lt;script&gt;", txt)
        self.assertIn("Agency &lt;draft&gt;", txt)
        self.assertIn("Fix quote &amp; inspect exact record", txt)
        self.assertIn("Section L.3", txt)
        self.assertIn("https://sam.gov/opp/test/view", txt)
        self.assertNotIn("cdn.", txt)
        self.assertNotIn("<iframe", txt)

    def test_priority_sorts_gate_changing_before_verify_and_monitor(self):
        trace = {"trace_state": "TRACE_COMPLETE", "assumptions": [
            {"assumption_id": "Z", "assumption": "Low", "finding": "Low",
             "next_action": "Watch", "evidence_state": "SUPPORTED",
             "decision_class": "MONITOR_ONLY", "citations": []},
            {"assumption_id": "B", "assumption": "High", "finding": "High",
             "next_action": "Stop", "evidence_state": "CONTRADICTED",
             "decision_class": "GATE_CHANGING", "citations": []},
            {"assumption_id": "A", "assumption": "Medium", "finding": "Medium",
             "next_action": "Verify", "evidence_state": "SOURCE_LIMITED",
             "decision_class": "VERIFY_NOW", "citations": []},
        ]}
        txt = render_action_brief_v2({"case_id": "CB-X", "family_id": "F",
                                     "current_posture": "HOLD"}, trace, FakeAudit(), now=NOW)
        self.assertLess(txt.index("id=\"finding-B\""), txt.index("id=\"finding-A\""))
        self.assertLess(txt.index("id=\"finding-A\""), txt.index("id=\"finding-Z\""))
        self.assertIn("Source limited", txt)
        self.assertIn("Evidence to request", txt)
        self.assertIn("no automatic approval", txt.lower())

    def test_missing_or_ambiguous_links_are_not_emitted_as_clickable_urls(self):
        case = {"case_id": "CB-X", "family_id": "F", "current_posture": "HOLD"}
        trace = {"trace_state": "TRACE_COMPLETE", "assumptions": [{
            "assumption_id": "A1", "assumption": "Question", "finding": "Hold",
            "evidence_state": "SOURCE_LIMITED", "decision_class": "VERIFY_NOW",
            "evidence_request": "Obtain controlling original first.",
            "citations": [{"source": {"title": "Unknown", "url": "javascript:alert(1)"},
                           "locator": "L.1", "quote": "Text"}]}]}
        txt = render_action_brief_v2(case, trace, FakeAudit(), now=NOW)
        self.assertNotIn('href="javascript:', txt)
        self.assertIn("Obtain controlling original first.", txt)
        self.assertIn("Unverified source link", txt)

    def test_unvalidated_trace_cannot_be_promoted_into_buyer_ready_v2_html(self):
        case = {"case_id": "CB-X", "family_id": "F", "current_posture": "HOLD"}
        with self.assertRaises(ValueError):
            render_action_brief_v2(case, {"trace_state": "TRACE_INCOMPLETE", "assumptions": []},
                                   FakeAudit(), now=NOW)
        with self.assertRaises(ValueError):
            render_action_brief_v2(case, {"trace_state": "TRACE_COMPLETE", "assumptions": []},
                                   FakeAudit(release_state="HOLD"), now=NOW)


if __name__ == "__main__":
    unittest.main()
