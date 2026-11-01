"""Fail closed on type-coerced SAM pagination in retained current-action receipts.

All receipts are produced from an injected synthetic API response. No credentials,
network requests, buyer records, external sends, or payment functions are used.
"""
from __future__ import annotations

import unittest
from datetime import timedelta

from capturebrief_core.authority import validate_current_action_receipts
from capturebrief_core.current_api import make_current_action_receipt
from capturebrief_core.model import canonical_json, parse_dt, sha256_hex
from tests.test_current_api_integrity import api_observation


def _receipt():
    observation = api_observation()
    notice_id = observation["record"]["noticeId"]
    history = [notice_id]
    return make_current_action_receipt(observation, history_action_ids=history), history


def _check(receipt, history):
    # Control time independently of the machine clock; stay within expiry.
    observed = parse_dt(receipt["observed_at"])
    assert observed is not None
    return validate_current_action_receipts(
        history, "ACTIVE", [receipt], now=observed + timedelta(minutes=1)
    )


def _retained_change(receipt, field, value):
    # Preserve a matching payload digest so the test exercises the numeric
    # authority gate, not the independent payload-integrity gate.
    receipt["evidence_payload"]["pagination"][field] = value
    receipt["evidence_payload_sha256"] = sha256_hex(
        canonical_json(receipt["evidence_payload"])
    )


class ApprovedReceiptPaginationTypesTests(unittest.TestCase):
    def test_unchanged_synthetic_api_receipt_still_proves_current_action(self):
        receipt, history = _receipt()
        verdict, action, findings = _check(receipt, history)
        self.assertEqual(verdict, "CURRENT_VERIFIED")
        self.assertEqual(action, history[0])
        self.assertEqual(findings, [])

    def test_rehashed_forged_boolean_and_fractional_counts_fail_closed(self):
        # Python int(True) == 1 and int(0.9) == 0; neither is a
        # legitimate JSON integer for an approved pagination receipt.
        invalid = (
            ("total_records", True),
            ("total_records", 1.9),
            ("returned_records", True),
            ("returned_records", 1.9),
            ("limit", True),
            ("limit", 100.9),
            ("offset", False),
            ("offset", 0.9),
            ("total_records", "1.0"),
            ("returned_records", None),
            ("offset", -1),
        )
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                receipt, history = _receipt()
                _retained_change(receipt, field, value)
                verdict, action, findings = _check(receipt, history)
                self.assertEqual(verdict, "CURRENT_UNKNOWN")
                self.assertIsNone(action)
                self.assertIn(
                    "RECEIPT_APPROVED_API_PAGINATION_INVALID",
                    {finding.code for finding in findings},
                )

    def test_decimal_strings_keep_existing_api_compatibility(self):
        receipt, history = _receipt()
        for field, value in (
            ("total_records", "1"),
            ("returned_records", "1"),
            ("limit", "100"),
            ("offset", "0"),
        ):
            _retained_change(receipt, field, value)
        verdict, action, findings = _check(receipt, history)
        self.assertEqual(verdict, "CURRENT_VERIFIED")
        self.assertEqual(action, history[0])
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
