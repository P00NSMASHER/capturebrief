from __future__ import annotations
import argparse,json,os
from pathlib import Path
from . import audit_case,compare_cases,render_markdown
from .ledger import append_record, verify_ledger
from .manifest import normalize_manifest_payload
from .current_api import download_resource_from_api_observation, fetch_latest_active, make_current_action_receipt
from .data_services import collect_history_from_files
from .packet import diff_manifest_receipts
from .intake import build_case_from_intake
from .workqueue import build_work_queue
from .evidence_apply import apply_approved_evidence


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
    x=sub.add_parser("case-from-intake"); x.add_argument("intake_json"); x.add_argument("--submitted-at"); x.add_argument("--output","-o")
    x=sub.add_parser("work-queue"); x.add_argument("case"); x.add_argument("--api-observation"); x.add_argument("--output","-o")
    x=sub.add_parser("apply-approved-evidence"); x.add_argument("case"); x.add_argument("--history-receipt"); x.add_argument("--current-receipt"); x.add_argument("--api-observation"); x.add_argument("--byte-receipt",action="append",default=[]); x.add_argument("--output","-o")
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
    if a.cmd=="case-from-intake":
        dump(build_case_from_intake(load(a.intake_json),submitted_at=a.submitted_at),a.output); return 0
    if a.cmd=="work-queue":
        observation=load(a.api_observation) if a.api_observation else None
        dump(build_work_queue(load(a.case),api_observation=observation),a.output); return 0
    if a.cmd=="apply-approved-evidence":
        history=load(a.history_receipt) if a.history_receipt else None
        current=load(a.current_receipt) if a.current_receipt else None
        observation=load(a.api_observation) if a.api_observation else None
        bytes_receipts=[load(path) for path in a.byte_receipt]
        updated=apply_approved_evidence(load(a.case),history_receipt=history,current_receipt=current,api_observation=observation,byte_receipts=bytes_receipts)
        dump(updated,a.output); return 0
    if a.cmd=="ledger-append": dump(append_record(a.ledger,record_type=a.record_type,payload=load(a.payload_json))); return 0
    if a.cmd=="ledger-verify":
        result=verify_ledger(a.ledger); dump(result); return 0 if result["valid"] else 2
    return 2
if __name__=="__main__": raise SystemExit(main())
