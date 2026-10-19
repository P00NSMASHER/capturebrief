"""Read-only, fail-closed CaptureBrief pilot technical preflight.

Never makes a charge, writes customer content, sends a message, or certifies the
independent operator/processor checks. An intake assertion is never payment proof.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

# Make direct "python scripts/pilot_preflight.py" work from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capturebrief_core.archive_catalog import (
    ArchiveCatalogStale, catalog_years_for_fiscal_year, fiscal_year_for_datetime,
)
from capturebrief_core.delivery_readiness import evaluate_delivery_readiness
from capturebrief_core.delivery_verify import verify_delivery_bundle
from capturebrief_core.watch_baseline import compare_watch_baseline
from scripts.source_coverage_audit import inspect_private_index

OFFICIAL_NOTICE = re.compile(r"^/opp/[0-9a-f]{32}/view/?$", re.I)


def official_opportunity(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        u = urlsplit(value)
    except ValueError:
        return False
    return (u.scheme == "https" and (u.hostname or "").lower() == "sam.gov"
            and not u.username and not u.password and not u.fragment
            and OFFICIAL_NOTICE.fullmatch(u.path) is not None)


def _read_object(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    item = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(item, dict):
        raise ValueError("expected a JSON object")
    return item


def inspect(
    *, now: datetime, case: dict[str, Any] | None = None,
    bundle_path: str | None = None, receipt: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
    observed_case: dict[str, Any] | None = None,
    stage: str = "completion", history_index: str | None = None,
    verify_source_bytes: bool = False,
) -> dict[str, Any]:
    """Assess observed evidence, separating admission from post-delivery work.

    The admission stage NEVER makes a customer-delivery claim. The completion
    stage preserves all existing evidence and watch requirements. Neither can
    grant payment, release, communications or certification authorization.
    """
    if stage not in {"admission", "completion"}:
        raise ValueError("stage must be admission or completion")
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("inspection time must include a timezone")
    now = now.astimezone(timezone.utc)
    gates: dict[str, dict[str, Any]] = {}

    def result(key: str, status: str, reason: str) -> None:
        gates[key] = {"status": status, "reason": reason}

    fiscal_year = fiscal_year_for_datetime(now)
    try:
        years = catalog_years_for_fiscal_year(fiscal_year)
        result("catalog", "CATALOG_YEAR_COVERED",
               f"FY{fiscal_year}: {len(years)} archive-year slots still require fresh source receipts")
    except ArchiveCatalogStale:
        result("catalog", "BLOCKED_STALE_CATALOG",
               f"FY{fiscal_year} exceeds the last independently pinned first-party catalog observation")

    if gates["catalog"]["status"] != "CATALOG_YEAR_COVERED":
        result("source_index", "BLOCKED_CATALOG_STALE",
               "No source index can override a catalog that is not independently certified through this fiscal year")
    elif not history_index:
        result("source_index", "BLOCKED_NO_PRIVATE_INDEX",
               "A private first-party source index and independently retained extracts are required")
    else:
        try:
            index_result = inspect_private_index(
                history_index, fiscal_year=fiscal_year, now=now,
                verify_bytes=verify_source_bytes,
            )
            if not index_result["metadata_complete"]:
                status = "BLOCKED_INDEX_COVERAGE"
            elif not verify_source_bytes:
                status = "BLOCKED_INDEX_BYTES_UNCHECKED"
            elif not index_result["local_file_hashes_match"]:
                status = "BLOCKED_SOURCE_HASH_MISMATCH"
            else:
                status = "INDEX_LOCAL_HASHES_MATCH"
            summary = {
                "required_slot_count": index_result["required_slot_count"],
                "fresh_slot_count": index_result["fresh_slot_count"],
                "missing_slots": index_result["missing_slots"],
                "stale_slots": index_result["stale_slots"],
                "unverified_slots": index_result["unverified_slots"],
                "missing_or_wrong_size_file_slots": index_result["missing_or_wrong_size_file_slots"],
                "hash_mismatch_slots": index_result["hash_mismatch_slots"],
                "file_hashes_checked": index_result["file_hashes_checked"],
                "publisher_authenticity_independently_established": False,
            }
            gates["source_index"] = {
                "status": status,
                "reason": "Private index local metadata/hash audit only; publisher origin and human catalog review need independent evidence",
                "coverage": summary,
            }
        except (ValueError, OSError, sqlite3.DatabaseError) as exc:
            result("source_index", "BLOCKED_UNREADABLE_INDEX",
                   "Private index unavailable, unsupported, or inconsistent: " + type(exc).__name__)

    if stage == "admission":
        result("real_case", "POST_ADMISSION_CUSTOMER_EVIDENCE",
               "A future customer's genuine pursuit is not required before admitting the first supervised pilot")
        result("release", "POST_ADMISSION_DELIVERY_REVIEW",
               "A real customer's reviewed evidence and trace are due before their deliverable")
    elif case is None:
        result("real_case", "BLOCKED_NO_CASE", "No retained real-pursuit case supplied")
        result("release", "BLOCKED_NO_CASE", "No case evidence to audit")
    else:
        url = (case.get("intake") or {}).get("public_opportunity")
        if official_opportunity(url):
            result("real_case", "PUBLIC_LINK_FORMAT_VERIFIED",
                   "Official public notice URL has the required structure; content and currentness are not thereby verified")
        else:
            result("real_case", "BLOCKED_NO_OFFICIAL_PILOT_NOTICE",
                   "Case needs a genuine first-party public SAM.gov notice reference")
        try:
            readiness = evaluate_delivery_readiness(case, now=now)
            if readiness.eligible:
                result("release", "CORE_EVIDENCE_ELIGIBLE",
                       "Case audit and non-synthetic Decision Evidence satisfy core technical checks")
            else:
                result("release", "BLOCKED_BY_CORE_EVIDENCE",
                       ", ".join(readiness.blocker_codes[:16]))
        except (ValueError, TypeError, KeyError) as exc:
            result("release", "BLOCKED_EVIDENCE_INVALID", type(exc).__name__)

    if stage == "admission":
        result("delivery", "POST_ADMISSION_CUSTOMER_BUNDLE",
               "A customer's verified bundle is required before that customer's delivery, not before pilot admission")
    elif not bundle_path or receipt is None or case is None:
        result("delivery", "BLOCKED_UNVERIFIED_BUNDLE",
               "Need an actual ZIP and its separately retained original build receipt")
    else:
        expected = receipt.get("bundle_sha256")
        try:
            verified = verify_delivery_bundle(
                bundle_path, expected_sha256=expected,
                expected_case_id=case.get("case_id"),
                expected_case_sha256=receipt.get("case_sha256"),
            )
        except (ValueError, OSError, TypeError, KeyError):
            verified = {"integrity_verified": False, "errors": ["VERIFICATION_ERROR"]}
        result("delivery", "BUNDLE_BYTES_VERIFIED" if verified["integrity_verified"]
               else "BLOCKED_BUNDLE_INTEGRITY",
               "Exact ZIP bytes matched independently retained digest and package contract"
               if verified["integrity_verified"] else
               ", ".join(verified.get("errors") or ["NO_INTEGRITY_PROOF"]))

    if stage == "admission":
        result("watch", "POST_ADMISSION_WATCH_OBSERVATION",
               "An actual 14-day watch can only be measured after customer delivery; operational setup still needs independent QA")
    elif baseline is None or observed_case is None:
        result("watch", "BLOCKED_NO_FRESH_WATCH_REPLAY",
               "Need a delivered baseline and a separately refreshed later public observation")
    else:
        try:
            observation = compare_watch_baseline(baseline, observed_case, now=now)
            if observation["watch_status"] == "EXPIRED":
                state = "BLOCKED_WATCH_EXPIRED"
            elif not observation["fresh_observation_evidenced"]:
                state = "BLOCKED_WATCH_NO_FRESH_SOURCE"
            elif observation["requires_human_review"]:
                state = "WATCH_REVIEW_REQUIRED"
            else:
                state = "WATCH_FRESH_OBSERVATION_VERIFIED"
            result("watch", state,
                   f"Status: {observation['watch_status']}; "
                   f"events: {len(observation['events'])}; "
                   "no automatic decision change or external notification")
        except (ValueError, KeyError, TypeError) as exc:
            result("watch", "BLOCKED_INVALID_WATCH_REPLAY", type(exc).__name__)

    # Deliberately not satisfied by browser redirects, website dropdowns,
    # customer-supplied receipts, test transactions, or invented approvals.
    result("intake", "MANUAL_INBOX_RECONCILIATION_REQUIRED",
           "Draft/copy is not server delivery; independently confirm arrival and consent before work")
    result("payment", "STRIPE_LIVE_RECORD_VERIFICATION_REQUIRED",
           "Verify the exact CaptureBrief live account/payment/refund state via Stripe, never a URL parameter")
    result("operator", "INDEPENDENT_REVIEW_AND_SEND_APPROVAL_REQUIRED",
           "Require signed scope, source and human-review signoffs; each external message is separately approved")
    result("production", "PROTECTED_RELEASE_REVIEW_REQUIRED",
           "Any code or website changes require passing exact-head QA and approved publication")

    technical = ("catalog", "source_index", "real_case", "release", "delivery", "watch")
    passes = {"CATALOG_YEAR_COVERED", "INDEX_LOCAL_HASHES_MATCH", "PUBLIC_LINK_FORMAT_VERIFIED",
              "CORE_EVIDENCE_ELIGIBLE", "BUNDLE_BYTES_VERIFIED",
              "WATCH_FRESH_OBSERVATION_VERIFIED"}
    # No mere presence of a future/fictional case, copied email or unverified
    # processor claim can turn an admission check into a signed launch approval.
    tech_ok = stage == "completion" and all(gates[key]["status"] in passes for key in technical)
    if stage == "admission":
        status = ("PILOT_ADMISSION_REVIEW_REQUIRED"
                  if (gates["catalog"]["status"] == "CATALOG_YEAR_COVERED"
                      and gates["source_index"]["status"] == "INDEX_LOCAL_HASHES_MATCH")
                  else "PILOT_ADMISSION_BLOCKED")
    else:
        status = "AWAITING_EXTERNAL_PILOT_APPROVAL" if tech_ok else "PILOT_BLOCKED"
    return {
        "schema": "capturebrief-pilot-preflight-v1",
        "stage": stage,
        "checked_at": now.isoformat().replace("+00:00", "Z"),
        "fiscal_year": fiscal_year,
        "technical_preflight_passed": tech_ok,
        "approved_to_accept_payment_or_send_customer_material": False,
        "status": status,
        "pre_pilot_gates": ["catalog", "source_index", "intake", "payment", "operator", "production"],
        "post_pilot_gates": ["real_case", "release", "delivery", "watch"],
        "gates": gates,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", help="Local private non-synthetic pursuit JSON")
    parser.add_argument("--bundle", help="Actual local customer-delivery ZIP")
    parser.add_argument("--receipt", help="Original separately retained bundle receipt")
    parser.add_argument("--baseline", help="Delivered watch-baseline JSON")
    parser.add_argument("--observed-case", help="Freshly sourced later case snapshot JSON")
    parser.add_argument("--as-of", help="Timezone-aware ISO-8601 check time (default now)")
    parser.add_argument("--history-index", help="Existing private read-only SAM source index; never created")
    parser.add_argument("--verify-source-bytes", action="store_true",
                        help="Stream/hash every required local extract (may require substantial disk I/O)")
    parser.add_argument("--stage", choices=("admission", "completion"), default="completion",
                        help="admission before the first customer; completion after the real delivered watch")
    args = parser.parse_args(argv)
    try:
        now = (datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
               if args.as_of else datetime.now(timezone.utc))
        out = inspect(now=now, case=_read_object(args.case),
                      bundle_path=args.bundle, receipt=_read_object(args.receipt),
                      baseline=_read_object(args.baseline),
                      observed_case=_read_object(args.observed_case), stage=args.stage,
                      history_index=args.history_index,
                      verify_source_bytes=args.verify_source_bytes)
    except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "PILOT_BLOCKED", "error": type(exc).__name__}))
        return 2
    print(json.dumps(out, indent=2, sort_keys=True))
    return 3 if out["technical_preflight_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
