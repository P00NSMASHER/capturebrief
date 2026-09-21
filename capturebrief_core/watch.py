"""Reopen affected assumptions for packet changes and bound source/rule changes."""
from __future__ import annotations
from typing import Any
from .decision_trace import trace_change_impact
from .packet_watch import compare_cases as compare_packet_cases


def compare_cases(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    packet = compare_packet_cases(before, after)
    trace = trace_change_impact(before, after)
    reopened: dict[str, dict] = {}
    for item in packet["reopened_assumptions"] + trace["reopened_assumptions"]:
        aid = str(item.get("assumption_id"))
        row = reopened.setdefault(aid, {"assumption_id": item.get("assumption_id"), "matched_triggers": []})
        row["matched_triggers"] = sorted(set(row["matched_triggers"]) | set(item.get("matched_triggers") or []))
        if item.get("requires_human_review"):
            row["requires_human_review"] = True
    return {"events": packet["events"] + trace["events"], "reopened_assumptions": [reopened[k] for k in sorted(reopened)]}
