from __future__ import annotations

import argparse
import json
from pathlib import Path

from .rule_candidates import attach_rule_candidate_proposal, attach_rule_candidate_review
from .rule_registry import (
    add_rule_version,
    diff_rule_versions,
    list_rule_versions,
    load_source_catalog,
    parse_deviation_manifest,
    parse_gsa_dita,
)


def _write(value, path=None):
    text = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    if path:
        Path(path).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def main(argv=None):
    p = argparse.ArgumentParser(prog="capturebrief-rule-registry")
    s = p.add_subparsers(dest="cmd", required=True)

    d = s.add_parser("parse-dita")
    d.add_argument("dita")
    d.add_argument("--namespace", required=True, choices=("FAR", "DFARS"))
    d.add_argument("--agency", required=True)
    d.add_argument("--edition", help="Fallback/source snapshot label when DITA text has no embedded rule edition")
    d.add_argument("--repository", required=True)
    d.add_argument("--revision", required=True)
    d.add_argument("--source-path", required=True)
    d.add_argument("--source-url", required=True)
    d.add_argument("--observed-at", required=True)
    d.add_argument("--effective-from")
    d.add_argument("--effective-until")
    d.add_argument("-o", "--output")

    a = s.add_parser("add")
    a.add_argument("registry")
    a.add_argument("record")

    l = s.add_parser("list")
    l.add_argument("registry")
    l.add_argument("--rule-key")
    l.add_argument("--namespace")
    l.add_argument("--citation")
    l.add_argument("--agency")
    l.add_argument("-o", "--output")

    df = s.add_parser("diff")
    df.add_argument("before")
    df.add_argument("after")
    df.add_argument("-o", "--output")

    dm = s.add_parser("parse-deviation-manifest")
    dm.add_argument("csv")
    dm.add_argument("--repository", required=True)
    dm.add_argument("--revision", required=True)
    dm.add_argument("--observed-at", required=True)
    dm.add_argument("-o", "--output")

    cat = s.add_parser("catalog")
    cat.add_argument("path", nargs="?", default="RULE-SOURCE-CATALOG.json")
    cat.add_argument("-o", "--output")

    pc = s.add_parser("case-propose-citations")
    pc.add_argument("registry")
    pc.add_argument("case")
    pc.add_argument("--source", action="append", required=True, help="SOURCE_ID=TEXT_FILE")
    pc.add_argument("--captured-by", required=True)
    pc.add_argument("--observed-at")
    pc.add_argument("-o", "--output")
    pc.add_argument("--result-output")

    rv = s.add_parser("case-review-citations")
    rv.add_argument("case")
    rv.add_argument("review")
    rv.add_argument("-o", "--output")
    rv.add_argument("--result-output")

    args = p.parse_args(argv)

    if args.cmd == "parse-dita":
        value = parse_gsa_dita(
            Path(args.dita).read_text(encoding="utf-8"),
            namespace=args.namespace,
            agency=args.agency,
            edition=args.edition,
            source_repository=args.repository,
            source_revision=args.revision,
            source_path=args.source_path,
            source_url=args.source_url,
            observed_at=args.observed_at,
            effective_from=args.effective_from,
            effective_until=args.effective_until,
        )
        _write(value, args.output)
    elif args.cmd == "add":
        record = json.loads(Path(args.record).read_text(encoding="utf-8"))
        print(add_rule_version(args.registry, record))
    elif args.cmd == "list":
        _write(
            list_rule_versions(
                args.registry,
                rule_key=args.rule_key,
                namespace=args.namespace,
                citation=args.citation,
                agency=args.agency,
            ),
            args.output,
        )
    elif args.cmd == "diff":
        _write(
            diff_rule_versions(
                json.loads(Path(args.before).read_text(encoding="utf-8")),
                json.loads(Path(args.after).read_text(encoding="utf-8")),
            ),
            args.output,
        )
    elif args.cmd == "parse-deviation-manifest":
        _write(
            parse_deviation_manifest(
                Path(args.csv).read_text(encoding="utf-8-sig"),
                source_repository=args.repository,
                source_revision=args.revision,
                observed_at=args.observed_at,
            ),
            args.output,
        )
    elif args.cmd == "catalog":
        _write(load_source_catalog(args.path), args.output)
    elif args.cmd == "case-propose-citations":
        case = json.loads(Path(args.case).read_text(encoding="utf-8"))
        source_texts = []
        for spec in args.source:
            if "=" not in spec:
                raise ValueError("--source must be SOURCE_ID=TEXT_FILE")
            source_id, path = spec.split("=", 1)
            source_texts.append({
                "source_id": source_id,
                "text": Path(path).read_text(encoding="utf-8"),
            })
        updated, result = attach_rule_candidate_proposal(
            case,
            args.registry,
            source_texts,
            captured_by=args.captured_by,
            observed_at=args.observed_at,
        )
        _write(updated, args.output)
        if args.result_output:
            _write(result, args.result_output)
    elif args.cmd == "case-review-citations":
        case = json.loads(Path(args.case).read_text(encoding="utf-8"))
        review = json.loads(Path(args.review).read_text(encoding="utf-8"))
        updated, result = attach_rule_candidate_review(case, review)
        _write(updated, args.output)
        if args.result_output:
            _write(result, args.result_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
