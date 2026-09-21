"""Human-reviewed authority state for captured class-deviation artifacts.

This stage binds reviewed text and exact passages to captured PDF bytes. It does
not decide solicitation applicability or change a buyer assumption.
"""
from __future__ import annotations

import copy
from datetime import date, datetime, timezone
from typing import Any

from .decision_trace import freeze_text_snapshot, passage
from .deviation_sync import (
    current_deviation_artifact_receipts,
    deviation_candidate_proposal_is_current,
)
from .rule_registry import canonical, digest

PREP_CONTRACT="capturebrief-deviation-text-preparation-v1"
REVIEW_CONTRACT="capturebrief-deviation-authority-review-v1"
CURRENTNESS={"CURRENT","SUPERSEDED","UNRESOLVED"}

def _dt(value: Any)->datetime|None:
    if not isinstance(value,str):
        return None
    try:
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None

def _date(value: Any)->date|None:
    if value in (None,""):
        return None
    if not isinstance(value,str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None

def _text(value: Any)->bool:
    return isinstance(value,str) and bool(value.strip())

def _candidate(case: dict[str,Any],deviation_source_id: str)->dict[str,Any]:
    if not deviation_candidate_proposal_is_current(case):
        raise ValueError("case does not contain a current deviation candidate proposal")
    rows=[
        x for x in case["packet"]["deviation_candidate_proposal"].get("candidates") or []
        if isinstance(x,dict) and x.get("deviation_source_id")==deviation_source_id
    ]
    if len(rows)!=1:
        raise ValueError("deviation_source_id must identify exactly one current candidate")
    return rows[0]

def _prep_payload(prep: dict[str,Any])->dict[str,Any]:
    return {k:v for k,v in prep.items() if k!="preparation_id"}

def _review_payload(review: dict[str,Any])->dict[str,Any]:
    return {k:v for k,v in review.items() if k!="authority_review_id"}

def current_deviation_text_preparations(case: dict[str,Any])->dict[str,dict[str,Any]]:
    receipts=current_deviation_artifact_receipts(case)
    current={}
    for prep in (case.get("packet") or {}).get("deviation_text_preparations") or []:
        if not isinstance(prep,dict) or prep.get("contract")!=PREP_CONTRACT:
            continue
        ident=str(prep.get("deviation_source_id") or "")
        receipt=receipts.get(ident)
        if receipt is None:
            continue
        if prep.get("artifact_receipt_id")!=receipt.get("artifact_receipt_id"):
            continue
        if prep.get("proposal_sha256")!=receipt.get("proposal_sha256"):
            continue
        if prep.get("document_sha256")!=receipt.get("pdf_sha256"):
            continue
        if prep.get("preparation_id")!="DEVTEXT:"+digest(canonical(_prep_payload(prep))):
            continue
        snap=prep.get("snapshot")
        source=prep.get("source")
        if not isinstance(snap,dict) or not isinstance(source,dict):
            continue
        if snap.get("document_sha256")!=receipt.get("pdf_sha256") or source.get("content_sha256")!=receipt.get("pdf_sha256"):
            continue
        current[ident]=prep
    return current

def prepare_deviation_text(
    case: dict[str,Any],deviation_source_id: str,*,text: str,
    prepared_by: str,prepared_at: str,mapping_note: str,
)->tuple[dict[str,Any],dict[str,Any]]:
    receipts=current_deviation_artifact_receipts(case)
    receipt=receipts.get(str(deviation_source_id))
    if receipt is None:
        raise ValueError("a current captured PDF receipt is required before text preparation")
    candidate=_candidate(case,str(deviation_source_id))
    when=_dt(prepared_at)
    observed=_dt(receipt.get("observed_at"))
    if when is None or observed is None or when<observed:
        raise ValueError("prepared_at must be timezone-aware and not precede PDF observation")
    if not _text(text) or not _text(prepared_by) or not _text(mapping_note):
        raise ValueError("reviewed text, prepared_by and mapping_note are required")

    source_id="deviation-pdf:"+receipt["pdf_sha256"]
    source={
        "source_id":source_id,
        "title":candidate.get("original_filename") or deviation_source_id,
        "authority":"SUPPORTING",
        "artifact_state":"PUBLIC",
        "url":receipt["source_url"],
        "observed_at":receipt["observed_at"],
        "content_sha256":receipt["pdf_sha256"],
    }
    source_key=f"CLASS_DEVIATION:{candidate.get('agency')}:{deviation_source_id}"
    version_label=f"{candidate.get('original_filename') or deviation_source_id} | sha256:{receipt['pdf_sha256'][:16]}"
    snap=freeze_text_snapshot(
        source=source,
        source_key=source_key,
        kind="DEVIATION",
        version_label=version_label,
        text=text,
        capture_method="REVIEWED_EXTRACTION",
        captured_by=prepared_by.strip(),
        mapping_note=mapping_note.strip(),
        published_at=None,
    )
    payload={
        "contract":PREP_CONTRACT,
        "proposal_sha256":receipt["proposal_sha256"],
        "artifact_receipt_id":receipt["artifact_receipt_id"],
        "deviation_source_id":deviation_source_id,
        "agency":candidate.get("agency"),
        "matched_parts":copy.deepcopy(candidate.get("matched_parts") or []),
        "document_sha256":receipt["pdf_sha256"],
        "source":source,
        "snapshot":snap,
        "prepared_by":prepared_by.strip(),
        "prepared_at":prepared_at,
        "mapping_note":mapping_note.strip(),
        "currentness":"UNRESOLVED",
        "effective_date":None,
        "applicability":"UNRESOLVED",
        "can_auto_apply":False,
    }
    prep={**payload,"preparation_id":"DEVTEXT:"+digest(canonical(payload))}
    result=copy.deepcopy(case)
    packet=result.setdefault("packet",{})
    rows=packet.setdefault("deviation_text_preparations",[])
    if not any(x.get("preparation_id")==prep["preparation_id"] for x in rows if isinstance(x,dict)):
        rows.append(copy.deepcopy(prep))
    result.setdefault("sources",[])
    existing={str(x.get("source_id")):x for x in result["sources"] if isinstance(x,dict) and x.get("source_id")}
    if source_id not in existing:
        result["sources"].append(copy.deepcopy(source))
    elif canonical(existing[source_id])!=canonical(source):
        raise ValueError("deviation source ID collision")
    return result,{
        "status":"DEVIATION_TEXT_PREPARED",
        "deviation_source_id":deviation_source_id,
        "preparation_id":prep["preparation_id"],
        "snapshot_id":snap["snapshot_id"],
        "document_sha256":receipt["pdf_sha256"],
        "currentness":"UNRESOLVED",
        "applicability":"UNRESOLVED",
        "can_auto_apply":False,
    }

def _select(snapshot: dict[str,Any],spec: dict[str,Any]|None,*,required: bool,name: str)->dict[str,Any]|None:
    if spec is None:
        if required:
            raise ValueError(f"{name} is required")
        return None
    if not isinstance(spec,dict):
        raise ValueError(f"{name} must be an object")
    try:
        return passage(
            snapshot,
            spec["line_start"],
            spec["line_end"],
            locator=spec["locator"],
        )
    except (KeyError,ValueError) as exc:
        raise ValueError(f"invalid {name}") from exc

def _trace_snapshot(case: dict[str,Any],snapshot_id: str)->dict[str,Any]:
    rows=[
        x for x in (case.get("decision_trace") or {}).get("snapshots") or []
        if isinstance(x,dict) and x.get("snapshot_id")==snapshot_id
    ]
    if len(rows)!=1:
        raise ValueError("currentness basis must reference exactly one retained Decision Evidence snapshot")
    return rows[0]

def current_deviation_authority_reviews(case: dict[str,Any])->dict[str,dict[str,Any]]:
    preps=current_deviation_text_preparations(case)
    current={}
    for review in (case.get("packet") or {}).get("deviation_authority_reviews") or []:
        if not isinstance(review,dict) or review.get("contract")!=REVIEW_CONTRACT:
            continue
        ident=str(review.get("deviation_source_id") or "")
        prep=preps.get(ident)
        if prep is None or review.get("preparation_id")!=prep.get("preparation_id"):
            continue
        if review.get("authority_review_id")!="DEVAUTH:"+digest(canonical(_review_payload(review))):
            continue
        current[ident]=review
    return current

def review_deviation_authority(
    case: dict[str,Any],review: dict[str,Any],
)->tuple[dict[str,Any],dict[str,Any]]:
    preps=current_deviation_text_preparations(case)
    reviewer=review.get("reviewed_by")
    reviewed_at=review.get("reviewed_at")
    when=_dt(reviewed_at)
    if not _text(reviewer) or when is None:
        raise ValueError("reviewed_by and timezone-aware reviewed_at are required")
    decisions=review.get("decisions")
    if not isinstance(decisions,list) or not decisions:
        raise ValueError("decisions must be a non-empty list")

    seen=set()
    records=[]
    for decision in decisions:
        if not isinstance(decision,dict):
            raise ValueError("deviation authority decision must be an object")
        ident=str(decision.get("deviation_source_id") or "")
        prep=preps.get(ident)
        if prep is None or ident in seen:
            raise ValueError("each decision must reference one unique current prepared deviation")
        seen.add(ident)
        prepared_at=_dt(prep.get("prepared_at"))
        if prepared_at is None or when<prepared_at:
            raise ValueError("authority review cannot precede text preparation")
        currentness=str(decision.get("currentness") or "").upper()
        if currentness not in CURRENTNESS:
            raise ValueError("currentness must be CURRENT, SUPERSEDED, or UNRESOLVED")
        rationale=decision.get("currentness_rationale")
        if not _text(rationale):
            raise ValueError("currentness_rationale is required")

        memo=_select(prep["snapshot"],decision.get("memo_passage"),required=True,name="memo_passage")

        effective_from=decision.get("effective_from")
        effective_until=decision.get("effective_until")
        start=_date(effective_from); end=_date(effective_until)
        if effective_from is not None and start is None:
            raise ValueError("effective_from must be an ISO date or null")
        if effective_until is not None and end is None:
            raise ValueError("effective_until must be an ISO date or null")
        if start and end and end<start:
            raise ValueError("effective_until cannot precede effective_from")
        effective_passage=_select(
            prep["snapshot"],
            decision.get("effective_date_passage"),
            required=bool(effective_from or effective_until),
            name="effective_date_passage",
        )

        currentness_basis=None
        basis_spec=decision.get("currentness_basis_passage")
        if currentness!="UNRESOLVED":
            if not isinstance(basis_spec,dict) or not _text(basis_spec.get("snapshot_id")):
                raise ValueError("resolved currentness requires a separate retained basis passage")
            basis_snapshot=_trace_snapshot(case,basis_spec["snapshot_id"])
            if basis_snapshot.get("snapshot_id")==prep["snapshot"].get("snapshot_id"):
                raise ValueError("deviation memo cannot self-certify its own currentness")
            currentness_basis=_select(
                basis_snapshot,basis_spec,required=True,name="currentness_basis_passage"
            )
        elif basis_spec is not None:
            raise ValueError("UNRESOLVED currentness cannot carry a resolved basis passage")

        superseding_reference=decision.get("superseding_reference")
        if currentness=="SUPERSEDED" and not _text(superseding_reference):
            raise ValueError("SUPERSEDED review requires superseding_reference")
        if currentness!="SUPERSEDED" and superseding_reference not in (None,""):
            raise ValueError("superseding_reference is only valid for SUPERSEDED reviews")

        payload={
            "contract":REVIEW_CONTRACT,
            "proposal_sha256":prep["proposal_sha256"],
            "artifact_receipt_id":prep["artifact_receipt_id"],
            "preparation_id":prep["preparation_id"],
            "deviation_source_id":ident,
            "agency":prep["agency"],
            "matched_parts":copy.deepcopy(prep.get("matched_parts") or []),
            "document_sha256":prep["document_sha256"],
            "snapshot_id":prep["snapshot"]["snapshot_id"],
            "memo_passage":memo,
            "effective_from":effective_from,
            "effective_until":effective_until,
            "effective_date_passage":effective_passage,
            "currentness":currentness,
            "currentness_rationale":rationale.strip(),
            "currentness_basis_passage":currentness_basis,
            "superseding_reference":superseding_reference,
            "reviewed_by":reviewer.strip(),
            "reviewed_at":reviewed_at,
            "human_reviewed":True,
            "currentness_authoritative":False,
            "applicability":"UNRESOLVED",
            "applicability_authoritative":False,
            "assumption_state_changed":False,
            "can_auto_apply":False,
        }
        records.append({**payload,"authority_review_id":"DEVAUTH:"+digest(canonical(payload))})

    result=copy.deepcopy(case)
    rows=result.setdefault("packet",{}).setdefault("deviation_authority_reviews",[])
    existing={x.get("authority_review_id") for x in rows if isinstance(x,dict)}
    for record in records:
        if record["authority_review_id"] not in existing:
            rows.append(copy.deepcopy(record))
    rows.sort(key=lambda x:(str(x.get("deviation_source_id") or ""),str(x.get("reviewed_at") or ""),str(x.get("authority_review_id") or "")))
    return result,{
        "status":"DEVIATION_AUTHORITY_REVIEWED",
        "authority_review_ids":[x["authority_review_id"] for x in records],
        "currentness_states":{x["deviation_source_id"]:x["currentness"] for x in records},
        "applicability":"UNRESOLVED",
        "assumption_state_changed":False,
        "can_auto_apply":False,
    }

def deviation_authority_work_items(case: dict[str,Any])->list[dict[str,Any]]:
    receipts=current_deviation_artifact_receipts(case)
    preps=current_deviation_text_preparations(case)
    reviews=current_deviation_authority_reviews(case)
    tasks=[]
    for ident,receipt in sorted(receipts.items()):
        if ident not in preps:
            tasks.append({
                "task_key":"deviation-text:"+ident,
                "priority":"P0",
                "title":"Prepare reviewed text for captured deviation PDF",
                "actor":"HUMAN_REVIEW",
                "can_auto_execute":False,
                "status":"OPEN",
                "reason":"The official PDF bytes are captured and hashed, but no reviewed text snapshot is bound to those bytes.",
                "evidence_needed":"Reviewed extraction/native text with mapping note, reviewer identity, and exact binding to the captured PDF SHA-256.",
                "metadata":{"deviation_source_id":ident,"artifact_receipt_id":receipt["artifact_receipt_id"],"can_auto_apply":False},
            })
            continue
        review=reviews.get(ident)
        if review is None:
            tasks.append({
                "task_key":"deviation-authority:"+ident,
                "priority":"P0",
                "title":"Review deviation memo authority state",
                "actor":"HUMAN_REVIEW",
                "can_auto_execute":False,
                "status":"OPEN",
                "reason":"Reviewed memo text exists, but currentness/effective/supersession state has not been explicitly reviewed.",
                "evidence_needed":"Exact memo passage; exact effective-date passage when claimed; and a separate retained public basis passage before CURRENT or SUPERSEDED can be recorded.",
                "metadata":{"deviation_source_id":ident,"preparation_id":preps[ident]["preparation_id"],"can_auto_apply":False},
            })
        elif review.get("currentness")=="UNRESOLVED":
            tasks.append({
                "task_key":"deviation-currentness:"+ident,
                "priority":"P0",
                "title":"Resolve deviation memo currentness",
                "actor":"HUMAN_REVIEW",
                "can_auto_execute":False,
                "status":"OPEN",
                "reason":"The memo was reviewed but currentness remains UNRESOLVED.",
                "evidence_needed":"A separate retained public source passage supporting CURRENT or SUPERSEDED, or keep the buyer-facing rule state unresolved.",
                "metadata":{"deviation_source_id":ident,"authority_review_id":review["authority_review_id"],"can_auto_apply":False},
            })
    return tasks
