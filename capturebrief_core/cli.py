from __future__ import annotations
import argparse,json
from pathlib import Path
from . import audit_case,compare_cases,render_markdown

def load(p): return json.loads(Path(p).read_text())
def main():
    p=argparse.ArgumentParser(prog="capturebrief-core"); sub=p.add_subparsers(dest="cmd",required=True)
    x=sub.add_parser("validate"); x.add_argument("case")
    x=sub.add_parser("render"); x.add_argument("case"); x.add_argument("--output","-o")
    x=sub.add_parser("diff"); x.add_argument("before"); x.add_argument("after")
    a=p.parse_args()
    if a.cmd=="validate":
        r=audit_case(load(a.case)); print(json.dumps(r.to_dict(),indent=2)); return 0 if r.release_state=="READY_FOR_HUMAN_RELEASE" else 2
    if a.cmd=="render":
        c=load(a.case); r=audit_case(c); out=render_markdown(c,r)
        if a.output: Path(a.output).write_text(out)
        else: print(out)
        return 0 if r.release_state=="READY_FOR_HUMAN_RELEASE" else 2
    print(json.dumps(compare_cases(load(a.before),load(a.after)),indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
