"""Fictional full-case backup acceptance: not production storage or real customer."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts import full_case_private_backup as backup
from capturebrief_core.accepted_case_release import SCHEMA as RELEASE_SCHEMA
from tests.test_accepted_case_release import AcceptedCaseReleaseTests

try:
    import cryptography
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

TEST_PHRASE = b"NOT_A_REAL_SECRET_TEST_ONLY_full_case_offdevice_candidate_2026"


@unittest.skipUnless(HAS_CRYPTO, "Pinned cryptography required for complete-case backup QA")
class FullCasePrivateBackupTests(unittest.TestCase):
    def setUp(self):
        # The established accepted-case fixture contains only invented identity,
        # documents and independent signers and mocks real core readiness.
        self.fixture = AcceptedCaseReleaseTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tmp.cleanup)
        self.root = self.fixture.root
        self.private = Path(self.fixture.tmp.name) / "encrypted-output"
        self.private.mkdir(mode=0o700)
        self.inventory = self.root / "pre-approval-inventory.json"
        self.output = self.private / "case-snapshot.cbak"
        self.rows = [
            {key: row[key] for key in ("id", "kind", "path", "sha256")}
            for row in self.fixture.manifest["files"]
            if row["kind"] not in {"OFFDEVICE_BACKUP", "RECOVERY_RECEIPT"}
        ]
        self._save_inventory()

    def _save_inventory(self):
        self.inventory.write_text(json.dumps({
            "schema": backup.SCHEMA,
            "case_sha256": self.fixture.manifest["case_sha256"],
            "files": self.rows,
        }, sort_keys=True))
        if os.name != "nt":
            self.inventory.chmod(0o600)

    def _create(self):
        return backup.create_backup(
            self.root, self.inventory, self.output, TEST_PHRASE,
        )

    def test_full_approval_input_inventory_recovers_exact_files_without_sends(self):
        created = self._create()
        self.assertEqual(created["status"], "FULL_CASE_LOCAL_ENCRYPTED_SNAPSHOT_CREATED")
        self.assertEqual(created["file_count"], len(self.rows))
        self.assertEqual(created["backup_sha256"], hashlib.sha256(self.output.read_bytes()).hexdigest())
        self.assertFalse(created["complete_source_history_verified"])
        self.assertFalse(created["customer_release_authorized"])
        self.assertFalse(created["offdevice_restore_verified"])
        self.assertNotIn(b"FICTIONAL original notice", self.output.read_bytes())
        self.assertNotIn(b"buyer@example.com", self.output.read_bytes())
        self.assertEqual(
            backup.verify_backup(self.output, TEST_PHRASE)["file_count"], len(self.rows)
        )
        restored = self.private / "restored-new"
        result = backup.restore_backup(self.output, restored, TEST_PHRASE)
        self.assertEqual(result["status"], "FULL_CASE_LOCALLY_RESTORED_RECONCILIATION_REQUIRED")
        self.assertTrue(result["reconciliation_required_before_use"])
        self.assertFalse(result["independent_offdevice_restore_proven"])
        for row in self.rows:
            self.assertEqual(
                (restored / row["path"]).read_bytes(), (self.root / row["path"]).read_bytes()
            )
            if os.name != "nt":
                self.assertEqual((restored / row["path"]).stat().st_mode & 0o077, 0)
        with self.assertRaises(ValueError):
            backup.restore_backup(self.output, restored, TEST_PHRASE)

    def test_bad_password_tampering_never_creates_private_plaintext(self):
        self._create()
        target = self.private / "should-not-exist"
        with self.assertRaises(Exception):
            backup.restore_backup(self.output, target, b"wrong_password_but_strong_length_123456")
        self.assertFalse(target.exists())
        old = self.output.read_bytes()
        corrupted = bytearray(old)
        corrupted[-5] ^= 0x40
        self.output.write_bytes(corrupted)
        with self.assertRaises(Exception):
            backup.restore_backup(self.output, target, TEST_PHRASE)
        self.assertFalse(target.exists())
        self.output.write_bytes(old)
        self.assertEqual(backup.verify_backup(self.output, TEST_PHRASE)["file_count"], len(self.rows))

    def test_modified_missing_and_unlisted_case_source_block_before_backup(self):
        changed = self.root / "actionB.bin"
        changed.write_bytes(b"ALTERED")
        with self.assertRaises(Exception):
            self._create()
        self.assertFalse(self.output.exists())
        changed.write_bytes(b"FICTIONAL amendment one")
        if os.name != "nt":
            changed.chmod(0o600)
        self.rows.pop()
        self._save_inventory()
        with self.assertRaises(ValueError):
            self._create()
        self.assertFalse(self.output.exists())

    def test_extra_authority_reused_id_unsafe_path_and_wrong_case_hash_block(self):
        original = list(self.rows)
        self.rows[0] = {**self.rows[0], "customer_release_authorized": True}
        self._save_inventory()
        with self.assertRaises(ValueError):
            self._create()
        self.rows = list(original)
        self.rows[1] = {**self.rows[1], "id": self.rows[0]["id"]}
        self._save_inventory()
        with self.assertRaises(ValueError):
            self._create()
        self.rows = list(original)
        self.rows[1] = {**self.rows[1], "path": "../outside/attachment.pdf"}
        self._save_inventory()
        with self.assertRaises(ValueError):
            self._create()
        self.rows = list(original)
        self._save_inventory()
        inv = json.loads(self.inventory.read_text())
        inv["case_sha256"] = "f" * 64
        self.inventory.write_text(json.dumps(inv))
        if os.name != "nt":
            self.inventory.chmod(0o600)
        with self.assertRaises(ValueError):
            self._create()
        self.assertFalse(self.output.exists())

    def test_no_external_destination_and_no_restore_overwrite(self):
        with self.assertRaises(Exception):
            backup.create_backup(
                self.root, self.inventory,
                Path(__file__).resolve().parents[1] / "unapproved-public.cbak",
                TEST_PHRASE,
            )
        self.assertFalse(self.output.exists())
        self._create()
        occupied = self.private / "occupied"
        occupied.mkdir()
        with self.assertRaises(ValueError):
            backup.restore_backup(self.output, occupied, TEST_PHRASE)

    def test_source_directory_link_alias_rejected(self):
        alias = Path(self.fixture.tmp.name) / "linked-case"
        try:
            alias.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Filesystem does not permit directory symlinks")
        with self.assertRaises(Exception):
            backup.create_backup(alias, alias / self.inventory.name, self.output, TEST_PHRASE)
        self.assertFalse(self.output.exists())

    def test_existing_delivery_authorization_and_review_still_fail_for_fictional_case(self):
        # Backup operates BEFORE a real restore/report review: never promote
        # the existing fictional case to an externally sendable report.
        self._create()
        with self.assertRaises(Exception):
            self.fixture.check(mock_core=False)
        self.assertEqual(self.fixture.manifest["schema"], RELEASE_SCHEMA)


if __name__ == "__main__":
    unittest.main()
