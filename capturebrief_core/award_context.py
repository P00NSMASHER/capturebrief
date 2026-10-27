"""Read-only USAspending prior-award context, never incumbent/PWin certification.

Input is a separately retrieved original USAspending.gov search response and
the exact bounded POST request used to obtain it. Local SHA-256 checks provide
integrity, NOT source authenticity. No network, credentials, payments, sends,
current solicitation inference, or public customer artifacts occur here.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

SCHEMA_VERSION = "1.0"
ENDPOINT = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
FIELDS = (
    "Award ID", "Recipient Name", "Awarding Agency", "Awarding Agency Code",
    "Base Obligation Date", "Award Amount", "NAICS",
    "generated_internal_id",
)
AWARD_TYPES = ("A", "B", "C", "D")
MAX_SOURCE_BYTES = 2_000_000
MAX_RECORDS = 25
_ID = re.compile(r"^[A-Za-z0-9_.:/-]{1,170}$")
_AGENCY = re.compile(r"^[A-Z0-9]{2,6}$")
_NAICS = re.compile(r"^[0-9]{6}$")
_CLEAN = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_SHA = re.compile(r"^[0-9a-f]{64}$")


class AwardContextHold(ValueError):
    """Research data cannot support a safe claim under this contract."""


def _date(text: Any, field: str) -> date:
    if not isinstance(text, str):
        raise AwardContextHold(f"{field}: missing ISO date")
    try:
        result = date.fromisoformat(text)
    except ValueError as exc:
        raise AwardContextHold(f"{field}: invalid ISO date") from exc
    if result.isoformat() != text:
        raise AwardContextHold(f"{field}: noncanonical ISO date")
    return result


def _time(text: Any, field: str) -> datetime:
    if not isinstance(text, str):
        raise AwardContextHold(f"{field}: missing UTC time")
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AwardContextHold(f"{field}: invalid UTC time") from exc
    if result.utcoffset() is None:
        raise AwardContextHold(f"{field}: timezone required")
    return result.astimezone(timezone.utc)


def _text(value: Any, field: str, *, max_chars: int = 200) -> str:
    if not isinstance(value, str):
        raise AwardContextHold(f"{field}: not text")
    clean = value.strip()
    if not clean or len(clean) > max_chars or _CLEAN.search(clean):
        raise AwardContextHold(f"{field}: empty, overlong, or control characters")
    return clean


def _source_json(raw: bytes, field: str) -> dict:
    if (not isinstance(raw, bytes) or not raw or len(raw) > MAX_SOURCE_BYTES):
        raise AwardContextHold(f"{field}: missing or oversized original bytes")
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise AwardContextHold(f"{field}: invalid UTF-8 JSON") from exc
    if not isinstance(obj, dict):
        raise AwardContextHold(f"{field}: JSON object required")
    return obj


def approved_request(*, start_date: str, end_date: str, limit: int = 25) -> dict:
    """Bounded official API POST shape. No search is performed by this function."""
    start, end = _date(start_date, "start_date"), _date(end_date, "end_date")
    if start > end or type(limit) is not int or not 1 <= limit <= MAX_RECORDS:
        raise AwardContextHold("Invalid time window or request limit")
    return {
        "subawards": False,
        "spending_level": "awards",
        "limit": limit,
        "page": 1,
        "filters": {
            "award_type_codes": list(AWARD_TYPES),
            "time_period": [{"start_date": start.isoformat(),
                             "end_date": end.isoformat()}],
        },
        "fields": list(FIELDS),
        "sort": "Base Obligation Date",
        "order": "desc",
    }


def _amount(value: Any) -> str | None:
    if value is None:
        return None
    if type(value) not in {int, float, str}:
        raise AwardContextHold("Award Amount: unsupported numeric type")
    if isinstance(value, str) and (not value or len(value) > 40):
        raise AwardContextHold("Award Amount: invalid numeric text")
    if isinstance(value, float) and not math.isfinite(value):
        raise AwardContextHold("Award Amount: nonfinite number")
    try:
        dec = Decimal(str(value))
    except InvalidOperation as exc:
        raise AwardContextHold("Award Amount: invalid number") from exc
    if not dec.is_finite() or abs(dec) >= Decimal("100000000000000000"):
        raise AwardContextHold("Award Amount: out of bounds")
    # Never emit dollars-cents as a *paid* figure; USAspending award
    # obligations may be updated after the original contract action.
    return str(dec)


def evaluate_award_context(
    request_bytes: bytes, response_bytes: bytes, *,
    observed_at: str, pursuit_as_of: str,
    target_agency_code: str, target_naics: str | None = None,
) -> dict:
    """Inspect one bounded original response; never assert complete award history.

    Request/response SHA-256 are local integrity proofs, not independent
    authentication that an official endpoint actually served the bytes.
    """
    req, doc = _source_json(request_bytes, "request"), _source_json(
        response_bytes, "response")
    try:
        start = req["filters"]["time_period"][0]["start_date"]
        end = req["filters"]["time_period"][0]["end_date"]
    except (KeyError, TypeError, IndexError) as exc:
        raise AwardContextHold("Unexpected award search query shape") from exc
    expected = approved_request(start_date=start, end_date=end,
                                limit=req.get("limit"))
    if req != expected:
        raise AwardContextHold("Unapproved award search filters or paging")
    observed, as_of = _time(observed_at, "observed_at"), _time(
        pursuit_as_of, "pursuit_as_of")
    agency = _text(target_agency_code, "target_agency_code", max_chars=6).upper()
    if not _AGENCY.fullmatch(agency):
        raise AwardContextHold("Invalid awarding agency code")
    if target_naics is not None and (type(target_naics) is not str
                                     or not _NAICS.fullmatch(target_naics)):
        raise AwardContextHold("NAICS must be an exact six-digit code")
    if doc.get("spending_level") != "awards" or type(doc.get("limit")) is not int or (
            doc["limit"] != req["limit"]):
        raise AwardContextHold("Wrong award level or pagination limit")
    rows, page = doc.get("results"), doc.get("page_metadata")
    if (type(rows) is not list or len(rows) > req["limit"]
            or type(page) is not dict or type(page.get("hasNext")) is not bool):
        raise AwardContextHold("Incomplete or malformed API page metadata")
    if type(doc.get("messages", [])) is not list or not all(
        isinstance(m, str) for m in doc.get("messages", [])
    ):
        raise AwardContextHold("Malformed API warning messages")
    warnings = doc.get("messages") or []
    seen = set()
    candidates = []
    exclusions = {"future_base_date": 0, "other_agency": 0, "other_naics": 0,
                  "missing_linkage_fields": 0}
    for row in rows:
        if type(row) is not dict:
            raise AwardContextHold("Malformed award row")
        identifier = row.get("generated_internal_id")
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
            raise AwardContextHold("Missing exact award identifier")
        if identifier in seen:
            raise AwardContextHold("Duplicate award identifier on one API page")
        seen.add(identifier)
        base_date = _date(row.get("Base Obligation Date"), "Base Obligation Date")
        if base_date > as_of.date():
            exclusions["future_base_date"] += 1
            continue
        actual_agency = row.get("Awarding Agency Code")
        if not isinstance(actual_agency, str) or actual_agency.upper() != agency:
            exclusions["other_agency"] += 1
            continue
        naics = row.get("NAICS")
        if target_naics is not None and (str(naics) != target_naics):
            exclusions["other_naics"] += 1
            continue
        award_id = row.get("Award ID")
        recipient = row.get("Recipient Name")
        if not isinstance(award_id, str) or not award_id.strip() or (
                not isinstance(recipient, str) or not recipient.strip()):
            exclusions["missing_linkage_fields"] += 1
            continue
        candidate = {
            "generated_internal_id": identifier,
            "award_id": _text(award_id, "Award ID", max_chars=90),
            "awarding_agency_code": agency,
            "recipient_name": _text(recipient, "Recipient Name"),
            "base_obligation_date": base_date.isoformat(),
            "award_amount_as_observed_not_historical_cash": _amount(
                row.get("Award Amount")),
            "naics": str(naics) if naics is not None else None,
            "evidence_class": "PRIOR_AWARD_CONTEXT_REVIEW_ONLY",
            "incumbent_for_requested_pursuit_verified": False,
            "customer_fit_or_win_probability": None,
            "current_award_amount_as_of_past_date_verified": False,
        }
        candidates.append(candidate)
    # A bounded award search is not an incumbent search, even if all fields
    # match. A fresh current snapshot can contain later award modifications.
    completeness = ("PAGE_INCOMPLETE" if page["hasNext"] else
                    "BOUNDED_SEARCH_ONLY")
    if warnings:
        completeness = "SOURCE_WARNING_REVIEW_REQUIRED"
    return {
        "schema_version": SCHEMA_VERSION,
        "source_endpoint": ENDPOINT,
        "publisher": "USAspending.gov / U.S. Treasury",
        "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
        "response_sha256_LOCAL_INTEGRITY_NOT_PUBLISHER_PROOF":
            hashlib.sha256(response_bytes).hexdigest(),
        "observed_at": observed.isoformat().replace("+00:00", "Z"),
        "pursuit_as_of": as_of.isoformat().replace("+00:00", "Z"),
        "temporal_basis": ("RETROSPECTIVE_ONLY_NO_AS_OF_CLAIM" if observed > as_of
                           else "CONTEMPORANEOUS_OBSERVATION_UNAUTHENTICATED"),
        "source_verified_by_independent_publisher_receipt": False,
        "request_fields_reviewed": True,
        "query_scope": "BOUNDED_PUBLIC_SEARCH_NOT_COMPLETE_MARKET_COVERAGE",
        "pagination_status": completeness,
        "number_of_rows_on_page": len(rows),
        "excluded_row_counts": exclusions,
        "award_context_candidates": candidates,
        "no_matching_awards_claimed": False,
        "incumbent_identification_verified": False,
        "award_amount_is_cash_received": False,
        "customer_pursuit_readiness_certified": False,
        "commercial_customer_scoring_approved": False,
    }
