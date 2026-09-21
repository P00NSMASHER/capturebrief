"""Fail-closed scope approval and fixed founding-pilot checkout invitation."""
from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from .decision_trace import canonical, digest

SCHEMA="1.0"
OFFER_ID="CAPTUREBRIEF_FOUNDING_PILOT_149_V1"
PRICE_CENTS=14900
CURRENCY="USD"
SCOPE_DECISIONS={"IN_SCOPE","OUT_OF_SCOPE","NEEDS_INFO"}
REASON_CODES={
    "PUBLIC_FEDERAL_IT_CYBER_CLOUD",
    "OUTSIDE_FEDERAL",
    "OUTSIDE_IT_CYBER_CLOUD",
    "RESTRICTED_SOURCE_REQUIRED",
    "PUBLIC_SOURCE_INSUFFICIENT",
    "OPPORTUNITY_NOT_RESOLVED",
    "INTAKE_INCOMPLETE",
    "OTHER",
}
POSITIVE_REASON="PUBLIC_FEDERAL_IT_CYBER_CLOUD"
DISQUALIFYING={
    "OUTSIDE_FEDERAL","OUTSIDE_IT_CYBER_CLOUD","RESTRICTED_SOURCE_REQUIRED",
    "PUBLIC_SOURCE_INSUFFICIENT","INTAKE_INCOMPLETE",
}
STRIPE_HOSTS={"buy.stripe.com","checkout.stripe.com"}


def _dt(value:Any)->datetime|None:
    if not isinstance(value,str): return None
    try:
        d=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        return None
    return d.astimezone(timezone.utc) if d.tzinfo is not None else None


def _text(value:Any)->bool:
    return isinstance(value,str) and bool(value.strip())


def _stripe_payment_link(url:Any)->bool:
    if not isinstance(url,str): return False
    try:
        p=urlsplit(url)
    except ValueError:
        return False
    if p.scheme!="https" or p.hostname not in STRIPE_HOSTS or p.username or p.password:
        return False
    if not p.path or p.path=="/":
        return False
    # Shared Payment Links should not need secrets/credentials in the query string.
    if re.search(r"(?:api[_-]?key|secret|token|credential|signature)=",p.query,re.I):
        return False
    return True


def review_scope(
    case:dict[str,Any],
    *,
    decision:str,
    reason_codes:list[str],
    reviewed_by_role:str,
    reviewed_at:str,
)->dict[str,Any]:
    """Create a content-addressed human scope review without charging/sending anything."""
    if not isinstance(case,dict) or not _text(case.get("case_id")):
        raise ValueError("case_id is required")
    decision=str(decision).upper()
    reasons=sorted({str(x).upper() for x in (reason_codes or [])})
    if decision not in SCOPE_DECISIONS:
        raise ValueError("invalid scope decision")
    if not reasons or any(x not in REASON_CODES for x in reasons):
        raise ValueError("invalid scope reason codes")
    if not _text(reviewed_by_role) or _dt(reviewed_at) is None:
        raise ValueError("scope review requires reviewer role and timezone-aware timestamp")

    intake=case.get("intake") or {}
    assumptions=[x for x in case.get("assumptions") or [] if isinstance(x,dict)]
    if intake.get("public_only_confirmation") is not True:
        raise ValueError("public/non-sensitive confirmation is required before scope approval")
    if not (1<=len(assumptions)<=5):
        raise ValueError("founding pilot requires one to five assumptions")
    if any(not _text(x.get("text")) for x in assumptions):
        raise ValueError("every scoped assumption needs text")

    if decision=="IN_SCOPE":
        if POSITIVE_REASON not in reasons:
            raise ValueError("IN_SCOPE requires explicit public federal IT/cyber/cloud scope confirmation")
        if set(reasons)&DISQUALIFYING:
            raise ValueError("IN_SCOPE cannot carry a disqualifying scope reason")
    elif decision=="OUT_OF_SCOPE" and POSITIVE_REASON in reasons:
        raise ValueError("OUT_OF_SCOPE cannot carry the positive scope reason")

    payload={
        "schema_version":SCHEMA,
        "case_id":case["case_id"],
        "decision":decision,
        "reason_codes":reasons,
        "reviewed_by_role":reviewed_by_role,
        "reviewed_at":reviewed_at,
        "assumption_count":len(assumptions),
        "public_only_confirmation":True,
        "offer_id":OFFER_ID if decision=="IN_SCOPE" else None,
        "automatic_charge_authorized":False,
        "automatic_send_authorized":False,
    }
    return {"scope_review_id":"SCOPE:"+digest(canonical(payload)),**payload}


def validate_scope_review(case:dict[str,Any],review:dict[str,Any])->list[str]:
    errors=[]
    if not isinstance(review,dict):
        return ["scope_review_not_object"]
    rid=review.get("scope_review_id")
    body={k:v for k,v in review.items() if k!="scope_review_id"}
    if rid!="SCOPE:"+digest(canonical(body)): errors.append("scope_review_hash_mismatch")
    if review.get("schema_version")!=SCHEMA: errors.append("scope_review_schema")
    if review.get("case_id")!=case.get("case_id"): errors.append("scope_review_case_mismatch")
    if review.get("decision") not in SCOPE_DECISIONS: errors.append("scope_review_decision")
    if _dt(review.get("reviewed_at")) is None: errors.append("scope_review_time")
    if not _text(review.get("reviewed_by_role")): errors.append("scope_review_reviewer")
    reasons=review.get("reason_codes")
    if not isinstance(reasons,list) or not reasons or any(x not in REASON_CODES for x in reasons): errors.append("scope_review_reasons")
    if review.get("automatic_charge_authorized") is not False: errors.append("scope_review_auto_charge")
    if review.get("automatic_send_authorized") is not False: errors.append("scope_review_auto_send")
    assumptions=[x for x in case.get("assumptions") or [] if isinstance(x,dict)]
    if review.get("assumption_count")!=len(assumptions): errors.append("scope_review_assumption_count")
    if (case.get("intake") or {}).get("public_only_confirmation") is not True or review.get("public_only_confirmation") is not True: errors.append("scope_review_public_only")
    if review.get("decision")=="IN_SCOPE":
        if POSITIVE_REASON not in (reasons or []): errors.append("scope_review_positive_reason_missing")
        if set(reasons or [])&DISQUALIFYING: errors.append("scope_review_disqualifying_reason")
        if review.get("offer_id")!=OFFER_ID: errors.append("scope_review_offer")
    return sorted(set(errors))


def build_activation_packet(
    case:dict[str,Any],
    scope_review:dict[str,Any],
    *,
    created_at:str,
    checkout_url:str|None=None,
)->dict[str,Any]:
    """Bind one approved case to the fixed founding offer. Does not send or charge."""
    errors=validate_scope_review(case,scope_review)
    if errors:
        raise ValueError("invalid scope review: "+",".join(errors))
    if scope_review.get("decision")!="IN_SCOPE":
        raise ValueError("checkout invitation requires an IN_SCOPE review")
    if _dt(created_at) is None:
        raise ValueError("activation created_at must be timezone-aware")
    if checkout_url is not None and not _stripe_payment_link(checkout_url):
        raise ValueError("checkout_url must be a verified Stripe Payment Link host")

    assumptions=[
        {"assumption_id":x.get("assumption_id"),"text":x.get("text")}
        for x in case.get("assumptions") or []
        if isinstance(x,dict)
    ]
    payload={
        "schema_version":SCHEMA,
        "case_id":case["case_id"],
        "scope_review_id":scope_review["scope_review_id"],
        "created_at":created_at,
        "status":"READY_TO_SEND" if checkout_url else "AWAITING_VERIFIED_CHECKOUT",
        "offer":{
            "offer_id":OFFER_ID,
            "name":"CaptureBrief Founding Decision Evidence Review",
            "price_cents":PRICE_CENTS,
            "currency":CURRENCY,
            "payment_model":"ONE_TIME",
            "automatic_renewal":False,
            "pursuits_included":1,
            "assumption_limit":5,
            "public_source_only":True,
            "targeted_watch_days":14,
        },
        "scoped_assumptions":assumptions,
        "checkout":{
            "provider":"STRIPE_PAYMENT_LINK",
            "url":checkout_url,
            "customer_not_charged_by_packet":True,
        },
        "delivery_promise":[
            "concise decision handoff",
            "exact public-source passages and source/version evidence",
            "reviewed rule edition/applicability basis when relevant",
            "explicit missing-evidence requests",
            "release-gated Decision Evidence package",
            "14-day targeted public-source change watch",
        ],
        "boundaries":[
            "no bid-submission service",
            "no PWin or win guarantee",
            "no legal advice or automatic eligibility decision",
            "no restricted/private-portal material",
            "customer retains pursue/hold/pass authority",
        ],
        "automatic_send_authorized":False,
        "automatic_charge_authorized":False,
    }
    return {"activation_id":"ACT:"+digest(canonical(payload)),**payload}


def validate_activation_packet(packet:dict[str,Any])->list[str]:
    errors=[]
    if not isinstance(packet,dict): return ["activation_not_object"]
    aid=packet.get("activation_id")
    body={k:v for k,v in packet.items() if k!="activation_id"}
    if aid!="ACT:"+digest(canonical(body)): errors.append("activation_hash_mismatch")
    if packet.get("schema_version")!=SCHEMA: errors.append("activation_schema")
    offer=packet.get("offer") or {}
    expected={
        "offer_id":OFFER_ID,"price_cents":PRICE_CENTS,"currency":CURRENCY,
        "payment_model":"ONE_TIME","automatic_renewal":False,"pursuits_included":1,
        "assumption_limit":5,"public_source_only":True,"targeted_watch_days":14,
    }
    for key,value in expected.items():
        if offer.get(key)!=value: errors.append("offer_"+key)
    checkout=packet.get("checkout") or {}
    url=checkout.get("url")
    if packet.get("status")=="READY_TO_SEND":
        if not _stripe_payment_link(url): errors.append("activation_checkout_url")
    elif packet.get("status")=="AWAITING_VERIFIED_CHECKOUT":
        if url is not None: errors.append("activation_pending_has_url")
    else:
        errors.append("activation_status")
    if checkout.get("customer_not_charged_by_packet") is not True: errors.append("activation_charge_boundary")
    if packet.get("automatic_send_authorized") is not False: errors.append("activation_auto_send")
    if packet.get("automatic_charge_authorized") is not False: errors.append("activation_auto_charge")
    if _dt(packet.get("created_at")) is None: errors.append("activation_created_at")
    return sorted(set(errors))


def render_checkout_invitation(packet:dict[str,Any])->str:
    errors=validate_activation_packet(packet)
    if errors: raise ValueError("invalid activation packet: "+",".join(errors))
    if packet["status"]!="READY_TO_SEND":
        raise ValueError("activation is waiting for a verified checkout URL")
    url=packet["checkout"]["url"]
    assumptions=packet.get("scoped_assumptions") or []
    lines=[
        "CaptureBrief founding review",
        "",
        f"Case: {packet['case_id']}",
        f"Price: $149 one time — no automatic renewal.",
        "",
        "Included:",
        "- one public federal IT / cyber / cloud pursuit",
        f"- {len(assumptions)} scoped assumption{'s' if len(assumptions)!=1 else ''} (maximum 5)",
        "- concise decision handoff",
        "- exact public-source passages and source/version evidence",
        "- reviewed rule edition/applicability basis when relevant",
        "- explicit missing-evidence requests",
        "- release-gated Decision Evidence package",
        "- 14-day targeted public-source change watch",
        "",
        "Checkout:",
        url,
        "",
        "Your team keeps all pursue / hold / pass decisions. CaptureBrief does not provide bid submission, legal advice, PWin scoring, or win guarantees.",
    ]
    return "\n".join(lines)+"\n"
