from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from capturebrief_core.fulfillment_plan import build_fulfillment_plan, effort_stage
from capturebrief_core.intake import build_case_from_intake

NOW=datetime(2026,9,21,18,50,tzinfo=timezone.utc)


class FulfillmentPlanTests(unittest.TestCase):
    def test_stage_mapping_is_stable(self):
        self.assertEqual(effort_stage("current:authority"),"HISTORY_CURRENT")
        self.assertEqual(effort_stage("bytes:ART-1"),"PACKET_BYTES")
        self.assertEqual(effort_stage("reference:R1"),"REFERENCE_REVIEW")
        self.assertEqual(effort_stage("trace:assumption:A1"),"ASSUMPTION_REVIEW")
        self.assertEqual(effort_stage("rule-applicability:A1"),"RULE_REVIEW")
        self.assertEqual(effort_stage("deviation-authority:DEV1"),"DEVIATION_REVIEW")
        self.assertEqual(effort_stage("something-new"),"OTHER")

    def test_fresh_intake_surfaces_human_review_and_no_auto_decision(self):
        case=build_case_from_intake({
            "public_only_confirmation":"yes",
            "public_opportunity":"https://sam.gov/opp/demo",
            "current_posture":"GO",
            "company":"Demo Co",
            "email":"demo@example.com",
            "assumption_1":"The current public packet supports our response plan.",
        },submitted_at="2026-09-21T18:00:00Z")
        plan=build_fulfillment_plan(case,now=NOW)
        self.assertEqual(plan["release_state"],"FAIL_CLOSED")
        self.assertGreater(plan["summary"]["open_tasks"],0)
        self.assertFalse(plan["summary"]["automatic_evidence_or_bid_decision"])
        self.assertIsNotNone(plan["next_task"])
        self.assertIn(plan["next_task"]["effort_stage"],{
            "HISTORY_CURRENT","PACKET_BYTES","REFERENCE_REVIEW",
            "ASSUMPTION_REVIEW","RULE_REVIEW","DEVIATION_REVIEW","OTHER",
        })
        self.assertTrue(plan["release_blocker_codes"])

    def test_release_ready_legacy_fixture_has_no_invented_work(self):
        case=json.loads(Path("fixtures/ready_case.json").read_text())
        plan=build_fulfillment_plan(case,now=NOW)
        self.assertEqual(plan["release_state"],"READY_FOR_HUMAN_RELEASE")
        self.assertEqual(plan["summary"]["open_tasks"],0)
        self.assertEqual(plan["fulfillment_state"],"READY_TO_BUILD_DELIVERY")
        self.assertIsNone(plan["next_task"])
        self.assertEqual(plan["safe_automation_batch"],[])
        self.assertEqual(plan["human_review_batch"],[])


if __name__=="__main__":
    unittest.main()
