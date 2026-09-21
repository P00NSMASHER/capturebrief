"""Compose packet authority checks with assumption-level traceability checks."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from .packet_audit import audit_case as audit_packet
from .decision_trace import validate_decision_trace
from .model import AuditResult


def audit_case(case: dict[str, Any], *, now: datetime | None = None) -> AuditResult:
    packet = audit_packet(case, now=now)
    findings = packet.findings + tuple(validate_decision_trace(case, now=now))
    blocked = any(f.severity == "BLOCK" for f in findings)
    return AuditResult(
        "FAIL_CLOSED" if blocked else "READY_FOR_HUMAN_RELEASE",
        packet.currentness_verdict, packet.current_action_id, findings,
    )
