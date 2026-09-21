"""Operator planning only: work availability is not execution or send authority."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .delivery_readiness import evaluate_delivery_readiness
from .workqueue import build_work_queue

_AUTOMATED_ACTORS = frozenset({"AUTOMATED_APPROVED_SOURCE", "AUTOMATED_LOCAL"})
_PRIORITY = {"P0": 0, "P1": 1, "P2": 2}


def effort_stage(task_key: str) -> str:
    key = str(task_key or "")
    if key.startswith(("history:", "history-index:", "current:", "family:")):
        return "HISTORY_CURRENT"
    if key.startswith(("manifest:", "manifest-conflict:", "bytes:")):
        return "PACKET_BYTES"
    if key.startswith(("reference:", "references:", "reference-matches:")):
        return "REFERENCE_REVIEW"
    if key.startswith(("assumption-", "trace:")):
        return "ASSUMPTION_REVIEW"
    if key.startswith(("rule-", "rule:", "rules:")):
        return "RULE_REVIEW"
    if key.startswith("deviation"):
        return "DEVIATION_REVIEW"
    if key.startswith("delivery:"):
        return "DELIVERY"
    return "OTHER"


def _automation_eligible(task: dict[str, Any]) -> bool:
    # HYBRID can contain an automated substep, but the whole task still needs review.
    return task.get("can_auto_execute") is True and task.get("actor") in _AUTOMATED_ACTORS


def build_fulfillment_plan(
    case: dict[str, Any],
    *,
    api_observation: dict[str, Any] | None = None,
    history_index_plan: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    readiness = evaluate_delivery_readiness(case, now=now)
    now = readiness.checked_at
    queue = build_work_queue(case, api_observation=api_observation,
                             history_index_plan=history_index_plan, now=now)
    audit = readiness.audit
    trace = readiness.trace
    blockers = readiness.blocker_codes
    trace_required = case.get("decision_trace_required") is True
    bundle_eligible = readiness.eligible
    tasks = []
    for task in queue["tasks"]:
        row = {**task}
        row["queue_can_auto_execute"] = task.get("can_auto_execute") is True
        row["can_auto_execute"] = _automation_eligible(task)
        row["effort_stage"] = effort_stage(task["task_key"])
        row["work_lane"] = "SAFE_AUTOMATION" if row["can_auto_execute"] else "HUMAN_OR_HYBRID"
        tasks.append(row)

    if not bundle_eligible:
        tasks.append({
            "task_key": "delivery:readiness", "priority": "P0", "status": "OPEN",
            "title": "Resolve customer-bundle readiness before packaging",
            "actor": "HUMAN_REVIEW", "can_auto_execute": False,
            "queue_can_auto_execute": False, "work_lane": "HUMAN_OR_HYBRID",
            "effort_stage": "DELIVERY",
            "reason": "Legacy readability or an empty work queue cannot authorize a customer bundle.",
            "evidence_needed": "Required non-synthetic complete Decision Evidence and a passing full case audit.",
            "metadata": {"finding_codes": list(blockers)},
        })

    tasks.sort(key=lambda t: (_PRIORITY.get(t["priority"], 0), t["task_key"]))
    by_priority = {p: [t for t in tasks if t["priority"] == p] for p in _PRIORITY}
    p0_auto = [t for t in by_priority["P0"] if t["can_auto_execute"]]
    p0_human = [t for t in by_priority["P0"] if not t["can_auto_execute"]]
    next_task = next((t for p in _PRIORITY for auto in (True, False)
                      for t in by_priority[p] if t["can_auto_execute"] is auto), None)
    stage_counts: dict[str, int] = {}
    for task in tasks:
        stage = task["effort_stage"]
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    if not trace_required:
        state = "TRACE_UPGRADE_REQUIRED"
    elif bundle_eligible and not tasks:
        state = "READY_TO_BUILD_DELIVERY"
    elif p0_human:
        state = "HUMAN_REVIEW_REQUIRED"
    elif p0_auto:
        state = "APPROVED_AUTOMATION_AVAILABLE"
    else:
        state = "WORK_REMAINS"

    return {
        "case_id": case.get("case_id"), "generated_at": queue["generated_at"],
        "fulfillment_state": state, "release_state": audit.release_state,
        "trace_state": trace["trace_state"],
        "delivery_bundle_eligible": bundle_eligible,
        "delivery_checked_at": now.isoformat().replace("+00:00", "Z"),
        "release_blocker_codes": list(blockers), "next_task": next_task,
        "safe_automation_batch": p0_auto, "human_review_batch": p0_human,
        "later_work": {"P1": by_priority["P1"], "P2": by_priority["P2"]},
        "summary": {
            "open_tasks": len(tasks), "p0": len(by_priority["P0"]),
            "p0_safe_automation": len(p0_auto), "p0_human_or_hybrid": len(p0_human),
            "stage_task_counts": dict(sorted(stage_counts.items())),
            "automatic_evidence_or_bid_decision": False,
            "automatic_execution_performed": False,
        },
        "communications": {
            "external_send_authorized": False,
            "approval_required_for_each_message": True,
            "inbound_reply_grants_send_permission": False,
            "completed_bundle_grants_send_permission": False,
        },
        "effort_logging": {
            "instruction": "Time actual operator work under the task's effort_stage; do not invent minutes.",
            "stages": sorted(stage_counts),
        },
    }
