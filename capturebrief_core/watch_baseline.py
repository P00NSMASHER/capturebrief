"""Minimal public-state baseline for CaptureBrief's targeted 14-day change watch."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from typing import Any

from .audit import audit_case
from .authority import validate_current_action_receipts
from .decision_trace import canonical, digest, evaluate_decision_trace
from .history import validate_history_receipts
from .manifest import validate_manifest_receipts
from .deviation_sync import deviation_candidate_proposal_is_current, current_deviation_artifact_receipts
from .deviation_review import current_deviation_authority_reviews
from .deviation_applicability import current_deviation_applicability_reviews
from .model import parse_dt

WATCH_SCHEMA="1.0"


def _aware(now:datetime)->datetime:
    if not isinstance(now,datetime) or now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(timezone.utc)


def _observation_watermark(case:dict[str,Any])->str|None:
    """Latest retained observation time across the public evidence planes.

    This is a freshness receipt, not proof that every source was refreshed.
    The watch still compares each evidence plane independently.
    """
    packet=case.get("packet") or {}
    values=[]
    for rows in (
        case.get("current_action_receipts") or [],
        packet.get("history_receipts") or [],
        packet.get("manifest_receipts") or [],
        case.get("sources") or [],
    ):
        for row in rows:
            if isinstance(row,dict):
                parsed=parse_dt(row.get("observed_at"))
                if parsed is not None:
                    values.append(parsed.astimezone(timezone.utc))
    if not values:
        return None
    return max(values).isoformat().replace("+00:00","Z")


def _latest_manifests(case:dict[str,Any])->dict[str,dict[str,Any]]:
    out={}
    for row in (case.get("packet") or {}).get("manifest_receipts") or []:
        if not isinstance(row,dict) or not row.get("action_id"):
            continue
        aid=str(row["action_id"]); prior=out.get(aid)
        t=parse_dt(row.get("observed_at"))
        pt=parse_dt(prior.get("observed_at")) if prior else None
        if prior is None or (t is not None and (pt is None or t>pt)):
            out[aid]={
                "action_id":aid,
                "status":row.get("status"),
                "raw_manifest_sha256":row.get("raw_manifest_sha256"),
                "normalized_manifest_sha256":row.get("normalized_manifest_sha256"),
                "observed_at":row.get("observed_at"),
            }
    return out


def _public_state(case:dict[str,Any],*,now:datetime)->dict[str,Any]:
    packet=case.get("packet") or {}
    history_ids=sorted({str(x) for x in packet.get("history_action_ids") or [] if str(x)})
    status=str(packet.get("family_status") or "UNKNOWN").upper()
    currentness,current_action,_=validate_current_action_receipts(
        history_ids,status,case.get("current_action_receipts") or [],now=now
    )
    history_verdict,_=validate_history_receipts(history_ids,packet.get("history_receipts") or [])
    manifest_verdict,_,_=validate_manifest_receipts(history_ids,packet.get("manifest_receipts") or [])

    artifacts={}
    for row in packet.get("artifacts") or []:
        if isinstance(row,dict) and row.get("artifact_id"):
            aid=str(row["artifact_id"])
            artifacts[aid]={
                "artifact_id":aid,
                "state":row.get("state"),
                "sha256":row.get("sha256"),
                "byte_state":row.get("byte_state"),
                "source_object_state":row.get("source_object_state"),
                "required_for_analysis":row.get("required_for_analysis"),
            }

    references={}
    for row in packet.get("references") or []:
        if isinstance(row,dict) and row.get("reference_id"):
            rid=str(row["reference_id"])
            references[rid]={
                "reference_id":rid,
                "resolution":row.get("resolution"),
                "resource_id":row.get("resource_id"),
                "successor_resource_id":row.get("successor_resource_id"),
                "byte_state":row.get("byte_state"),
                "byte_sha256":row.get("byte_sha256"),
                "source_object_state":row.get("source_object_state"),
            }

    trace=case.get("decision_trace") or {}
    snapshots={
        str(row.get("snapshot_id")):row
        for row in trace.get("snapshots") or []
        if isinstance(row,dict) and row.get("snapshot_id")
    }
    rules={
        str(row.get("rule_version_id")):row
        for row in trace.get("rule_versions") or []
        if isinstance(row,dict) and row.get("rule_version_id")
    }
    source_versions={}
    for sid,row in snapshots.items():
        key=str(row.get("source_key") or "")
        if key:
            source_versions.setdefault(key,[]).append({
                "snapshot_id":sid,
                "document_sha256":row.get("document_sha256"),
                "version_label":row.get("version_label"),
                "observed_at":row.get("observed_at"),
            })
    for rows in source_versions.values():
        rows.sort(key=lambda x:str(x.get("snapshot_id") or ""))

    rule_versions={}
    for rid,row in rules.items():
        key=str(row.get("rule_key") or "")
        if key:
            rule_versions.setdefault(key,[]).append({
                "rule_version_id":rid,
                "edition":row.get("edition"),
                "revision_ref":row.get("revision_ref"),
            })
    for rows in rule_versions.values():
        rows.sort(key=lambda x:str(x.get("rule_version_id") or ""))

    deviation_proposal=None
    proposal=(case.get("packet") or {}).get("deviation_candidate_proposal")
    if deviation_candidate_proposal_is_current(case):
        candidates=[
            {
                "deviation_source_id":str(row.get("deviation_source_id") or ""),
                "url_hash":row.get("url_hash"),
                "pdf_size_bytes":row.get("pdf_size_bytes"),
                "matched_parts":sorted(row.get("matched_parts") or []),
            }
            for row in proposal.get("candidates") or []
            if isinstance(row,dict) and row.get("deviation_source_id")
        ]
        candidates.sort(key=lambda x:x["deviation_source_id"])
        deviation_proposal={
            "proposal_sha256":proposal.get("proposal_sha256"),
            "manifest_sha256":proposal.get("manifest_sha256"),
            "manifest_revision":proposal.get("manifest_revision"),
            "agency":proposal.get("agency"),
            "part_numbers":sorted(proposal.get("part_numbers") or []),
            "candidate_count":proposal.get("candidate_count"),
            "candidate_ids":[x["deviation_source_id"] for x in candidates],
            "candidate_fingerprint_sha256":digest(canonical(candidates)),
        }

    deviation_artifacts={}
    for ident,row in current_deviation_artifact_receipts(case).items():
        deviation_artifacts[ident]={
            "artifact_receipt_id":row.get("artifact_receipt_id"),
            "proposal_sha256":row.get("proposal_sha256"),
            "pdf_sha256":row.get("pdf_sha256"),
            "observed_pdf_size_bytes":row.get("observed_pdf_size_bytes"),
            "declared_size_matches_observed":row.get("declared_size_matches_observed"),
            "observed_at":row.get("observed_at"),
        }

    deviation_authority={}
    for ident,row in current_deviation_authority_reviews(case).items():
        deviation_authority[ident]={
            "authority_review_id":row.get("authority_review_id"),
            "document_sha256":row.get("document_sha256"),
            "currentness":row.get("currentness"),
            "effective_from":row.get("effective_from"),
            "effective_until":row.get("effective_until"),
            "reviewed_at":row.get("reviewed_at"),
        }

    deviation_applicability={}
    for ident,row in current_deviation_applicability_reviews(case).items():
        deviation_applicability[ident]={
            "applicability_review_id":row.get("applicability_review_id"),
            "authority_review_id":row.get("authority_review_id"),
            "assumption_id":row.get("assumption_id"),
            "rule_version_id":row.get("rule_version_id"),
            "applicability":row.get("applicability"),
            "basis":row.get("basis"),
            "reviewed_at":row.get("reviewed_at"),
        }

    assumptions={
        str(row.get("assumption_id")):row
        for row in case.get("assumptions") or []
        if isinstance(row,dict) and row.get("assumption_id")
    }
    deviation_ids_by_assumption={}
    for ident,row in deviation_applicability.items():
        aid=str(row.get("assumption_id") or "")
        if aid:
            deviation_ids_by_assumption.setdefault(aid,set()).add(ident)

    dependencies=[]
    for review in trace.get("reviews") or []:
        if not isinstance(review,dict) or not review.get("assumption_id"):
            continue
        aid=str(review["assumption_id"])
        source_keys=sorted({
            str(snapshots.get(str(c.get("snapshot_id")),{}).get("source_key"))
            for c in review.get("citations") or []
            if isinstance(c,dict) and snapshots.get(str(c.get("snapshot_id")),{}).get("source_key")
        })
        rule_keys=sorted({
            str(rules.get(str(link.get("rule_version_id")),{}).get("rule_key"))
            for link in review.get("rule_links") or []
            if isinstance(link,dict) and rules.get(str(link.get("rule_version_id")),{}).get("rule_key")
        })
        dependencies.append({
            "assumption_id":aid,
            "source_keys":source_keys,
            "rule_keys":rule_keys,
            "deviation_source_ids":sorted(deviation_ids_by_assumption.get(aid,set())),
            "case_reopen_triggers":sorted({str(x) for x in (assumptions.get(aid) or {}).get("reopen_triggers") or [] if str(x)}),
        })
    dependencies.sort(key=lambda x:x["assumption_id"])

    return {
        "observation_watermark":_observation_watermark(case),
        "currentness_verdict":currentness,
        "current_action_id":current_action,
        "history_verdict":history_verdict,
        "history_action_ids":history_ids,
        "history_set_sha256":digest(canonical(history_ids)),
        "manifest_verdict":manifest_verdict,
        "manifests":{k:v for k,v in sorted(_latest_manifests(case).items())},
        "artifacts":{k:v for k,v in sorted(artifacts.items())},
        "references":{k:v for k,v in sorted(references.items())},
        "source_versions":{k:v for k,v in sorted(source_versions.items())},
        "rule_versions":{k:v for k,v in sorted(rule_versions.items())},
        "deviation_proposal":deviation_proposal,
        "deviation_artifacts":{k:v for k,v in sorted(deviation_artifacts.items())},
        "deviation_authority":{k:v for k,v in sorted(deviation_authority.items())},
        "deviation_applicability":{k:v for k,v in sorted(deviation_applicability.items())},
        "assumption_dependencies":dependencies,
    }


def build_watch_baseline(case:dict[str,Any],*,now:datetime|None=None)->dict[str,Any]:
    now=_aware(now or datetime.now(timezone.utc))
    if case.get("decision_trace_required") is not True:
        raise ValueError("watch baseline requires decision_trace_required=true")
    audit=audit_case(case,now=now)
    if audit.release_state!="READY_FOR_HUMAN_RELEASE":
        raise ValueError("watch baseline requires a release-ready case")
    trace=evaluate_decision_trace(case,now=now)
    if trace.get("trace_state")!="TRACE_COMPLETE" or trace.get("synthetic") is True:
        raise ValueError("watch baseline requires a complete non-synthetic trace")
    state=_public_state(case,now=now)
    payload={
        "schema_version":WATCH_SCHEMA,
        "case_id":case.get("case_id"),
        "family_id":case.get("family_id"),
        "created_at":now.isoformat().replace("+00:00","Z"),
        "watch_until":(now+timedelta(days=14)).isoformat().replace("+00:00","Z"),
        "case_sha256":digest(canonical(case)),
        "state":state,
        "contains_raw_case":False,
        "contains_source_text":False,
        "automatic_decision_change":False,
    }
    return {**payload,"baseline_sha256":digest(canonical(payload))}


def _validate_baseline(baseline:dict[str,Any])->None:
    if not isinstance(baseline,dict) or baseline.get("schema_version")!=WATCH_SCHEMA:
        raise ValueError("invalid watch baseline schema")
    body={k:v for k,v in baseline.items() if k!="baseline_sha256"}
    if digest(canonical(body))!=baseline.get("baseline_sha256"):
        raise ValueError("watch baseline hash mismatch")
    if baseline.get("contains_raw_case") is not False or baseline.get("contains_source_text") is not False:
        raise ValueError("watch baseline privacy contract invalid")
    created=parse_dt(baseline.get("created_at"))
    watch_until=parse_dt(baseline.get("watch_until"))
    if created is None or watch_until is None or watch_until-created!=timedelta(days=14):
        raise ValueError("watch baseline requires an exact 14-day validity window")


def compare_watch_baseline(
    baseline:dict[str,Any],
    case:dict[str,Any],
    *,
    now:datetime|None=None,
)->dict[str,Any]:
    now=_aware(now or datetime.now(timezone.utc))
    _validate_baseline(baseline)
    if (baseline.get("case_id"),baseline.get("family_id"))!=(case.get("case_id"),case.get("family_id")):
        raise ValueError("watch baseline and case identify different pursuits")
    created=parse_dt(baseline.get("created_at"))
    watch_until=parse_dt(baseline.get("watch_until"))
    if created is None or watch_until is None:
        raise ValueError("watch baseline time window invalid")
    if now<created:
        raise ValueError("watch observation cannot precede baseline creation")
    before=baseline["state"]; after=_public_state(case,now=now)
    events=[]

    def event(kind,key,before_value,after_value,*,alias_keys=None,**extra):
        if before_value!=after_value:
            row={
                "type":kind,"key":key,"before":copy.deepcopy(before_value),
                "after":copy.deepcopy(after_value),**extra,
            }
            if alias_keys:
                row["alias_keys"]=sorted({str(x) for x in alias_keys if str(x)})
            events.append(row)

    event("CURRENTNESS_VERDICT_CHANGED","CURRENTNESS_VERDICT",before.get("currentness_verdict"),after.get("currentness_verdict"))
    event("HISTORY_VERDICT_CHANGED","HISTORY_VERDICT",before.get("history_verdict"),after.get("history_verdict"))
    event("MANIFEST_VERDICT_CHANGED","MANIFEST_VERDICT",before.get("manifest_verdict"),after.get("manifest_verdict"))
    event("CURRENT_ACTION_CHANGED","CURRENT_ACTION_CHANGE",before.get("current_action_id"),after.get("current_action_id"))
    event("HISTORY_ACTION_SET_CHANGED","HISTORY_ACTION_SET_CHANGE",before.get("history_set_sha256"),after.get("history_set_sha256"))

    baseline_watermark=parse_dt(before.get("observation_watermark"))
    current_watermark=parse_dt(after.get("observation_watermark"))
    fresh_observation=(
        now==created or
        (baseline_watermark is not None and current_watermark is not None and current_watermark>baseline_watermark)
    )
    if now>created and not fresh_observation:
        events.append({
            "type":"WATCH_NO_FRESH_OBSERVATION",
            "key":"WATCH_FRESHNESS",
            "before":before.get("observation_watermark"),
            "after":after.get("observation_watermark"),
            "reason":"No retained public-source observation advanced after the delivered baseline.",
        })
    expired=now>watch_until
    if expired:
        events.append({
            "type":"WATCH_WINDOW_EXPIRED",
            "key":"WATCH_WINDOW",
            "before":baseline.get("created_at"),
            "after":now.isoformat().replace("+00:00","Z"),
            "watch_until":baseline.get("watch_until"),
        })

    for aid in sorted(set(before.get("manifests") or {})|set(after.get("manifests") or {})):
        event("MANIFEST_CHANGED",f"MANIFEST:{aid}",(before.get("manifests") or {}).get(aid),(after.get("manifests") or {}).get(aid),action_id=aid)
    for aid in sorted(set(before.get("artifacts") or {})|set(after.get("artifacts") or {})):
        event(
            "ARTIFACT_CHANGED",
            f"ARTIFACT:{aid}",
            (before.get("artifacts") or {}).get(aid),
            (after.get("artifacts") or {}).get(aid),
            alias_keys=[f"RESOURCE:{aid}"],
            artifact_id=aid,
        )
    for rid in sorted(set(before.get("references") or {})|set(after.get("references") or {})):
        event("REFERENCE_CHANGED",f"REFERENCE:{rid}",(before.get("references") or {}).get(rid),(after.get("references") or {}).get(rid),reference_id=rid)
    for key in sorted(set(before.get("source_versions") or {})|set(after.get("source_versions") or {})):
        event("SOURCE_VERSION_CHANGED",f"SOURCE:{key}",(before.get("source_versions") or {}).get(key),(after.get("source_versions") or {}).get(key),source_key=key)
    for key in sorted(set(before.get("rule_versions") or {})|set(after.get("rule_versions") or {})):
        event("RULE_VERSION_CHANGED",f"RULE:{key}",(before.get("rule_versions") or {}).get(key),(after.get("rule_versions") or {}).get(key),rule_key=key)

    before_prop=before.get("deviation_proposal")
    after_prop=after.get("deviation_proposal")
    proposal_ids=set((before_prop or {}).get("candidate_ids") or [])|set((after_prop or {}).get("candidate_ids") or [])
    event(
        "DEVIATION_PROPOSAL_CHANGED",
        "DEVIATION_PROPOSAL",
        before_prop,
        after_prop,
        alias_keys=[f"DEVIATION:{x}" for x in proposal_ids],
    )
    for field,kind in (
        ("deviation_artifacts","DEVIATION_ARTIFACT_CHANGED"),
        ("deviation_authority","DEVIATION_AUTHORITY_CHANGED"),
        ("deviation_applicability","DEVIATION_APPLICABILITY_CHANGED"),
    ):
        bmap=before.get(field) or {}; amap=after.get(field) or {}
        for ident in sorted(set(bmap)|set(amap)):
            event(kind,f"DEVIATION:{ident}",bmap.get(ident),amap.get(ident),deviation_source_id=ident)

    keys={e["key"] for e in events}
    for e in events:
        keys.update(e.get("alias_keys") or [])
    reopened=[]
    for dep in before.get("assumption_dependencies") or []:
        matched=set(dep.get("case_reopen_triggers") or []) & keys
        matched.update(
            f"SOURCE:{key}" for key in dep.get("source_keys") or []
            if f"SOURCE:{key}" in keys
        )
        matched.update(
            f"RULE:{key}" for key in dep.get("rule_keys") or []
            if f"RULE:{key}" in keys
        )
        matched.update(
            f"DEVIATION:{ident}" for ident in dep.get("deviation_source_ids") or []
            if f"DEVIATION:{ident}" in keys
        )
        if matched:
            reopened.append({
                "assumption_id":dep.get("assumption_id"),
                "matched_dependencies":sorted(matched),
                "status":"REVIEW_REQUIRED",
                "previous_decision_preserved":True,
            })

    trace=evaluate_decision_trace(case,now=now)
    integrity_findings=[
        copy.deepcopy(f) for f in trace.get("findings") or []
        if f.get("severity")=="BLOCK"
    ]
    observation={
        "schema_version":WATCH_SCHEMA,
        "case_id":case.get("case_id"),
        "family_id":case.get("family_id"),
        "baseline_sha256":baseline.get("baseline_sha256"),
        "observed_at":now.isoformat().replace("+00:00","Z"),
        "watch_until":baseline.get("watch_until"),
        "watch_status":"EXPIRED" if expired else "REVIEW_REQUIRED" if (events or integrity_findings) else "NO_CHANGE_OBSERVED",
        "fresh_observation_evidenced":fresh_observation,
        "baseline_observation_watermark":before.get("observation_watermark"),
        "current_observation_watermark":after.get("observation_watermark"),
        "events":events,
        "reopened_assumptions":reopened,
        "integrity_findings":integrity_findings,
        "requires_human_review":bool(events or integrity_findings),
        "automatic_decision_change":False,
        "previous_decision_preserved":True,
    }
    observation["observation_sha256"]=digest(canonical(observation))
    return observation
