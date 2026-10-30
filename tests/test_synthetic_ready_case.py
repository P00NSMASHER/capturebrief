"""Fail-closed proof that short-lived demo fixture renewal never changes live rules."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from capturebrief_core.delivery_readiness import evaluate_delivery_readiness
from tests.synthetic_ready_case import (
    _SOURCE, current_synthetic_case, write_current_synthetic_case,
)


class DemoFixtureFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 21, 15, 21, 0, tzinfo=timezone.utc)

    def test_original_stale_demo_is_rejected_and_fresh_test_only_case_is_bounded(self):
        frozen_bytes = _SOURCE.read_bytes()
        original = json.loads(frozen_bytes)
        old = evaluate_delivery_readiness(original, now=self.now)
        self.assertFalse(old.eligible)
        self.assertIn("ACTIVE_AUTHORITY_NOT_VERIFIED", old.blocker_codes)

        renewed = current_synthetic_case(now=self.now)
        current = evaluate_delivery_readiness(renewed, now=self.now)
        self.assertTrue(current.eligible, current.blocker_codes)
        expired = evaluate_delivery_readiness(
            renewed, now=self.now + timedelta(minutes=11),
        )
        self.assertFalse(expired.eligible)
        self.assertIn("ACTIVE_AUTHORITY_NOT_VERIFIED", expired.blocker_codes)
        self.assertEqual(_SOURCE.read_bytes(), frozen_bytes)

    def test_no_mutation_or_overwrite_of_prior_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "case.json"
            write_current_synthetic_case(target, now=self.now)
            before = target.read_bytes()
            with self.assertRaises(FileExistsError):
                write_current_synthetic_case(target, now=self.now)
            self.assertEqual(before, target.read_bytes())
            with self.assertRaises(ValueError):
                write_current_synthetic_case(_SOURCE, now=self.now)

    def test_rejects_untrusted_case_identity_and_naive_timestamp(self):
        with self.assertRaises(ValueError):
            current_synthetic_case(now=datetime(2026, 10, 21))
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "not-our-fixture.json"
            spoof = json.loads(_SOURCE.read_text())
            spoof["case_id"] = "CUSTOMER-UNKNOWN"
            fake.write_text(json.dumps(spoof))
            with patch("tests.synthetic_ready_case._SOURCE", fake):
                with self.assertRaises(ValueError):
                    current_synthetic_case(now=self.now)


if __name__ == "__main__":
    unittest.main()
