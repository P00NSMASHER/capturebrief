"""Offline tests for raw-body signature verification."""

from datetime import datetime, timezone
import hashlib
import hmac
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webhook_boundary import WebhookSignatureError, verify_raw_body_signature  # noqa: E402


SECRET = "whsec_testsecret123"
NOW = datetime.fromtimestamp(1_800_000_000, tz=timezone.utc)
BODY = b'{"id":"evt_123","type":"payment_succeeded"}'


def header(timestamp: int, secret: str = SECRET, body: bytes = BODY) -> str:
    signed = f"{timestamp}.".encode("ascii") + body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


class WebhookBoundaryTests(unittest.TestCase):
    def test_valid_signature_returns_timestamp(self):
        timestamp = int(NOW.timestamp())
        self.assertEqual(verify_raw_body_signature(BODY, header(timestamp), SECRET, now=NOW), timestamp)

    def test_rotation_accepts_any_valid_v1_signature(self):
        timestamp = int(NOW.timestamp())
        old = header(timestamp, "whsec_oldsecret123").split("v1=", 1)[1]
        current = header(timestamp).split("v1=", 1)[1]
        self.assertEqual(
            verify_raw_body_signature(BODY, f"t={timestamp},v1={old},v1={current}", SECRET, now=NOW), timestamp
        )

    def test_body_secret_and_timestamp_are_verified(self):
        timestamp = int(NOW.timestamp())
        with self.assertRaises(WebhookSignatureError):
            verify_raw_body_signature(BODY + b" ", header(timestamp), SECRET, now=NOW)
        with self.assertRaises(WebhookSignatureError):
            verify_raw_body_signature(BODY, header(timestamp, "whsec_othersecret"), SECRET, now=NOW)
        with self.assertRaises(WebhookSignatureError):
            verify_raw_body_signature(BODY, header(timestamp - 301), SECRET, now=NOW)

    def test_malformed_headers_and_secret_fail_closed(self):
        timestamp = int(NOW.timestamp())
        bad = ("", "t=x,v1=abc", f"t={timestamp}", f"t={timestamp},v1={'0' * 63}g", f"t={timestamp},v1={'0' * 64},t={timestamp}")
        for signature in bad:
            with self.subTest(signature=signature), self.assertRaises(WebhookSignatureError):
                verify_raw_body_signature(BODY, signature, SECRET, now=NOW)
        with self.assertRaises(WebhookSignatureError):
            verify_raw_body_signature(BODY, header(timestamp), "not-a-secret", now=NOW)
        with self.assertRaises(WebhookSignatureError):
            verify_raw_body_signature(b"", header(timestamp), SECRET, now=NOW)
        with self.assertRaises(ValueError):
            verify_raw_body_signature(BODY, header(timestamp), SECRET, now=datetime.now())


if __name__ == "__main__":
    unittest.main()
