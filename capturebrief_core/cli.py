from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from . import audit_case,compare_cases,render_markdown
from .ledger import append_record, verify_ledger
from .manifest import download_public_resource, fetch_manifest, normalize_manifest_payload
from .packet import diff_manifest_receipts


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
    x=sub.add_parser("observe-manifest"); x.add_argument("action_id"); x.add_argument("--output","-o"); x.add_argument("--ledger")
    x=sub.add_parser("manifest-diff"); x.add_argument("before"); x.add_argument("after")
    x=sub.add_parser("capture-resource"); x.add_argument("manifest_receipt"); x.add_argument("resource_id"); x.add_argument("--output","-o",required=True); x.add_argument("--receipt-output"); x.add_argument("--ledger"); x.add_argument("--max-bytes",type=int,default=50*1024*1024)
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
        receipt=normalize_manifest_payload(a.action_id,load(a.raw_json),observed_at=a.observed_at); dump(receipt,a.output); return 0
    if a.cmd=="observe-manifest":
        receipt=fetch_manifest(a.action_id); dump(receipt,a.output)
        if a.ledger: append_record(a.ledger,record_type="SAM_MANIFEST_OBSERVATION",payload=receipt)
        return 0
    if a.cmd=="manifest-diff": dump(diff_manifest_receipts(load(a.before),load(a.after))); return 0
    if a.cmd=="capture-resource":
        manifest=load(a.manifest_receipt); resource=next((r for r in manifest.get("items",[]) if str(r.get("resource_id"))==a.resource_id),None)
        if resource is None: raise SystemExit(f"resource_id not found in manifest receipt: {a.resource_id}")
        receipt,content=download_public_resource(resource,max_bytes=a.max_bytes); Path(a.output).write_bytes(content)
        receipt["stored_path"]=str(Path(a.output)); dump(receipt,a.receipt_output)
        if a.ledger: append_record(a.ledger,record_type="SAM_PUBLIC_BYTE_CAPTURE",payload=receipt)
        return 0
    if a.cmd=="ledger-append": dump(append_record(a.ledger,record_type=a.record_type,payload=load(a.payload_json))); return 0
    if a.cmd=="ledger-verify":
        result=verify_ledger(a.ledger); dump(result); return 0 if result["valid"] else 2
    return 2
if __name__=="__main__": raise SystemExit(main())
