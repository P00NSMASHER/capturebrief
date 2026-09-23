from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .model import sha256_hex


class IntakeError(ValueError):
    pass


_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}$")
_ASSUMPTION_KEY_RE = re.compile(r"^assumption_(\d+)$")


def _bounded_text(value: Any, *, field: str, maximum: int, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise IntakeError(f"{field} is required")
    if len(text) > maximum:
        raise IntakeError(f"{field} must be {maximum} characters or fewer")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
        raise IntakeError(f"{field} contains unsupported control characters")
    return text


def _public_web_reference(value: Any) -> str:
    opportunity = _bounded_text(
        value,
        field="public opportunity URL",
        maximum=2048,
    )
    try:
        parsed = urlparse(opportunity)
    except ValueError as exc:
        raise IntakeError("public opportunity must be a complete http:// or https:// URL") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise IntakeError("public opportunity must be a complete http:// or https:// URL")
    if parsed.username or parsed.password:
        raise IntakeError("public opportunity URL must not contain credentials")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in {"localhost", "127.0.0.1", "::1"} or hostname.endswith(".local"):
        raise IntakeError("public opportunity URL must reference a public host")
    return opportunity


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "confirmed"}


def build_case_from_intake(
    intake: dict[str, Any],
    *,
    submitted_at: str | None = None,
) -> dict[str, Any]:
    """Convert the current website intake into a non-evidentiary case skeleton.

    The intake is a customer assertion, not source evidence. No assumption is marked supported,
    no source is invented, and the initial case is intentionally non-releasable.
    """
    if not _truthy(intake.get("public_only_confirmation")):
        raise IntakeError("public/non-sensitive information confirmation is required")

    opportunity = _public_web_reference(intake.get("public_opportunity"))
    posture = str(intake.get("current_posture") or "").strip().upper()
    company = _bounded_text(intake.get("company"), field="company", maximum=200)
    email = _bounded_text(intake.get("email"), field="work email", maximum=254)

    if posture not in {"GO", "HOLD", "PASS", "NO-GO", "UNSURE"}:
        raise IntakeError("current posture must be GO, HOLD, PASS, or UNSURE")
    if posture == "NO-GO":
        posture = "PASS"
    if not _EMAIL_RE.fullmatch(email):
        raise IntakeError("work email must be a valid email address")

    submitted_at = submitted_at or datetime.now(timezone.utc).isoformat()
    token = sha256_hex(f"{opportunity}|{company}|{submitted_at}")[:10].upper()

    extra_assumptions = sorted(
        key
        for key, value in intake.items()
        if (match := _ASSUMPTION_KEY_RE.fullmatch(str(key)))
        and int(match.group(1)) > 5
        and str(value or "").strip()
    )
    if extra_assumptions:
        raise IntakeError("no more than five assumptions may be submitted")

    assumptions = []
    seen_assumptions: set[str] = set()
    for idx in range(1, 6):
        text = _bounded_text(
            intake.get(f"assumption_{idx}"),
            field=f"assumption {idx}",
            maximum=500,
            required=False,
        )
        if not text:
            continue
        normalized = " ".join(text.casefold().split())
        if normalized in seen_assumptions:
            raise IntakeError("duplicate assumptions are not allowed")
        seen_assumptions.add(normalized)
        assumptions.append({
            "assumption_id": f"A{idx}",
            "text": text,
            "evidence_state": "UNPROVEN",
            "decision_class": "VERIFY_NOW",
            "finding": "Not yet tested against controlling public evidence.",
            "next_action": "Verify against the controlling public opportunity record and packet.",
            "owner": "CaptureBrief reviewer",
            "source_ids": [],
            "reopen_triggers": [
                "CURRENT_ACTION_CHANGE",
                "PACKET_REFERENCE_CLOSURE_CHANGE",
            ],
        })

    if not assumptions:
        raise IntakeError("at least one assumption is required")

    return {
        "case_schema_version": "0.2",
        "decision_trace_required": True,
        "case_id": f"CB-{token}",
        "family_id": f"UNRESOLVED-{token}",
        "current_posture": posture,
        "intake": {
            "submitted_at": submitted_at,
            "company": company,
            "email": email,
            "public_opportunity": opportunity,
            "note": _bounded_text(
                intake.get("question"),
                field="question",
                maximum=2000,
                required=False,
            ) or None,
            "public_only_confirmation": True,
        },
        "packet": {
            "family_status": "UNKNOWN",
            "history_action_ids": [],
            "history_receipts": [],
            "manifest_receipts": [],
            "reference_scan": {"status": "PENDING"},
            "references": [],
            "artifacts": [],
            "external_dependencies": [],
        },
        "current_action_receipts": [],
        "sources": [],
        "assumptions": assumptions,
    }
