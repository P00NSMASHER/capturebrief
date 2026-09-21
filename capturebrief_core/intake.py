"""All new website intakes require assumption/source/rule/version history."""
from __future__ import annotations
from typing import Any
from .base_intake import IntakeError, build_case_from_intake as build_base_case
from .decision_trace import initialize_trace


def build_case_from_intake(intake: dict[str, Any], *, submitted_at: str | None = None) -> dict[str, Any]:
    case = build_base_case(intake, submitted_at=submitted_at)
    for assumption in case["assumptions"]:
        assumption["reopen_triggers"] = [
            "PACKET_REFERENCE_CLOSURE" if t == "PACKET_REFERENCE_CLOSURE_CHANGE" else t
            for t in assumption.get("reopen_triggers", [])
        ]
    try:
        return initialize_trace(case, decision_at=case["intake"]["submitted_at"])
    except ValueError as exc:
        raise IntakeError(str(exc)) from exc
