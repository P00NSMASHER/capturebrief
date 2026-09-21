from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .authority import validate_current_action_receipts
from .history import validate_history_receipts
from .manifest import validate_manifest_receipts
from .model import parse_dt
from .packet import validate_reference_closure

_PRIORITY = {"P0": 0, "P1": 1, "P2": 2}


def _task(
    key: str,
    title: str,
    *,
    priority: str = "P0",
    actor: str = "HUMAN_REVIEW",
    can_auto_execute: bool = False,
    reason: str,
    evidence_needed: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "task_key": key,
        "priority": priority,
        "title": title,
        "actor": actor,
        "can_auto_execute": can_auto_execute,
        "reason": reason,
        "evidence_needed": evidence_needed,
        "metadata": metadata or {},
        "status": "OPEN",
    }


def build_work_queue(
    case: dict[str, Any],
    *,
    api_observation: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Generate the smallest next-step queue needed to move a case toward release.

    This function does not mutate evidence or make findings true. It translates existing
    evidence state into operational work and labels which steps can use approved automation.
    """
    now = now or datetime.now(timezone.utc)
    packet = case.get("packet") or {}
    history_ids = packet.get("history_action_ids") or []
    status = str(packet.get("family_status") or "UNKNOWN").upper()
    tasks: dict[str, dict[str, Any]] = {}

    def add(task: dict[str, Any]) -> None:
        tasks.setdefault(task["task_key"], task)

    history_verdict, history_findings = validate_history_receipts(
        history_ids,
        packet.get("history_receipts") or [],
    )
    if history_verdict != "HISTORY_COMPLETE":
        add(_task(
            "history:establish",
            "Establish the complete public action set",
            actor="HYBRID",
            can_auto_execute=True,
            reason="The action/version history is not yet supported by a complete receipt.",
            evidence_needed="SAM Data Services active extract plus confirmed fiscal-year archive coverage.",
            metadata={"finding_codes": sorted({f.code for f in history_findings})},
        ))

    current_verdict, current_action, current_findings = validate_current_action_receipts(
        history_ids,
        status,
        case.get("current_action_receipts") or [],
        now=now,
    )
    required = {
        "ACTIVE": "CURRENT_VERIFIED",
        "CANCELLED": "TERMINAL_CANCELLED_VERIFIED",
        "ARCHIVED": "TERMINAL_ARCHIVED_VERIFIED",
    }
    if status == "UNKNOWN":
        add(_task(
            "family:status",
            "Determine the opportunity family status",
            actor="HYBRID",
            can_auto_execute=True,
            reason="The intake has not yet been resolved to an active, cancelled, archived, inactive, or deleted family.",
            evidence_needed="Documented SAM opportunity/API evidence linked to the submitted pursuit.",
        ))
    elif status in required and current_verdict != required[status]:
        add(_task(
            "current:authority",
            "Verify the controlling current or terminal action",
            actor="AUTOMATED_APPROVED_SOURCE" if status == "ACTIVE" else "HUMAN_REVIEW",
            can_auto_execute=status == "ACTIVE",
            reason=f"Family status is {status}, but authority state is {current_verdict}.",
            evidence_needed="Documented Opportunities API receipt for active currentness, or explicit first-party terminal evidence.",
            metadata={"finding_codes": sorted({f.code for f in current_findings})},
        ))

    manifest_verdict, manifest_summary, manifest_findings = validate_manifest_receipts(
        history_ids,
        packet.get("manifest_receipts") or [],
    )
    if manifest_verdict != "MANIFEST_COMPLETE":
        missing = manifest_summary.get("missing_actions") or []
        conflicts = manifest_summary.get("conflicting_actions") or []
        for action_id in missing:
            add(_task(
                f"manifest:{action_id}",
                f"Inspect attachment/tombstone state for action {action_id}",
                actor="HUMAN_REVIEW",
                can_auto_execute=False,
                reason="Historical deletion-inclusive packet state is not available from an approved automated source.",
                evidence_needed="Human-supervised first-party SAM packet/attachment observation retained and hashed.",
                metadata={"action_id": action_id},
            ))
        for action_id in conflicts:
            add(_task(
                f"manifest-conflict:{action_id}",
                f"Reconcile conflicting packet observations for action {action_id}",
                actor="HUMAN_REVIEW",
                reason="Multiple successful observations disagree for the same action.",
                evidence_needed="Fresh first-party observation plus retained conflicting snapshots.",
                metadata={"action_id": action_id},
            ))
        if not missing and not conflicts:
            add(_task(
                "manifest:review",
                "Resolve packet-manifest validation blockers",
                actor="HUMAN_REVIEW",
                reason="Manifest coverage is not releasable even though no simple missing/conflict action was identified.",
                evidence_needed="Corrected first-party manifest receipts.",
                metadata={"finding_codes": sorted({f.code for f in manifest_findings})},
            ))

    scan = packet.get("reference_scan") or {}
    if scan.get("status") != "COMPLETE":
        add(_task(
            "references:scan",
            "Complete the named-dependency scan",
            actor="HUMAN_REVIEW",
            reason="The notice/document reference inventory is not complete.",
            evidence_needed="Reviewed named amendments, attachments, exhibits, schedules, drawings, and external systems.",
        ))

    reference_verdict, ref_findings = validate_reference_closure(packet)
    if reference_verdict != "REFERENCE_CLOSURE_COMPLETE":
        for ref in packet.get("references") or []:
            resolution = str(ref.get("resolution") or "UNRESOLVED").upper()
            if resolution == "UNRESOLVED":
                rid = str(ref.get("reference_id") or ref.get("label") or "unknown")
                add(_task(
                    f"reference:{rid}",
                    f"Resolve referenced dependency: {ref.get('label') or rid}",
                    actor="HUMAN_REVIEW",
                    reason="A controlling/named dependency is still unresolved.",
                    evidence_needed="Verified resource+bytes, source-backed supersession, or explicit external/restricted dependency.",
                    metadata={"reference_id": ref.get("reference_id")},
                ))
        if not any(key.startswith("reference:") for key in tasks):
            add(_task(
                "references:closure",
                "Resolve reference-closure blockers",
                actor="HUMAN_REVIEW",
                reason="Reference closure is not complete.",
                evidence_needed="Corrected reference states and supporting evidence.",
                metadata={"finding_codes": sorted({f.code for f in ref_findings})},
            ))

    api_observation = api_observation or packet.get("current_api_observation") or {}
    approved_links = set(api_observation.get("resource_links") or [])
    for artifact in packet.get("artifacts") or []:
        if artifact.get("required_for_analysis") is not True:
            continue
        aid = str(artifact.get("artifact_id") or "unknown")
        state = str(artifact.get("state") or "UNKNOWN").upper()
        byte_state = str(artifact.get("byte_state") or "").upper()
        url = artifact.get("resource_url")
        auto = bool(url and url in approved_links)
        captureable = state == "PUBLIC" or (state == "UNKNOWN" and auto)
        if captureable and (
            not artifact.get("sha256") or byte_state != "BYTES_VERIFIED_HASHED"
        ):
            add(_task(
                f"bytes:{aid}",
                f"Capture required public bytes for {artifact.get('name') or aid}",
                actor="AUTOMATED_APPROVED_SOURCE" if auto else "HUMAN_REVIEW",
                can_auto_execute=auto,
                reason="A required public artifact does not yet have verified immutable bytes.",
                evidence_needed="SHA-256 byte receipt bound to the source object.",
                metadata={"artifact_id": aid, "resource_url": url},
            ))

    for item in case.get("assumptions") or []:
        aid = str(item.get("assumption_id") or "unknown")
        decision = str(item.get("decision_class") or "").upper()
        if decision in {"GATE_CHANGING", "VERIFY_NOW"}:
            if not item.get("next_action"):
                add(_task(
                    f"assumption-action:{aid}",
                    f"Define next action for assumption {aid}",
                    priority="P1",
                    reason="Decision-changing items require a concrete next action.",
                    evidence_needed="Explicit reviewer action.",
                ))
            if not item.get("owner") and not item.get("evidence_request"):
                add(_task(
                    f"assumption-owner:{aid}",
                    f"Assign owner/evidence request for assumption {aid}",
                    priority="P1",
                    reason="Decision-changing items cannot remain unowned.",
                    evidence_needed="Owner or specific evidence request.",
                ))
        if not item.get("source_ids"):
            add(_task(
                f"assumption-source:{aid}",
                f"Link evidence to assumption {aid}",
                priority="P1",
                reason="The assumption is not linked to any retained source evidence.",
                evidence_needed="One or more source IDs supporting the evidence state.",
            ))
        if item.get("deadline") is not None and not parse_dt(item.get("deadline")):
            add(_task(
                f"assumption-deadline:{aid}",
                f"Correct deadline timezone for assumption {aid}",
                priority="P1",
                reason="Decision-relevant deadlines must preserve an explicit timezone/offset.",
                evidence_needed="Timezone-aware ISO-8601 deadline.",
            ))

    ordered = sorted(
        tasks.values(),
        key=lambda task: (_PRIORITY[task["priority"]], task["task_key"]),
    )
    counts = {
        priority: sum(task["priority"] == priority for task in ordered)
        for priority in _PRIORITY
    }
    auto_count = sum(task["can_auto_execute"] for task in ordered)

    return {
        "case_id": case.get("case_id"),
        "generated_at": now.isoformat(),
        "release_blocked": bool(ordered),
        "summary": {
            "open_tasks": len(ordered),
            "auto_executable": auto_count,
            "human_or_hybrid": len(ordered) - auto_count,
            "by_priority": counts,
            "current_action": current_action,
        },
        "tasks": ordered,
    }
