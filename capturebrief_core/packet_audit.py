from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from .authority import validate_current_action_receipts
from .history import validate_history_receipts
from .manifest import validate_manifest_receipts
from .packet import validate_reference_closure
from .model import ARTIFACT_STATES, DECISION_CLASSES, EVIDENCE_STATES, SOURCE_AUTHORITIES, AuditResult, Finding, parse_dt, valid_sha256


def audit_case(case:dict[str,Any],*,now:datetime|None=None)->AuditResult:
    findings:list[Finding]=[]; now=now or datetime.now(timezone.utc)
    for field in ("case_id","family_id","current_posture"):
        if not case.get(field): findings.append(Finding("MISSING_REQUIRED_CASE_FIELD","BLOCK",f"Missing required case field: {field}",field))
    if case.get("case_schema_version") != "0.2":
        findings.append(Finding("CASE_SCHEMA_VERSION_UNSUPPORTED","BLOCK","Case must use CaptureBrief case schema version 0.2.","case_schema_version"))

    packet=case.get("packet") or {}; status=str(packet.get("family_status","UNKNOWN")).upper(); history_ids=packet.get("history_action_ids") or []

    history_verdict,hf=validate_history_receipts(history_ids,packet.get("history_receipts") or []); findings.extend(hf)
    if history_verdict != "HISTORY_COMPLETE": findings.append(Finding("HISTORY_UNRESOLVED","BLOCK","Public action/version history is not proven complete by a verified first-party receipt."))

    verdict,current,rf=validate_current_action_receipts(history_ids,status,case.get("current_action_receipts") or [],now=now); findings.extend(rf)
    required={"ACTIVE":"CURRENT_VERIFIED","CANCELLED":"TERMINAL_CANCELLED_VERIFIED","ARCHIVED":"TERMINAL_ARCHIVED_VERIFIED"}
    if status in required and verdict!=required[status]: findings.append(Finding(f"{status}_AUTHORITY_NOT_VERIFIED","BLOCK",f"{status.title()} family lacks the required verified first-party authority receipt."))
    if status in {"INACTIVE","DELETED","UNKNOWN"}: findings.append(Finding("FAMILY_AUTHORITY_UNKNOWN","BLOCK","Family status cannot establish a controlling current/terminal action without stronger first-party authority."))

    manifest_verdict,manifest_summary,mf=validate_manifest_receipts(history_ids,packet.get("manifest_receipts") or []); findings.extend(mf)
    if manifest_verdict != "MANIFEST_COMPLETE": findings.append(Finding("MANIFEST_UNRESOLVED","BLOCK","Deletion-inclusive first-party resource manifests are not complete for every history action."))
    # A caller-supplied boolean is intentionally ignored; a deceptive green flag gets called out.
    if packet.get("manifest_complete") is True and manifest_verdict != "MANIFEST_COMPLETE":
        findings.append(Finding("MANIFEST_BOOLEAN_CANNOT_OVERRIDE_RECEIPTS","BLOCK","manifest_complete cannot override missing or conflicting per-action receipts.","packet.manifest_complete"))

    reference_verdict,ref_findings=validate_reference_closure(packet); findings.extend(ref_findings)
    if reference_verdict != "REFERENCE_CLOSURE_COMPLETE":
        findings.append(Finding("REFERENCE_CLOSURE_UNRESOLVED","BLOCK","Named/incorporated packet dependencies are not semantically closed."))

    sources={str(s.get("source_id")):s for s in case.get("sources",[]) if s.get("source_id")}
    for sid,s in sources.items():
        if str(s.get("authority","")).upper() not in SOURCE_AUTHORITIES: findings.append(Finding("BAD_SOURCE_AUTHORITY","BLOCK",f"Source {sid} has invalid authority state."))
        if str(s.get("artifact_state","PUBLIC")).upper() not in ARTIFACT_STATES: findings.append(Finding("BAD_ARTIFACT_STATE","BLOCK",f"Source {sid} has invalid artifact state."))
        if not s.get("url"): findings.append(Finding("SOURCE_URL_MISSING","BLOCK",f"Source {sid} has no URL."))
        if not parse_dt(s.get("observed_at")): findings.append(Finding("SOURCE_TIME_INVALID","BLOCK",f"Source {sid} lacks a timezone-aware observation timestamp."))
        if s.get("content_sha256") is not None and not valid_sha256(s.get("content_sha256")): findings.append(Finding("SOURCE_HASH_INVALID","BLOCK",f"Source {sid} content hash is malformed."))

    action_items=0; seen=set()
    for i,item in enumerate(case.get("assumptions") or []):
        path=f"assumptions[{i}]"; aid=str(item.get("assumption_id","")); evidence=str(item.get("evidence_state","")).upper(); decision=str(item.get("decision_class","")).upper()
        if not aid or aid in seen: findings.append(Finding("ASSUMPTION_ID_INVALID","BLOCK","Assumption ID is missing or duplicated.",path))
        seen.add(aid)
        if evidence not in EVIDENCE_STATES: findings.append(Finding("BAD_EVIDENCE_STATE","BLOCK","Assumption has invalid evidence state.",path))
        if decision not in DECISION_CLASSES: findings.append(Finding("BAD_DECISION_CLASS","BLOCK","Assumption has invalid decision class.",path))
        if decision in {"GATE_CHANGING","VERIFY_NOW"}:
            action_items+=1
            if not item.get("next_action"): findings.append(Finding("ACTION_ITEM_MISSING_NEXT_ACTION","BLOCK","Decision-changing item lacks a concrete next action.",path))
            if not item.get("owner") and not item.get("evidence_request"): findings.append(Finding("ACTION_ITEM_UNOWNED","BLOCK","Decision-changing item lacks an owner or evidence request.",path))
        if evidence=="UNPROVEN" and decision=="GATE_CHANGING": findings.append(Finding("UNKNOWN_MUST_BE_VERIFY_NOW","BLOCK","UNPROVEN evidence must be VERIFY_NOW, not a resolved gate-changing fact.",path))
        if evidence=="SOURCE_LIMITED" and decision=="GATE_CHANGING": findings.append(Finding("SOURCE_LIMITED_MUST_NOT_ASSERT_GATE_FACT","BLOCK","SOURCE_LIMITED evidence cannot be a resolved gate-changing fact.",path))
        ids=[str(x) for x in item.get("source_ids",[]) if str(x)]
        if not ids: findings.append(Finding("ASSUMPTION_UNSOURCED","BLOCK","Assumption has no linked evidence source.",path))
        missing=[x for x in ids if x not in sources]
        if missing: findings.append(Finding("ASSUMPTION_SOURCE_MISSING","BLOCK",f"Assumption references missing sources: {', '.join(missing)}",path))
        linked=[sources[x] for x in ids if x in sources]
        nonpublic=[s for s in linked if str(s.get("artifact_state","PUBLIC")).upper() in {"RESTRICTED","EXPORT_CONTROLLED","UNAVAILABLE","UNKNOWN"}]
        if nonpublic and evidence not in {"SOURCE_LIMITED","UNPROVEN"}: findings.append(Finding("NONPUBLIC_SOURCE_ASSERTION","BLOCK","Restricted/unavailable evidence must safe-stop as SOURCE_LIMITED or UNPROVEN.",path))
        if item.get("deadline") is not None and not parse_dt(item.get("deadline")): findings.append(Finding("DEADLINE_TIMEZONE_MISSING","BLOCK","Deadline must include timezone/offset.",path))
    if action_items>5: findings.append(Finding("HANDOFF_TOO_LARGE","BLOCK","Default buyer handoff contains more than five GATE_CHANGING/VERIFY_NOW items."))

    # Artifact bytes are independent from source-object presence. Historical IDs can survive after bytes vanish.
    for a in packet.get("artifacts") or []:
        aid=str(a.get("artifact_id","?")); state=str(a.get("state","UNKNOWN")).upper()
        if state not in ARTIFACT_STATES: findings.append(Finding("BAD_PACKET_ARTIFACT_STATE","BLOCK",f"Packet artifact {aid} has invalid state."))
        if state=="PUBLIC" and a.get("required_for_analysis") is True and not a.get("sha256"):
            findings.append(Finding("PUBLIC_ARTIFACT_HASH_MISSING","BLOCK",f"Required public artifact {aid} lacks an immutable content hash."))
        if a.get("sha256") and not valid_sha256(a.get("sha256")): findings.append(Finding("PUBLIC_ARTIFACT_HASH_INVALID","BLOCK",f"Packet artifact {aid} has malformed hash."))
        if a.get("source_object_state") in {"VERIFIED_SOURCE_OBJECT","INFERRED_SOURCE_OBJECT"} and a.get("byte_state")=="BYTES_UNAVAILABLE_AT_OBSERVATION" and a.get("required_for_analysis") is True:
            findings.append(Finding("HISTORICAL_BYTES_UNAVAILABLE","BLOCK",f"Required artifact {aid} has source identity but its bytes are unavailable."))

    for i,d in enumerate(packet.get("external_dependencies") or []):
        if not d.get("url") or not d.get("reason"): findings.append(Finding("EXTERNAL_DEPENDENCY_INCOMPLETE","BLOCK","External/restricted dependency must include URL and reason.",f"packet.external_dependencies[{i}]"))

    blocked=any(x.severity=="BLOCK" for x in findings)
    return AuditResult("FAIL_CLOSED" if blocked else "READY_FOR_HUMAN_RELEASE",verdict,current,tuple(findings))
