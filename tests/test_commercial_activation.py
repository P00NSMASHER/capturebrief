from __future__ import annotations

import copy
import unittest

from capturebrief_core.commercial_activation import (
    OFFER_ID,
    build_activation_packet,
    render_checkout_invitation,
    review_scope,
    validate_activation_packet,
    validate_scope_review,
)
from capturebrief_core.intake import build_case_from_intake

REVIEWED_AT="2026-09-21T18:30:00Z"
CREATED_AT="2026-09-21T18:31:00Z"
CHECKOUT="https://buy.stripe.com/test_capturebrief_demo"


def case():
    return build_case_from_intake({
        "public_only_confirmation":"yes",
        "public_opportunity":"https://sam.gov/opp/11111111111111111111111111111111/view",
        "current_posture":"GO",
        "company":"Example Buyer LLC",
        "email":"buyer@example.com",
        "assumption_1":"The current amendment permits a 15-page technical response.",
        "assumption_2":"The incorporated rule edition is still controlling.",
    },submitted_at="2026-09-21T18:00:00Z")


def in_scope(c):
    return review_scope(
        c,
        decision="IN_SCOPE",
        reason_codes=["PUBLIC_FEDERAL_IT_CYBER_CLOUD"],
        reviewed_by_role="CaptureBrief scope reviewer",
        reviewed_at=REVIEWED_AT,
    )


class CommercialActivationTests(unittest.TestCase):
    def test_in_scope_review_is_content_addressed_and_non_automatic(self):
        c=case(); review=in_scope(c)
        self.assertTrue(review["scope_review_id"].startswith("SCOPE:"))
        self.assertEqual(review["offer_id"],OFFER_ID)
        self.assertFalse(review["automatic_charge_authorized"])
        self.assertFalse(review["automatic_send_authorized"])
        self.assertEqual(validate_scope_review(c,review),[])

    def test_in_scope_requires_positive_reason(self):
        with self.assertRaises(ValueError):
            review_scope(
                case(),decision="IN_SCOPE",
                reason_codes=["OPPORTUNITY_NOT_RESOLVED"],
                reviewed_by_role="CaptureBrief scope reviewer",
                reviewed_at=REVIEWED_AT,
            )

    def test_in_scope_cannot_carry_disqualifying_reason(self):
        with self.assertRaises(ValueError):
            review_scope(
                case(),decision="IN_SCOPE",
                reason_codes=["PUBLIC_FEDERAL_IT_CYBER_CLOUD","RESTRICTED_SOURCE_REQUIRED"],
                reviewed_by_role="CaptureBrief scope reviewer",
                reviewed_at=REVIEWED_AT,
            )

    def test_out_of_scope_review_cannot_generate_checkout(self):
        c=case()
        review=review_scope(
            c,decision="OUT_OF_SCOPE",reason_codes=["OUTSIDE_IT_CYBER_CLOUD"],
            reviewed_by_role="CaptureBrief scope reviewer",reviewed_at=REVIEWED_AT,
        )
        with self.assertRaises(ValueError):
            build_activation_packet(c,review,created_at=CREATED_AT,checkout_url=CHECKOUT)

    def test_scope_review_tamper_is_detected(self):
        c=case(); review=in_scope(c)
        review["reason_codes"].append("OTHER")
        self.assertIn("scope_review_hash_mismatch",validate_scope_review(c,review))

    def test_scope_review_is_bound_to_exact_case(self):
        c=case(); review=in_scope(c)
        other=copy.deepcopy(c); other["case_id"]="CB-OTHER"
        self.assertIn("scope_review_case_mismatch",validate_scope_review(other,review))
        with self.assertRaises(ValueError):
            build_activation_packet(other,review,created_at=CREATED_AT,checkout_url=CHECKOUT)

    def test_packet_waits_for_verified_checkout_without_charging(self):
        c=case(); packet=build_activation_packet(c,in_scope(c),created_at=CREATED_AT)
        self.assertEqual(packet["status"],"AWAITING_VERIFIED_CHECKOUT")
        self.assertIsNone(packet["checkout"]["url"])
        self.assertFalse(packet["automatic_charge_authorized"])
        self.assertFalse(packet["automatic_send_authorized"])
        self.assertTrue(packet["checkout"]["customer_not_charged_by_packet"])
        self.assertEqual(validate_activation_packet(packet),[])
        with self.assertRaises(ValueError):
            render_checkout_invitation(packet)

    def test_verified_stripe_link_produces_fixed_149_offer(self):
        c=case(); packet=build_activation_packet(c,in_scope(c),created_at=CREATED_AT,checkout_url=CHECKOUT)
        self.assertEqual(packet["status"],"READY_TO_SEND")
        self.assertEqual(packet["offer"]["price_cents"],14900)
        self.assertEqual(packet["offer"]["currency"],"USD")
        self.assertEqual(packet["offer"]["payment_model"],"ONE_TIME")
        self.assertFalse(packet["offer"]["automatic_renewal"])
        self.assertEqual(packet["offer"]["targeted_watch_days"],14)
        self.assertEqual(validate_activation_packet(packet),[])
        invitation=render_checkout_invitation(packet)
        self.assertIn("$149 one time — no automatic renewal.",invitation)
        self.assertIn(CHECKOUT,invitation)
        self.assertIn("2 scoped assumptions",invitation)

    def test_non_stripe_or_credentialized_url_is_rejected(self):
        c=case(); review=in_scope(c)
        for url in (
            "https://example.com/pay",
            "http://buy.stripe.com/demo",
            "https://user:pass@buy.stripe.com/demo",
            "https://buy.stripe.com/demo?secret=abc",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    build_activation_packet(c,review,created_at=CREATED_AT,checkout_url=url)

    def test_offer_terms_cannot_be_mutated_after_hash(self):
        c=case(); packet=build_activation_packet(c,in_scope(c),created_at=CREATED_AT,checkout_url=CHECKOUT)
        packet["offer"]["price_cents"]=9900
        errors=validate_activation_packet(packet)
        self.assertIn("activation_hash_mismatch",errors)
        self.assertIn("offer_price_cents",errors)

    def test_activation_excludes_intake_identity(self):
        c=case(); packet=build_activation_packet(c,in_scope(c),created_at=CREATED_AT,checkout_url=CHECKOUT)
        text=str(packet)
        self.assertNotIn("buyer@example.com",text)
        self.assertNotIn("Example Buyer LLC",text)

    def test_public_only_confirmation_is_required(self):
        c=case(); c["intake"]["public_only_confirmation"]=False
        with self.assertRaises(ValueError):
            in_scope(c)

    def test_timezone_aware_review_and_activation_required(self):
        c=case()
        with self.assertRaises(ValueError):
            review_scope(c,decision="IN_SCOPE",reason_codes=["PUBLIC_FEDERAL_IT_CYBER_CLOUD"],reviewed_by_role="reviewer",reviewed_at="2026-09-21T18:30:00")
        with self.assertRaises(ValueError):
            build_activation_packet(c,in_scope(c),created_at="2026-09-21T18:31:00")


if __name__=="__main__":
    unittest.main()
