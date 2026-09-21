from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from capturebrief_core.outcomes import (
    append_outcome_event,
    make_outcome_event,
    summarize_outcomes,
    validate_outcome_event,
)


CASE_SHA="a"*64
BUNDLE_SHA="b"*64


def event(kind,case_id="CB-1",at="2026-09-21T18:00:00Z",**data):
    return make_outcome_event(
        case_id=case_id,
        case_sha256=CASE_SHA,
        delivery_bundle_sha256=BUNDLE_SHA,
        event_type=kind,
        event_at=at,
        data=data,
    )


class OutcomeLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/"outcomes.jsonl"

    def tearDown(self):
        self.temp.cleanup()

    def append(self,value,recorded_at="2026-09-21T18:10:00Z"):
        return append_outcome_event(self.path,value,recorded_at=recorded_at)

    def test_evidence_backed_engagement_summary(self):
        self.append(event("PAYMENT",state="PAID",amount_cents=14900,currency="USD",payment_evidence_ref="stripe:pi_demo_001"))
        self.append(event("DELIVERY",at="2026-09-21T20:00:00Z",started_at="2026-09-21T18:00:00Z",delivered_at="2026-09-21T20:00:00Z",delivery_evidence_ref="bundle:sha256:demo001"))
        self.append(event("EFFORT",at="2026-09-21T18:30:00Z",stage="HISTORY_CURRENT",minutes=18,effort_evidence_ref="timer:CB-1:history"))
        self.append(event("EFFORT",at="2026-09-21T19:30:00Z",stage="ASSUMPTION_REVIEW",minutes=42,effort_evidence_ref="timer:CB-1:assumptions"))
        self.append(event("FEEDBACK",at="2026-09-22T15:00:00Z",usefulness="USEFUL",action_effect="CHANGED_ACTION",source_limited=False,finding_classes=["SOURCE_VERSION","DEADLINE"],feedback_evidence_ref="feedback:form:001"))
        self.append(event("REPEAT_REQUEST",at="2026-09-22T15:01:00Z",state="REQUESTED_REPEAT",repeat_evidence_ref="feedback:form:001"))
        summary=summarize_outcomes(self.path)
        self.assertEqual(summary["engagements"],1)
        self.assertEqual(summary["paid_engagements"],1)
        self.assertEqual(summary["paid_amount_cents_recorded"],14900)
        self.assertEqual(summary["delivered_engagements"],1)
        self.assertEqual(summary["turnaround_hours"]["median"],2.0)
        self.assertEqual(summary["effort_hours"]["median"],1.0)
        self.assertEqual(summary["effort_stage_minutes"]["HISTORY_CURRENT"],18)
        self.assertEqual(summary["effort_stage_minutes"]["ASSUMPTION_REVIEW"],42)
        self.assertEqual(summary["paid_effort_coverage"]["paid_with_effort"],1)
        self.assertEqual(summary["collected_cents_per_recorded_effort_hour_by_currency"]["USD"],14900.0)
        self.assertEqual(summary["feedback"]["useful"],1)
        self.assertEqual(summary["feedback"]["changed_action"],1)
        self.assertEqual(summary["repeat"]["requested_repeat"],1)
        self.assertEqual(summary["finding_classes"]["SOURCE_VERSION"],1)
        self.assertTrue(summary["ledger"]["valid"])
        self.assertIn("ROI",summary["claims_not_computed"])

    def test_three_paid_cases_plus_repeat_and_action_meet_only_objective_gates(self):
        for i in range(1,4):
            cid=f"CB-{i}"
            self.append(event("PAYMENT",case_id=cid,at=f"2026-09-2{i}T12:00:00Z",state="PAID",payment_evidence_ref=f"stripe:pi_{i}"))
            self.append(event("DELIVERY",case_id=cid,at=f"2026-09-2{i}T15:00:00Z",started_at=f"2026-09-2{i}T13:00:00Z",delivered_at=f"2026-09-2{i}T15:00:00Z",delivery_evidence_ref=f"bundle:{i}"))
            self.append(event("EFFORT",case_id=cid,at=f"2026-09-2{i}T14:00:00Z",stage="ASSUMPTION_REVIEW",minutes=45,effort_evidence_ref=f"timer:{cid}:assumptions"))
        self.append(event("FEEDBACK",case_id="CB-1",at="2026-09-24T12:00:00Z",usefulness="USEFUL",action_effect="CLOSED_COSTLY_UNCERTAINTY",source_limited=False,finding_classes=["RULE_CURRENCY"],feedback_evidence_ref="feedback:1"))
        self.append(event("REPEAT_REQUEST",case_id="CB-1",at="2026-09-24T12:01:00Z",state="REQUESTED_REPEAT",repeat_evidence_ref="feedback:1"))
        gates=summarize_outcomes(self.path)["commercial_proof_threshold_evidence"]
        self.assertTrue(gates["paid_engagements_at_least_3"])
        self.assertTrue(gates["repeat_request_at_least_1"])
        self.assertTrue(gates["action_changed_or_costly_uncertainty_closed_at_least_1"])
        self.assertTrue(gates["turnaround_evidence_present"])
        self.assertTrue(gates["effort_evidence_present"])
        self.assertTrue(gates["paid_engagement_effort_coverage_complete"])
        self.assertTrue(gates["turnaround_acceptability_requires_human_threshold"])
        self.assertTrue(gates["effort_acceptability_requires_human_threshold"])
        self.assertTrue(gates["retraction_acceptability_requires_human_threshold"])
        self.assertFalse(gates["automatic_pricing_or_subscription_change"])

    def test_effort_is_additive_and_stage_bounded(self):
        self.append(event("EFFORT",stage="REFERENCE_REVIEW",minutes=12,effort_evidence_ref="timer:CB-1:ref1"))
        self.append(event("EFFORT",at="2026-09-21T18:15:00Z",stage="REFERENCE_REVIEW",minutes=8,effort_evidence_ref="timer:CB-1:ref2"))
        summary=summarize_outcomes(self.path)
        self.assertEqual(summary["effort_hours"]["total"],20/60)
        self.assertEqual(summary["effort_stage_minutes"]["REFERENCE_REVIEW"],20)
        with self.assertRaises(ValueError):
            event("EFFORT",stage="MADE_UP_STAGE",minutes=5,effort_evidence_ref="timer:bad")
        with self.assertRaises(ValueError):
            event("EFFORT",stage="WATCH",minutes=0,effort_evidence_ref="timer:bad")

    def test_paid_without_effort_does_not_claim_complete_effort_coverage(self):
        self.append(event("PAYMENT",state="PAID",amount_cents=14900,currency="USD",payment_evidence_ref="stripe:pi_1"))
        gates=summarize_outcomes(self.path)["commercial_proof_threshold_evidence"]
        self.assertFalse(gates["effort_evidence_present"])
        self.assertFalse(gates["paid_engagement_effort_coverage_complete"])

    def test_paid_and_refunded_latest_payment_is_not_counted_as_paid(self):
        self.append(event("PAYMENT",at="2026-09-21T12:00:00Z",state="PAID",amount_cents=14900,currency="USD",payment_evidence_ref="stripe:pi_1"))
        self.append(event("PAYMENT",at="2026-09-22T12:00:00Z",state="REFUNDED",amount_cents=14900,currency="USD",payment_evidence_ref="stripe:re_1"))
        summary=summarize_outcomes(self.path)
        self.assertEqual(summary["paid_engagements"],0)
        self.assertEqual(summary["paid_amount_cents_recorded"],0)

    def test_paid_requires_payment_evidence(self):
        with self.assertRaises(ValueError):
            event("PAYMENT",state="PAID",amount_cents=14900,currency="USD")

    def test_feedback_has_no_free_text_or_customer_identity_fields(self):
        base={
            "schema_version":"1.0","case_id":"CB-1","case_sha256":CASE_SHA,
            "event_type":"FEEDBACK","event_at":"2026-09-21T18:00:00Z",
            "delivery_bundle_sha256":BUNDLE_SHA,
            "data":{"usefulness":"USEFUL","action_effect":"CHANGED_ACTION","source_limited":False,"finding_classes":["DEADLINE"],"feedback_evidence_ref":"feedback:1","notes":"great"},
        }
        self.assertTrue(any("unknown_fields" in x or "forbidden_field" in x for x in validate_outcome_event(base)))
        base["data"].pop("notes")
        base["data"]["email"]="buyer@example.com"
        self.assertTrue(any("forbidden_field" in x for x in validate_outcome_event(base)))

    def test_roi_and_pwin_fields_are_forbidden(self):
        value={
            "schema_version":"1.0","case_id":"CB-1","case_sha256":CASE_SHA,
            "event_type":"FEEDBACK","event_at":"2026-09-21T18:00:00Z",
            "delivery_bundle_sha256":BUNDLE_SHA,
            "data":{"usefulness":"USEFUL","action_effect":"CHANGED_ACTION","source_limited":False,"finding_classes":["DEADLINE"],"feedback_evidence_ref":"feedback:1","roi":25000},
        }
        errors=validate_outcome_event(value)
        self.assertTrue(any("forbidden_field" in x for x in errors))

    def test_retraction_is_counted_without_erasing_prior_feedback(self):
        self.append(event("FEEDBACK",usefulness="USEFUL",action_effect="CHANGED_ACTION",source_limited=False,finding_classes=["DEADLINE"],feedback_evidence_ref="feedback:1"))
        self.append(event("RETRACTION",at="2026-09-22T10:00:00Z",severity="CRITICAL",reason_code="WRONG_VERSION",retraction_evidence_ref="retraction:1"))
        summary=summarize_outcomes(self.path)
        self.assertEqual(summary["feedback"]["changed_action"],1)
        self.assertEqual(summary["quality"]["engagements_with_retraction"],1)
        self.assertEqual(summary["quality"]["critical_retractions"],1)

    def test_tampered_ledger_blocks_summary_and_append(self):
        self.append(event("PAYMENT",state="UNPAID"))
        row=json.loads(self.path.read_text().splitlines()[0])
        row["payload"]["data"]["state"]="PAID"
        self.path.write_text(json.dumps(row)+"\n")
        with self.assertRaises(ValueError):
            summarize_outcomes(self.path)
        with self.assertRaises(ValueError):
            self.append(event("PAYMENT",case_id="CB-2",state="UNPAID"))

    def test_delivery_interval_must_be_ordered_and_timezone_aware(self):
        with self.assertRaises(ValueError):
            event("DELIVERY",started_at="2026-09-21T20:00:00Z",delivered_at="2026-09-21T18:00:00Z",delivery_evidence_ref="bundle:1")
        with self.assertRaises(ValueError):
            event("DELIVERY",started_at="2026-09-21T18:00:00",delivered_at="2026-09-21T20:00:00Z",delivery_evidence_ref="bundle:1")


if __name__=="__main__":
    unittest.main()
