from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from capturebrief_core.fulfillment_plan import build_fulfillment_plan, effort_stage
from capturebrief_core.intake import build_case_from_intake
from capturebrief_core.delivery_bundle import build_delivery_files

NOW = datetime(2026, 9, 21, 20, tzinfo=timezone.utc)


def ready_trace():
    return json.loads(Path("fixtures/ready_trace_case.json").read_text())


class FulfillmentPlanTests(unittest.TestCase):
    def test_stage_mapping_is_stable(self):
        pairs = {"current:authority": "HISTORY_CURRENT", "bytes:ART-1": "PACKET_BYTES",
                 "reference:R1": "REFERENCE_REVIEW", "trace:assumption:A1": "ASSUMPTION_REVIEW",
                 "rule-applicability:A1": "RULE_REVIEW", "deviation-authority:DEV1": "DEVIATION_REVIEW",
                 "delivery:readiness": "DELIVERY", "something-new": "OTHER"}
        for key, expected in pairs.items():
            self.assertEqual(effort_stage(key), expected)

    def test_fresh_intake_cannot_be_delivered(self):
        case = build_case_from_intake({
            "public_only_confirmation": "yes", "public_opportunity": "https://sam.gov/opp/demo",
            "current_posture": "GO", "company": "Demo Co", "email": "demo@example.com",
            "assumption_1": "The current public packet supports our response plan.",
        }, submitted_at="2026-09-21T18:00:00Z")
        plan = build_fulfillment_plan(case, now=NOW)
        self.assertEqual(plan["release_state"], "FAIL_CLOSED")
        self.assertGreater(plan["summary"]["open_tasks"], 0)
        self.assertFalse(plan["delivery_bundle_eligible"])
        self.assertFalse(plan["summary"]["automatic_evidence_or_bid_decision"])
        self.assertIsNotNone(plan["next_task"])

    def test_legacy_case_cannot_claim_bundle_readiness(self):
        case = json.loads(Path("fixtures/ready_case.json").read_text())
        plan = build_fulfillment_plan(case, now=NOW)
        self.assertEqual(plan["release_state"], "READY_FOR_HUMAN_RELEASE")
        self.assertEqual(plan["fulfillment_state"], "TRACE_UPGRADE_REQUIRED")
        self.assertFalse(plan["delivery_bundle_eligible"])
        self.assertIn("DELIVERY_REQUIRES_DECISION_TRACE", plan["release_blocker_codes"])
        self.assertIn("delivery:readiness", [t["task_key"] for t in plan["human_review_batch"]])
        with self.assertRaises(ValueError):
            build_delivery_files(case, now=NOW)

    def test_traced_case_matches_actual_bundle_gate(self):
        case = ready_trace()
        self.assertIn("brief.md", build_delivery_files(case, now=NOW))
        plan = build_fulfillment_plan(case, now=NOW)
        self.assertTrue(plan["delivery_bundle_eligible"])
        self.assertEqual(plan["trace_state"], "TRACE_COMPLETE")

    def test_tampered_case_never_claims_bundle_readiness(self):
        case = ready_trace()
        case["decision_trace"]["snapshots"][0]["text"] += "\nUnexpected edit."
        plan = build_fulfillment_plan(case, now=NOW)
        self.assertFalse(plan["delivery_bundle_eligible"])
        self.assertNotEqual(plan["fulfillment_state"], "READY_TO_BUILD_DELIVERY")
        with self.assertRaises(ValueError):
            build_delivery_files(case, now=NOW)

    def test_synthetic_trace_is_not_customer_ready(self):
        case = ready_trace()
        case["decision_trace"]["synthetic"] = True
        self.assertFalse(build_fulfillment_plan(case, now=NOW)["delivery_bundle_eligible"])

    def test_hybrid_human_unknown_and_truthy_flags_are_not_full_automation(self):
        rows = [
            {"task_key": "hybrid:1", "priority": "P0", "actor": "HYBRID", "can_auto_execute": True},
            {"task_key": "human:1", "priority": "P0", "actor": "HUMAN_REVIEW", "can_auto_execute": True},
            {"task_key": "unknown:1", "priority": "P0", "actor": "NEW_ACTOR", "can_auto_execute": True},
            {"task_key": "truthy:1", "priority": "P0", "actor": "AUTOMATED_LOCAL", "can_auto_execute": "true"},
            {"task_key": "local:1", "priority": "P0", "actor": "AUTOMATED_LOCAL", "can_auto_execute": True},
        ]
        queue = {"generated_at": NOW.isoformat(), "tasks": rows}
        with patch("capturebrief_core.fulfillment_plan.build_work_queue", return_value=queue):
            plan = build_fulfillment_plan(ready_trace(), now=NOW)
        self.assertEqual([x["task_key"] for x in plan["safe_automation_batch"]], ["local:1"])
        self.assertEqual(plan["next_task"]["task_key"], "local:1")
        self.assertEqual(len(plan["human_review_batch"]), 4)
        self.assertTrue(rows[0]["can_auto_execute"])
        self.assertFalse(plan["summary"]["automatic_execution_performed"])

    def test_planning_preserves_case_and_does_not_authorize_sending(self):
        case = ready_trace()
        before = copy.deepcopy(case)
        plan = build_fulfillment_plan(case, now=NOW)
        self.assertEqual(case, before)
        self.assertFalse(plan["communications"]["external_send_authorized"])
        self.assertTrue(plan["communications"]["approval_required_for_each_message"])
        self.assertFalse(plan["communications"]["inbound_reply_grants_send_permission"])
        self.assertFalse(plan["communications"]["completed_bundle_grants_send_permission"])

    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):
            build_fulfillment_plan(ready_trace(), now=datetime(2026, 9, 21))


if __name__ == "__main__":
    unittest.main()
