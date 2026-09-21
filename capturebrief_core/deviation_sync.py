"""Pinned class-deviation manifest retrieval and candidate review for CaptureBrief.

This layer discovers possible agency/FAR-Part deviation artifacts. It never decides
that a deviation is current, applicable, incorporated, or controlling.
"""
from __future__ import annotations

import copy
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .rule_registry import canonical, digest, filter_deviation_sources, load_source_catalog, parse_deviation_manifest

MANIFEST_CONTRACT="capturebrief-pinned-deviation-manifest-v1"
PROPOSAL_CONTRACT="capturebrief-deviation-candidate-proposal-v1"
MAX_MANIFEST_BYTES=2*1024*1024
MAX_DEVIATION_PDF_BYTES=25*1024*1024
ARTIFACT_CONTRACT="capturebrief-deviation-artifact-capture-v1"
_REVISION=re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_REPO="acqagent/rfo-deviations"
_ALLOWED_SOURCE_ID="acqagent-rfo-deviations"

def _dt(value: Any) -> bool:
    if not isinstance(value,str):
        return False
    try:
        d=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        return False
    return d.tzinfo is not None

def _catalog_row(catalog: dict[str,Any]) -> dict[str,Any]:
    rows=[x for x in catalog.get("sources") or [] if isinstance(x,dict) and x.get("source_id")==_ALLOWED_SOURCE_ID]
    if len(rows)!=1:
        raise ValueError("deviation source catalog must contain exactly one pinned source")
    row=rows[0]
    if row.get("namespace")!="CLASS_DEVIATION" or row.get("repository")!=_ALLOWED_REPO:
        raise ValueError("deviation source catalog entry is not approved")
    if not _REVISION.fullmatch(str(row.get("revision") or "")):
        raise ValueError("deviation source must use a full immutable Git revision")
    return row

def build_pinned_manifest_request(catalog: dict[str,Any]) -> dict[str,Any]:
    if catalog.get("schema_version")!="1.0":
        raise ValueError("rule source catalog schema is unsupported")
    row=_catalog_row(catalog)
    revision=row["revision"]
    raw=f"https://raw.githubusercontent.com/{_ALLOWED_REPO}/{revision}/manifest.csv"
    display=f"https://github.com/{_ALLOWED_REPO}/blob/{revision}/manifest.csv"
    return {
        "source_id":_ALLOWED_SOURCE_ID,
        "namespace":"CLASS_DEVIATION",
        "repository":_ALLOWED_REPO,
        "revision":revision,
        "path":"manifest.csv",
        "raw_url":raw,
        "display_url":display,
        "snapshot_label":row.get("snapshot_label"),
        "catalog_sha256":digest(canonical(catalog)),
        "mutable_ref_used":False,
        "caller_url_used":False,
    }

def _default_fetcher(url: str,max_bytes: int)->tuple[bytes,str]:
    request=urllib.request.Request(url,headers={"User-Agent":"CaptureBrief-DeviationSync/1.0","Accept":"text/csv,text/plain"},method="GET")
    with urllib.request.urlopen(request,timeout=20) as response:
        final=response.geturl()
        length=response.headers.get("Content-Length")
        if length is not None and int(length)>max_bytes:
            raise ValueError("deviation manifest exceeds byte limit")
        data=response.read(max_bytes+1)
    return data,final

def _validate_final_url(requested: str,final: str)->None:
    if final!=requested:
        raise ValueError("pinned deviation manifest fetch redirected or changed URL")
    parsed=urlsplit(final)
    if parsed.scheme!="https" or parsed.hostname!="raw.githubusercontent.com" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("pinned deviation manifest ended on an unapproved URL")

def fetch_pinned_deviation_manifest(
    catalog: dict[str,Any],*,observed_at: str,
    fetcher: Callable[[str,int],tuple[bytes,str]]|None=None,
)->tuple[dict[str,Any],dict[str,Any]]:
    if not _dt(observed_at):
        raise ValueError("observed_at must be timezone-aware ISO-8601")
    request=build_pinned_manifest_request(catalog)
    data,final=(fetcher or _default_fetcher)(request["raw_url"],MAX_MANIFEST_BYTES)
    if not isinstance(data,(bytes,bytearray)):
        raise ValueError("deviation manifest fetcher must return bytes")
    data=bytes(data)
    if len(data)>MAX_MANIFEST_BYTES:
        raise ValueError("deviation manifest exceeds byte limit")
    _validate_final_url(request["raw_url"],final)
    try:
        text=data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("deviation manifest is not UTF-8") from exc
    manifest=parse_deviation_manifest(text,source_repository=request["repository"],source_revision=request["revision"],observed_at=observed_at)
    receipt_payload={
        "contract":MANIFEST_CONTRACT,
        "source_id":request["source_id"],
        "repository":request["repository"],
        "revision":request["revision"],
        "path":request["path"],
        "requested_raw_url":request["raw_url"],
        "final_raw_url":final,
        "display_url":request["display_url"],
        "catalog_sha256":request["catalog_sha256"],
        "observed_at":observed_at,
        "byte_length":len(data),
        "manifest_sha256":digest(data),
        "parsed_manifest_sha256":manifest["manifest_sha256"],
        "row_count":manifest["row_count"],
        "mutable_ref_used":False,
        "caller_url_used":False,
        "applicability_authoritative":False,
    }
    if receipt_payload["manifest_sha256"]!=receipt_payload["parsed_manifest_sha256"]:
        raise ValueError("deviation manifest byte/parser digest mismatch")
    receipt={**receipt_payload,"fetch_receipt_id":"DEVMANIFEST:"+digest(canonical(receipt_payload))}
    return manifest,receipt

def sync_pinned_deviation_manifest(catalog_path: str|Path,*,observed_at: str,fetcher=None)->dict[str,Any]:
    catalog=load_source_catalog(catalog_path)
    manifest,receipt=fetch_pinned_deviation_manifest(catalog,observed_at=observed_at,fetcher=fetcher)
    return {"status":"PINNED_DEVIATION_MANIFEST_SYNCED","manifest":manifest,"fetch_receipt":receipt,"can_auto_apply":False}

def _proposal_body(proposal: dict[str,Any])->dict[str,Any]:
    return {k:v for k,v in proposal.items() if k!="proposal_sha256"}

def deviation_candidate_proposal_is_current(case: dict[str,Any])->bool:
    proposal=(case.get("packet") or {}).get("deviation_candidate_proposal")
    if not isinstance(proposal,dict) or proposal.get("contract")!=PROPOSAL_CONTRACT or proposal.get("status")!="PROPOSED":
        return False
    if proposal.get("can_auto_apply") is not False or proposal.get("applicability_authoritative") is not False:
        return False
    return digest(canonical(_proposal_body(proposal)))==proposal.get("proposal_sha256")

def build_deviation_candidate_proposal(
    manifest: dict[str,Any],receipt: dict[str,Any],*,
    agency: str,part_numbers: list[int],proposed_by: str,proposed_at: str,
)->dict[str,Any]:
    if receipt.get("contract")!=MANIFEST_CONTRACT or receipt.get("row_count")!=manifest.get("row_count") or receipt.get("parsed_manifest_sha256")!=manifest.get("manifest_sha256"):
        raise ValueError("deviation manifest receipt does not bind the parsed manifest")
    receipt_body={k:v for k,v in receipt.items() if k!="fetch_receipt_id"}
    if receipt.get("fetch_receipt_id")!="DEVMANIFEST:"+digest(canonical(receipt_body)):
        raise ValueError("deviation manifest receipt digest mismatch")
    if not isinstance(agency,str) or not agency.strip() or not isinstance(proposed_by,str) or not proposed_by.strip() or not _dt(proposed_at):
        raise ValueError("agency, proposed_by and timezone-aware proposed_at are required")
    if not isinstance(part_numbers,list) or not part_numbers or any(type(x) is not int or x<1 or x>53 for x in part_numbers):
        raise ValueError("part_numbers must contain FAR Part integers 1-53")
    parts=sorted(set(part_numbers))
    selected=[]
    by_url={}
    for part in parts:
        for row in filter_deviation_sources(manifest,agency=agency.strip(),part_number=part,is_dod=False):
            key=row["source_url"]
            item=by_url.get(key)
            if item is None:
                item={
                    "deviation_source_id":row["deviation_source_id"],
                    "agency":row["agency"],
                    "matched_parts":[],
                    "original_filename":row["original_filename"],
                    "source_url":row["source_url"],
                    "pdf_size_bytes":row["pdf_size_bytes"],
                    "url_hash":row["url_hash"],
                    "source_repository":row["source_repository"],
                    "source_revision":row["source_revision"],
                    "manifest_observed_at":row["observed_at"],
                    "artifact_state":"CANDIDATE_ONLY",
                    "effective_date":None,
                    "currentness":"UNRESOLVED",
                    "applicability":"UNRESOLVED",
                }
                by_url[key]=item
            item["matched_parts"].append(part)
    selected=sorted(by_url.values(),key=lambda x:(x["matched_parts"],x["original_filename"],x["source_url"]))
    payload={
        "contract":PROPOSAL_CONTRACT,
        "status":"PROPOSED",
        "agency":agency.strip(),
        "part_numbers":parts,
        "proposed_by":proposed_by.strip(),
        "proposed_at":proposed_at,
        "manifest_fetch_receipt_id":receipt["fetch_receipt_id"],
        "manifest_sha256":manifest["manifest_sha256"],
        "manifest_repository":manifest["source_repository"],
        "manifest_revision":manifest["source_revision"],
        "candidates":selected,
        "candidate_count":len(selected),
        "review_required":True,
        "applicability_authoritative":False,
        "can_auto_apply":False,
    }
    return {**payload,"proposal_sha256":digest(canonical(payload))}

def attach_deviation_candidate_proposal(
    case: dict[str,Any],manifest: dict[str,Any],receipt: dict[str,Any],*,
    agency: str,part_numbers: list[int],proposed_by: str,proposed_at: str,
)->tuple[dict[str,Any],dict[str,Any]]:
    proposal=build_deviation_candidate_proposal(manifest,receipt,agency=agency,part_numbers=part_numbers,proposed_by=proposed_by,proposed_at=proposed_at)
    result=copy.deepcopy(case)
    packet=result.setdefault("packet",{})
    old=packet.get("deviation_candidate_proposal")
    if old is not None:
        packet.setdefault("deviation_candidate_proposal_history",[]).append(old)
    packet["deviation_candidate_proposal"]=proposal
    return result,{"status":"DEVIATION_CANDIDATES_ATTACHED","proposal_sha256":proposal["proposal_sha256"],"candidate_count":proposal["candidate_count"],"can_auto_apply":False}

def deviation_candidate_work_item(case: dict[str,Any])->dict[str,Any]|None:
    if not deviation_candidate_proposal_is_current(case):
        return None
    proposal=case["packet"]["deviation_candidate_proposal"]
    captured=current_deviation_artifact_receipts(case)
    candidate_ids={str(x.get("deviation_source_id") or "") for x in proposal.get("candidates") or []}
    missing=sorted(x for x in candidate_ids if x and x not in captured)
    zero=proposal.get("candidate_count")==0
    return {
        "task_key":"deviations:review-candidates",
        "priority":"P0" if zero or not missing else "P1",
        "title":"Review agency class-deviation candidates",
        "actor":"HUMAN_REVIEW",
        "can_auto_execute":False,
        "status":"OPEN",
        "reason":(
            "The pinned corpus returned no candidate rows; bounded-corpus absence is not proof that no deviation exists."
            if zero else
            "Candidate official PDFs are captured; human review must establish currentness, effective date, supersession, and pursuit-specific applicability."
            if not missing else
            "Deviation candidates exist, but official PDF capture should complete before human authority/applicability review."
        ),
        "evidence_needed":"Retain/hash candidate official artifacts, establish currentness/effective date/supersession, then cite pursuit-specific applicability basis in Decision Evidence.",
        "metadata":{
            "agency":proposal["agency"],
            "part_numbers":proposal["part_numbers"],
            "candidate_count":proposal["candidate_count"],
            "captured_candidate_count":len(captured),
            "missing_artifact_ids":missing,
            "proposal_sha256":proposal["proposal_sha256"],
            "applicability_authoritative":False,
            "can_auto_apply":False,
        },
    }


def _candidate_map(case: dict[str,Any])->dict[str,dict[str,Any]]:
    if not deviation_candidate_proposal_is_current(case):
        raise ValueError("case does not contain a current deviation candidate proposal")
    proposal=case["packet"]["deviation_candidate_proposal"]
    rows={}
    for row in proposal.get("candidates") or []:
        ident=str(row.get("deviation_source_id") or "")
        if not ident or ident in rows:
            raise ValueError("deviation candidates require unique source IDs")
        rows[ident]=row
    return rows

def _safe_official_deviation_url(value: Any)->bool:
    if not isinstance(value,str):
        return False
    try:
        parsed=urlsplit(value)
    except ValueError:
        return False
    return (
        parsed.scheme=="https"
        and parsed.hostname in {"acquisition.gov","www.acquisition.gov"}
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    )

def build_deviation_artifact_request(case: dict[str,Any],deviation_source_id: str)->dict[str,Any]:
    candidates=_candidate_map(case)
    candidate=candidates.get(str(deviation_source_id))
    if candidate is None:
        raise ValueError("deviation_source_id is not in the current candidate proposal")
    source_url=str(candidate.get("source_url") or "")
    if not _safe_official_deviation_url(source_url):
        raise ValueError("candidate deviation URL is not an approved acquisition.gov HTTPS artifact")
    expected_url_hash=digest(source_url)[:16]
    if candidate.get("url_hash")!=expected_url_hash:
        raise ValueError("candidate URL hash does not match source URL")
    proposal=case["packet"]["deviation_candidate_proposal"]
    return {
        "proposal_sha256":proposal["proposal_sha256"],
        "deviation_source_id":candidate["deviation_source_id"],
        "agency":candidate["agency"],
        "matched_parts":copy.deepcopy(candidate.get("matched_parts") or []),
        "source_url":source_url,
        "url_hash":candidate["url_hash"],
        "declared_pdf_size_bytes":candidate.get("pdf_size_bytes"),
        "manifest_revision":proposal.get("manifest_revision"),
        "manifest_sha256":proposal.get("manifest_sha256"),
        "caller_url_used":False,
        "mutable_ref_used":False,
    }

def _default_pdf_fetcher(url: str,max_bytes: int)->tuple[bytes,str]:
    request=urllib.request.Request(
        url,
        headers={"User-Agent":"CaptureBrief-DeviationArtifact/1.0","Accept":"application/pdf"},
        method="GET",
    )
    with urllib.request.urlopen(request,timeout=30) as response:
        final=response.geturl()
        length=response.headers.get("Content-Length")
        if length is not None and int(length)>max_bytes:
            raise ValueError("deviation PDF exceeds byte limit")
        data=response.read(max_bytes+1)
    return data,final

def _validate_official_pdf_final_url(requested: str,final: str)->None:
    if final!=requested:
        raise ValueError("deviation PDF fetch redirected or changed URL")
    if not _safe_official_deviation_url(final):
        raise ValueError("deviation PDF fetch ended on an unapproved URL")

def capture_deviation_artifact(
    case: dict[str,Any],deviation_source_id: str,*,observed_at: str,
    fetcher: Callable[[str,int],tuple[bytes,str]]|None=None,
)->tuple[dict[str,Any],bytes]:
    if not _dt(observed_at):
        raise ValueError("observed_at must be timezone-aware ISO-8601")
    request=build_deviation_artifact_request(case,deviation_source_id)
    data,final=(fetcher or _default_pdf_fetcher)(request["source_url"],MAX_DEVIATION_PDF_BYTES)
    if not isinstance(data,(bytes,bytearray)):
        raise ValueError("deviation PDF fetcher must return bytes")
    data=bytes(data)
    if len(data)>MAX_DEVIATION_PDF_BYTES:
        raise ValueError("deviation PDF exceeds byte limit")
    _validate_official_pdf_final_url(request["source_url"],final)
    if not data.startswith(b"%PDF-"):
        raise ValueError("deviation artifact is not a PDF")
    declared=request.get("declared_pdf_size_bytes")
    size_matches=type(declared) is int and declared==len(data)
    payload={
        "contract":ARTIFACT_CONTRACT,
        "proposal_sha256":request["proposal_sha256"],
        "deviation_source_id":request["deviation_source_id"],
        "agency":request["agency"],
        "matched_parts":request["matched_parts"],
        "source_url":request["source_url"],
        "url_hash":request["url_hash"],
        "manifest_revision":request["manifest_revision"],
        "manifest_sha256":request["manifest_sha256"],
        "observed_at":observed_at,
        "final_url":final,
        "declared_pdf_size_bytes":declared,
        "observed_pdf_size_bytes":len(data),
        "declared_size_matches_observed":size_matches,
        "pdf_sha256":digest(data),
        "pdf_header_verified":True,
        "index_byte_identity_proven":False,
        "currentness":"UNRESOLVED",
        "effective_date":None,
        "supersession":"UNRESOLVED",
        "applicability":"UNRESOLVED",
        "caller_url_used":False,
        "redirect_used":False,
        "can_auto_apply":False,
    }
    return {**payload,"artifact_receipt_id":"DEVART:"+digest(canonical(payload))},data

def _valid_artifact_receipt(case: dict[str,Any],receipt: dict[str,Any],candidate: dict[str,Any])->bool:
    if not isinstance(receipt,dict) or receipt.get("contract")!=ARTIFACT_CONTRACT:
        return False
    body={k:v for k,v in receipt.items() if k!="artifact_receipt_id"}
    if receipt.get("artifact_receipt_id")!="DEVART:"+digest(canonical(body)):
        return False
    proposal=(case.get("packet") or {}).get("deviation_candidate_proposal") or {}
    if receipt.get("proposal_sha256")!=proposal.get("proposal_sha256"):
        return False
    if (
        receipt.get("deviation_source_id")!=candidate.get("deviation_source_id")
        or receipt.get("source_url")!=candidate.get("source_url")
        or receipt.get("url_hash")!=candidate.get("url_hash")
        or not re.fullmatch(r"[0-9a-f]{64}",str(receipt.get("pdf_sha256") or ""))
        or receipt.get("pdf_header_verified") is not True
        or receipt.get("index_byte_identity_proven") is not False
        or receipt.get("currentness")!="UNRESOLVED"
        or receipt.get("applicability")!="UNRESOLVED"
        or receipt.get("can_auto_apply") is not False
        or not _dt(receipt.get("observed_at"))
    ):
        return False
    return True

def attach_deviation_artifact_receipt(case: dict[str,Any],receipt: dict[str,Any])->dict[str,Any]:
    candidates=_candidate_map(case)
    candidate=candidates.get(str(receipt.get("deviation_source_id") or ""))
    if candidate is None or not _valid_artifact_receipt(case,receipt,candidate):
        raise ValueError("deviation artifact receipt is invalid for the current proposal")
    result=copy.deepcopy(case)
    packet=result.setdefault("packet",{})
    rows=packet.setdefault("deviation_artifact_receipts",[])
    if any(x.get("artifact_receipt_id")==receipt["artifact_receipt_id"] for x in rows if isinstance(x,dict)):
        return result
    rows.append(copy.deepcopy(receipt))
    rows.sort(key=lambda x:(str(x.get("deviation_source_id") or ""),str(x.get("observed_at") or ""),str(x.get("artifact_receipt_id") or "")))
    return result

def current_deviation_artifact_receipts(case: dict[str,Any])->dict[str,dict[str,Any]]:
    try:
        candidates=_candidate_map(case)
    except ValueError:
        return {}
    latest={}
    for receipt in (case.get("packet") or {}).get("deviation_artifact_receipts") or []:
        ident=str(receipt.get("deviation_source_id") or "") if isinstance(receipt,dict) else ""
        candidate=candidates.get(ident)
        if candidate is None or not _valid_artifact_receipt(case,receipt,candidate):
            continue
        current=latest.get(ident)
        if current is None or str(receipt.get("observed_at"))>str(current.get("observed_at")):
            latest[ident]=receipt
    return latest

def deviation_artifact_work_items(case: dict[str,Any])->list[dict[str,Any]]:
    if not deviation_candidate_proposal_is_current(case):
        return []
    proposal=case["packet"]["deviation_candidate_proposal"]
    captured=current_deviation_artifact_receipts(case)
    tasks=[]
    for candidate in proposal.get("candidates") or []:
        ident=str(candidate.get("deviation_source_id") or "")
        if ident in captured:
            continue
        tasks.append({
            "task_key":"deviation-bytes:"+ident,
            "priority":"P0",
            "title":"Capture official deviation PDF bytes",
            "actor":"AUTOMATED_APPROVED_SOURCE",
            "can_auto_execute":True,
            "status":"OPEN",
            "reason":"A pinned deviation candidate exists, but its underlying acquisition.gov PDF has not been independently captured and hashed for this proposal.",
            "evidence_needed":"Fetch the exact candidate acquisition.gov URL, verify PDF bytes, record SHA-256/length, and preserve any declared-size mismatch without inferring applicability.",
            "metadata":{
                "deviation_source_id":ident,
                "source_url":candidate.get("source_url"),
                "agency":candidate.get("agency"),
                "matched_parts":candidate.get("matched_parts") or [],
                "proposal_sha256":proposal.get("proposal_sha256"),
                "can_auto_apply":False,
            },
        })
    return tasks

def capture_and_attach_deviation_artifact(
    case: dict[str,Any],deviation_source_id: str,*,observed_at: str,fetcher=None,
)->tuple[dict[str,Any],dict[str,Any],bytes]:
    receipt,data=capture_deviation_artifact(case,deviation_source_id,observed_at=observed_at,fetcher=fetcher)
    updated=attach_deviation_artifact_receipt(case,receipt)
    return updated,receipt,data
