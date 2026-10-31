"""SAM latest-active proof must reject truncated or boolean pagination metadata.

Hermetic provider responses only; no network, credentials, or customer data.
"""
from __future__ import annotations

import json
import unittest

from capturebrief_core.current_api import (
    CurrentApiError,
    fetch_latest_active,
    validate_api_observation,
)
from tests.test_current_api_integrity import FakeResponse, api_observation, payload


class PaginationMetadataTypeTests(unittest.TestCase):
    def test_fetched_api_page_rejects_coerced_counts(self):
        # Before the repair, int(True) == 1 and int(1.9) == 1.
        # These payloads could incorrectly establish a complete first page.
        invalid = (
            ("totalRecords", True),
            ("totalRecords", 1.9),
            ("limit", True),
            ("limit", 1.9),
            ("offset", False),
            ("offset", 0.9),
            ("totalRecords", "1.0"),
        )
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                response = payload()
                response[field] = value
                raw = json.dumps(response).encode("utf-8")
                with self.assertRaises(CurrentApiError):
                    fetch_latest_active(
                        solicitation_number="SOL-1",
                        posted_from="09/01/2026",
                        posted_to="09/21/2026",
                        api_key="synthetic-test-only",
                        opener=lambda req, timeout=30: FakeResponse(raw),
                    )

    def test_retained_observation_rejects_coerced_counts(self):
        for field, value in (
            ("total_records", True),
            ("total_records", 1.9),
            ("returned_records", True),
            ("returned_records", 1.9),
            ("limit", True),
            ("limit", 100.9),
            ("offset", False),
            ("offset", 0.9),
        ):
            with self.subTest(field=field, value=value):
                observation = api_observation()
                observation["pagination"][field] = value
                with self.assertRaises(CurrentApiError):
                    validate_api_observation(observation)

    def test_decimal_strings_remain_backward_compatible(self):
        page = payload()
        page["totalRecords"] = "1"
        page["limit"] = "100"
        page["offset"] = "0"
        raw = json.dumps(page).encode("utf-8")
        observation = fetch_latest_active(
            solicitation_number="SOL-1",
            posted_from="09/01/2026",
            posted_to="09/21/2026",
            api_key="synthetic-test-only",
            opener=lambda req, timeout=30: FakeResponse(raw),
        )
        self.assertEqual(observation["pagination"]["total_records"], 1)
        self.assertEqual(observation["pagination"]["limit"], 100)
        self.assertEqual(observation["pagination"]["offset"], 0)

    def test_negative_and_missing_counts_stay_blocked(self):
        for field, value in (("totalRecords", -1), ("limit", None), ("offset", "-1")):
            with self.subTest(field=field, value=value):
                page = payload()
                page[field] = value
                raw = json.dumps(page).encode("utf-8")
                with self.assertRaises(CurrentApiError):
                    fetch_latest_active(
                        solicitation_number="SOL-1",
                        posted_from="09/01/2026",
                        posted_to="09/21/2026",
                        api_key="synthetic-test-only",
                        opener=lambda req, timeout=30: FakeResponse(raw),
                    )


if __name__ == "__main__":
    unittest.main()
