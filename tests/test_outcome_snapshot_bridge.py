"""No-network verification of CaptureBrief's private immutable RETALLY snapshot handoff."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from capturebrief_core.ledger import (
    LEDGER_VERSION, GENESIS, _ledger_lock, append_record,
    read_verified_outcome_snapshot, verify_ledger,
)
from capturebrief_core.outcomes import make_outcome_event, summarize_outcomes


class ImmutableHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "approved-outcome-ledger.jsonl"

    def append(self, case_id="CB-SYNTHETIC", *, unicode=False):
        event = make_outcome_event(
            case_id=case_id,
            case_sha256="a" * 64,
            event_type="EFFORT",
            event_at="2026-09-21T18:00:00Z",
            data={"stage": "OTHER", "minutes": 7,
                  "effort_evidence_ref": "timer:synthetic:seven"},
        )
        return append_record(
            self.path, record_type="CAPTUREBRIEF_OUTCOME_EVENT",
            payload=event, recorded_at="2026-09-21T18:10:00Z",
        )

    def test_verified_byte_snapshot_matches_adapter_wire_contract(self):
        record = self.append()
        original = self.path.read_bytes()
        result = read_verified_outcome_snapshot(self.path)
        self.assertEqual({"present", "content", "snapshot_sha256", "observed_at"}, set(result))
        self.assertIs(result["present"], True)
        self.assertEqual(original, result["content"])
        self.assertEqual(hashlib.sha256(original).hexdigest(), result["snapshot_sha256"])
        self.assertEqual(record["record_sha256"], verify_ledger(self.path)["head_sha256"])
        self.assertLessEqual(
            datetime.fromisoformat(result["observed_at"].replace("Z", "+00:00")),
            datetime.now(timezone.utc),
        )
        self.assertIsNone((self.path.parent / (self.path.name + ".lock")).exists()
                          or None)
        self.assertEqual(original, self.path.read_bytes())

    def test_real_unicode_json_line_separators_are_not_new_record_delimiters(self):
        self.append(case_id="CB-UNICODE-\u2028-\u2029-\u0085")
        self.assertTrue(verify_ledger(self.path)["valid"])
        self.assertEqual(1, summarize_outcomes(self.path)["engagements"])
        snapshot = read_verified_outcome_snapshot(self.path)
        self.assertEqual(1, snapshot["content"].count(b"\n"))
        self.assertIn("CB-UNICODE-", snapshot["content"].decode("utf-8"))

    def test_missing_source_never_claims_empty_or_creates_parent(self):
        absent = self.path.parent / "never-created" / "outcome.jsonl"
        with self.assertRaises((ValueError, FileNotFoundError)):
            read_verified_outcome_snapshot(absent)
        self.assertFalse(absent.parent.exists())
        self.assertFalse(absent.with_name(absent.name + ".lock").exists())

    def test_tampering_partial_records_and_size_limits_refuse(self):
        self.append()
        with self.assertRaises(ValueError):
            read_verified_outcome_snapshot(self.path, max_bytes=4)
        for tail in (b"NOT_JSON\n", b"NO_NEWLINE", b"\n"):
            with self.subTest(tail=tail):
                original = self.path.read_bytes()
                self.path.write_bytes(original + tail)
                try:
                    with self.assertRaises(ValueError):
                        read_verified_outcome_snapshot(self.path)
                finally:
                    self.path.write_bytes(original)
                self.assertFalse(self.path.with_name(self.path.name + ".lock").exists())
        self.assertTrue(verify_ledger(self.path)["valid"])

    def test_locked_source_cannot_be_snapshotted_with_stale_bytes(self):
        self.append()
        with _ledger_lock(self.path):
            with self.assertRaises(ValueError):
                read_verified_outcome_snapshot(self.path, lock_timeout_seconds=0.01)
        self.assertTrue(verify_ledger(self.path)["valid"])

    def test_nonpositive_or_boolean_limits_refused(self):
        self.append()
        for limit in (0, -1, True, 16 * 1024 * 1024 + 1):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    read_verified_outcome_snapshot(self.path, max_bytes=limit)

    def test_symlink_source_is_not_treated_as_an_approved_ledger(self):
        self.append()
        link = self.path.with_name("unapproved-link.jsonl")
        try:
            link.symlink_to(self.path)
        except (OSError, NotImplementedError):
            self.skipTest("No symlink privilege on this filesystem")
        with self.assertRaises((ValueError, FileNotFoundError)):
            read_verified_outcome_snapshot(link)
        self.assertFalse(link.with_name(link.name + ".lock").exists())


if __name__ == "__main__":
    unittest.main()
