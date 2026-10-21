"""Register one PRIVATE buyer intake only after a DIRECT read of live Stripe.

Operator supplies a Checkout Session ID from their independently reviewed
payment channel. The key remains in an environment variable, never in args,
logs, DB, or Git. All read requests use pinned account/Payment Link/amount.
Synthetic injected fetchers are allowed only in explicit test mode.
No payment, refund, email, case release or source promotion is performed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from capturebrief_core.private_order_registry import register_order, order_summary, OrderConflict
from scripts.batch_import_request_drafts import _private_directory
from scripts.review_private_cases import _load_unverified_pair
from scripts.reconcile_stripe_checkout import check_live_payment, _stripe_get

_CASE_NAME = re.compile(r"^request-([0-9a-f]{64})\.case\.json$")


def register_checkout(
    case_file: str | Path,
    *,
    checkout_session_id: str,
    database_path: str | Path,
    api_key: str,
    fetcher: Callable[[str, str], dict] | None = None,
    synthetic_test_mode: bool = False,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Use authenticated live provider by default; injected providers are test-only."""
    if type(synthetic_test_mode) is not bool or (fetcher is None) == synthetic_test_mode:
        raise ValueError("Injected payment providers require explicit synthetic test mode")
    supplied = Path(case_file).expanduser().absolute()
    private_root = _private_directory(supplied.parent)
    case_path = private_root / supplied.name
    match = _CASE_NAME.fullmatch(case_path.name)
    if not match or case_path.is_symlink():
        raise ValueError("Expected a private digest-addressed original intake case")
    receipt = private_root / f"request-{match.group(1)}.receipt.json"
    if receipt.is_symlink():
        raise ValueError("Linked private receipt is unsupported")
    # Refuse data while an existing importer may be modifying it.
    for path in (case_path, receipt):
        lock = path.with_name(path.name + ".intake.lock")
        if lock.exists() or lock.is_symlink():
            raise ValueError("Private case import is in progress")
    case = _load_unverified_pair(case_path, receipt, match.group(1))
    refs: dict[str, str] = {}
    provider = fetcher if synthetic_test_mode else _stripe_get

    def pinned_provider(path: str, key: str) -> dict[str, Any]:
        record = provider(path, key)
        if path.startswith("/v1/checkout/sessions/") and isinstance(record, dict):
            refs["payment_intent_id"] = record.get("payment_intent")
        return record

    checked = check_live_payment(
        case=case, session_id=checkout_session_id,
        api_key=api_key, fetcher=pinned_provider, observed_at=observed_at,
    )
    # Receipt remains a local consistency check, NOT independent provider
    # cryptographic authentication, source acceptance or send authorization.
    if checked["payment_verified_by_matching_records"] is not True:
        return {
            "status": "PAYMENT_RECONCILIATION_BLOCKED",
            "error_codes": checked["error_codes"],
            "private_order_created": False,
            "work_authorized": False,
            "external_send_authorized": False,
            "customer_release_authorized": False,
        }
    for path in (case_path, receipt):
        if path.with_name(path.name + ".intake.lock").exists():
            raise ValueError("Private case import began during payment reconciliation")
    return register_order(
        database_path,
        case=case,
        source_request_sha256=match.group(1),
        session_id=checkout_session_id,
        payment_intent_id=refs["payment_intent_id"],
        payment_report=checked,
        synthetic_provider=synthetic_test_mode,
        observed_at=observed_at,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", help="Digest-addressed private request-<sha>.case.json")
    parser.add_argument("checkout_session_id", help="Independently obtained cs_live_... session ID")
    parser.add_argument("--registry", required=True, help="Private operator order-registry.sqlite")
    parser.add_argument("--key-env", default="STRIPE_CAPTUREBRIEF_SECRET_KEY")
    parser.add_argument("--status-only", action="store_true",
                        help="Read existing order states, never contact Stripe or write")
    args = parser.parse_args(argv)
    if args.status_only:
        try:
            out = order_summary(args.registry)
        except (ValueError, OSError, TypeError):
            out = {"status": "PRIVATE_ORDER_REGISTRY_BLOCKED",
                   "all_customer_release_authorized": False}
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0 if not out["status"].endswith("BLOCKED") else 3
    try:
        key = os.environ.get(args.key_env, "")
        report = register_checkout(
            args.case, checkout_session_id=args.checkout_session_id,
            database_path=args.registry, api_key=key,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] in {
            "PRIVATE_ORDER_REGISTERED_REVIEW_REQUIRED",
            "ALREADY_REGISTERED_UNVERIFIED",
        } else 3
    except (ValueError, OSError, TypeError, KeyError, RuntimeError, OrderConflict) as exc:
        print(json.dumps({
            "status": "PRIVATE_ORDER_REGISTRATION_BLOCKED",
            "error_type": type(exc).__name__,
            "payment_verified": False,
            "work_authorized": False,
            "customer_release_authorized": False,
            "external_send_authorized": False,
        }, sort_keys=True))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
