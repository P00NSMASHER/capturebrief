"""Render the existing concise handoff plus an assumption-specific evidence history."""
from __future__ import annotations
from typing import Any
from .audit import audit_case
from .decision_trace import render_trace_markdown
from .model import AuditResult
from .packet_render import render_markdown as render_packet_markdown


def render_markdown(case: dict[str, Any], audit: AuditResult | None = None) -> str:
    audit = audit or audit_case(case)
    original = render_packet_markdown(case, audit)
    marker = "## Forensic appendix"
    history = render_trace_markdown(case)
    if marker in original:
        return original.replace(marker, marker + "\n\n" + history, 1)
    return original + "\n\n" + history
