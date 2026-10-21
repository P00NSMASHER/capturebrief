"""Read-only, privacy-minimized triage of CaptureBrief's PRIVATE imported cases.

This is an operator report, not an approval, inbox service, billing lookup,
or execution engine. No case, receipt, lock or source request is ever written.
A matching hash is local integrity evidence, NOT authenticated customer identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from capturebrief_core.fulfillment_plan import build_fulfillment_plan
from capturebrief_core.model import canonical_json, sha256_hex
from scripts.batch_import_request_drafts import _private_directory

MAX_CASES = 100
MAX_CASE_BYTES = 256 * 1024
MAX_RECEIPT_BYTES = 16 * 1024
_CASE_NAME = re.compile(r"^request-([0-9a-f]{64})\.(case|receipt)\.json$")

# Only these bounded labels are returned, never task titles, arbitrary
# task keys, URL/notice identifiers, contact details, or input paths.
_SAFE_STAGES = frozenset({
    "HISTORY_CURRENT", "PACKET_BYTES", "REFERENCE_REVIEW",
    "ASSUMPTION_REVIEW", "RULE_REVIEW", "DEVIATION_REVIEW",
    "DELIVERY", "OTHER",
})


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate private case or receipt JSON key")
        obj[key] = value
    return obj


def _bounded_json(path: Path, maximum: int) -> tuple[dict[str, Any], bytes]:
    junction = getattr(path, "is_junction", None)
    if (path.is_symlink() or (junction is not None and junction())
            or not path.is_file() or not 0 < path.stat().st_size <= maximum):
        raise ValueError("Private case or receipt is not a bounded regular file")
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if not 0 < len(data) <= maximum:
        raise ValueError("Private case or receipt changed during read")
    obj = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_fields)
    if not isinstance(obj, dict):
        raise ValueError("Private case or receipt is not a JSON object")
    return obj, data


def _is_false(record: dict[str, Any], names: tuple[str, ...]) -> bool:
    return all(record.get(key) is False for key in names)


def _load_unverified_pair(case_file: Path, receipt_file: Path, source_sha: str) -> dict[str, Any]:
    case, case_bytes = _bounded_json(case_file, MAX_CASE_BYTES)
    receipt, _ = _bounded_json(receipt_file, MAX_RECEIPT_BYTES)
    if (receipt.get("schema") != "capturebrief-private-intake-receipt-v1"
            or receipt.get("source_kind") != "BUYER_SUPPLIED_EMAIL_DRAFT"
            or receipt.get("request_sha256") != source_sha
            or receipt.get("case_file_sha256") != hashlib.sha256(case_bytes).hexdigest()
            or receipt.get("case_sha256") != sha256_hex(canonical_json(case))
            or receipt.get("case_id") != case.get("case_id")
            or receipt.get("independent_payment_lookup") != "NOT_PERFORMED"
            or receipt.get("operator_review_required") is not True
            or not _is_false(receipt, (
                "purchase_claim_verified", "sender_authenticated",
                "message_delivery_verified", "source_evidence_verified",
                "ready_to_start_work", "external_send_authorized",
                "case_release_authorized", "case_submitted_at_is_email_delivery_proof",
            ))):
        raise ValueError("Private intake receipt is inconsistent or asserts authority")
    intake = case.get("intake")
    if not isinstance(intake, dict):
        raise ValueError("Private case has invalid intake")
    if (case.get("case_schema_version") != "0.2"
            or case.get("decision_trace_required") is not True
            or case.get("sources") != []
            or case.get("current_action_receipts") != []
            or not isinstance(case.get("assumptions"), list)
            or not case["assumptions"]
            or any(not isinstance(row, dict) or row.get("evidence_state") != "UNPROVEN"
                   for row in case["assumptions"])
            or intake.get("record_time_basis") != "LOCAL_IMPORT_TIME_NOT_MAIL_PROVIDER_RECEIPT"
            or receipt.get("imported_at") != intake.get("submitted_at")
            or not isinstance(intake.get("email"), str)
            or not isinstance(intake.get("public_opportunity"), str)):
        raise ValueError("Private case is no longer the original unverified intake")
    return case


def _case_tag(digest: str) -> str:
    return hashlib.sha256(("capturebrief-review:" + digest).encode("ascii")).hexdigest()[:14]


def review_private_cases(
    cases_directory: str | Path,
    *,
    max_cases: int = MAX_CASES,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Make a read-only work queue from locally consistent UNPROVEN intakes."""
    if type(max_cases) is not int or not 1 <= max_cases <= MAX_CASES:
        raise ValueError("Case review must be bounded to 1-100 cases")
    checked_at = now if now is not None else datetime.now(timezone.utc)
    if (not isinstance(checked_at, datetime)
            or checked_at.utcoffset() is None):
        raise ValueError("Case queue timestamp must include a time zone")
    checked_at = checked_at.astimezone(timezone.utc)
    root = _private_directory(cases_directory)
    entries = sorted(root.iterdir(), key=lambda p: (p.name.casefold(), p.name))
    files: dict[str, set[str]] = {}
    for entry in entries:
        match = _CASE_NAME.fullmatch(entry.name)
        if match:
            files.setdefault(match.group(1), set()).add(match.group(2))
    if len(files) > max_cases:
        raise ValueError("Too many private cases for bounded review")
    summaries: list[dict[str, Any]] = []
    grouping: dict[tuple[str, str], list[int]] = {}
    blocked = 0
    missing_partner = 0
    verified = 0
    for digest in sorted(files):
        case_file = root / f"request-{digest}.case.json"
        receipt_file = root / f"request-{digest}.receipt.json"
        row: dict[str, Any] = {"case_tag": _case_tag(digest)}
        if files[digest] != {"case", "receipt"}:
            missing_partner += 1
            row["state"] = "MISSING_PARTNER"
        else:
            try:
                # Never assert work can proceed while another importer may be
                # creating or repairing one of these private output files.
                for output in (case_file, receipt_file):
                    if output.with_name(output.name + ".intake.lock").exists():
                        raise ValueError("Concurrent private importer lock exists")
                case = _load_unverified_pair(case_file, receipt_file, digest)
                plan = build_fulfillment_plan(case, now=checked_at)
                if (plan.get("delivery_bundle_eligible") is not False
                        or plan.get("release_state") != "FAIL_CLOSED"
                        or (plan.get("communications") or {}).get("external_send_authorized") is not False):
                    raise ValueError("Original unverified case cannot be customer releasable")
                next_task = plan.get("next_task") or {}
                stage = next_task.get("effort_stage") or "OTHER"
                if stage not in _SAFE_STAGES:
                    raise ValueError("Unexpected operator work stage")
                for output in (case_file, receipt_file):
                    if output.with_name(output.name + ".intake.lock").exists():
                        raise ValueError("Private importer started during review")
                row.update({
                    "state": "UNVERIFIED_INTAKE_REVIEW_REQUIRED",
                    "open_tasks": plan["summary"]["open_tasks"],
                    "p0_tasks": plan["summary"]["p0"],
                    "next_effort_stage": stage,
                    "next_priority": next_task.get("priority") or "NONE",
                    "related_same_buyer_and_opportunity": 0,
                    "payment_verified": False,
                    "release_authorized": False,
                    "external_send_authorized": False,
                })
                email = case["intake"]["email"].casefold()
                opportunity = case["intake"]["public_opportunity"]
                grouping.setdefault((email, opportunity), []).append(len(summaries))
                verified += 1
            except (OSError, ValueError, TypeError, KeyError, UnicodeError, AttributeError) as exc:
                blocked += 1
                row.update({
                    "state": "BLOCKED_INTEGRITY",
                    "error_type": type(exc).__name__,
                })
        summaries.append(row)

    related_pairs = 0
    for indices in grouping.values():
        n = len(indices)
        if n > 1:
            related_pairs += n * (n - 1) // 2
            for index in indices:
                summaries[index]["related_same_buyer_and_opportunity"] = n - 1
    return {
        "schema": "capturebrief-private-case-review-v1",
        "status": ("PRIVATE_CASE_REVIEW_BLOCKED" if blocked or missing_partner
                   else "PRIVATE_CASE_REVIEW_PENDING" if verified
                   else "PRIVATE_CASE_REVIEW_EMPTY"),
        "checked_at": checked_at.isoformat().replace("+00:00", "Z"),
        "input_pairs_or_orphans": len(files),
        "verified_intake_pairs": verified,
        "blocked": blocked,
        "missing_partner": missing_partner,
        "ignored_non_case_entries": len(entries) - sum(len(v) for v in files.values()),
        "possible_related_case_pairs": related_pairs,
        "cases": summaries,
        "read_only": True,
        "any_customer_payment_verified": False,
        "any_external_send_authorized": False,
        "any_customer_release_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases-dir", required=True, help="Existing private folder with imported case pairs")
    parser.add_argument("--max-cases", type=int, default=MAX_CASES)
    parser.add_argument("--now", help="Explicit timezone-aware audit time for reproducible QA")
    args = parser.parse_args(argv)
    try:
        now = (datetime.fromisoformat(args.now.replace("Z", "+00:00"))
               if args.now else None)
        result = review_private_cases(args.cases_dir, max_cases=args.max_cases, now=now)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            "status": "PRIVATE_CASE_REVIEW_BLOCKED",
            "error_type": type(exc).__name__,
            "any_customer_release_authorized": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 3 if result["blocked"] or result["missing_partner"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
