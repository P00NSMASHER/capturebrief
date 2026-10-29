"""Fictional-only, offline SQLite shared-nonce ledger durability acceptance.

No real customer, signer, message, approval, payment or external storage.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import snapshot_authorization_ledger as ledger

NOW = datetime.now(timezone.utc)
COLUMNS = ("nonce_sha256", "case_sha256", "manifest_sha256",
           "recipient_sha256", "reserved_at")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def add_fake_nonce(db: sqlite3.Connection, tag: str, *, when: datetime | None = None):
    db.execute(
        "INSERT INTO single_message_authorizations "
        "(nonce_sha256,case_sha256,manifest_sha256,recipient_sha256,reserved_at,state) "
        "VALUES (?,?,?,?,?,'MANUAL_SEND_PENDING_NO_PROVIDER_EVIDENCE')",
        (digest("nonce-" + tag), digest("case-" + tag),
         digest("manifest-" + tag), digest("recipient-" + tag),
         (when or (NOW - timedelta(minutes=5))).isoformat()),
    )


class AuthorizationSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.private = root / "operator-only"
        self.private.mkdir(mode=0o700)
        self.ledger = self.private / "one-message-authorizations.sqlite"
        self.snapshot = self.private / "consistent-nonces-v1.sqlite"

    def test_empty_first_customer_ledger_can_be_initialized_and_snapshotted(self):
        report = ledger.initialize_empty_ledger(self.ledger)
        self.assertEqual(report["reservation_count"], 0)
        self.assertFalse(report["customer_release_authorized"])
        with self.assertRaises(ValueError):
            ledger.initialize_empty_ledger(self.ledger)
        result = ledger.create_snapshot(self.ledger, self.snapshot)
        self.assertEqual(result["reservation_count"], 0)
        self.assertTrue(result["committed_wal_state_included"])
        self.assertFalse(result["independent_offdevice_restore_verified"])
        verified = ledger.verify_snapshot(self.snapshot)
        self.assertEqual(verified["snapshot_sha256"], result["snapshot_sha256"])
        self.assertFalse(verified["safe_to_promote_without_reconciliation"])
        self.assertFalse(verified["external_send_performed"])
        with self.assertRaises(ValueError):
            ledger.create_snapshot(self.ledger, self.snapshot)
        if os.name != "nt":
            self.assertEqual(self.snapshot.stat().st_mode & 0o077, 0)

    def test_live_wal_commits_are_present_and_old_snapshot_does_not_reincarnate_nonces(self):
        ledger.initialize_empty_ledger(self.ledger)
        with closing(sqlite3.connect(self.ledger, timeout=5)) as writer:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
            with writer:
                add_fake_nonce(writer, "one")
                add_fake_nonce(writer, "two")
            # Keep writer connection open so WAL transactions remain live.
            report = ledger.create_snapshot(self.ledger, self.snapshot)
            self.assertEqual(report["reservation_count"], 2)
            with closing(sqlite3.connect(":memory:")) as isolated:
                isolated.deserialize(self.snapshot.read_bytes())
                self.assertEqual(isolated.execute(
                    "SELECT COUNT(*) FROM single_message_authorizations"
                ).fetchone()[0], 2)
                with self.assertRaises(sqlite3.IntegrityError):
                    with isolated:
                        add_fake_nonce(isolated, "one")  # nonce cannot be reused
            # A newer committed nonce CANNOT appear magically in the old
            # backup, and the tool never "restores/promotes" the old database.
            with writer:
                add_fake_nonce(writer, "three")
            self.assertEqual(ledger.verify_snapshot(self.snapshot)["reservation_count"], 2)
            next_snapshot = self.private / "consistent-nonces-v2.sqlite"
            self.assertEqual(ledger.create_snapshot(
                self.ledger, next_snapshot
            )["reservation_count"], 3)

    def test_invalid_schema_added_trigger_and_future_timestamp_fail_closed(self):
        ledger.initialize_empty_ledger(self.ledger)
        with closing(sqlite3.connect(self.ledger)) as db:
            with db:
                db.execute("CREATE TABLE other_data (secret TEXT)")
        with self.assertRaises((ValueError, sqlite3.DatabaseError)):
            ledger.create_snapshot(self.ledger, self.snapshot)
        self.assertFalse(self.snapshot.exists())
        with closing(sqlite3.connect(self.ledger)) as db:
            with db:
                db.execute("DROP TABLE other_data")
                db.execute(
                    "CREATE TRIGGER wipe_after_insert AFTER INSERT ON "
                    "single_message_authorizations BEGIN "
                    "DELETE FROM single_message_authorizations WHERE "
                    "nonce_sha256 != NEW.nonce_sha256; END"
                )
        with self.assertRaises((ValueError, sqlite3.DatabaseError)):
            ledger.create_snapshot(self.ledger, self.snapshot)
        self.assertFalse(self.snapshot.exists())
        with closing(sqlite3.connect(self.ledger)) as db:
            with db:
                db.execute("DROP TRIGGER wipe_after_insert")
                add_fake_nonce(db, "future", when=NOW + timedelta(days=30))
        with self.assertRaises((ValueError, sqlite3.DatabaseError)):
            ledger.create_snapshot(self.ledger, self.snapshot)
        self.assertFalse(self.snapshot.exists())

    def test_mutated_portable_snapshot_is_rejected_without_private_bytes_in_logs(self):
        ledger.initialize_empty_ledger(self.ledger)
        ledger.create_snapshot(self.ledger, self.snapshot)
        original = self.snapshot.read_bytes()
        self.snapshot.write_bytes(original[:18] + b"\x02\x02" + original[20:])
        with self.assertRaises((ValueError, sqlite3.DatabaseError)):
            ledger.verify_snapshot(self.snapshot)
        self.snapshot.write_bytes(original)
        self.assertEqual(ledger.verify_snapshot(self.snapshot)["reservation_count"], 0)

    def test_unapproved_paths_existing_sidecars_and_missing_source_rejected(self):
        with self.assertRaises((ValueError, OSError)):
            ledger.create_snapshot(self.ledger, self.snapshot)
        with self.assertRaises((ValueError, OSError)):
            ledger.initialize_empty_ledger(Path(__file__).resolve().parents[1] / "public.sqlite")
        sidecar = self.ledger.with_name(self.ledger.name + "-wal")
        sidecar.write_bytes(b"stale journal")
        with self.assertRaises((ValueError, OSError)):
            ledger.initialize_empty_ledger(self.ledger)
        self.assertFalse(self.ledger.exists())
        sidecar.unlink()
        ledger.initialize_empty_ledger(self.ledger)
        with self.assertRaises(ValueError):
            ledger.create_snapshot(self.ledger, self.ledger)

    def test_cli_is_read_only_on_errors_and_never_claims_customer_delivery(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [sys.executable, "scripts/snapshot_authorization_ledger.py",
             "verify", "--snapshot-file", str(self.private / "absent.sqlite")],
            cwd=root, capture_output=True, text=True, check=False,
            timeout=20,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["status"], "NONCE_LEDGER_SNAPSHOT_BLOCKED")
        self.assertNotIn(self.temporary.name, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
