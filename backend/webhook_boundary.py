"""Minimal Stripe-style raw-body signature boundary (stdlib only).

The production endpoint must read the untouched request body, verify this
signature before parsing JSON, and then pass only fixed, validated event fields
to ``entitlement_ledger.Ledger.apply_payment_event``. This module never stores
the body or secret and never activates an account from a browser redirect.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import re


class WebhookSignatureError(ValueError):
    """The provider signature is absent, malformed, stale, or invalid."""


_SECRET = re.compile(r"whsec_[A-Za-z0-9._~-]{8,}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def verify_raw_body_signature(
    raw_body: bytes,
    signature_header: str,
    endpoint_secret: str,
    *,
    now: datetime | None = None,
    tolerance_seconds: int = 300,
) -> int:
    """Verify a Stripe-compatible ``t=...,v1=...`` header.

    Returns the signed Unix timestamp only. The caller must retain no secret or
    raw payload in logs. A separate event-id dedupe transaction is required
    after parsing the verified JSON.
    """
    if type(raw_body) is not bytes or not raw_body:
        raise WebhookSignatureError("Raw request body is required")
    if not isinstance(endpoint_secret, str) or not _SECRET.fullmatch(endpoint_secret):
        raise WebhookSignatureError("Endpoint secret is not configured")
    if (type(tolerance_seconds) is not int or not 0 <= tolerance_seconds <= 86_400):
        raise ValueError("tolerance_seconds must be between 0 and 86400")
    if not isinstance(signature_header, str) or len(signature_header) > 2048:
        raise WebhookSignatureError("Malformed signature header")
    timestamp: int | None = None
    signatures: list[str] = []
    for item in signature_header.split(","):
        if "=" not in item:
            raise WebhookSignatureError("Malformed signature header")
        name, value = item.split("=", 1)
        if name == "t":
            if timestamp is not None or not value.isdigit():
                raise WebhookSignatureError("Malformed timestamp")
            timestamp = int(value)
        elif name == "v1":
            if not _HEX.fullmatch(value):
                raise WebhookSignatureError("Malformed signature digest")
            signatures.append(value)
        # Stripe may add other scheme versions; they are ignored, but at least
        # one current v1 signature is mandatory.
    if timestamp is None or not signatures:
        raise WebhookSignatureError("Current signature is missing")
    instant = now or datetime.now(timezone.utc)
    if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    age = abs(instant.timestamp() - timestamp)
    if age > tolerance_seconds:
        raise WebhookSignatureError("Signature timestamp is outside tolerance")
    signed = str(timestamp).encode("ascii") + b"." + raw_body
    expected = hmac.new(endpoint_secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise WebhookSignatureError("Signature verification failed")
    return timestamp
