from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Iterable
from .model import FAMILY_STATUSES, RECEIPT_SEMANTICS, Finding, canonical_json, first_party_sam, history_set_digest, parse_dt, sha256_hex, valid_sha256
from .source_policy import classify_sam_url

def _fresh(r:dict[str,Any],now:datetime)->bool:
    observed,expires=parse_dt(r.get("observed_at")),parse_dt(r.get("expires_at"))
    return bool(observed and expires and observed<=now<=expires and expires>observed)

def _payload_verified(r:dict[str,Any])->bool:
    digest=r.get("evidence_payload_sha256")
    if not valid_sha256(digest): return False
    if r.get("evidence_payload") is not None:
        return sha256_hex(canonical_json(r["evidence_payload"]))==digest
    return r.get("payload_hash_verified") is True

def _approved_api_contract_ok(r:dict[str,Any])->tuple[bool,str|None,str|None]:
    mode=r.get("automation_mode")
    if mode is None or mode=="HUMAN_SUPERVISED":
        return True,None,None
    if mode!="APPROVED_API":
        return False,"RECEIPT_AUTOMATION_MODE_INVALID","Receipt automation mode is not recognized."
    if classify_sam_url(str(r.get("source_url","")))!="SAM_PUBLIC_API":
        return False,"RECEIPT_APPROVED_API_SOURCE_INVALID","Approved API receipt does not point to the documented SAM public API."
    evidence=r.get("evidence_payload")
    if not isinstance(evidence,dict):
        return False,"RECEIPT_APPROVED_API_EVIDENCE_MISSING","Approved API receipt lacks structured evidence."
    if evidence.get("source_contract")!="SAM_GET_OPPORTUNITIES_V2":
        return False,"RECEIPT_APPROVED_API_CONTRACT_INVALID","Approved API receipt source contract is invalid."
    if str(evidence.get("notice_id",""))!=str(r.get("asserted_action_id","")):
        return False,"RECEIPT_APPROVED_API_NOTICE_MISMATCH","Approved API receipt notice ID does not match the asserted action."
    if not valid_sha256(evidence.get("api_payload_sha256")):
        return False,"RECEIPT_APPROVED_API_PAYLOAD_HASH_INVALID","Approved API receipt lacks a valid API payload SHA-256."
    if not valid_sha256(evidence.get("api_response_sha256")):
        return False,"RECEIPT_APPROVED_API_RESPONSE_HASH_INVALID","Approved API receipt lacks a valid raw-response SHA-256."
    pagination=evidence.get("pagination")
    if not isinstance(pagination,dict) or pagination.get("complete") is not True:
        return False,"RECEIPT_APPROVED_API_PAGINATION_MISSING","Approved API receipt lacks pagination-completeness evidence."
    try:
        total=int(pagination.get("total_records"))
        returned=int(pagination.get("returned_records"))
        limit=int(pagination.get("limit"))
        offset=int(pagination.get("offset"))
    except (TypeError,ValueError):
        return False,"RECEIPT_APPROVED_API_PAGINATION_INVALID","Approved API receipt pagination values are malformed."
    if min(total,returned,limit,offset)<0 or offset!=0 or total!=returned or returned>limit:
        return False,"RECEIPT_APPROVED_API_PAGINATION_INCOMPLETE","Approved API receipt does not prove a complete first page/result set."
    links=evidence.get("resource_links") or []
    if not isinstance(links,list):
        return False,"RECEIPT_APPROVED_API_RESOURCE_LINKS_INVALID","Approved API receipt resource links are not a list."
    for link in links:
        if classify_sam_url(str(link))!="SAM_API_RESOURCE_LINK":
            return False,"RECEIPT_APPROVED_API_RESOURCE_LINK_INVALID","Approved API receipt contains a resource link outside the approved SAM resource-link contract."
    return True,None,None

def validate_current_action_receipts(history_ids:Iterable[str],family_status:str,receipts:Iterable[dict[str,Any]],*,now:datetime|None=None):
    findings:list[Finding]=[]
    now=now or datetime.now(timezone.utc)
    status=str(family_status or "UNKNOWN").upper()
    history={str(x) for x in history_ids if str(x)}
    digest=history_set_digest(history)
    if status not in FAMILY_STATUSES:
        status="UNKNOWN"; findings.append(Finding("UNKNOWN_FAMILY_STATUS","BLOCK","Family status is not recognized."))
    accepted=[]
    for i,r in enumerate(receipts):
        path=f"current_action_receipts[{i}]"; sem=str(r.get("semantics","")).upper(); action=str(r.get("asserted_action_id","")); observed_status=str(r.get("observed_family_status","")).upper()
        checks=[
            (sem in RECEIPT_SEMANTICS,"RECEIPT_BAD_SEMANTICS","Receipt semantics are invalid."),
            (_fresh(r,now),"RECEIPT_STALE_OR_TIME_INVALID","Receipt is stale or has invalid observation/expiry timestamps."),
            (first_party_sam(r.get("source_url")),"RECEIPT_NOT_FIRST_PARTY","Receipt does not point to a first-party sam.gov HTTPS surface."),
            (_payload_verified(r),"RECEIPT_PAYLOAD_UNVERIFIED","Receipt payload hash is absent, malformed, or not verified."),
            (bool(action and action in history),"RECEIPT_ACTION_OUTSIDE_HISTORY","Asserted action is not a member of the observed history set."),
            (r.get("history_set_sha256")==digest,"RECEIPT_HISTORY_DIGEST_MISMATCH","Receipt history-set digest does not match the observed history set."),
            (observed_status==status,"RECEIPT_STATUS_MISMATCH","Receipt status does not match the case family status."),
        ]
        api_ok,api_code,api_message=_approved_api_contract_ok(r)
        if not api_ok:
            checks.append((False,api_code or "RECEIPT_APPROVED_API_INVALID",api_message or "Approved API receipt failed source-contract validation."))
        failed=next(((c,m) for ok,c,m in checks if not ok),None)
        if failed:
            findings.append(Finding(failed[0],"WARN",failed[1],path)); continue
        compatible=(status=="ACTIVE" and sem=="CURRENT_ACTIVE") or (status=="CANCELLED" and sem=="TERMINAL_CANCELLED") or (status=="ARCHIVED" and sem=="TERMINAL_ARCHIVED")
        if not compatible:
            findings.append(Finding("RECEIPT_SEMANTICS_STATUS_CONFLICT","WARN","Receipt semantics are incompatible with the observed family status.",path)); continue
        accepted.append((sem,action))
    if status in {"INACTIVE","DELETED","UNKNOWN"}: return "CURRENT_UNKNOWN",None,findings
    claims=set(accepted)
    if len(claims)>1:
        findings.append(Finding("CURRENT_ACTION_SOURCE_DISAGREEMENT","BLOCK","Fresh verified first-party receipts disagree on controlling/terminal action.")); return "CURRENT_ACTION_SOURCE_DISAGREEMENT",None,findings
    if not claims: return "CURRENT_UNKNOWN",None,findings
    sem,action=next(iter(claims))
    verdict={"CURRENT_ACTIVE":"CURRENT_VERIFIED","TERMINAL_CANCELLED":"TERMINAL_CANCELLED_VERIFIED","TERMINAL_ARCHIVED":"TERMINAL_ARCHIVED_VERIFIED"}[sem]
    return verdict,action,findings
