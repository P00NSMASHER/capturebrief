"""Private, bounded CaptureBrief source collection for ONE free-check pursuit.

Unlike the full SAM history-index workflow, this does not download historical
CSV archives or require Cloudflare R2. It never sends email, bills, approves
human review, or releases a report. Source evidence is scoped per case.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.request import build_opener
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capturebrief_core.atomic_io import ensure_exact_bytes, exclusive_path_lock
from capturebrief_core.model import canonical_json, sha256_hex
from capturebrief_core.scoped_source import (
    _intake_identity, _private_path, bind_reviewed_scoped_case,
    observe_scoped_case, private_root, read_private_case, retain_review_source,
    verify_scoped_capture, ScopedApiRedirects, ScopedSourceBlocked,
    MAX_CAPTURE_BYTES,
)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ScopedSourceBlocked("Duplicate scoped receipt field")
        result[key] = value
    return result


def load_capture(case: dict[str, Any], root: Path, capture_path: str | Path) -> dict[str, Any]:
    path = _private_path(capture_path, directory=False)
    identity = _intake_identity(case)
    folder = root / ("case-" + identity["case_tag"])
    if path.parent != folder or not re.fullmatch(r"sam-current-[0-9a-f]{64}\.json", path.name):
        raise ScopedSourceBlocked("Scoped receipt is not bound to the selected private case")
    if not 0 < path.stat().st_size <= MAX_CAPTURE_BYTES:
        raise ScopedSourceBlocked("Scoped observation receipt size is invalid")
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except (ValueError, UnicodeError, OSError):
        raise ScopedSourceBlocked("Scoped observation receipt cannot be read") from None
    if not isinstance(value, dict) or path.name != "sam-current-" + str(value.get("capture_sha256")) + ".json":
        raise ScopedSourceBlocked("Scoped receipt filename is not content-addressed")
    if raw != (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode():
        raise ScopedSourceBlocked("Scoped receipt bytes are not canonical")
    return value


def run(args: argparse.Namespace) -> dict[str, Any]:
    case = read_private_case(args.case)
    root = private_root(args.private_dir)
    identity = _intake_identity(case)
    if args.command == "observe":
        from capturebrief_core.scoped_source import MAX_API_BYTES
        return observe_scoped_case(
            case, solicitation_number=args.solicitation,
            posted_from=args.posted_from, posted_to=args.posted_to,
            api_key=os.environ.get("SAM_API_KEY", ""), private_dir=root,
            opener=build_opener(ScopedApiRedirects()).open,
        )
    if args.command == "retain":
        return retain_review_source(
            case, original_file=args.file, source_url=args.source_url,
            private_dir=root,
        )
    capture = load_capture(case, root, args.capture)
    observation = verify_scoped_capture(case, capture)
    if args.command == "verify":
        return {
            "status": "SCOPED_SOURCE_INTEGRITY_VERIFIED_REVIEW_REQUIRED",
            "case_tag": identity["case_tag"],
            "capture_sha256": capture["capture_sha256"],
            "current_api_source_bound": True,
            "hash_does_not_prove_origin_or_human_review": True,
            "history_completeness_verified": False,
            "customer_release_authorized": False,
            "external_send_authorized": False,
        }
    if args.command == "bind":
        updated, transition = bind_reviewed_scoped_case(case, capture)
        case_dir = root / ("case-" + identity["case_tag"])
        raw = (json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
        if len(raw) > 1024 * 1024:
            raise ScopedSourceBlocked("Scoped reviewed case exceeds private output bound")
        digest = sha256_hex(canonical_json(updated))
        name = "case-current-" + digest + ".json"
        with exclusive_path_lock(case_dir / ".scoped-case-output"):
            ensure_exact_bytes(case_dir / name, raw, mode=0o600)
        return {
            **transition,
            "case_tag": identity["case_tag"], "case_sha256": digest,
            "case_file": name,
            "source_document_review_still_required": True,
            "decision_evidence_review_still_required": True,
            "customer_release_authorized": False,
            "external_send_authorized": False,
        }
    raise ScopedSourceBlocked("Unsupported scoped source command")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("observe", "retain", "verify", "bind"):
        p = commands.add_parser(name)
        p.add_argument("--case", required=True, help="Previously private-imported case JSON")
        p.add_argument("--private-dir", required=True,
                       help="Existing 0700 private operator workspace outside every Git checkout")
        if name == "observe":
            p.add_argument("--solicitation", required=True)
            p.add_argument("--posted-from", required=True, help="MM/DD/YYYY")
            p.add_argument("--posted-to", required=True, help="MM/DD/YYYY")
        elif name == "retain":
            p.add_argument("--file", required=True, help="Operator-retrieved public original file, max 50 MiB")
            p.add_argument("--source-url", required=True,
                           help="Observed official HTTPS SAM/GSA source reference")
        else:
            p.add_argument("--capture", required=True,
                           help="Immutable sam-current-<sha>.json in same private case folder")
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except Exception as error:
        # Never print source exceptions, paths, submitted buyer fields or
        # possible credential-bearing URLs. This includes network errors.
        print(json.dumps({
            "status": "SCOPED_SOURCE_REVIEW_BLOCKED",
            "error_type": type(error).__name__,
            "customer_release_authorized": False,
            "external_send_authorized": False,
            "payment_authorized": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if args.command in {"observe", "retain", "verify"} else 3


if __name__ == "__main__":
    raise SystemExit(main())
