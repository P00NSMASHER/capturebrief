"""Synthetic offline recovery tests: not an actual production/off-device restore."""
from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from capturebrief_core.free_trial import reserve_free_check, TrialConflict
from scripts import free_check_registry_backup as backup
from tests.test_free_trial import NOW, REVIEW, private_pair

PHRASE = b"TEST_ONLY_free_registry_recovery_long_phrase_not_real_secret"

try:
    import cryptography
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


@unittest.skipUnless(HAS_CRYPTO, "Pinned cryptography is required for registry recovery QA")
class FreeRegistryRecoveryTests(unittest.TestCase):
    def _prepare(self, root: Path):
        private = root / "operator-only"
        private.mkdir(mode=0o700)
        case, receipt, _ = private_pair(root)
        registry = private / "free-checks.sqlite"
        reserve_free_check(
            registry, case=case, receipt=receipt,
            reviewed_business_key="domain:example.com",
            identity_review_sha256=REVIEW, observed_at=NOW,
        )
        backup_dir = root / "encrypted"
        backup_dir.mkdir(mode=0o700)
        saved = backup_dir / "snapshot.cbak"
        return private, registry, saved, case, receipt

    def test_wal_consistent_snapshot_restores_existing_identity_and_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private, registry, saved, case, receipt = self._prepare(root)
            with sqlite3.connect(registry) as active:
                self.assertEqual(active.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
                result = backup.create_backup(registry, saved, PHRASE)
                self.assertEqual(result["reservation_count"], 1)
                self.assertFalse(result["customer_release_authorized"])
                self.assertTrue(result["reconciliation_required_before_use"])
                self.assertEqual(result["backup_sha256"], hashlib.sha256(saved.read_bytes()).hexdigest())
                self.assertNotIn(b"free_check_reservations", saved.read_bytes())
                self.assertEqual(backup.verify_backup(saved, PHRASE)["reservation_count"], 1)
            recovered = private / "restored.sqlite"
            status = backup.restore_backup(saved, recovered, PHRASE)
            self.assertTrue(status["reconciliation_required_before_use"])
            self.assertFalse(status["independent_offdevice_restore_proven"])
            with sqlite3.connect(recovered) as restored:
                self.assertEqual(restored.execute(
                    "SELECT COUNT(*) FROM free_check_reservations"
                ).fetchone()[0], 1)
            repeated = reserve_free_check(
                recovered, case=case, receipt=receipt,
                reviewed_business_key="domain:example.com",
                identity_review_sha256=REVIEW, observed_at=NOW + timedelta(hours=1),
            )
            self.assertEqual(repeated["status"], "ALREADY_RESERVED_REVIEW_REQUIRED")
            with self.assertRaises(TrialConflict):
                reserve_free_check(
                    recovered, case=case, receipt=receipt,
                    reviewed_business_key="domain:newalias.com",
                    identity_review_sha256=REVIEW, observed_at=NOW + timedelta(hours=1),
                )
            with self.assertRaises(ValueError):
                backup.restore_backup(saved, recovered, PHRASE)

    def test_bad_phrase_tamper_and_sidecar_never_write_restored_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private, registry, saved, *_ = self._prepare(root)
            backup.create_backup(registry, saved, PHRASE)
            dest = private / "dest.sqlite"
            with self.assertRaises(Exception):
                backup.restore_backup(saved, dest, b"wrong_but_sufficiently_long_password_12345")
            self.assertFalse(dest.exists())
            old = saved.read_bytes()
            corrupt = bytearray(old)
            corrupt[-5] ^= 0x40
            saved.write_bytes(corrupt)
            with self.assertRaises(Exception):
                backup.restore_backup(saved, dest, PHRASE)
            self.assertFalse(dest.exists())
            saved.write_bytes(old)
            journal = private / "dest.sqlite-wal"
            journal.write_bytes(b"stale WAL")
            with self.assertRaises(ValueError):
                backup.restore_backup(saved, dest, PHRASE)
            self.assertFalse(dest.exists())

    def test_extra_tables_and_unauthorized_flags_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, registry, saved, *_ = self._prepare(root)
            with sqlite3.connect(registry) as db:
                db.execute("CREATE TABLE other_stored_data (secret TEXT)")
            with self.assertRaises(ValueError):
                backup.create_backup(registry, saved, PHRASE)
            self.assertFalse(saved.exists())
            with sqlite3.connect(registry) as db:
                db.execute("DROP TABLE other_stored_data")
                db.execute("PRAGMA ignore_check_constraints=ON")
                db.execute("UPDATE free_check_reservations SET customer_release_authorized=1")
            with self.assertRaises(ValueError):
                backup.create_backup(registry, saved, PHRASE)
            self.assertFalse(saved.exists())

    def test_invalid_digest_and_more_than_ten_rows_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, registry, saved, *_ = self._prepare(root)
            with sqlite3.connect(registry) as db:
                db.execute("UPDATE free_check_reservations SET business_sha256='bad'")
            with self.assertRaises(ValueError):
                backup.create_backup(registry, saved, PHRASE)
            with sqlite3.connect(registry) as db:
                db.execute("UPDATE free_check_reservations SET business_sha256=?", ("1" * 64,))
                for i in range(10):
                    digests = [hashlib.sha256((str(i) + str(j)).encode()).hexdigest() for j in range(4)]
                    db.execute("INSERT INTO free_check_reservations VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (digests[0], digests[1], digests[2], digests[3], "f" * 64,
                         "2026-10-29T00:00:00Z", "RESERVED_REVIEW_REQUIRED", 0, 0, 0, 0))
            with self.assertRaises(ValueError):
                backup.create_backup(registry, saved, PHRASE)
            self.assertFalse(saved.exists())

    def test_public_paths_wrong_extension_and_nonexistent_db_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private, registry, saved, *_ = self._prepare(root)
            with self.assertRaises(ValueError):
                backup.create_backup(registry, Path(__file__).resolve().parents[1] / "public.cbak", PHRASE)
            with self.assertRaises(ValueError):
                backup.create_backup(private / "missing.sqlite", saved, PHRASE)
            with self.assertRaises(ValueError):
                backup.restore_backup(saved, private / "wrong.json", PHRASE)
            self.assertFalse(saved.exists())


if __name__ == "__main__":
    unittest.main()
