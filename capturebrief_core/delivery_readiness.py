"""One fail-closed preparation contract for the planner and delivery builder.

This checks evidence readiness, not permission to transmit a package, publish it,
or make a procurement decision. The existing audit and trace engines remain the
sources of their respective findings.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .audit import audit_case
from .decision_trace import evaluate_decision_trace
from .model import AuditResult


@dataclass(frozen=True)
class DeliveryReadiness:
    checked_at: datetime
    audit: AuditResult
    trace: dict[str, Any]
    blocker_codes: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return not self.blocker_codes


def evaluate_delivery_readiness(
    case: dict[str, Any], *, now: datetime | None = None,
) -> DeliveryReadiness:
    """Evaluate both evidence planes using one explicit, timezone-aware clock.

    Legacy case readability never satisfies the required Decision Evidence
    contract. A contradictory green state plus a blocking finding remains red.
    No precomputed verdict or caller-supplied approval flag is accepted.
    """
    if not isinstance(case, dict):
        raise ValueError("case must be an object")
    checked_at = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(checked_at, datetime) or checked_at.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    checked_at = checked_at.astimezone(timezone.utc)

    audit = audit_case(case, now=checked_at)
    trace = evaluate_decision_trace(case, now=checked_at)
    blockers = {f.code for f in audit.findings if f.severity == "BLOCK"}
    blockers.update(
        f["code"] for f in trace["findings"] if f["severity"] == "BLOCK"
    )
    if case.get("decision_trace_required") is not True:
        blockers.add("DELIVERY_REQUIRES_DECISION_TRACE")
    if audit.release_state != "READY_FOR_HUMAN_RELEASE":
        blockers.add("DELIVERY_CASE_AUDIT_FAILED")
    if trace.get("trace_state") != "TRACE_COMPLETE":
        blockers.add("DELIVERY_TRACE_INCOMPLETE")
    if trace.get("synthetic") is True:
        blockers.add("DELIVERY_SYNTHETIC_EVIDENCE")

    return DeliveryReadiness(
        checked_at=checked_at,
        audit=audit,
        trace=trace,
        blocker_codes=tuple(sorted(blockers)),
    )
