from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .authority import validate_current_action_receipts
from .history import validate_history_receipts
from .manifest import validate_manifest_receipts
from .model import parse_dt, valid_sha256
from .packet import validate_reference_closure
from .reference_match import reference_match_proposal_is_current
from .rule_candidates import rule_candidate_work_item, rule_sync_work_items
from .rule_evidence import rule_evidence_work_item

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
    history_index_plan: dict[str, Any] | None = None,
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
        plan = history_index_plan or {}
        api_record = (api_observation or {}).get("record") or {}
        seed_notice_id = str(api_record.get("noticeId") or "")
        solicitation_number = str(api_record.get("solicitationNumber") or "")
        if plan:
            if plan.get("complete") is True:
                if seed_notice_id and solicitation_number:
                    add(_task(
                        "history:issue-from-index",
                        "Issue the complete action-set receipt from the shared Data Services index",
                        actor="AUTOMATED_APPROVED_SOURCE",
                        can_auto_execute=True,
                        reason="The full-catalog Data Services index is complete and fresh, and the documented API supplied the family seed action.",
                        evidence_needed="A FULL_CATALOG history receipt bound to the API seed Notice ID.",
                        metadata={
                            "index_fiscal_year": plan.get("fiscal_year"),
                            "seed_notice_id": seed_notice_id,
                            "solicitation_number": solicitation_number,
                        },
                    ))
                else:
                    add(_task(
                        "history:seed-current-action",
                        "Obtain the first-party current-action seed for indexed history lookup",
                        actor="AUTOMATED_APPROVED_SOURCE",
                        can_auto_execute=True,
                        reason="The shared history index is ready, but family lookup must be anchored to an independently observed current action rather than selected from bulk data.",
                        evidence_needed="Documented SAM Opportunities API observation containing Notice ID and solicitation number.",
                    ))
            else:
                download_plan = plan.get("download_plan") or []
                reason_counts: dict[str, int] = {}
                for item in download_plan:
                    reason = str(item.get("reason") or "MISSING")
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
                if download_plan:
                    add(_task(
                        "history-index:refresh",
                        f"Bring {len(download_plan)} Data Services source slot(s) to releasable state",
                        actor="AUTOMATED_APPROVED_SOURCE",
                        can_auto_execute=True,
                        reason="The shared full-catalog history index has missing, stale, or unverified source slots.",
                        evidence_needed="Approved first-party source checks for every required ACTIVE/archive slot.",
                        metadata={
                            "index_fiscal_year": plan.get("fiscal_year"),
                            "reason_counts": reason_counts,
                            "download_plan": download_plan,
                        },
                    ))
                else:
                    add(_task(
                        "history-index:diagnose",
                        "Diagnose the shared Data Services history index",
                        actor="HUMAN_REVIEW",
                        can_auto_execute=False,
                        reason="The history index reports incomplete coverage but did not produce a source remediation plan.",
                        evidence_needed="Index status/coverage review and corrected sync plan.",
                        metadata={"index_fiscal_year": plan.get("fiscal_year")},
                    ))
        else:
            add(_task(
                "history:establish",
                "Establish the complete public action set",
                actor="HYBRID",
                can_auto_execute=True,
                reason="The action/version history is not yet supported by a complete receipt.",
                evidence_needed="Fresh shared Data Services index coverage or a complete approved extract receipt.",
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
    scan_status = str(scan.get("status") or "PENDING").upper()
    if scan_status == "PROPOSED":
        add(_task(
            "references:review-proposal",
            "Review the proposed named-dependency inventory",
            actor="HUMAN_REVIEW",
            can_auto_execute=False,
            reason="Automation has surfaced candidate references but cannot attest semantic completeness or decide which mentions are controlling dependencies.",
            evidence_needed="Human decision for every proposed candidate, source-coverage attestation, and any manually added parser misses.",
            metadata={"proposal_sha256": scan.get("proposal_sha256")},
        ))
    elif scan_status != "COMPLETE":
        add(_task(
            "references:propose",
            "Generate a conservative named-dependency proposal from retained public text",
            actor="AUTOMATED_LOCAL",
            can_auto_execute=True,
            reason="No reviewed dependency inventory exists yet. Automated extraction may propose candidates but cannot mark the scan complete.",
            evidence_needed="Retained public notice/document text followed by human review.",
        ))

    if scan_status == "COMPLETE":
        reference_verdict, ref_findings = validate_reference_closure(packet)
        if reference_verdict != "REFERENCE_CLOSURE_COMPLETE":
            unresolved_refs = [
                ref for ref in packet.get("references") or []
                if str(ref.get("resolution") or "UNRESOLVED").upper() == "UNRESOLVED"
            ]
            if unresolved_refs and not reference_match_proposal_is_current(case):
                add(_task(
                    "reference-matches:propose",
                    "Propose likely retained resource matches for unresolved references",
                    actor="AUTOMATED_LOCAL",
                    can_auto_execute=True,
                    reason="The human-confirmed dependency inventory has unresolved references but no current local resource-match proposal.",
                    evidence_needed="Deterministic local match proposal over retained manifest/resource metadata. Human resolution remains required.",
                    metadata={"unresolved_reference_ids": [ref.get("reference_id") for ref in unresolved_refs]},
                ))
            elif unresolved_refs:
                match_rows = {
                    str(row.get("reference_id")): row
                    for row in (packet.get("reference_match_proposal") or {}).get("matches") or []
                    if row.get("reference_id")
                }
                for ref in unresolved_refs:
                    rid = str(ref.get("reference_id") or ref.get("label") or "unknown")
                    match = match_rows.get(str(ref.get("reference_id"))) or {}
                    add(_task(
                        f"reference:{rid}",
                        f"Resolve referenced dependency: {ref.get('label') or rid}",
                        actor="HUMAN_REVIEW",
                        reason="A controlling/named dependency is still unresolved. Local match candidates are suggestions only.",
                        evidence_needed="Human choice of verified resource+bytes, source-backed supersession, or explicit external/restricted dependency.",
                        metadata={
                            "reference_id": ref.get("reference_id"),
                            "candidate_count": match.get("candidate_count", 0),
                            "ambiguous_top_score": match.get("ambiguous_top_score", False),
                            "same_name_ambiguity_resource_ids": match.get("same_name_ambiguity_resource_ids", []),
                            "candidates": (match.get("candidates") or [])[:5],
                            "can_auto_resolve": False,
                        },
                    ))
            if not unresolved_refs:
                add(_task(
                    "references:closure",
                    "Resolve reference-review or closure blockers",
                    actor="HUMAN_REVIEW",
                    reason="The human-confirmed reference inventory has no unresolved references but still does not satisfy closure rules.",
                    evidence_needed="Corrected review receipt, reference states, and supporting evidence.",
                    metadata={"finding_codes": sorted({f.code for f in ref_findings})},
                ))

    approved_links: set[str] = set()
    supplied_api = api_observation or {}
    if (
        supplied_api.get("source_contract") == "SAM_GET_OPPORTUNITIES_V2"
        and supplied_api.get("automation_mode") == "APPROVED_API"
        and valid_sha256(supplied_api.get("payload_sha256"))
    ):
        approved_links.update(str(x) for x in supplied_api.get("resource_links") or [])
    retained_api = packet.get("current_api_observation") or {}
    retained_links = [str(x) for x in packet.get("current_resource_links") or [] if str(x)]
    if (
        retained_api.get("source_contract") == "SAM_GET_OPPORTUNITIES_V2"
        and valid_sha256(retained_api.get("api_payload_sha256"))
        and int(retained_api.get("resource_link_count") or 0) == len(retained_links)
    ):
        approved_links.update(retained_links)
    for artifact in packet.get("artifacts") or []:
        if artifact.get("required_for_analysis") is not True:
            continue
        aid = str(artifact.get("artifact_id") or "unknown")
        state = str(artifact.get("state") or "UNKNOWN").upper()
        byte_state = str(artifact.get("byte_state") or "").upper()
        if state == "PUBLIC" and (
            not artifact.get("sha256") or byte_state != "BYTES_VERIFIED_HASHED"
        ):
            url = artifact.get("resource_url")
            auto = bool(url and url in approved_links)
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

    if case.get("decision_trace_required") is True or "decision_trace" in case:
        from .decision_trace import trace_work_items
        for task in trace_work_items(case, now=now):
            add(task)

    for task in rule_sync_work_items(case):
        add(task)

    rule_task = rule_candidate_work_item(case)
    if rule_task is not None:
        add(rule_task)

    rule_evidence_task = rule_evidence_work_item(case)
    if rule_evidence_task is not None:
        add(rule_evidence_task)

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
