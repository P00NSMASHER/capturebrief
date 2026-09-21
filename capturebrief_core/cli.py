from __future__ import annotations
import argparse,json,os
from pathlib import Path
from . import audit_case,compare_cases,render_markdown
from .ledger import append_record, verify_ledger
from .manifest import normalize_manifest_payload
from .current_api import download_resource_from_api_observation, fetch_latest_active, make_current_action_receipt
from .case_current import apply_current_api_observation
from .case_references import apply_reference_resolution, apply_reference_review_result
from .current_search import build_current_search_plan, fetch_and_apply_current
from .data_services import ACTIVE_DOWNLOAD, ARCHIVE_DOWNLOAD, collect_history_from_files
from .packet import diff_manifest_receipts
from .references import confirm_reference_scan, propose_reference_scan
from .archive_catalog import catalog_snapshot
from .history_index import (
    fetch_and_ingest_slot, index_status, ingest_extract_file,
    issue_history_receipt_from_index, sync_plan,
)
from .history_sync import sync_missing_slots
from .opportunity_ref import parse_opportunity_reference
from .resolver import attach_history_resolution, resolve_reference_from_index
from .intake import build_case_from_intake
from .workqueue import build_work_queue


def load(p): return json.loads(Path(p).read_text())
def dump(value,output=None):
    text=json.dumps(value,indent=2,ensure_ascii=False)
    if output: Path(output).write_text(text+"\n")
    else: print(text)

def main():
    p=argparse.ArgumentParser(prog="capturebrief-core"); sub=p.add_subparsers(dest="cmd",required=True)
    x=sub.add_parser("validate"); x.add_argument("case")
    x=sub.add_parser("render"); x.add_argument("case"); x.add_argument("--output","-o")
    x=sub.add_parser("diff"); x.add_argument("before"); x.add_argument("after")
    x=sub.add_parser("normalize-manifest"); x.add_argument("action_id"); x.add_argument("raw_json"); x.add_argument("--observed-at",required=True); x.add_argument("--output","-o")
    x=sub.add_parser("manifest-diff"); x.add_argument("before"); x.add_argument("after")
    x=sub.add_parser("history-from-extracts"); x.add_argument("solicitation_number"); x.add_argument("active_csv"); x.add_argument("--archive",action="append",default=[]); x.add_argument("--seed-notice-id"); x.add_argument("--scope-start-fy",type=int); x.add_argument("--scope-end-fy",type=int); x.add_argument("--confirm-scope",action="store_true"); x.add_argument("--observed-at"); x.add_argument("--output","-o"); x.add_argument("--ledger")
    x=sub.add_parser("current-from-api"); x.add_argument("solicitation_number"); x.add_argument("history_receipt"); x.add_argument("posted_from"); x.add_argument("posted_to"); x.add_argument("--organization-code"); x.add_argument("--api-key-env",default="SAM_API_KEY"); x.add_argument("--output","-o"); x.add_argument("--observation-output")
    x=sub.add_parser("capture-api-resource"); x.add_argument("api_observation"); x.add_argument("resource_url"); x.add_argument("--output","-o",required=True); x.add_argument("--receipt-output"); x.add_argument("--ledger"); x.add_argument("--max-bytes",type=int,default=50*1024*1024)
    x=sub.add_parser("archive-catalog"); x.add_argument("--output","-o")
    x=sub.add_parser("history-index-status"); x.add_argument("index_db"); x.add_argument("--fiscal-year",type=int); x.add_argument("--output","-o")
    x=sub.add_parser("history-index-plan"); x.add_argument("index_db"); x.add_argument("--fiscal-year",type=int); x.add_argument("--output","-o")
    x=sub.add_parser("history-index-ingest"); x.add_argument("index_db"); x.add_argument("csv_path"); x.add_argument("--kind",choices=["active","archive"],required=True); x.add_argument("--fiscal-year",type=int); x.add_argument("--snapshot-dir"); x.add_argument("--observed-at"); x.add_argument("--output","-o")
    x=sub.add_parser("history-index-fetch"); x.add_argument("index_db"); x.add_argument("slot"); x.add_argument("destination"); x.add_argument("--snapshot-dir"); x.add_argument("--observed-at"); x.add_argument("--max-bytes",type=int,default=2_000_000_000); x.add_argument("--output","-o")
    x=sub.add_parser("history-from-index"); x.add_argument("index_db"); x.add_argument("solicitation_number"); x.add_argument("--seed-notice-id",required=True); x.add_argument("--fiscal-year",type=int); x.add_argument("--observed-at"); x.add_argument("--output","-o"); x.add_argument("--ledger")
    x=sub.add_parser("parse-opportunity-ref"); x.add_argument("reference"); x.add_argument("--output","-o")
    x=sub.add_parser("history-index-resolve"); x.add_argument("index_db"); x.add_argument("reference"); x.add_argument("--fiscal-year",type=int); x.add_argument("--observed-at"); x.add_argument("--output","-o")
    x=sub.add_parser("case-resolve-history"); x.add_argument("index_db"); x.add_argument("case"); x.add_argument("--fiscal-year",type=int); x.add_argument("--observed-at"); x.add_argument("--output","-o",required=True); x.add_argument("--resolution-output")
    x=sub.add_parser("history-index-sync"); x.add_argument("index_db"); x.add_argument("download_dir"); x.add_argument("--snapshot-dir"); x.add_argument("--fiscal-year",type=int); x.add_argument("--observed-at"); x.add_argument("--max-slots",type=int,default=1); x.add_argument("--all",action="store_true"); x.add_argument("--max-bytes",type=int,default=2_000_000_000); x.add_argument("--output","-o")
    x=sub.add_parser("references-propose"); x.add_argument("--source",action="append",required=True,metavar="SOURCE_ID=TEXTFILE"); x.add_argument("--observed-at"); x.add_argument("--output","-o")
    x=sub.add_parser("references-confirm"); x.add_argument("proposal"); x.add_argument("review_json"); x.add_argument("--output","-o"); x.add_argument("--scan-output"); x.add_argument("--references-output")
    x=sub.add_parser("case-apply-reference-review"); x.add_argument("case"); x.add_argument("review_result"); x.add_argument("--output","-o",required=True); x.add_argument("--transition-output")
    x=sub.add_parser("case-resolve-reference"); x.add_argument("case"); x.add_argument("reference_id"); x.add_argument("decision_json"); x.add_argument("--output","-o",required=True); x.add_argument("--transition-output")
    x=sub.add_parser("case-from-intake"); x.add_argument("intake_json"); x.add_argument("--submitted-at"); x.add_argument("--output","-o")
    x=sub.add_parser("case-apply-current"); x.add_argument("case"); x.add_argument("api_observation"); x.add_argument("--output","-o",required=True); x.add_argument("--transition-output")
    x=sub.add_parser("current-search-plan"); x.add_argument("case"); x.add_argument("--output","-o")
    x=sub.add_parser("case-fetch-current"); x.add_argument("case"); x.add_argument("--api-key-env",default="SAM_API_KEY"); x.add_argument("--organization-code"); x.add_argument("--output","-o",required=True); x.add_argument("--result-output")
    x=sub.add_parser("work-queue"); x.add_argument("case"); x.add_argument("--api-observation"); x.add_argument("--history-index-plan"); x.add_argument("--output","-o")
    x=sub.add_parser("ledger-append"); x.add_argument("ledger"); x.add_argument("record_type"); x.add_argument("payload_json")
    x=sub.add_parser("ledger-verify"); x.add_argument("ledger")
    a=p.parse_args()
    if a.cmd=="validate":
        r=audit_case(load(a.case)); dump(r.to_dict()); return 0 if r.release_state=="READY_FOR_HUMAN_RELEASE" else 2
    if a.cmd=="render":
        c=load(a.case); r=audit_case(c); out=render_markdown(c,r)
        if a.output: Path(a.output).write_text(out)
        else: print(out)
        return 0 if r.release_state=="READY_FOR_HUMAN_RELEASE" else 2
    if a.cmd=="diff": dump(compare_cases(load(a.before),load(a.after))); return 0
    if a.cmd=="normalize-manifest":
        receipt=normalize_manifest_payload(a.action_id,load(a.raw_json),observed_at=a.observed_at,observation_mode="HUMAN_SUPERVISED"); dump(receipt,a.output); return 0
    if a.cmd=="manifest-diff": dump(diff_manifest_receipts(load(a.before),load(a.after))); return 0
    if a.cmd=="history-from-extracts":
        archives=[]
        for value in a.archive:
            fy,path=value.split(":",1); archives.append((int(fy),path))
        receipt=collect_history_from_files(solicitation_number=a.solicitation_number,active_csv=a.active_csv,archive_csvs=archives,seed_notice_id=a.seed_notice_id,scope_start_fy=a.scope_start_fy,scope_end_fy=a.scope_end_fy,scope_confirmed=a.confirm_scope,observed_at=a.observed_at)
        dump(receipt,a.output)
        if a.ledger: append_record(a.ledger,record_type="SAM_DATA_SERVICES_HISTORY",payload=receipt)
        return 0 if receipt["status"]=="COMPLETE" else 2
    if a.cmd=="current-from-api":
        api_key=os.environ.get(a.api_key_env,"")
        if not api_key: raise SystemExit(f"missing API key environment variable: {a.api_key_env}")
        history=load(a.history_receipt)
        observation=fetch_latest_active(solicitation_number=a.solicitation_number,posted_from=a.posted_from,posted_to=a.posted_to,api_key=api_key,organization_code=a.organization_code)
        receipt=make_current_action_receipt(observation,history_action_ids=history.get("action_ids") or [])
        dump(receipt,a.output)
        if a.observation_output: dump(observation,a.observation_output)
        return 0
    if a.cmd=="capture-api-resource":
        observation=load(a.api_observation)
        receipt,content=download_resource_from_api_observation(observation,a.resource_url,max_bytes=a.max_bytes)
        Path(a.output).write_bytes(content); receipt["stored_path"]=str(Path(a.output)); dump(receipt,a.receipt_output)
        if a.ledger: append_record(a.ledger,record_type="SAM_APPROVED_API_BYTE_CAPTURE",payload=receipt)
        return 0
    if a.cmd=="archive-catalog":
        dump(catalog_snapshot(),a.output); return 0
    if a.cmd=="history-index-status":
        result=index_status(a.index_db,fiscal_year=a.fiscal_year); dump(result,a.output); return 0 if result["complete"] else 2
    if a.cmd=="history-index-plan":
        result=sync_plan(a.index_db,fiscal_year=a.fiscal_year); dump(result,a.output); return 0 if result["complete"] else 2
    if a.cmd=="history-index-ingest":
        kind=a.kind.upper()
        if kind=="ARCHIVE" and a.fiscal_year is None: raise SystemExit("--fiscal-year is required for archive ingest")
        if kind=="ACTIVE" and a.fiscal_year is not None: raise SystemExit("--fiscal-year must be omitted for active ingest")
        source_url=ACTIVE_DOWNLOAD if kind=="ACTIVE" else ARCHIVE_DOWNLOAD.format(fy=a.fiscal_year)
        result=ingest_extract_file(a.index_db,a.csv_path,source_url=source_url,source_kind=kind,fiscal_year=a.fiscal_year,observed_at=a.observed_at,snapshot_dir=a.snapshot_dir)
        dump(result,a.output); return 0
    if a.cmd=="history-index-fetch":
        result=fetch_and_ingest_slot(a.index_db,slot=a.slot,destination=a.destination,snapshot_dir=a.snapshot_dir,observed_at=a.observed_at,max_bytes=a.max_bytes)
        dump(result,a.output); return 0
    if a.cmd=="history-from-index":
        receipt=issue_history_receipt_from_index(a.index_db,solicitation_number=a.solicitation_number,seed_notice_id=a.seed_notice_id,observed_at=a.observed_at,fiscal_year=a.fiscal_year)
        dump(receipt,a.output)
        if a.ledger: append_record(a.ledger,record_type="SAM_DATA_SERVICES_HISTORY_INDEX",payload=receipt)
        return 0 if receipt["status"]=="COMPLETE" else 2
    if a.cmd=="parse-opportunity-ref":
        dump(parse_opportunity_reference(a.reference),a.output); return 0
    if a.cmd=="history-index-resolve":
        result=resolve_reference_from_index(a.index_db,a.reference,fiscal_year=a.fiscal_year,observed_at=a.observed_at)
        dump(result,a.output)
        return 0 if result["status"] in {"RESOLVED","RESOLVED_PARTIAL_COVERAGE"} else 2
    if a.cmd=="case-resolve-history":
        case,resolution=attach_history_resolution(load(a.case),a.index_db,fiscal_year=a.fiscal_year,observed_at=a.observed_at)
        dump(case,a.output)
        if a.resolution_output: dump(resolution,a.resolution_output)
        return 0 if resolution["status"] in {"RESOLVED","RESOLVED_PARTIAL_COVERAGE"} else 2
    if a.cmd=="history-index-sync":
        limit=None if a.all else a.max_slots
        result=sync_missing_slots(a.index_db,a.download_dir,snapshot_dir=a.snapshot_dir,fiscal_year=a.fiscal_year,max_slots=limit,observed_at=a.observed_at,max_bytes=a.max_bytes)
        dump(result,a.output); return 0
    if a.cmd=="references-propose":
        sources=[]
        for token in a.source:
            if "=" not in token: raise SystemExit(f"invalid --source value, expected SOURCE_ID=TEXTFILE: {token}")
            source_id,path=token.split("=",1)
            text=Path(path).read_text(encoding="utf-8",errors="replace")
            sources.append({"source_id":source_id,"text":text})
        proposal=propose_reference_scan(sources,observed_at=a.observed_at)
        dump(proposal,a.output); return 0
    if a.cmd=="references-confirm":
        scan,references=confirm_reference_scan(load(a.proposal),load(a.review_json))
        combined={"reference_scan":scan,"references":references}
        dump(combined,a.output)
        if a.scan_output: dump(scan,a.scan_output)
        if a.references_output: dump(references,a.references_output)
        return 0
    if a.cmd=="case-apply-reference-review":
        updated,transition=apply_reference_review_result(load(a.case),load(a.review_result))
        dump(updated,a.output)
        if a.transition_output: dump(transition,a.transition_output)
        return 0
    if a.cmd=="case-resolve-reference":
        updated,transition=apply_reference_resolution(load(a.case),a.reference_id,load(a.decision_json))
        dump(updated,a.output)
        if a.transition_output: dump(transition,a.transition_output)
        return 0
    if a.cmd=="case-from-intake":
        dump(build_case_from_intake(load(a.intake_json),submitted_at=a.submitted_at),a.output); return 0
    if a.cmd=="case-apply-current":
        updated,transition=apply_current_api_observation(load(a.case),load(a.api_observation))
        dump(updated,a.output)
        if a.transition_output: dump(transition,a.transition_output)
        return 0
    if a.cmd=="current-search-plan":
        dump(build_current_search_plan(load(a.case)),a.output); return 0
    if a.cmd=="case-fetch-current":
        api_key=os.environ.get(a.api_key_env,"")
        if not api_key: raise SystemExit(f"missing API key environment variable: {a.api_key_env}")
        updated,result=fetch_and_apply_current(load(a.case),api_key=api_key,organization_code=a.organization_code)
        dump(updated,a.output)
        if a.result_output: dump(result,a.result_output)
        return 0 if result["fetch"]["status"]=="CURRENT_OBSERVATION_FOUND" else 2
    if a.cmd=="work-queue":
        observation=load(a.api_observation) if a.api_observation else None
        history_plan=load(a.history_index_plan) if a.history_index_plan else None
        dump(build_work_queue(load(a.case),api_observation=observation,history_index_plan=history_plan),a.output); return 0
    if a.cmd=="ledger-append": dump(append_record(a.ledger,record_type=a.record_type,payload=load(a.payload_json))); return 0
    if a.cmd=="ledger-verify":
        result=verify_ledger(a.ledger); dump(result); return 0 if result["valid"] else 2
    return 2
if __name__=="__main__": raise SystemExit(main())
