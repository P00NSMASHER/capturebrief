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
    return {
        "task_key":"deviations:review-candidates",
        "priority":"P0",
        "title":"Review agency class-deviation candidates",
        "actor":"HUMAN_REVIEW",
        "can_auto_execute":False,
        "status":"OPEN",
        "reason":"The pinned deviation corpus contains agency/FAR-Part artifacts that may affect this pursuit. Corpus membership does not establish currentness, effective date, incorporation, or applicability.",
        "evidence_needed":"Open the underlying public deviation artifact, retain/hash the exact artifact, establish currentness/effective date/supersession, then cite pursuit-specific applicability basis in Decision Evidence.",
        "metadata":{
            "agency":proposal["agency"],
            "part_numbers":proposal["part_numbers"],
            "candidate_count":proposal["candidate_count"],
            "proposal_sha256":proposal["proposal_sha256"],
            "applicability_authoritative":False,
            "can_auto_apply":False,
        },
    }
