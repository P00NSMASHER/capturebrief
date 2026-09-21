from __future__ import annotations
import argparse
import json
from pathlib import Path
from .atomic_io import atomic_write_text, ensure_exact_bytes
from .decision_trace import canonical, compare_decision_traces, digest, evaluate_decision_trace
from .trace_render import render_trace_html, render_trace_markdown
from .delivery_bundle import build_delivery_bundle
from .watch_baseline import build_watch_baseline, compare_watch_baseline


def read_case(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def freeze_case(case: dict, directory: str) -> Path:
    raw = (json.dumps(case, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    target = Path(directory) / (digest(canonical(case)) + ".json")
    try:
        ensure_exact_bytes(target, raw)
    except ValueError as exc:
        raise ValueError("existing content-addressed decision file is corrupted") from exc
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="capturebrief-decision-evidence")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check"); check.add_argument("case"); check.add_argument("--allow-synthetic", action="store_true")
    report = sub.add_parser("report"); report.add_argument("case"); report.add_argument("--format", choices=("json","markdown","html"), default="markdown"); report.add_argument("-o","--output"); report.add_argument("--allow-synthetic", action="store_true")
    freeze = sub.add_parser("freeze"); freeze.add_argument("case"); freeze.add_argument("--directory", required=True)
    compare = sub.add_parser("compare"); compare.add_argument("before"); compare.add_argument("after")
    bundle = sub.add_parser("bundle"); bundle.add_argument("case"); bundle.add_argument("-o","--output",required=True); bundle.add_argument("--overwrite",action="store_true")
    watch = sub.add_parser("watch-baseline"); watch.add_argument("case"); watch.add_argument("-o","--output",required=True)
    watch_check = sub.add_parser("watch-check"); watch_check.add_argument("baseline"); watch_check.add_argument("case"); watch_check.add_argument("-o","--output")
    args = parser.parse_args(argv)
    if args.cmd == "compare": payload = compare_decision_traces(read_case(args.before), read_case(args.after))
    elif args.cmd == "freeze":
        print(freeze_case(read_case(args.case), args.directory)); return 0
    elif args.cmd == "bundle":
        payload=build_delivery_bundle(read_case(args.case),args.output,overwrite=args.overwrite)
    elif args.cmd == "watch-baseline":
        payload=build_watch_baseline(read_case(args.case))
    elif args.cmd == "watch-check":
        payload=compare_watch_baseline(read_case(args.baseline),read_case(args.case))
    else:
        case = read_case(args.case); state = evaluate_decision_trace(case, allow_synthetic=args.allow_synthetic)
        if args.cmd == "check": print(json.dumps(state, indent=2)); return 1 if state["trace_state"] == "TRACE_INCOMPLETE" else 0
        payload = state if args.format == "json" else render_trace_html(case) if args.format == "html" else render_trace_markdown(case)
    text = json.dumps(payload, indent=2, ensure_ascii=False) if isinstance(payload, dict) else payload
    if getattr(args, "output", None): atomic_write_text(args.output,text + ("" if text.endswith("\n") else "\n"))
    else: print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
