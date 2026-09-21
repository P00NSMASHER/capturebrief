"""Operator-facing fulfillment plan built from the existing fail-closed work queue."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .audit import audit_case
from .workqueue import build_work_queue


def effort_stage(task_key: str) -> str:
    key=str(task_key or "")
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
    return "OTHER"


def build_fulfillment_plan(
    case: dict[str, Any],
    *,
    api_observation: dict[str, Any] | None = None,
    history_index_plan: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    queue=build_work_queue(
        case,
        api_observation=api_observation,
        history_index_plan=history_index_plan,
        now=now,
    )
    audit=audit_case(case,now=now)
    tasks=[]
    for task in queue["tasks"]:
        row={**task}
        row["effort_stage"]=effort_stage(task["task_key"])
        row["work_lane"]="SAFE_AUTOMATION" if task["can_auto_execute"] else "HUMAN_OR_HYBRID"
        tasks.append(row)

    p0=[x for x in tasks if x["priority"]=="P0"]
    p1=[x for x in tasks if x["priority"]=="P1"]
    p2=[x for x in tasks if x["priority"]=="P2"]
    p0_auto=[x for x in p0 if x["can_auto_execute"]]
    p0_human=[x for x in p0 if not x["can_auto_execute"]]

    # Clear deterministic approved-source/local work first, but never convert that
    # preference into permission to perform a human evidence/applicability decision.
    next_task=(p0_auto or p0_human or [x for x in p1 if x["can_auto_execute"]]
               or [x for x in p1 if not x["can_auto_execute"]]
               or [x for x in p2 if x["can_auto_execute"]]
               or [x for x in p2 if not x["can_auto_execute"]])
    next_task=next_task[0] if next_task else None

    stage_counts={}
    for task in tasks:
        stage=task["effort_stage"]
        stage_counts[stage]=stage_counts.get(stage,0)+1

    if audit.release_state=="READY_FOR_HUMAN_RELEASE" and not tasks:
        state="READY_TO_BUILD_DELIVERY"
    elif p0_human:
        state="HUMAN_REVIEW_REQUIRED"
    elif p0_auto:
        state="APPROVED_AUTOMATION_AVAILABLE"
    else:
        state="WORK_REMAINS"

    return {
        "case_id":case.get("case_id"),
        "generated_at":queue["generated_at"],
        "fulfillment_state":state,
        "release_state":audit.release_state,
        "release_blocker_codes":sorted({x.code for x in audit.findings if x.severity=="BLOCK"}),
        "next_task":next_task,
        "safe_automation_batch":p0_auto,
        "human_review_batch":p0_human,
        "later_work":{"P1":p1,"P2":p2},
        "summary":{
            "open_tasks":len(tasks),
            "p0":len(p0),
            "p0_safe_automation":len(p0_auto),
            "p0_human_or_hybrid":len(p0_human),
            "stage_task_counts":dict(sorted(stage_counts.items())),
            "automatic_evidence_or_bid_decision":False,
        },
        "effort_logging":{
            "instruction":"Time the actual operator work under the task's effort_stage; do not estimate or backfill invented minutes.",
            "stages":sorted(stage_counts),
        },
    }
