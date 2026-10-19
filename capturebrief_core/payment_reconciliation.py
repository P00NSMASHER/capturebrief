"""Fail-closed Stripe payment reconciliation for one CaptureBrief founding review.

Only fully paid, non-refunded LIVE checkout records on the exact CaptureBrief
Payment Link can reach a reconciliation state. Even then, no case may be sent,
worked, or released without separately confirmed inbox, scope and human review.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

ACCOUNT_ID = "acct_1UItcBRVKNw4DyjZ"
PAYMENT_LINK_ID = "plink_1UIvfJRVKNw4DyjZSj7aRJz1"
AMOUNT_USD_CENTS = 14900
CURRENCY = "usd"
def _valid_id(value: Any, prefix: str) -> bool:
    # Stripe object IDs can have a compound prefix such as cs_live_;
    # match the exact expected object prefix rather than a generic one.
    return (isinstance(value, str) and
            re.fullmatch(re.escape(prefix) + r"_[A-Za-z0-9]+", value) is not None)


def _safe_email(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    email = value.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}", email):
        return None
    return email


def reconcile_capturebrief_payment(
    session: dict[str, Any],
    payment_intent: dict[str, Any],
    charge: dict[str, Any],
    *,
    account_id: str,
    buyer_email: str,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Reconcile three separate Stripe API records without trusting checkout URLs.

    Do not pass browser-generated or customer-supplied copies as trusted Stripe
    records. The caller must independently acquire all three via authenticated
    direct GETs from the intended LIVE account.
    """
    at = observed_at or datetime.now(timezone.utc)
    if not isinstance(at, datetime) or at.utcoffset() is None:
        raise ValueError("observed_at must include a timezone")
    at = at.astimezone(timezone.utc)
    errors: list[str] = []

    def check(ok: bool, code: str) -> None:
        if not ok:
            errors.append(code)

    if not all(isinstance(v, dict) for v in (session, payment_intent, charge)):
        raise ValueError("Stripe API records must be objects")
    check(account_id == ACCOUNT_ID, "WRONG_STRIPE_ACCOUNT")
    expected_email = _safe_email(buyer_email)
    check(expected_email is not None, "BUYER_EMAIL_MISSING_OR_INVALID")

    check(session.get("object") == "checkout.session"
          and _valid_id(session.get("id"), "cs_live"), "BAD_LIVE_CHECKOUT_SESSION")
    check(session.get("livemode") is True, "SESSION_NOT_LIVE")
    check(session.get("payment_link") == PAYMENT_LINK_ID, "PAYMENT_LINK_MISMATCH")
    check(session.get("mode") == "payment", "NOT_ONE_TIME_PAYMENT")
    check(session.get("status") == "complete"
          and session.get("payment_status") == "paid", "CHECKOUT_UNPAID")
    check(session.get("currency") == CURRENCY
          and type(session.get("amount_total")) is int
          and session["amount_total"] == AMOUNT_USD_CENTS, "CHECKOUT_AMOUNT_MISMATCH")

    session_email = _safe_email((session.get("customer_details") or {}).get("email"))
    session_fallback_email = _safe_email(session.get("customer_email"))
    check(session_email is not None or session_fallback_email is not None,
          "PROCESSOR_BUYER_EMAIL_MISSING")
    if expected_email:
        check(expected_email in (session_email, session_fallback_email),
              "BUYER_EMAIL_MISMATCH")

    pi_id = session.get("payment_intent")
    check(_valid_id(pi_id, "pi"), "MISSING_PAYMENT_INTENT")
    check(payment_intent.get("object") == "payment_intent"
          and payment_intent.get("id") == pi_id, "PAYMENT_INTENT_MISMATCH")
    check(payment_intent.get("livemode") is True, "PAYMENT_INTENT_NOT_LIVE")
    check(payment_intent.get("status") == "succeeded"
          and payment_intent.get("capture_method", "automatic") == "automatic",
          "PAYMENT_INTENT_NOT_SUCCEEDED")
    check(payment_intent.get("currency") == CURRENCY
          and type(payment_intent.get("amount")) is int
          and payment_intent["amount"] == AMOUNT_USD_CENTS
          and type(payment_intent.get("amount_received")) is int
          and payment_intent["amount_received"] == AMOUNT_USD_CENTS,
          "PAYMENT_INTENT_AMOUNT_MISMATCH")

    ch_id = payment_intent.get("latest_charge")
    check(_valid_id(ch_id, "ch"), "MISSING_LATEST_CHARGE")
    check(charge.get("object") == "charge" and charge.get("id") == ch_id
          and charge.get("payment_intent") == pi_id,
          "CHARGE_NOT_BOUND_TO_PAYMENT_INTENT")
    check(charge.get("livemode") is True, "CHARGE_NOT_LIVE")
    check(charge.get("paid") is True and charge.get("captured") is True
          and charge.get("status") == "succeeded", "CHARGE_NOT_CAPTURED")
    check(charge.get("currency") == CURRENCY
          and type(charge.get("amount")) is int
          and charge["amount"] == AMOUNT_USD_CENTS,
          "CHARGE_AMOUNT_MISMATCH")
    check(charge.get("refunded") is False
          and type(charge.get("amount_refunded")) is int
          and charge["amount_refunded"] == 0, "REFUNDED_OR_UNKNOWN")
    check(charge.get("disputed") is False, "DISPUTED_OR_UNKNOWN")
    check(charge.get("failure_code") is None, "CHARGE_HAS_FAILURE_CODE")

    # A signed/hashed receipt proves local consistency only, not independent
    # Stripe signature/authentication: caller is responsible for direct API GET.
    fingerprint = {
        "session_id": session.get("id") if _valid_id(session.get("id"), "cs_live") else None,
        "payment_intent_id": pi_id if _valid_id(pi_id, "pi") else None,
        "charge_id": ch_id if _valid_id(ch_id, "ch") else None,
        "account_id": account_id,
        "payment_link_id": PAYMENT_LINK_ID,
        "amount_usd_cents": AMOUNT_USD_CENTS,
        "currency": CURRENCY,
        "checked_at": at.isoformat().replace("+00:00", "Z"),
        "error_codes": sorted(set(errors)),
    }
    digest = hashlib.sha256(json.dumps(
        fingerprint, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    return {
        "schema": "capturebrief-stripe-reconciliation-v1",
        "status": ("PROCESSOR_RECORDS_CONSISTENT_REVIEW_REQUIRED"
                   if not errors else "PAYMENT_RECONCILIATION_BLOCKED"),
        "payment_verified_by_matching_records": not errors,
        "processor_records_authenticated_by_caller": False,
        "operator_must_verify_account_and_source": True,
        "case_release_authorized": False,
        "work_authorized": False,
        "external_send_authorized": False,
        "checked_at": fingerprint["checked_at"],
        "payment_reference": fingerprint["session_id"],
        "reconciliation_sha256": digest,
        "error_codes": sorted(set(errors)),
    }
