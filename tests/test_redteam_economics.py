from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from capturebrief_core.outcomes import (
    append_outcome_event,
    make_outcome_event,
    summarize_outcomes,
)

CASE_A="a"*64
CASE_B="b"*64
CASE_C="c"*64
BUNDLE_A="1"*64
BUNDLE_B="2"*64
BUNDLE_C="3"*64


def event(kind, *, case_id="CB-A", case_sha256=CASE_A, bundle=None,
          at="2026-09-21T18:00:00Z", **data):
    return make_outcome_event(
        case_id=case_id,
        case_sha256=case_sha256,
        delivery_bundle_sha256=bundle,
        event_type=kind,
        event_at=at,
        data=data,
    )


class FulfillmentEconomicsRedTeamTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger=Path(self.temp.name)/"outcomes.jsonl"

    def append(self, value, recorded_at=None):
        return append_outcome_event(
            self.ledger, value,
            recorded_at=recorded_at or value["event_at"],
        )

    def paid(self, cid, case_sha, ref, *, at, amount=14900):
        self.append(event(
            "PAYMENT", case_id=cid, case_sha256=case_sha, at=at,
            state="PAID", amount_cents=amount, currency="USD",
            payment_evidence_ref=ref,
        ))

    def delivery(self, cid, case_sha, bundle, *, start, delivered, evidence):
        self.append(event(
            "DELIVERY", case_id=cid, case_sha256=case_sha, bundle=bundle,
            at=delivered, started_at=start, delivered_at=delivered,
            delivery_evidence_ref=evidence,
        ))

    def effort(self, cid, case_sha, ref, *, at, minutes):
        self.append(event(
            "EFFORT", case_id=cid, case_sha256=case_sha, at=at,
            stage="ASSUMPTION_REVIEW", minutes=minutes,
            effort_evidence_ref=ref,
        ))

    def test_three_payments_do_not_satisfy_three_delivered_engagements(self):
        rows=[
            ("CB-A",CASE_A,BUNDLE_A),
            ("CB-B",CASE_B,BUNDLE_B),
            ("CB-C",CASE_C,BUNDLE_C),
        ]
        for i,(cid,case_sha,bundle) in enumerate(rows):
            self.paid(cid,case_sha,f"stripe:paid:{cid}",at=f"2026-09-21T1{i}:00:00Z")
            self.effort(cid,case_sha,f"timer:{cid}",at=f"2026-09-21T1{i}:10:00Z",minutes=60 if i==0 else 1)
        self.delivery("CB-A",CASE_A,BUNDLE_A,start="2026-09-21T10:00:00Z",
                      delivered="2026-09-21T11:00:00Z",evidence="delivery:CB-A")
        self.append(event(
            "FEEDBACK",case_id="CB-A",case_sha256=CASE_A,bundle=BUNDLE_A,
            at="2026-09-21T12:00:00Z",usefulness="USEFUL",
            action_effect="CHANGED_ACTION",source_limited=False,
            finding_classes=["SOURCE_VERSION"],feedback_evidence_ref="feedback:CB-A",
        ))
        self.append(event(
            "REPEAT_REQUEST",case_id="CB-A",case_sha256=CASE_A,bundle=BUNDLE_A,
            at="2026-09-21T12:01:00Z",state="REQUESTED_REPEAT",
            repeat_evidence_ref="repeat:CB-A",
        ))
        summary=summarize_outcomes(self.ledger)
        gates=summary["commercial_proof_threshold_evidence"]
        self.assertEqual(summary["paid_engagements"],3)
        self.assertEqual(summary["delivered_engagements"],1)
        self.assertFalse(gates["paid_delivered_engagements_at_least_3"])
        self.assertFalse(gates["all_current_paid_engagements_delivered"])
        self.assertFalse(gates["commercial_proof_objective_gates_complete"])

    def test_unit_economics_ignore_prepaid_but_undelivered_cases(self):
        self.paid("CB-A",CASE_A,"stripe:A",at="2026-09-21T10:00:00Z")
        self.effort("CB-A",CASE_A,"timer:A",at="2026-09-21T10:10:00Z",minutes=60)
        self.delivery("CB-A",CASE_A,BUNDLE_A,start="2026-09-21T10:00:00Z",
                      delivered="2026-09-21T11:00:00Z",evidence="delivery:A")
        for cid,sha in (("CB-B",CASE_B),("CB-C",CASE_C)):
            self.paid(cid,sha,f"stripe:{cid}",at="2026-09-21T12:00:00Z")
            self.effort(cid,sha,f"timer:{cid}",at="2026-09-21T12:01:00Z",minutes=1)
        summary=summarize_outcomes(self.ledger)
        self.assertEqual(
            summary["collected_cents_per_recorded_effort_hour_by_currency"]["USD"],
            14900.0,
        )
        self.assertEqual(summary["paid_delivered_effort_coverage"]["paid_delivered"],1)

    def test_payment_evidence_reference_cannot_fund_multiple_cases(self):
        self.paid("CB-A",CASE_A,"stripe:one-payment",at="2026-09-21T10:00:00Z")
        self.paid("CB-B",CASE_B,"stripe:one-payment",at="2026-09-21T10:01:00Z")
        with self.assertRaisesRegex(ValueError,"payment evidence reference"):
            summarize_outcomes(self.ledger)

    def test_effort_receipt_cannot_cover_multiple_cases(self):
        self.effort("CB-A",CASE_A,"timer:one-session",at="2026-09-21T10:00:00Z",minutes=10)
        self.effort("CB-B",CASE_B,"timer:one-session",at="2026-09-21T10:01:00Z",minutes=10)
        with self.assertRaisesRegex(ValueError,"effort evidence reference"):
            summarize_outcomes(self.ledger)

    def test_one_delivery_bundle_cannot_be_attributed_to_two_cases(self):
        self.delivery("CB-A",CASE_A,BUNDLE_A,start="2026-09-21T10:00:00Z",
                      delivered="2026-09-21T11:00:00Z",evidence="delivery:A")
        self.delivery("CB-B",CASE_B,BUNDLE_A,start="2026-09-21T10:00:00Z",
                      delivered="2026-09-21T11:01:00Z",evidence="delivery:B")
        with self.assertRaisesRegex(ValueError,"delivery bundle"):
            summarize_outcomes(self.ledger)

    def test_delivery_event_cannot_be_recorded_before_delivery_happens(self):
        with self.assertRaises(ValueError):
            event(
                "DELIVERY",bundle=BUNDLE_A,at="2026-09-21T10:00:00Z",
                started_at="2026-09-21T09:00:00Z",
                delivered_at="2026-09-21T11:00:00Z",
                delivery_evidence_ref="delivery:A",
            )

    def test_recorded_at_cannot_precede_event_time(self):
        value=event(
            "PAYMENT",at="2026-09-21T12:00:00Z",state="PAID",
            payment_evidence_ref="stripe:A",
        )
        with self.assertRaisesRegex(ValueError,"recorded_at"):
            append_outcome_event(
                self.ledger,value,recorded_at="2026-09-21T11:59:59Z"
            )

    def test_conflicting_payment_states_at_same_event_time_are_ambiguous(self):
        self.append(event(
            "PAYMENT",at="2026-09-21T12:00:00Z",state="PAID",
            payment_evidence_ref="stripe:A",
        ),recorded_at="2026-09-21T12:00:01Z")
        self.append(event(
            "PAYMENT",at="2026-09-21T12:00:00Z",state="REFUNDED",
            payment_evidence_ref="stripe:refund:A",
        ),recorded_at="2026-09-21T12:00:02Z")
        with self.assertRaisesRegex(ValueError,"ambiguous payment state"):
            summarize_outcomes(self.ledger)

    def test_feedback_after_first_delivery_stays_bound_if_same_bundle_is_resent(self):
        self.delivery("CB-A",CASE_A,BUNDLE_A,start="2026-09-21T10:00:00Z",
                      delivered="2026-09-21T11:00:00Z",evidence="delivery:first")
        self.append(event(
            "FEEDBACK",case_id="CB-A",case_sha256=CASE_A,bundle=BUNDLE_A,
            at="2026-09-21T12:00:00Z",usefulness="USEFUL",
            action_effect="CONFIRMED_EXISTING_VIEW",source_limited=False,
            finding_classes=["SOURCE_VERSION"],feedback_evidence_ref="feedback:A",
        ))
        self.delivery("CB-A",CASE_A,BUNDLE_A,start="2026-09-21T13:00:00Z",
                      delivered="2026-09-21T14:00:00Z",evidence="delivery:resend")
        summary=summarize_outcomes(self.ledger)
        self.assertEqual(summary["buyer_feedback_cases"],1)
        self.assertEqual(summary["unbound_outcome_events"],0)


if __name__=="__main__":
    unittest.main()
