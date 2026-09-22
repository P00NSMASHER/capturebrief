"""Evidence-grounded commercial outcome events for CaptureBrief."""
from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .ledger import append_record, verify_ledger
from .model import canonical_json, sha256_hex

OUTCOME_SCHEMA="1.0"
RECORD_TYPE="CAPTUREBRIEF_OUTCOME_EVENT"
EVENT_TYPES={"PAYMENT","DELIVERY","FEEDBACK","RETRACTION","REPEAT_REQUEST","EFFORT"}
PAYMENT_STATES={"PAID","UNPAID","REFUNDED","UNKNOWN"}
USEFULNESS={"USEFUL","NOT_USEFUL","UNKNOWN"}
ACTION_EFFECTS={
    "CHANGED_ACTION","CLOSED_COSTLY_UNCERTAINTY","CONFIRMED_EXISTING_VIEW",
    "ALREADY_KNEW","FALSE_POSITIVE","NO_DECISION","UNKNOWN",
}
REPEAT_STATES={"REQUESTED_REPEAT","WOULD_REPEAT","NO_REPEAT","UNKNOWN"}
RETRACTION_SEVERITIES={"CRITICAL","NONCRITICAL"}
RETRACTION_REASONS={
    "WRONG_SOURCE","WRONG_VERSION","WRONG_RULE_EDITION","BAD_APPLICABILITY",
    "BAD_IDENTITY","MISREAD_PASSAGE","MISSING_CONTROLLING_EVIDENCE","OTHER",
}
EFFORT_STAGES={
    "INTAKE_SCOPE","HISTORY_CURRENT","PACKET_BYTES","REFERENCE_REVIEW",
    "ASSUMPTION_REVIEW","RULE_REVIEW","DEVIATION_REVIEW","WATCH",
    "DELIVERY","CUSTOMER_COMMS","OTHER",
}
FINDING_CLASS_RE=re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
SHA_RE=re.compile(r"^[0-9a-f]{64}$")
REF_RE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{2,199}$")
ALLOWED_COMMON={
    "schema_version","case_id","case_sha256","event_type","event_at",
    "delivery_bundle_sha256","data",
}
FORBIDDEN_KEYS={
    "email","company","company_name","buyer","buyer_name","customer","customer_name",
    "contact","contact_name","phone","address","notes","free_text","roi","pwin",
    "proposal_savings","revenue_uplift",
}


def _dt(value:Any)->datetime|None:
    if not isinstance(value,str): return None
    try:
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _sha(value:Any)->bool:
    return isinstance(value,str) and SHA_RE.fullmatch(value) is not None


def _ref(value:Any)->bool:
    return isinstance(value,str) and REF_RE.fullmatch(value) is not None


def _no_forbidden_keys(value:Any,path="event")->list[str]:
    errors=[]
    if isinstance(value,dict):
        for key,item in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                errors.append(f"{path}.{key}:forbidden_field")
            errors.extend(_no_forbidden_keys(item,f"{path}.{key}"))
    elif isinstance(value,list):
        for i,item in enumerate(value):
            errors.extend(_no_forbidden_keys(item,f"{path}[{i}]"))
    return errors


def validate_outcome_event(event:dict[str,Any])->list[str]:
    errors=[]
    if not isinstance(event,dict): return ["event:not_object"]
    unknown=set(event)-ALLOWED_COMMON
    if unknown: errors.append("event:unknown_fields:"+",".join(sorted(unknown)))
    errors.extend(_no_forbidden_keys(event))
    if event.get("schema_version")!=OUTCOME_SCHEMA: errors.append("schema_version")
    if not isinstance(event.get("case_id"),str) or not event["case_id"].strip(): errors.append("case_id")
    if not _sha(event.get("case_sha256")): errors.append("case_sha256")
    if event.get("delivery_bundle_sha256") is not None and not _sha(event.get("delivery_bundle_sha256")): errors.append("delivery_bundle_sha256")
    kind=str(event.get("event_type") or "").upper()
    if kind in {"DELIVERY","FEEDBACK","RETRACTION","REPEAT_REQUEST"} and not _sha(event.get("delivery_bundle_sha256")):
        errors.append("delivery_bundle_sha256_required")
    if kind not in EVENT_TYPES: errors.append("event_type")
    if _dt(event.get("event_at")) is None: errors.append("event_at")
    data=event.get("data")
    if not isinstance(data,dict): return sorted(set(errors+["data:not_object"]))

    allowed:set[str]
    required:set[str]
    if kind=="PAYMENT":
        allowed={"state","amount_cents","currency","payment_evidence_ref"}
        required={"state"}
        if data.get("state") not in PAYMENT_STATES: errors.append("data.state")
        if data.get("state") in {"PAID","REFUNDED"} and not _ref(data.get("payment_evidence_ref")): errors.append("data.payment_evidence_ref")
        amount=data.get("amount_cents")
        if amount is not None and (type(amount) is not int or amount<0): errors.append("data.amount_cents")
        if amount is not None and (not isinstance(data.get("currency"),str) or not re.fullmatch(r"[A-Z]{3}",data["currency"])): errors.append("data.currency")
    elif kind=="DELIVERY":
        allowed={"started_at","delivered_at","delivery_evidence_ref"}
        required={"started_at","delivered_at","delivery_evidence_ref"}
        a,b=_dt(data.get("started_at")),_dt(data.get("delivered_at"))
        if a is None: errors.append("data.started_at")
        if b is None: errors.append("data.delivered_at")
        if a and b and b<a: errors.append("data.delivery_interval")
        if not _ref(data.get("delivery_evidence_ref")): errors.append("data.delivery_evidence_ref")
    elif kind=="FEEDBACK":
        allowed={"usefulness","action_effect","source_limited","finding_classes","feedback_evidence_ref"}
        required={"usefulness","action_effect","source_limited","finding_classes","feedback_evidence_ref"}
        if data.get("usefulness") not in USEFULNESS: errors.append("data.usefulness")
        if data.get("action_effect") not in ACTION_EFFECTS: errors.append("data.action_effect")
        if type(data.get("source_limited")) is not bool: errors.append("data.source_limited")
        classes=data.get("finding_classes")
        if not isinstance(classes,list) or any(not isinstance(x,str) or FINDING_CLASS_RE.fullmatch(x) is None for x in classes) or len(set(classes or []))!=len(classes or []): errors.append("data.finding_classes")
        if not _ref(data.get("feedback_evidence_ref")): errors.append("data.feedback_evidence_ref")
    elif kind=="RETRACTION":
        allowed={"severity","reason_code","retraction_evidence_ref"}
        required=allowed
        if data.get("severity") not in RETRACTION_SEVERITIES: errors.append("data.severity")
        if data.get("reason_code") not in RETRACTION_REASONS: errors.append("data.reason_code")
        if not _ref(data.get("retraction_evidence_ref")): errors.append("data.retraction_evidence_ref")
    elif kind=="REPEAT_REQUEST":
        allowed={"state","repeat_evidence_ref"}
        required=allowed
        if data.get("state") not in REPEAT_STATES: errors.append("data.state")
        if data.get("state")!="UNKNOWN" and not _ref(data.get("repeat_evidence_ref")): errors.append("data.repeat_evidence_ref")
    elif kind=="EFFORT":
        allowed={"stage","minutes","effort_evidence_ref"}
        required=allowed
        if data.get("stage") not in EFFORT_STAGES: errors.append("data.stage")
        minutes=data.get("minutes")
        if type(minutes) is not int or minutes<1 or minutes>1440: errors.append("data.minutes")
        if not _ref(data.get("effort_evidence_ref")): errors.append("data.effort_evidence_ref")
    else:
        allowed=set(); required=set()

    missing=required-set(data)
    if missing: errors.append("data:missing_fields:"+",".join(sorted(missing)))
    extra=set(data)-allowed
    if extra: errors.append("data:unknown_fields:"+",".join(sorted(extra)))
    return sorted(set(errors))


def make_outcome_event(*,case_id:str,case_sha256:str,event_type:str,event_at:str,data:dict[str,Any],delivery_bundle_sha256:str|None=None)->dict[str,Any]:
    event={
        "schema_version":OUTCOME_SCHEMA,
        "case_id":case_id,
        "case_sha256":case_sha256,
        "event_type":str(event_type).upper(),
        "event_at":event_at,
        "delivery_bundle_sha256":delivery_bundle_sha256,
        "data":data,
    }
    errors=validate_outcome_event(event)
    if errors: raise ValueError("invalid outcome event: "+",".join(errors))
    return event


def append_outcome_event(path:str|Path,event:dict[str,Any],*,recorded_at:str|None=None)->dict[str,Any]:
    errors=validate_outcome_event(event)
    if errors: raise ValueError("invalid outcome event: "+",".join(errors))
    status=verify_ledger(path)
    if not status["valid"]:
        raise ValueError("refusing to append to invalid outcome ledger")
    return append_record(path,record_type=RECORD_TYPE,payload=event,recorded_at=recorded_at)


def _outcome_records(path:str|Path)->list[dict[str,Any]]:
    status=verify_ledger(path)
    if not status["valid"]: raise ValueError("outcome ledger failed hash-chain verification")
    p=Path(path)
    if not p.exists(): return []
    rows=[]
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        record=json.loads(line)
        if record.get("record_type")!=RECORD_TYPE: continue
        event=record.get("payload")
        errors=validate_outcome_event(event)
        if errors: raise ValueError("stored outcome event invalid: "+",".join(errors))
        rows.append({"record_sha256":record["record_sha256"],"recorded_at":record["recorded_at"],"event":event})
    return rows


def summarize_outcomes(path:str|Path)->dict[str,Any]:
    records=_outcome_records(path)
    cases:dict[str,dict[str,Any]]={}
    finding_counts=Counter()
    for row in records:
        event=row["event"]; cid=event["case_id"]; kind=event["event_type"]
        state=cases.setdefault(cid,{"events":0,"case_sha256":event["case_sha256"],"payments":[],"deliveries":[],"feedback":[],"retractions":[],"repeat":[],"effort":[]})
        if state["case_sha256"]!=event["case_sha256"]:
            raise ValueError(f"case fingerprint mismatch for {cid}")
        state["events"]+=1
        state[{"PAYMENT":"payments","DELIVERY":"deliveries","FEEDBACK":"feedback","RETRACTION":"retractions","REPEAT_REQUEST":"repeat","EFFORT":"effort"}[kind]].append(row)
    paid=0; paid_cents=0; paid_with_amount=0; delivered=0; turnaround=[]; feedback_cases=0
    useful=not_useful=changed=closed=confirmed=already=false_positive=source_limited=0
    repeat_requested=would_repeat=no_repeat=0; retraction_cases=critical_retractions=0
    paid_amount_by_currency=Counter(); effort_case_minutes=[]; effort_stage_minutes=Counter()
    paid_effort_covered=0; paid_effort_minutes_by_currency=Counter(); paid_effort_amount_by_currency=Counter()
    unbound_outcome_events=0
    for cid,state in cases.items():
        effort_minutes=sum(x["event"]["data"]["minutes"] for x in state["effort"])
        if effort_minutes:
            effort_case_minutes.append(effort_minutes)
            for effort_row in state["effort"]:
                effort_stage_minutes[effort_row["event"]["data"]["stage"]]+=effort_row["event"]["data"]["minutes"]
        latest_payment=max(state["payments"],key=lambda x:_dt(x["event"]["event_at"])) if state["payments"] else None
        if latest_payment and latest_payment["event"]["data"]["state"]=="PAID":
            paid+=1
            payment_data=latest_payment["event"]["data"]
            amount=payment_data.get("amount_cents")
            currency=payment_data.get("currency")
            if amount is not None:
                paid_cents+=amount; paid_with_amount+=1
                paid_amount_by_currency[currency]+=amount
            if effort_minutes:
                paid_effort_covered+=1
                if amount is not None:
                    paid_effort_amount_by_currency[currency]+=amount
                    paid_effort_minutes_by_currency[currency]+=effort_minutes
        latest_delivery=max(state["deliveries"],key=lambda x:_dt(x["event"]["event_at"])) if state["deliveries"] else None
        delivered_by_bundle={}
        for delivery_row in state["deliveries"]:
            delivery_event=delivery_row["event"]
            bundle_sha=delivery_event.get("delivery_bundle_sha256")
            delivered_at=_dt(delivery_event["data"]["delivered_at"])
            if bundle_sha and delivered_at:
                prior=delivered_by_bundle.get(bundle_sha)
                if prior is None or delivered_at>prior:
                    delivered_by_bundle[bundle_sha]=delivered_at
        if latest_delivery:
            delivered+=1
            data=latest_delivery["event"]["data"]; a,b=_dt(data["started_at"]),_dt(data["delivered_at"])
            turnaround.append((b-a).total_seconds()/3600)

        def bound(rows):
            nonlocal unbound_outcome_events
            valid=[]
            for row in rows:
                event=row["event"]
                bundle_sha=event.get("delivery_bundle_sha256")
                delivered_at=delivered_by_bundle.get(bundle_sha)
                event_at=_dt(event.get("event_at"))
                if delivered_at is None or event_at is None or event_at<delivered_at:
                    unbound_outcome_events+=1
                    continue
                valid.append(row)
            return valid

        bound_feedback=bound(state["feedback"])
        latest_feedback=max(bound_feedback,key=lambda x:_dt(x["event"]["event_at"])) if bound_feedback else None
        if latest_feedback:
            feedback_cases+=1; data=latest_feedback["event"]["data"]
            finding_counts.update(data["finding_classes"])
            useful+=data["usefulness"]=="USEFUL"; not_useful+=data["usefulness"]=="NOT_USEFUL"
            effect=data["action_effect"]
            changed+=effect=="CHANGED_ACTION"; closed+=effect=="CLOSED_COSTLY_UNCERTAINTY"; confirmed+=effect=="CONFIRMED_EXISTING_VIEW"
            already+=effect=="ALREADY_KNEW"; false_positive+=effect=="FALSE_POSITIVE"; source_limited+=bool(data["source_limited"])

        bound_repeat=bound(state["repeat"])
        latest_repeat=max(bound_repeat,key=lambda x:_dt(x["event"]["event_at"])) if bound_repeat else None
        if latest_repeat:
            val=latest_repeat["event"]["data"]["state"]
            repeat_requested+=val=="REQUESTED_REPEAT"; would_repeat+=val=="WOULD_REPEAT"; no_repeat+=val=="NO_REPEAT"

        bound_retractions=bound(state["retractions"])
        if bound_retractions:
            retraction_cases+=1
            critical_retractions+=sum(x["event"]["data"]["severity"]=="CRITICAL" for x in bound_retractions)

    threshold={
        "paid_engagements_at_least_3":paid>=3,
        "repeat_request_at_least_1":repeat_requested>=1,
        "action_changed_or_costly_uncertainty_closed_at_least_1":changed+closed>=1,
        "turnaround_evidence_present":bool(turnaround),
        "effort_evidence_present":bool(effort_case_minutes),
        "paid_engagement_effort_coverage_complete":paid>0 and paid_effort_covered==paid,
        "outcome_binding_complete":unbound_outcome_events==0,
        "retraction_evidence_present":bool(cases),
        "turnaround_acceptability_requires_human_threshold":True,
        "effort_acceptability_requires_human_threshold":True,
        "retraction_acceptability_requires_human_threshold":True,
        "automatic_pricing_or_subscription_change":False,
    }
    return {
        "schema_version":OUTCOME_SCHEMA,
        "ledger":verify_ledger(path),
        "events":len(records),
        "engagements":len(cases),
        "paid_engagements":paid,
        "paid_amount_cents_recorded":paid_cents,
        "paid_amount_cents_by_currency":dict(sorted(paid_amount_by_currency.items())),
        "paid_engagements_with_amount":paid_with_amount,
        "delivered_engagements":delivered,
        "turnaround_hours":{"count":len(turnaround),"median":statistics.median(turnaround) if turnaround else None,"min":min(turnaround) if turnaround else None,"max":max(turnaround) if turnaround else None},
        "effort_hours":{
            "count":len(effort_case_minutes),
            "total":sum(effort_case_minutes)/60 if effort_case_minutes else 0,
            "median":statistics.median(effort_case_minutes)/60 if effort_case_minutes else None,
            "min":min(effort_case_minutes)/60 if effort_case_minutes else None,
            "max":max(effort_case_minutes)/60 if effort_case_minutes else None,
        },
        "effort_stage_minutes":dict(sorted(effort_stage_minutes.items())),
        "paid_effort_coverage":{"paid_engagements":paid,"paid_with_effort":paid_effort_covered},
        "collected_cents_per_recorded_effort_hour_by_currency":{
            currency: round(cents/(paid_effort_minutes_by_currency[currency]/60),2)
            for currency,cents in sorted(paid_effort_amount_by_currency.items())
            if paid_effort_minutes_by_currency[currency]>0
        },
        "buyer_feedback_cases":feedback_cases,
        "unbound_outcome_events":unbound_outcome_events,
        "feedback":{
            "useful":useful,"not_useful":not_useful,"changed_action":changed,
            "closed_costly_uncertainty":closed,"confirmed_existing_view":confirmed,
            "already_knew":already,"false_positive":false_positive,"source_limited":source_limited,
        },
        "repeat":{"requested_repeat":repeat_requested,"would_repeat":would_repeat,"no_repeat":no_repeat},
        "quality":{"engagements_with_retraction":retraction_cases,"critical_retractions":critical_retractions},
        "finding_classes":dict(sorted(finding_counts.items())),
        "commercial_proof_threshold_evidence":threshold,
        "claims_not_computed":["accuracy","PWin uplift","proposal savings","ROI","revenue uplift"],
    }
