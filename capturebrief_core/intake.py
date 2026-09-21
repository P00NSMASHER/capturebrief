from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .model import sha256_hex


class IntakeError(ValueError):
    pass


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

    opportunity = str(intake.get("public_opportunity") or "").strip()
    posture = str(intake.get("current_posture") or "").strip().upper()
    company = str(intake.get("company") or "").strip()
    email = str(intake.get("email") or "").strip()

    if not opportunity:
        raise IntakeError("public opportunity URL or notice ID is required")
    if posture not in {"GO", "HOLD", "NO-GO", "UNSURE"}:
        raise IntakeError("current posture must be GO, HOLD, NO-GO, or UNSURE")
    if not company or not email:
        raise IntakeError("company and work email are required")

    submitted_at = submitted_at or datetime.now(timezone.utc).isoformat()
    token = sha256_hex(f"{opportunity}|{company}|{submitted_at}")[:10].upper()

    assumptions = []
    for idx in range(1, 6):
        text = str(intake.get(f"assumption_{idx}") or "").strip()
        if not text:
            continue
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
            "note": str(intake.get("question") or "").strip() or None,
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
