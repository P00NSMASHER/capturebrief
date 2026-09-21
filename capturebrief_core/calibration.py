"""Structured internal methodology calibration for CaptureBrief.

External expert review is product evidence, not customer evidence, legal authority,
or public endorsement. Public attribution defaults to false and requires a separate
explicit evidence reference.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .model import canonical_json, parse_dt, sha256_hex, valid_sha256

CALIBRATION_SCHEMA="1.0"
CATEGORIES={
    "DECISION_LOGIC","HARD_GATE","ELIGIBILITY_SECURITY","DEADLINE_SUBMISSION",
    "SOURCE_CONTROL","CAVEAT_LANGUAGE","CHECKLIST","PRODUCT_BOUNDARY","OTHER",
}
SEVERITIES={"CRITICAL","MATERIAL","MINOR","OBSERVATION"}
DISPOSITIONS={"PENDING","ACCEPT","PARTIAL","REJECT","DEFER"}
IMPLEMENTATION_STATES={"NOT_STARTED","IMPLEMENTED","NO_CHANGE","DEFERRED"}
ID_RE=re.compile(r"^[A-Z][A-Z0-9_-]{1,63}$")
REF_RE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{2,199}$")

TOP_LEVEL_FIELDS={
    "schema_version","review_id","sample_ref","sample_sha256","received_at",
    "reviewer_ref","scope_ref","internal_only","public_attribution_approved",
    "public_attribution_evidence_ref","findings",
}
FINDING_FIELDS={
    "finding_id","category","severity","summary","evidence_ref","recommendation",
    "disposition","disposition_rationale","implementation_status","change_ref","test_ref",
}


def _text(value:Any)->bool:
    return isinstance(value,str) and bool(value.strip())


def _ref(value:Any)->bool:
    return isinstance(value,str) and REF_RE.fullmatch(value) is not None


def validate_calibration_review(review:dict[str,Any])->list[str]:
    errors:list[str]=[]
    if not isinstance(review,dict):
        return ["review:not_object"]
    extra=set(review)-TOP_LEVEL_FIELDS
    if extra:
        errors.append("review:unknown_fields:"+",".join(sorted(extra)))
    if review.get("schema_version")!=CALIBRATION_SCHEMA:
        errors.append("schema_version")
    if not _text(review.get("review_id")) or ID_RE.fullmatch(str(review.get("review_id"))) is None:
        errors.append("review_id")
    if not _ref(review.get("sample_ref")):
        errors.append("sample_ref")
    if not valid_sha256(review.get("sample_sha256")):
        errors.append("sample_sha256")
    if parse_dt(review.get("received_at")) is None:
        errors.append("received_at")
    if not _ref(review.get("reviewer_ref")):
        errors.append("reviewer_ref")
    if not _ref(review.get("scope_ref")):
        errors.append("scope_ref")
    if review.get("internal_only") is not True:
        errors.append("internal_only_must_be_true")
    if type(review.get("public_attribution_approved")) is not bool:
        errors.append("public_attribution_approved")
    if review.get("public_attribution_approved") is True:
        if not _ref(review.get("public_attribution_evidence_ref")):
            errors.append("public_attribution_evidence_ref")
    elif review.get("public_attribution_evidence_ref") is not None:
        errors.append("public_attribution_evidence_without_approval")

    findings=review.get("findings")
    if not isinstance(findings,list) or not findings:
        return sorted(set(errors+["findings:not_nonempty_list"]))

    seen:set[str]=set()
    for i,finding in enumerate(findings):
        path=f"findings[{i}]"
        if not isinstance(finding,dict):
            errors.append(path+":not_object")
            continue
        extra_f=set(finding)-FINDING_FIELDS
        if extra_f:
            errors.append(path+":unknown_fields:"+",".join(sorted(extra_f)))
        fid=finding.get("finding_id")
        if not _text(fid) or ID_RE.fullmatch(str(fid)) is None or fid in seen:
            errors.append(path+":finding_id")
        else:
            seen.add(str(fid))
        if finding.get("category") not in CATEGORIES:
            errors.append(path+":category")
        if finding.get("severity") not in SEVERITIES:
            errors.append(path+":severity")
        if not _text(finding.get("summary")):
            errors.append(path+":summary")
        if not _ref(finding.get("evidence_ref")):
            errors.append(path+":evidence_ref")
        if finding.get("recommendation") is not None and not _text(finding.get("recommendation")):
            errors.append(path+":recommendation")

        disposition=finding.get("disposition")
        state=finding.get("implementation_status")
        if disposition not in DISPOSITIONS:
            errors.append(path+":disposition")
        if state not in IMPLEMENTATION_STATES:
            errors.append(path+":implementation_status")
        if disposition=="PENDING":
            if state!="NOT_STARTED":
                errors.append(path+":pending_must_be_not_started")
            if finding.get("disposition_rationale") is not None:
                errors.append(path+":pending_has_disposition_rationale")
        elif disposition in {"ACCEPT","PARTIAL"}:
            if not _text(finding.get("disposition_rationale")):
                errors.append(path+":disposition_rationale")
            if state not in {"NOT_STARTED","IMPLEMENTED"}:
                errors.append(path+":accepted_state")
            if state=="IMPLEMENTED":
                if not _ref(finding.get("change_ref")):
                    errors.append(path+":change_ref")
                if not _ref(finding.get("test_ref")):
                    errors.append(path+":test_ref")
        elif disposition=="REJECT":
            if not _text(finding.get("disposition_rationale")):
                errors.append(path+":disposition_rationale")
            if state!="NO_CHANGE":
                errors.append(path+":reject_must_be_no_change")
        elif disposition=="DEFER":
            if not _text(finding.get("disposition_rationale")):
                errors.append(path+":disposition_rationale")
            if state!="DEFERRED":
                errors.append(path+":defer_must_be_deferred")

        if state!="IMPLEMENTED" and (finding.get("change_ref") is not None or finding.get("test_ref") is not None):
            errors.append(path+":implementation_refs_without_implementation")

    return sorted(set(errors))


def summarize_calibration_review(review:dict[str,Any])->dict[str,Any]:
    errors=validate_calibration_review(review)
    if errors:
        return {
            "schema_version":CALIBRATION_SCHEMA,
            "valid":False,
            "errors":errors,
            "calibration_state":"INVALID",
            "methodology_calibration_complete":False,
            "public_attribution_allowed":False,
        }

    findings=review["findings"]
    categories=Counter(x["category"] for x in findings)
    severities=Counter(x["severity"] for x in findings)
    dispositions=Counter(x["disposition"] for x in findings)

    open_findings=[
        x for x in findings
        if x["disposition"]=="PENDING"
        or (x["disposition"] in {"ACCEPT","PARTIAL"} and x["implementation_status"]!="IMPLEMENTED")
    ]
    open_critical_material=[
        x for x in open_findings if x["severity"] in {"CRITICAL","MATERIAL"}
    ]
    implemented=[
        x for x in findings
        if x["disposition"] in {"ACCEPT","PARTIAL"} and x["implementation_status"]=="IMPLEMENTED"
    ]

    if open_critical_material:
        state="OPEN_CRITICAL_OR_MATERIAL"
    elif open_findings:
        state="OPEN"
    else:
        state="CLOSED"

    return {
        "schema_version":CALIBRATION_SCHEMA,
        "valid":True,
        "review_id":review["review_id"],
        "sample_ref":review["sample_ref"],
        "sample_sha256":review["sample_sha256"],
        "review_sha256":sha256_hex(canonical_json(review)),
        "calibration_state":state,
        "methodology_calibration_complete":state=="CLOSED",
        "finding_count":len(findings),
        "open_finding_count":len(open_findings),
        "open_critical_or_material_count":len(open_critical_material),
        "implemented_change_count":len(implemented),
        "categories":dict(sorted(categories.items())),
        "severities":dict(sorted(severities.items())),
        "dispositions":dict(sorted(dispositions.items())),
        "public_attribution_allowed":(
            review["public_attribution_approved"] is True
            and _ref(review.get("public_attribution_evidence_ref"))
        ),
        "public_attribution_evidence_ref":review.get("public_attribution_evidence_ref"),
        "automatic_product_or_public_claim_change":False,
        "next_required_actions":[
            {
                "finding_id":x["finding_id"],
                "severity":x["severity"],
                "category":x["category"],
                "disposition":x["disposition"],
                "implementation_status":x["implementation_status"],
            }
            for x in open_findings
        ],
    }
