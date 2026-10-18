"""Strict, local-only bridge from a CaptureBrief customer email draft into core intake.

The website's "Open email draft" or "Copy request" feature does not submit
anything to a server. This parser accepts the exact plain-text draft format,
never treats a buyer's payment assertion as verified, and does not authenticate
the sender, delivery, source documents, or procurement claims.

Only the existing build_case_from_intake validates and creates the case.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .intake import IntakeError, build_case_from_intake

MAX_REQUEST_TEXT = 16_384

TO_LINE = "To: jayp19386@gmail.com"
SCOPE_SUBJECT = "CaptureBrief scope request"
PAID_SUBJECT = "CaptureBrief checkout-reported intake (payment verification needed)"
PAID_CLAIM = "Already purchased"
SCOPE_CLAIM = "Scope check before purchase"
HEADER = "Hello CaptureBrief,"
ASSUMPTIONS = "Assumptions to check:"
CONFIRMATION = "I confirm this request contains only public, non-sensitive information."
SCOPE_END = "Please confirm fit, source coverage, delivery date, and written terms before purchase."
PAID_END = (
    "Please independently verify payment in Stripe, then confirm fit, source "
    "coverage, and the delivery date. I understand an out-of-scope request "
    "will be refunded before work begins."
)

_STATUS_PREFIX = "Purchase status (customer-reported, not verified): "
_FIELDS = (
    ("Company: ", "company"),
    ("Work email: ", "email"),
    ("Public opportunity link: ", "public_opportunity"),
    ("Current posture: ", "current_posture"),
)
_ASSUMPTION = re.compile(r"^([1-5])\. (.+)$")


@dataclass(frozen=True)
class ParsedDraft:
    """Customer-provided data with explicit, untrusted purchase-claim metadata."""

    intake: dict[str, Any]
    purchase_claim: str
    envelope_present: bool


def parse_customer_draft(raw: str) -> ParsedDraft:
    if not isinstance(raw, str) or not raw or len(raw) > MAX_REQUEST_TEXT:
        raise IntakeError("intake draft must be nonempty plain text within the size limit")
    text = raw.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    if any(ord(c) < 32 and c not in "\n\t" for c in text):
        raise IntakeError("intake draft contains unsupported control characters")
    lines = text.split("\n")
    pos = 0
    subject = None
    envelope_present = False

    # Clipboard draft includes To/Subject; email body omits them. Do not
    # accept arbitrary forwarded headers, modified recipients, or fake subject.
    if lines[0].startswith(("To:", "Subject:")):
        if len(lines) < 4 or lines[0] != TO_LINE or not lines[1].startswith("Subject: "):
            raise IntakeError("intake draft header does not match the local request builder")
        subject = lines[1].removeprefix("Subject: ")
        if subject not in {SCOPE_SUBJECT, PAID_SUBJECT} or lines[2] != "":
            raise IntakeError("intake draft subject or header is unsupported")
        pos = 3
        envelope_present = True

    def require(line: str) -> None:
        nonlocal pos
        if pos >= len(lines) or lines[pos] != line:
            raise IntakeError("intake draft layout or mandatory statement is invalid")
        pos += 1

    require(HEADER)
    require("")
    if pos >= len(lines) or not lines[pos].startswith(_STATUS_PREFIX):
        raise IntakeError("intake draft does not state the unverified purchase claim")
    claim = lines[pos][len(_STATUS_PREFIX):]
    pos += 1
    if claim not in {PAID_CLAIM, SCOPE_CLAIM}:
        raise IntakeError("intake draft purchase claim is unsupported")
    if subject and subject != (PAID_SUBJECT if claim == PAID_CLAIM else SCOPE_SUBJECT):
        raise IntakeError("intake draft subject contradicts the purchase claim")

    values: dict[str, str] = {}
    for prefix, field in _FIELDS:
        if pos >= len(lines) or not lines[pos].startswith(prefix):
            raise IntakeError("intake draft required field is missing or out of order")
        value = lines[pos][len(prefix):]
        if not value or value != value.strip():
            raise IntakeError("intake draft contains an empty or malformed field")
        values[field] = value
        pos += 1

    require("")
    require(ASSUMPTIONS)
    count = 0
    while pos < len(lines) and lines[pos] != "":
        match = _ASSUMPTION.fullmatch(lines[pos])
        if not match or int(match.group(1)) != count + 1:
            raise IntakeError("intake draft assumptions must be numbered consecutively 1–5")
        count += 1
        values[f"assumption_{count}"] = match.group(2)
        pos += 1
    if count == 0:
        raise IntakeError("intake draft must contain at least one assumption")

    require("")
    require(CONFIRMATION)
    require("")
    require(PAID_END if claim == PAID_CLAIM else SCOPE_END)
    if pos != len(lines):
        raise IntakeError("intake draft contains unexpected content or a signature")

    values["public_only_confirmation"] = "yes"
    # The existing core is the final authority for URL, email, field size,
    # distinct-assumption and posture validation; the parser adds no sources.
    return ParsedDraft(values, claim, envelope_present)


def create_unverified_case(raw: str, *, submitted_at: str | None = None) -> tuple[dict, dict]:
    parsed = parse_customer_draft(raw)
    case = build_case_from_intake(parsed.intake, submitted_at=submitted_at)
    return case, {
        "source_kind": "BUYER_SUPPLIED_EMAIL_DRAFT",
        "purchase_claim": parsed.purchase_claim,
        "purchase_claim_verified": False,
        "sender_authenticated": False,
        "message_delivery_verified": False,
        "source_evidence_verified": False,
        "external_send_authorized": False,
        "ready_to_start_work": False,
        "envelope_present": parsed.envelope_present,
    }
