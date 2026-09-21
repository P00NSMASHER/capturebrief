"""Packet work plus explicit human source/rule/history review tasks."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from .decision_trace import validate_decision_trace
from .packet_workqueue import build_work_queue as build_packet_queue, _task


def build_work_queue(case: dict[str, Any], *, api_observation: dict[str, Any] | None = None, now: datetime | None = None) -> dict[str, Any]:
    queue = build_packet_queue(case, api_observation=api_observation, now=now)
    groups: dict[str, list] = {}
    for finding in validate_decision_trace(case, now=now):
        groups.setdefault(finding.path or "decision_trace", []).append(finding)
    for path, findings in sorted(groups.items()):
        queue["tasks"].append(_task(
            "decision-trace:" + path,
            "Complete source / rule / version review: " + path,
            priority="P0", actor="HUMAN_REVIEW", can_auto_execute=False,
            reason="; ".join(dict.fromkeys(f.message for f in findings)),
            evidence_needed="Exact source passage and hash; dated rule and pursuit-specific applicability basis where relevant; retained amendment history; named review bound to current inputs.",
            metadata={"finding_codes": sorted({f.code for f in findings}), "path": path},
        ))
    priority = {"P0": 0, "P1": 1, "P2": 2}
    queue["tasks"].sort(key=lambda task: (priority[task["priority"]], task["task_key"]))
    tasks = queue["tasks"]
    auto = sum(bool(t["can_auto_execute"]) for t in tasks)
    queue["release_blocked"] = bool(tasks)
    queue["summary"].update(open_tasks=len(tasks), auto_executable=auto, human_or_hybrid=len(tasks)-auto,
                            by_priority={p: sum(t["priority"] == p for t in tasks) for p in priority})
    return queue
