from __future__ import annotations
import argparse
import json
from pathlib import Path
from .decision_trace import canonical, compare_decision_traces, digest, evaluate_decision_trace
from .trace_render import render_trace_html, render_trace_markdown


def read_case(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def freeze_case(case: dict, directory: str) -> Path:
    raw = json.dumps(case, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    target = Path(directory) / (digest(canonical(case)) + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_text(encoding="utf-8") != raw:
        raise ValueError("existing content-addressed decision file is corrupted")
    target.write_text(raw, encoding="utf-8")
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="capturebrief-decision-evidence")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check"); check.add_argument("case"); check.add_argument("--allow-synthetic", action="store_true")
    report = sub.add_parser("report"); report.add_argument("case"); report.add_argument("--format", choices=("json","markdown","html"), default="markdown"); report.add_argument("-o","--output"); report.add_argument("--allow-synthetic", action="store_true")
    freeze = sub.add_parser("freeze"); freeze.add_argument("case"); freeze.add_argument("--directory", required=True)
    compare = sub.add_parser("compare"); compare.add_argument("before"); compare.add_argument("after")
    args = parser.parse_args(argv)
    if args.cmd == "compare": payload = compare_decision_traces(read_case(args.before), read_case(args.after))
    elif args.cmd == "freeze":
        print(freeze_case(read_case(args.case), args.directory)); return 0
    else:
        case = read_case(args.case); state = evaluate_decision_trace(case, allow_synthetic=args.allow_synthetic)
        if args.cmd == "check": print(json.dumps(state, indent=2)); return 1 if state["trace_state"] == "TRACE_INCOMPLETE" else 0
        payload = state if args.format == "json" else render_trace_html(case) if args.format == "html" else render_trace_markdown(case)
    text = json.dumps(payload, indent=2, ensure_ascii=False) if isinstance(payload, dict) else payload
    if getattr(args, "output", None): Path(args.output).write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")
    else: print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
