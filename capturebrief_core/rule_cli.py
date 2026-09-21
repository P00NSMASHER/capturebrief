from __future__ import annotations

import argparse
import json
from pathlib import Path

from .rule_candidates import attach_rule_candidate_proposal, attach_rule_candidate_review, sync_missing_rule_candidates_for_case
from .rule_sync import sync_pinned_gsa_rule
from .rule_evidence import prepare_rule_evidence
from .rule_applicability import review_rule_applicability
from .deviation_sync import attach_deviation_candidate_proposal, capture_and_attach_deviation_artifact, sync_pinned_deviation_manifest
from .deviation_review import prepare_deviation_text, review_deviation_authority
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

    sdv = s.add_parser("sync-deviation-manifest")
    sdv.add_argument("--catalog", default="RULE-SOURCE-CATALOG.json")
    sdv.add_argument("--observed-at", required=True)
    sdv.add_argument("--manifest-output")
    sdv.add_argument("--receipt-output")

    pdv = s.add_parser("case-propose-deviations")
    pdv.add_argument("case")
    pdv.add_argument("manifest")
    pdv.add_argument("receipt")
    pdv.add_argument("--agency", required=True)
    pdv.add_argument("--part", action="append", type=int, required=True)
    pdv.add_argument("--proposed-by", required=True)
    pdv.add_argument("--proposed-at", required=True)
    pdv.add_argument("-o", "--output")
    pdv.add_argument("--result-output")

    cad = s.add_parser("case-capture-deviation-artifact")
    cad.add_argument("case")
    cad.add_argument("deviation_source_id")
    cad.add_argument("--observed-at", required=True)
    cad.add_argument("--artifact-output", required=True)
    cad.add_argument("--receipt-output")
    cad.add_argument("-o", "--output", required=True)

    pdt = s.add_parser("case-prepare-deviation-text")
    pdt.add_argument("case")
    pdt.add_argument("deviation_source_id")
    pdt.add_argument("text_file")
    pdt.add_argument("--prepared-by", required=True)
    pdt.add_argument("--prepared-at", required=True)
    pdt.add_argument("--mapping-note", required=True)
    pdt.add_argument("-o", "--output", required=True)
    pdt.add_argument("--result-output")

    rda = s.add_parser("case-review-deviation-authority")
    rda.add_argument("case")
    rda.add_argument("review")
    rda.add_argument("-o", "--output", required=True)
    rda.add_argument("--result-output")

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

    sd = s.add_parser("sync-dita")
    sd.add_argument("registry")
    sd.add_argument("--catalog", default="RULE-SOURCE-CATALOG.json")
    sd.add_argument("--source-id", required=True, choices=("gsa-far-dita", "gsa-dfars-dita"))
    sd.add_argument("--citation", required=True)
    sd.add_argument("--observed-at", required=True)
    sd.add_argument("--receipt-output")
    sd.add_argument("--record-output")

    sm = s.add_parser("case-sync-missing-rules")
    sm.add_argument("registry")
    sm.add_argument("case")
    sm.add_argument("--catalog", default="RULE-SOURCE-CATALOG.json")
    sm.add_argument("--observed-at", required=True)
    sm.add_argument("-o", "--output")
    sm.add_argument("--result-output")

    pe = s.add_parser("case-prepare-rule-evidence")
    pe.add_argument("registry")
    pe.add_argument("case")
    pe.add_argument("preparation")
    pe.add_argument("-o", "--output")
    pe.add_argument("--result-output")

    ar = s.add_parser("case-review-rule-applicability")
    ar.add_argument("case")
    ar.add_argument("review")
    ar.add_argument("-o", "--output")
    ar.add_argument("--result-output")

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
    elif args.cmd == "sync-deviation-manifest":
        result = sync_pinned_deviation_manifest(
            args.catalog,
            observed_at=args.observed_at,
        )
        _write({
            "status": result["status"],
            "row_count": result["manifest"]["row_count"],
            "manifest_sha256": result["manifest"]["manifest_sha256"],
            "fetch_receipt_id": result["fetch_receipt"]["fetch_receipt_id"],
            "can_auto_apply": False,
        })
        if args.manifest_output:
            _write(result["manifest"], args.manifest_output)
        if args.receipt_output:
            _write(result["fetch_receipt"], args.receipt_output)
    elif args.cmd == "case-propose-deviations":
        case = json.loads(Path(args.case).read_text(encoding="utf-8"))
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
        updated, transition = attach_deviation_candidate_proposal(
            case,
            manifest,
            receipt,
            agency=args.agency,
            part_numbers=args.part,
            proposed_by=args.proposed_by,
            proposed_at=args.proposed_at,
        )
        _write(updated, args.output)
        if args.result_output:
            _write(transition, args.result_output)
    elif args.cmd == "case-capture-deviation-artifact":
        case = json.loads(Path(args.case).read_text(encoding="utf-8"))
        updated, receipt, data = capture_and_attach_deviation_artifact(
            case,
            args.deviation_source_id,
            observed_at=args.observed_at,
        )
        Path(args.artifact_output).write_bytes(data)
        _write(updated, args.output)
        if args.receipt_output:
            _write(receipt, args.receipt_output)
        _write({
            "status": "DEVIATION_ARTIFACT_CAPTURED",
            "deviation_source_id": receipt["deviation_source_id"],
            "pdf_sha256": receipt["pdf_sha256"],
            "observed_pdf_size_bytes": receipt["observed_pdf_size_bytes"],
            "declared_size_matches_observed": receipt["declared_size_matches_observed"],
            "index_byte_identity_proven": False,
            "currentness": "UNRESOLVED",
            "applicability": "UNRESOLVED",
            "can_auto_apply": False,
        })
    elif args.cmd == "case-prepare-deviation-text":
        case = json.loads(Path(args.case).read_text(encoding="utf-8"))
        updated, transition = prepare_deviation_text(
            case,
            args.deviation_source_id,
            text=Path(args.text_file).read_text(encoding="utf-8"),
            prepared_by=args.prepared_by,
            prepared_at=args.prepared_at,
            mapping_note=args.mapping_note,
        )
        _write(updated, args.output)
        if args.result_output:
            _write(transition, args.result_output)
    elif args.cmd == "case-review-deviation-authority":
        case = json.loads(Path(args.case).read_text(encoding="utf-8"))
        review = json.loads(Path(args.review).read_text(encoding="utf-8"))
        updated, transition = review_deviation_authority(case, review)
        _write(updated, args.output)
        if args.result_output:
            _write(transition, args.result_output)
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
    elif args.cmd == "sync-dita":
        result = sync_pinned_gsa_rule(
            args.registry,
            args.catalog,
            source_id=args.source_id,
            citation=args.citation,
            observed_at=args.observed_at,
        )
        summary = {k: v for k, v in result.items() if k != "record"}
        _write(summary)
        if args.receipt_output:
            _write(result["fetch_receipt"], args.receipt_output)
        if args.record_output:
            _write(result["record"], args.record_output)
    elif args.cmd == "case-sync-missing-rules":
        case = json.loads(Path(args.case).read_text(encoding="utf-8"))
        updated, result = sync_missing_rule_candidates_for_case(
            case,
            args.registry,
            args.catalog,
            observed_at=args.observed_at,
        )
        _write(updated, args.output)
        if args.result_output:
            _write(result, args.result_output)
    elif args.cmd == "case-prepare-rule-evidence":
        case = json.loads(Path(args.case).read_text(encoding="utf-8"))
        preparation = json.loads(Path(args.preparation).read_text(encoding="utf-8"))
        updated, result = prepare_rule_evidence(
            case,
            args.registry,
            preparation,
        )
        _write(updated, args.output)
        if args.result_output:
            _write(result, args.result_output)
    elif args.cmd == "case-review-rule-applicability":
        case = json.loads(Path(args.case).read_text(encoding="utf-8"))
        review = json.loads(Path(args.review).read_text(encoding="utf-8"))
        updated, result = review_rule_applicability(case, review)
        _write(updated, args.output)
        if args.result_output:
            _write(result, args.result_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
