"""Adversarial, fictional-only nonces: missing/reset shared ledgers must fail closed.

The signed-release checker is mocked ONLY to isolate the ledger boundary.
These tests do not constitute real signoff, off-device restore, or send authority.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from capturebrief_core.accepted_case_release import AcceptedCaseBlocked
from capturebrief_core.authorization_ledger import reserve_once
from scripts.snapshot_authorization_ledger import initialize_empty_ledger

NOW = datetime(2026, 10, 29, 20, 0, tzinfo=timezone.utc)
FICTIONAL_GATE = {"status": "EVIDENCE_AND_PER_MESSAGE_APPROVAL_VERIFIED_MANUAL_SEND_ONLY"}


class SharedNoncePreprovisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "private-operator"
        self.root.mkdir(mode=0o700)
        self.ledger = self.root / "shared-authorizations.sqlite"
        self.manifest = {
            "case_sha256": "a" * 64,
            "delivery": {
                "recipient": "fictional@example.invalid",
                "authorization_nonce": "b" * 64,
                "expires_at": (NOW + timedelta(hours=1)).isoformat(),
            },
        }

    def reserve(self, path=None):
        with patch(
            "capturebrief_core.authorization_ledger.inspect_accepted_case",
            return_value=FICTIONAL_GATE,
        ):
            return reserve_once(
                self.manifest, case={}, private_root=self.root,
                trusted_keys={}, ledger_path=path or self.ledger, at=NOW,
            )

    def test_missing_shared_ledger_cannot_be_recreated_by_reservation(self):
        self.assertFalse(self.ledger.exists())
        with self.assertRaises(AcceptedCaseBlocked):
            self.reserve()
        self.assertFalse(self.ledger.exists(), "a deleted ledger must never be recreated")

    def test_existing_empty_sqlite_without_authorization_schema_cannot_be_repaired(self):
        with closing(sqlite3.connect(self.ledger)) as db, db:
            db.execute("PRAGMA user_version=1")
        if os.name != "nt":
            self.ledger.chmod(0o600)
        before = self.ledger.read_bytes()
        with self.assertRaises(AcceptedCaseBlocked):
            self.reserve()
        self.assertEqual(before, self.ledger.read_bytes(),
                         "reservation must not install a new empty nonce schema")

    def test_explicitly_initialized_shared_ledger_preserves_one_use_semantics(self):
        initialized = initialize_empty_ledger(self.ledger)
        self.assertEqual(initialized["reservation_count"], 0)
        first = self.reserve()
        self.assertEqual(first["status"],
                         "SINGLE_MESSAGE_AUTHORIZATION_RESERVED_MANUAL_SEND_PENDING")
        self.assertFalse(first["external_send_performed"])
        with self.assertRaises(AcceptedCaseBlocked):
            self.reserve()
        with closing(sqlite3.connect(self.ledger)) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM single_message_authorizations"
            ).fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
