"""Run full FICTIONAL CaptureBrief order-to-delivery/watch acceptance, offline.

Never accesses a real inbox, Stripe account, customer, SAM.gov or network.
The fixture bundle/watch success is an INDEPENDENT golden DEMO and does NOT
turn the unverified synthetic order into a releasable customer.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from capturebrief_core.delivery_bundle import build_delivery_bundle
from capturebrief_core.delivery_verify import verify_delivery_bundle
from capturebrief_core.watch_baseline import build_watch_baseline, compare_watch_baseline
from scripts.batch_import_request_drafts import batch_import
from scripts.process_private_order_queue import process_private_order_queue
from scripts.inspect_private_order_fulfillment import inspect_fulfillment
from tests.test_private_order_os import provider_for, stripe_records
from tests.test_request_draft import draft

PILOT_NOW = datetime(2026, 10, 21, 16, 0, tzinfo=timezone.utc)
GOLDEN_NOW = datetime(2026, 9, 21, 17, 30, tzinfo=timezone.utc)


def _check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError("Fictional pilot acceptance failed: " + label)


def run_acceptance() -> dict:
    with tempfile.TemporaryDirectory(prefix="capturebrief-fake-order-") as t:
        base = Path(t)
        inbox, cases, associations, orders = [
            base / name for name in ("incoming", "cases", "associations", "orders")
        ]
        for directory in (inbox, cases, associations, orders):
            directory.mkdir()
        registry = orders / "registry.sqlite"
        message = draft(paid=True, company="Fictional Pilot Operator")
        (inbox / "a.txt").write_text(message, encoding="utf-8")
        (inbox / "exact-copy.txt").write_text(message, encoding="utf-8")
        (inbox / "bad.txt").write_text("fictional incomplete request", encoding="utf-8")
        (inbox / "b.txt").write_text(
            draft(company="Fictional Other Buyer",email="other@example.com"),
            encoding="utf-8",
        )
        preview = batch_import(inbox, cases, preview=True)
        _check(preview["preview_new"] == 2 and preview["duplicates"] == 1
               and preview["blocked"] == 1, "preview counts")
        _check(not list(cases.iterdir()), "preview made persistent files")
        imported = batch_import(inbox, cases)
        _check(imported["created"] == 2 and imported["blocked"] == 1
               and imported["duplicates"] == 1, "private intake and exact dedup")
        sha = hashlib.sha256(message.encode("utf-8")).hexdigest()
        association = {
            "schema": "capturebrief-private-checkout-association-v1",
            "request_sha256": sha,
            "checkout_session_id": "cs_live_REGISTRATION",
        }
        (associations / f"request-{sha}.order.json").write_text(json.dumps(association))
        fetcher, calls = provider_for(stripe_records("REGISTRATION"))
        scan = process_private_order_queue(
            cases, associations, registry, preview_only=True,
            synthetic_test_mode=True, synthetic_provider=fetcher,
        )
        _check(scan["preview_ready"] == 1 and scan["registered"] == 0
               and not calls and not registry.exists(), "dry-run provider separation")
        ingested = process_private_order_queue(
            cases, associations, registry, preview_only=False,
            api_key="sk_live_FICTIONAL_TEST_KEY",
            synthetic_test_mode=True, synthetic_provider=fetcher,
        )
        _check(ingested["registered"] == 1 and len(calls) == 4
               and not ingested["any_external_send_authorized"],
               "source-pinned fake checkout registration")
        rerun = process_private_order_queue(
            cases, associations, registry, preview_only=False,
            api_key="sk_live_FICTIONAL_TEST_KEY",
            synthetic_test_mode=True, synthetic_provider=fetcher,
        )
        _check(rerun["reused"] == 1 and rerun["registered"] == 0,
               "exact retries do not create duplicate orders")
        report = inspect_fulfillment(cases, registry, now=PILOT_NOW)
        _check(report["status"] == "PRIVATE_ORDER_FULFILLMENT_REVIEW_PENDING",
               "unverified private order review")
        _check(report["source_catalog"]["requested_fiscal_year"] == 2027
               and report["source_catalog"]["status"] == "SOURCE_CATALOG_REFRESH_REVIEW_REQUIRED"
               and report["orders"][0]["delivery_state"] == "NOT_VERIFIED"
               and report["orders"][0]["watch_state"] == "NOT_STARTED",
               "FY2027 catalog and delivery/watch cannot be promoted")
        _check(not report["customer_release_authorized"], "no customer release")

        # Separate golden DEMO only, proving actual package integrity +
        # targeted watch functions can execute without approving this order.
        golden_case = json.loads((PROJECT / "fixtures" / "ready_trace_case.json").read_text(encoding="utf-8"))
        archive = base / "fictional-golden-delivery.zip"
        receipt = build_delivery_bundle(golden_case, archive, now=GOLDEN_NOW)
        verified = verify_delivery_bundle(
            archive, expected_sha256=receipt["bundle_sha256"],
            expected_case_id=golden_case["case_id"],
            expected_case_sha256=receipt["case_sha256"],
        )
        _check(verified["integrity_verified"], "golden delivery archive verification")
        baseline = build_watch_baseline(golden_case, now=GOLDEN_NOW)
        watch = compare_watch_baseline(baseline, golden_case, now=GOLDEN_NOW)
        _check(watch.get("watch_status") == "NO_CHANGE_OBSERVED",
               "targeted golden watch baseline")
        _check(not receipt["external_send_authorized"],
               "golden bundle does not grant permission to send")
        # A broken archive must fail against the separately retained digest.
        archive.write_bytes(b"fictional archive tamper")
        tamper = verify_delivery_bundle(archive, expected_sha256=receipt["bundle_sha256"])
        _check(not tamper["integrity_verified"], "tampered golden archive rejected")
        return {
            "schema": "capturebrief-offline-full-order-acceptance-v1",
            "status": "FICTIONAL_END_TO_END_PILOT_PASSED",
            "data_mode": "FICTIONAL_ONLY_NO_CUSTOMER_DATA",
            "preview_unique_valid": preview["preview_new"],
            "preview_rejected": preview["blocked"],
            "preview_exact_duplicates": preview["duplicates"],
            "private_cases_created": imported["created"],
            "simulated_stripe_direct_read_calls": 4,
            "private_orders_registered_synthetic": ingested["registered"],
            "idempotent_order_replays": rerun["reused"],
            "fy2027_catalog_still_unapproved": True,
            "unverified_case_delivery_blocked": True,
            "unverified_case_watch_not_started": True,
            "separate_golden_demo_bundle_integrity_verified": True,
            "separate_golden_demo_watch_no_change": True,
            "golden_demo_tamper_rejected": True,
            "real_customer_payments_verified": False,
            "real_customer_delivery_proven": False,
            "real_14_day_watch_completed": False,
            "customer_release_authorized": False,
            "external_send_authorized": False,
        }


def main() -> int:
    try:
        print(json.dumps(run_acceptance(), indent=2, sort_keys=True))
        return 0
    except (AssertionError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({
            "status": "FICTIONAL_PILOT_BLOCKED",
            "error_type": type(exc).__name__,
            "failed_fictional_check": (
                str(exc).removeprefix("Fictional pilot acceptance failed: ")[:90]
                if isinstance(exc, AssertionError) else None
            ),
            "customer_release_authorized": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
