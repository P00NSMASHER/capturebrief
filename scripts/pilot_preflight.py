"""Read-only, fail-closed CaptureBrief pilot technical preflight.

Never makes a charge, writes customer content, sends a message, or certifies the
independent operator/processor checks. An intake assertion is never payment proof.
"""
from __future__ import annotations

import argparse
import json
import re
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
) -> dict[str, Any]:
    """Assess actual source and deliverable artifacts; no caller-supplied PASS flags."""
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

    if case is None:
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

    if not bundle_path or receipt is None or case is None:
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

    if baseline is None or observed_case is None:
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

    technical = ("catalog", "real_case", "release", "delivery", "watch")
    passes = {"CATALOG_YEAR_COVERED", "PUBLIC_LINK_FORMAT_VERIFIED",
              "CORE_EVIDENCE_ELIGIBLE", "BUNDLE_BYTES_VERIFIED",
              "WATCH_FRESH_OBSERVATION_VERIFIED"}
    tech_ok = all(gates[key]["status"] in passes for key in technical)
    return {
        "schema": "capturebrief-pilot-preflight-v1",
        "checked_at": now.isoformat().replace("+00:00", "Z"),
        "fiscal_year": fiscal_year,
        "technical_preflight_passed": tech_ok,
        "approved_to_accept_payment_or_send_customer_material": False,
        "status": "AWAITING_EXTERNAL_PILOT_APPROVAL" if tech_ok else "PILOT_BLOCKED",
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
    args = parser.parse_args(argv)
    try:
        now = (datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
               if args.as_of else datetime.now(timezone.utc))
        out = inspect(now=now, case=_read_object(args.case),
                      bundle_path=args.bundle, receipt=_read_object(args.receipt),
                      baseline=_read_object(args.baseline),
                      observed_case=_read_object(args.observed_case))
    except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "PILOT_BLOCKED", "error": type(exc).__name__}))
        return 2
    print(json.dumps(out, indent=2, sort_keys=True))
    return 3 if out["technical_preflight_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
