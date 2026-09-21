"""Bind reviewed class-deviation authority evidence to one bid assumption.

Resolved applicability always needs separate pursuit-specific evidence. This stage
adds a CLASS_DEVIATION rule link to Decision Evidence but never mutates the
buyer-facing assumption state.
"""
from __future__ import annotations
import copy
from datetime import datetime
from typing import Any

from .decision_trace import canonical, digest, freeze_rule_version
from .deviation_review import (
    current_deviation_authority_reviews,
    current_deviation_text_preparations,
)

CONTRACT="capturebrief-deviation-applicability-review-v1"
APPLICABILITY={"APPLIES","DOES_NOT_APPLY","UNRESOLVED"}
BASES={"SOLICITATION_TEXT","AMENDMENT_TEXT","DEVIATION_REVIEW","EFFECTIVE_DATE_REVIEW","UNRESOLVED"}
ALLOWED_KINDS={"SOLICITATION","AMENDMENT","CONTEXT"}

def _dt(v):
    if not isinstance(v,str): return None
    try:
        d=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else None

def _text(v): return isinstance(v,str) and bool(v.strip())

def _trace(case):
    t=case.get("decision_trace")
    if not isinstance(t,dict) or t.get("schema_version")!="1.0" or t.get("family_id")!=case.get("family_id"):
        raise ValueError("valid Decision Evidence trace is required")
    assumptions={str(x.get("assumption_id")):x for x in case.get("assumptions") or [] if isinstance(x,dict) and x.get("assumption_id")}
    reviews={}
    for x in t.get("reviews") or []:
        if not isinstance(x,dict) or not x.get("assumption_id"): continue
        aid=str(x["assumption_id"])
        if aid in reviews: raise ValueError("duplicate Decision Evidence assumption review")
        reviews[aid]=x
    snaps={str(x.get("snapshot_id")):x for x in t.get("snapshots") or [] if isinstance(x,dict) and x.get("snapshot_id")}
    return t,assumptions,reviews,snaps

def _basis(spec,snaps,*,forbidden,required,reviewed_at,basis_name):
    if spec is None:
        if required: raise ValueError("resolved deviation applicability requires a separate pursuit-specific basis passage")
        return None
    if not isinstance(spec,dict): raise ValueError("basis_passage must be an exact Decision Evidence passage")
    sid=str(spec.get("snapshot_id") or "")
    if sid==forbidden: raise ValueError("deviation memo cannot be its own pursuit-specific applicability basis")
    snap=snaps.get(sid)
    if snap is None: raise ValueError("basis_passage references an unknown Decision Evidence snapshot")
    if snap.get("kind") not in ALLOWED_KINDS: raise ValueError("applicability basis must be solicitation/amendment/context evidence")
    if basis_name=="SOLICITATION_TEXT" and snap.get("kind")!="SOLICITATION": raise ValueError("SOLICITATION_TEXT basis must use solicitation evidence")
    if basis_name=="AMENDMENT_TEXT" and snap.get("kind")!="AMENDMENT": raise ValueError("AMENDMENT_TEXT basis must use amendment evidence")
    observed=_dt(snap.get("observed_at")); when=_dt(reviewed_at)
    if observed is None or when is None or observed>when: raise ValueError("applicability basis cannot be observed after review")
    lines=str(snap.get("text") or "").splitlines(); a,b=spec.get("line_start"),spec.get("line_end")
    if type(a) is not int or type(b) is not int or a<1 or b<a or b>len(lines): raise ValueError("basis_passage line range is invalid")
    if not _text(spec.get("locator")): raise ValueError("basis_passage requires locator")
    quote="\n".join(lines[a-1:b])
    if spec.get("quote")!=quote: raise ValueError("basis_passage quote does not match retained evidence")
    return copy.deepcopy(spec)

def _review_body(x): return {k:v for k,v in x.items() if k!="applicability_review_id"}

def current_deviation_applicability_reviews(case):
    authorities=current_deviation_authority_reviews(case)
    out={}
    for row in (case.get("packet") or {}).get("deviation_applicability_reviews") or []:
        if not isinstance(row,dict) or row.get("contract")!=CONTRACT: continue
        ident=str(row.get("deviation_source_id") or "")
        authority=authorities.get(ident)
        if authority is None or row.get("authority_review_id")!=authority.get("authority_review_id"): continue
        if row.get("applicability_review_id")!="DEVAPP:"+digest(canonical(_review_body(row))): continue
        out[ident]=row
    return out

def review_deviation_applicability(case: dict[str,Any],review: dict[str,Any])->tuple[dict[str,Any],dict[str,Any]]:
    authorities=current_deviation_authority_reviews(case)
    preps=current_deviation_text_preparations(case)
    trace,assumptions,trace_reviews,snaps=_trace(case)
    reviewer=review.get("reviewed_by"); reviewed_at=review.get("reviewed_at"); when=_dt(reviewed_at)
    if not _text(reviewer) or when is None: raise ValueError("reviewed_by and timezone-aware reviewed_at are required")
    decisions=review.get("decisions")
    if not isinstance(decisions,list) or not decisions: raise ValueError("decisions must be non-empty")
    normalized=[]; seen=set()

    for row in decisions:
        if not isinstance(row,dict): raise ValueError("deviation applicability decision must be an object")
        ident=str(row.get("deviation_source_id") or "")
        authority=authorities.get(ident); prep=preps.get(ident)
        if authority is None or prep is None or ident in seen: raise ValueError("each decision must reference one unique current deviation authority review")
        seen.add(ident)
        authority_time=_dt(authority.get("reviewed_at"))
        if authority_time is None or when<authority_time: raise ValueError("applicability review cannot precede authority review")
        aid=str(row.get("assumption_id") or "")
        if aid not in assumptions or aid not in trace_reviews: raise ValueError("applicability must target an assumption with Decision Evidence review")
        app=str(row.get("applicability") or "").upper(); basis_name=str(row.get("basis") or "").upper()
        if app not in APPLICABILITY or basis_name not in BASES: raise ValueError("invalid deviation applicability or basis")
        if app=="UNRESOLVED" and basis_name!="UNRESOLVED": raise ValueError("UNRESOLVED applicability must use UNRESOLVED basis")
        if app!="UNRESOLVED" and basis_name=="UNRESOLVED": raise ValueError("resolved applicability needs a resolved basis")
        if app!="UNRESOLVED" and authority.get("currentness")=="UNRESOLVED":
            raise ValueError("resolved applicability requires resolved deviation currentness")
        if app=="APPLIES" and authority.get("currentness")=="SUPERSEDED" and basis_name not in {"SOLICITATION_TEXT","AMENDMENT_TEXT"}:
            raise ValueError("APPLIES for a superseded deviation requires explicit solicitation/amendment basis")
        rationale=row.get("rationale"); scope=row.get("scope_rationale")
        if not _text(rationale) or not _text(scope): raise ValueError("applicability and scope rationales are required")
        basis_passage=_basis(
            row.get("basis_passage"),snaps,
            forbidden=prep["snapshot"]["snapshot_id"],
            required=app!="UNRESOLVED",reviewed_at=reviewed_at,basis_name=basis_name,
        )
        rule=freeze_rule_version(
            namespace="CLASS_DEVIATION",
            citation=str(prep["source"].get("title") or ident),
            edition="sha256:"+prep["document_sha256"][:16],
            agency=str(authority.get("agency") or prep.get("agency") or "UNKNOWN"),
            text_passage=copy.deepcopy(authority["memo_passage"]),
            effective_from=authority.get("effective_from"),
            effective_until=authority.get("effective_until"),
            effective_date_passage=copy.deepcopy(authority.get("effective_date_passage")),
            revision_ref=authority.get("artifact_receipt_id"),
        )
        normalized.append({
            "deviation_source_id":ident,
            "authority_review_id":authority["authority_review_id"],
            "preparation_id":prep["preparation_id"],
            "assumption_id":aid,
            "rule_version":rule,
            "snapshot":copy.deepcopy(prep["snapshot"]),
            "applicability":app,
            "basis":basis_name,
            "rationale":rationale.strip(),
            "scope_rationale":scope.strip(),
            "basis_passage":basis_passage,
            "reviewed_by":reviewer.strip(),
            "reviewed_at":reviewed_at,
            "human_reviewed":True,
            "applicability_authoritative":False,
            "assumption_state_changed":False,
            "can_auto_apply":False,
        })

    result=copy.deepcopy(case); t=result["decision_trace"]
    snap_map={str(x.get("snapshot_id")):x for x in t.setdefault("snapshots",[]) if isinstance(x,dict) and x.get("snapshot_id")}
    rule_map={str(x.get("rule_version_id")):x for x in t.setdefault("rule_versions",[]) if isinstance(x,dict) and x.get("rule_version_id")}
    review_map={str(x.get("assumption_id")):x for x in t.setdefault("reviews",[]) if isinstance(x,dict) and x.get("assumption_id")}

    for d in normalized:
        snap=d["snapshot"]; rule=d["rule_version"]
        if snap["snapshot_id"] not in snap_map:
            t["snapshots"].append(copy.deepcopy(snap)); snap_map[snap["snapshot_id"]]=snap
        elif canonical(snap_map[snap["snapshot_id"]])!=canonical(snap): raise ValueError("Decision Evidence snapshot ID collision")
        if rule["rule_version_id"] not in rule_map:
            t["rule_versions"].append(copy.deepcopy(rule)); rule_map[rule["rule_version_id"]]=rule
        elif canonical(rule_map[rule["rule_version_id"]])!=canonical(rule): raise ValueError("Decision Evidence rule-version ID collision")

        target=review_map[d["assumption_id"]]
        link={
            "rule_version_id":rule["rule_version_id"],
            "family_id":result["family_id"],
            "applicability":d["applicability"],
            "basis":d["basis"],
            "incorporated_edition":None,
            "rationale":d["rationale"],
            "basis_passage":copy.deepcopy(d["basis_passage"]),
            "reviewed_by":d["reviewed_by"],
            "reviewed_at":d["reviewed_at"],
        }
        existing=[x for x in target.setdefault("rule_links",[]) if isinstance(x,dict) and x.get("rule_version_id")==rule["rule_version_id"]]
        if existing:
            if len(existing)!=1 or canonical(existing[0])!=canonical(link):
                raise ValueError("existing deviation rule link differs; create a new preserved decision version instead of rewriting")
        else:
            target["rule_links"].append(link)
        desired={"status":"REQUIRED","rationale":d["scope_rationale"]}
        prior=target.get("rule_scope")
        if isinstance(prior,dict) and prior.get("status")=="REQUIRED" and len(target["rule_links"])>1 and prior!=desired:
            raise ValueError("multi-rule scope rationale cannot be silently rewritten")
        target["rule_scope"]=desired

    packet=result.setdefault("packet",{}); rows=packet.setdefault("deviation_applicability_reviews",[])
    outputs=[]
    for d in normalized:
        payload={
            "contract":CONTRACT,
            "deviation_source_id":d["deviation_source_id"],
            "authority_review_id":d["authority_review_id"],
            "preparation_id":d["preparation_id"],
            "assumption_id":d["assumption_id"],
            "rule_version_id":d["rule_version"]["rule_version_id"],
            "applicability":d["applicability"],
            "basis":d["basis"],
            "rationale":d["rationale"],
            "scope_rationale":d["scope_rationale"],
            "basis_passage":copy.deepcopy(d["basis_passage"]),
            "reviewed_by":d["reviewed_by"],
            "reviewed_at":d["reviewed_at"],
            "human_reviewed":True,
            "applicability_authoritative":False,
            "assumption_state_changed":False,
            "can_auto_apply":False,
        }
        record={**payload,"applicability_review_id":"DEVAPP:"+digest(canonical(payload))}
        if not any(x.get("applicability_review_id")==record["applicability_review_id"] for x in rows if isinstance(x,dict)):
            rows.append(record)
        outputs.append(record)
    rows.sort(key=lambda x:(str(x.get("deviation_source_id") or ""),str(x.get("reviewed_at") or ""),str(x.get("applicability_review_id") or "")))
    return result,{
        "status":"DEVIATION_APPLICABILITY_REVIEW_ATTACHED",
        "applicability_review_ids":[x["applicability_review_id"] for x in outputs],
        "assumption_ids":sorted({x["assumption_id"] for x in outputs}),
        "human_reviewed":True,
        "applicability_authoritative":False,
        "assumption_state_changed":False,
        "can_auto_apply":False,
    }

def deviation_applicability_work_items(case):
    authorities=current_deviation_authority_reviews(case)
    done=current_deviation_applicability_reviews(case)
    trace=case.get("decision_trace")
    if not isinstance(trace,dict) or not (trace.get("reviews") or []): return []
    tasks=[]
    for ident,authority in sorted(authorities.items()):
        if authority.get("currentness")=="UNRESOLVED" or ident in done: continue
        tasks.append({
            "task_key":"deviation-applicability:"+ident,
            "priority":"P0",
            "title":"Bind reviewed deviation to bid assumption",
            "actor":"HUMAN_REVIEW",
            "can_auto_execute":False,
            "status":"OPEN",
            "reason":"Deviation memo authority is reviewed, but assumption-specific applicability still requires separate pursuit evidence.",
            "evidence_needed":"Select the affected assumption and APPLIES / DOES_NOT_APPLY / UNRESOLVED. Any resolved decision requires an exact solicitation/amendment/context passage distinct from the deviation memo.",
            "metadata":{"deviation_source_id":ident,"authority_review_id":authority["authority_review_id"],"currentness":authority["currentness"],"can_auto_apply":False},
        })
    return tasks
