"""Read-only live Stripe payment check for an operator-held CaptureBrief case.

Requires an operator-controlled *LIVE* CaptureBrief Stripe restricted/secret key.
No checkout, charge, refund, network redirect, customer contact or email.
No card data or customer email is written to the output receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from capturebrief_core.atomic_io import ensure_exact_bytes
from capturebrief_core.model import canonical_json, sha256_hex
from capturebrief_core.payment_reconciliation import (
    ACCOUNT_ID, reconcile_capturebrief_payment, _valid_id,
)

STRIPE_API = "https://api.stripe.com"
MAX_JSON_BYTES = 2 * 1024 * 1024


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Stripe API redirect refused")


def _private_file(path: str | Path, *, existing: bool) -> Path:
    source = Path(path).expanduser().absolute()
    if source.is_symlink() or source.is_relative_to(REPO):
        raise ValueError("Payment files must remain outside the public repository")
    result = source.resolve(strict=existing)
    if result.is_relative_to(REPO):
        raise ValueError("Payment files must remain outside the public repository")
    if existing and not result.is_file():
        raise ValueError("Input case must be a regular private file")
    if not existing and result.exists() and not result.is_file():
        raise ValueError("Payment receipt must be a regular private file")
    return result


def _object(raw: bytes) -> dict:
    def pairs_unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("Duplicate fields in Stripe API response")
            obj[key] = value
        return obj
    decoded = json.loads(raw, object_pairs_hook=pairs_unique,
                         parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    if not isinstance(decoded, dict):
        raise ValueError("Stripe API response is not an object")
    return decoded


def _stripe_get(path: str, api_key: str) -> dict:
    if (not path.startswith("/v1/") or "?" in path or "#" in path
            or ".." in path or "\\" in path):
        raise ValueError("Unsupported Stripe API resource path")
    request = Request(
        STRIPE_API + path,
        headers={"Authorization": "Bearer " + api_key,
                 "Accept": "application/json",
                 "User-Agent": "CaptureBrief-Payment-QA/1.0"},
        method="GET",
    )
    try:
        opener = build_opener(_NoRedirect)
        with opener.open(request, timeout=20) as response:
            if response.status != 200 or response.geturl() != STRIPE_API + path:
                raise ValueError("Unexpected Stripe API response or redirect")
            body = response.read(MAX_JSON_BYTES + 1)
    except (HTTPError, URLError) as exc:
        # NEVER put a raw URL, provider response or key in exception/logs.
        raise ValueError("Stripe API request failed") from exc
    if len(body) > MAX_JSON_BYTES:
        raise ValueError("Stripe API response exceeds byte limit")
    return _object(body)


def check_live_payment(
    *,
    case: dict[str, Any], session_id: str, api_key: str,
    fetcher: Callable[[str, str], dict] = _stripe_get,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    if not api_key.startswith(("sk_live_", "rk_live_")):
        raise ValueError("Live Stripe credential required")
    if not _valid_id(session_id, "cs_live"):
        raise ValueError("A live Stripe Checkout Session ID is required")
    intake = case.get("intake") or {}
    email = intake.get("email")
    if not isinstance(email, str) or not email:
        raise ValueError("A private case with buyer email is required")
    account = fetcher("/v1/account", api_key)
    if account.get("object") != "account" or account.get("id") != ACCOUNT_ID:
        raise ValueError("Stripe key is not scoped to the CaptureBrief live account")
    session = fetcher("/v1/checkout/sessions/" + session_id, api_key)
    if session.get("livemode") is not True or session.get("id") != session_id:
        raise ValueError("Provider returned an unexpected or test-mode Checkout Session")
    pi_id = session.get("payment_intent")
    if not _valid_id(pi_id, "pi"):
        raise ValueError("Checkout has no valid PaymentIntent ID")
    payment = fetcher("/v1/payment_intents/" + pi_id, api_key)
    charge_id = payment.get("latest_charge")
    if not _valid_id(charge_id, "ch"):
        raise ValueError("PaymentIntent has no latest charge")
    charge = fetcher("/v1/charges/" + charge_id, api_key)
    check = reconcile_capturebrief_payment(
        session, payment, charge, account_id=account["id"],
        buyer_email=email, observed_at=observed_at,
    )
    return {
        **check,
        "case_sha256": sha256_hex(canonical_json(case)),
        "case_id": case.get("case_id"),
        "source": "STRIPE_DIRECT_LIVE_READ_ONLY_API",
        "private_operator_record": True,
        "sender_verified": False,
        "scope_approved": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", help="Private CaptureBrief case file")
    parser.add_argument("checkout_session_id", help="Stripe live cs_live_... ID")
    parser.add_argument("--receipt-output", required=True,
                        help="Private output JSON file outside public repository")
    parser.add_argument("--key-env", default="STRIPE_CAPTUREBRIEF_SECRET_KEY",
                        help="Environment variable containing a live restricted/secret key")
    args = parser.parse_args(argv)
    try:
        input_path = _private_file(args.case, existing=True)
        output_path = _private_file(args.receipt_output, existing=False)
        if input_path == output_path:
            raise ValueError("Input and output paths must be different")
        key = os.environ.get(args.key_env, "")
        raw = input_path.read_bytes()
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("Case file exceeds safe input limit")
        case = _object(raw)
        report = check_live_payment(case=case, session_id=args.checkout_session_id,
                                    api_key=key)
        encoded = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
        ensure_exact_bytes(output_path, encoded)
        # Do not output any customer data, key, charge details or provider URLs.
        print(json.dumps({
            "status": report["status"],
            "case_id": report["case_id"],
            "receipt_sha256": hashlib.sha256(encoded).hexdigest(),
            "error_codes": report["error_codes"],
            "external_send_authorized": False,
        }, sort_keys=True))
        return 0 if report["payment_verified_by_matching_records"] else 3
    except (ValueError, OSError, TypeError, KeyError, RuntimeError) as exc:
        print(json.dumps({
            "status": "PAYMENT_RECONCILIATION_BLOCKED",
            "error_type": type(exc).__name__,
            "external_send_authorized": False,
        }, sort_keys=True))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
