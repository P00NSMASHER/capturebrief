"""Fail closed on type-coerced SAM pagination in retained current-action receipts.

All receipts are produced from an injected synthetic API response. No credentials,
network requests, buyer records, external sends, or payment functions are used.
"""
from __future__ import annotations

import unittest
from datetime import timedelta

from capturebrief_core.authority import validate_current_action_receipts
from capturebrief_core.current_api import CurrentApiError, make_current_action_receipt
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



class ApprovedReceiptResourceLinkTypesTests(unittest.TestCase):
    def test_non_list_resource_collections_fail_even_with_valid_hash(self):
        # Before the fix, 'or []' silently converted every falsey value
        # below into a legitimate empty resource-link list.
        invalid = (None, False, 0, "", {}, "[]", {"url": "https://example.invalid"})
        for value in invalid:
            with self.subTest(value=value):
                receipt, history = _receipt()
                receipt["evidence_payload"]["resource_links"] = value
                receipt["evidence_payload_sha256"] = sha256_hex(
                    canonical_json(receipt["evidence_payload"])
                )
                verdict, action, findings = _check(receipt, history)
                self.assertEqual(verdict, "CURRENT_UNKNOWN")
                self.assertIsNone(action)
                self.assertIn(
                    "RECEIPT_APPROVED_API_RESOURCE_LINKS_INVALID",
                    {finding.code for finding in findings},
                )

    def test_missing_resource_collection_fails_closed(self):
        receipt, history = _receipt()
        receipt["evidence_payload"].pop("resource_links", None)
        receipt["evidence_payload_sha256"] = sha256_hex(
            canonical_json(receipt["evidence_payload"])
        )
        verdict, action, findings = _check(receipt, history)
        self.assertEqual(verdict, "CURRENT_UNKNOWN")
        self.assertIsNone(action)
        self.assertIn(
            "RECEIPT_APPROVED_API_RESOURCE_LINKS_INVALID",
            {finding.code for finding in findings},
        )

    def test_real_empty_resource_list_remains_valid(self):
        receipt, history = _receipt()
        receipt["evidence_payload"]["resource_links"] = []
        receipt["evidence_payload_sha256"] = sha256_hex(
            canonical_json(receipt["evidence_payload"])
        )
        verdict, action, findings = _check(receipt, history)
        self.assertEqual((verdict, action, findings), ("CURRENT_VERIFIED", history[0], []))


class ApprovedReceiptProviderActiveStatusTests(unittest.TestCase):
    def test_rehashed_archived_or_malformed_source_status_never_verifies_active(self):
        # The producer validates source status; retained proof validation must
        # independently reject altered evidence even with a matching SHA-256.
        for active in ("No", "yes", "YES", None, False, True, 1):
            with self.subTest(active=active):
                receipt, history = _receipt()
                receipt["evidence_payload"]["active"] = active
                receipt["evidence_payload_sha256"] = sha256_hex(
                    canonical_json(receipt["evidence_payload"])
                )
                verdict, action, findings = _check(receipt, history)
                self.assertEqual((verdict, action), ("CURRENT_UNKNOWN", None))
                self.assertIn("RECEIPT_APPROVED_API_NOT_ACTIVE",
                              {finding.code for finding in findings})
        receipt, history = _receipt()
        receipt["evidence_payload"].pop("active")
        receipt["evidence_payload_sha256"] = sha256_hex(
            canonical_json(receipt["evidence_payload"])
        )
        self.assertIn("RECEIPT_APPROVED_API_NOT_ACTIVE",
                      {finding.code for finding in _check(receipt, history)[2]})
        valid_receipt, valid_history = _receipt()
        self.assertEqual(_check(valid_receipt, valid_history)[0], "CURRENT_VERIFIED")


class ApprovedReceiptProducerStatusTests(unittest.TestCase):
    def test_missing_or_archived_status_cannot_mint_current_active_receipt(self):
        for active in (None, "No", "yes", True):
            with self.subTest(active=active):
                observation = api_observation()
                if active is None:
                    observation["record"].pop("active")
                else:
                    observation["record"]["active"] = active
                with self.assertRaisesRegex(CurrentApiError, "active opportunity"):
                    make_current_action_receipt(
                        observation,
                        history_action_ids=[observation["record"]["noticeId"]],
                    )


class ApprovedReceiptModeBoundaryTests(unittest.TestCase):
    def test_automated_api_source_requires_explicit_mode(self):
        # Before this change, dropping APPROVED_API from an otherwise valid
        # receipt skipped all source-contract validation as a manual receipt.
        for mode in (None, "HUMAN_SUPERVISED"):
            with self.subTest(mode=mode):
                receipt, history = _receipt()
                if mode is None:
                    receipt.pop("automation_mode")
                else:
                    receipt["automation_mode"] = mode
                verdict, action, findings = _check(receipt, history)
                self.assertEqual((verdict, action), ("CURRENT_UNKNOWN", None))
                self.assertIn(
                    "RECEIPT_APPROVED_API_MODE_REQUIRED",
                    {finding.code for finding in findings},
                )

    def test_legacy_manual_web_receipts_still_pass(self):
        # Maintain the existing generic first-party SAM manual contract.
        for mode in (None, "HUMAN_SUPERVISED"):
            with self.subTest(mode=mode):
                receipt, history = _receipt()
                receipt["source_url"] = "https://sam.gov/opportunities/example"
                if mode is None:
                    receipt.pop("automation_mode")
                else:
                    receipt["automation_mode"] = mode
                verdict, action, findings = _check(receipt, history)
                self.assertEqual((verdict, action, findings),
                                 ("CURRENT_VERIFIED", history[0], []))


class ApprovedReceiptFreshnessBoundaryTests(unittest.TestCase):
    def test_digest_valid_extended_api_receipt_is_not_current(self):
        # Before the fix a fully hashed 25-hour (or year-long) API receipt
        # was still accepted one minute after observation.
        for hours in (25, 24 * 365):
            with self.subTest(hours=hours):
                receipt, history = _receipt()
                observed = parse_dt(receipt["observed_at"])
                self.assertIsNotNone(observed)
                receipt["expires_at"] = (observed + timedelta(hours=hours)).isoformat()
                verdict, action, findings = _check(receipt, history)
                self.assertEqual((verdict, action), ("CURRENT_UNKNOWN", None))
                self.assertIn(
                    "RECEIPT_APPROVED_API_TTL_INVALID",
                    {finding.code for finding in findings},
                )

    def test_api_receipt_producer_refuses_invalid_ttl_values(self):
        observation = api_observation()
        history = [observation["record"]["noticeId"]]
        for hours in (None, False, True, 0, -1, 25, 1.5, "24"):
            with self.subTest(hours=hours):
                with self.assertRaisesRegex(CurrentApiError, "expiry"):
                    make_current_action_receipt(
                        observation, history_action_ids=history, expires_hours=hours
                    )

    def test_short_lived_api_receipts_are_still_verified(self):
        observation = api_observation()
        history = [observation["record"]["noticeId"]]
        for hours in (1, 24):
            with self.subTest(hours=hours):
                receipt = make_current_action_receipt(
                    observation, history_action_ids=history, expires_hours=hours
                )
                self.assertEqual(_check(receipt, history)[:2],
                                 ("CURRENT_VERIFIED", history[0]))

    def test_legacy_manual_receipt_retains_original_expiry_contract(self):
        receipt, history = _receipt()
        receipt["source_url"] = "https://sam.gov/opportunities/example"
        receipt["automation_mode"] = "HUMAN_SUPERVISED"
        observed = parse_dt(receipt["observed_at"])
        self.assertIsNotNone(observed)
        receipt["expires_at"] = (observed + timedelta(hours=72)).isoformat()
        self.assertEqual(_check(receipt, history)[:2],
                         ("CURRENT_VERIFIED", history[0]))


class ApprovedReceiptSemanticsBoundaryTests(unittest.TestCase):
    def test_active_api_provenance_cannot_be_relabelled_terminal(self):
        # Before the guard, metadata alone could turn a genuine active API
        # receipt into TERMINAL_*_VERIFIED without changing its payload hash.
        for semantics, status in (("TERMINAL_ARCHIVED", "ARCHIVED"),
                                  ("TERMINAL_CANCELLED", "CANCELLED")):
            with self.subTest(semantics=semantics):
                receipt, history = _receipt()
                receipt["semantics"] = semantics
                receipt["observed_family_status"] = status
                observed = parse_dt(receipt["observed_at"])
                self.assertIsNotNone(observed)
                verdict, action, findings = validate_current_action_receipts(
                    history, status, [receipt], now=observed + timedelta(minutes=1)
                )
                self.assertEqual((verdict, action), ("CURRENT_UNKNOWN", None))
                self.assertIn(
                    "RECEIPT_APPROVED_API_SEMANTICS_INVALID",
                    {finding.code for finding in findings},
                )

    def test_current_active_api_provenance_remains_valid(self):
        receipt, history = _receipt()
        self.assertEqual(_check(receipt, history), ("CURRENT_VERIFIED", history[0], []))


if __name__ == "__main__":
    unittest.main()
