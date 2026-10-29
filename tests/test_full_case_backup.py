"""Complete-case backup QA uses FICTIONAL customer/source files and TEST key only.

No off-device production storage, real key custodian, customer contact or
delivery is created by these tests. Authenticated byte restore alone cannot
certify customer-report source completeness or human approval.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts import full_case_backup as backup

try:
    import cryptography
    from cryptography.exceptions import InvalidTag
    CRYPTO = True
except ImportError:
    CRYPTO = False

TEST_KEY=b"FICTIONAL_TEST_RECOVERY_KEY_NOT_OWNER_CUSTODY_2026"

KINDS=(
    "CASE","HISTORY","RESOURCE_INVENTORY","ACTION_ORIGINAL",
    "RESOURCE_ORIGINAL","BUSINESS_EVIDENCE","INBOUND_RECEIPT",
    "SCOPE_AGREEMENT","REPORT","REPORT_RECEIPT","REGISTRY_SNAPSHOT",
    "AUTHORIZATION_LEDGER_SNAPSHOT","MESSAGE_BODY",
)


@unittest.skipUnless(CRYPTO,"Pinned cryptography is required for full-case security QA")
class FullCaseBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.root=self.base/"private-case"
        self.root.mkdir(mode=0o700)
        self.staging=self.base/"encrypted-staging"
        self.staging.mkdir(mode=0o700)
        self.recovered=self.base/"restore-parent"
        self.recovered.mkdir(mode=0o700)
        self.entries=[]
        for i,kind in enumerate(KINDS):
            name=f"evidence/doc-{i:02d}.bin"
            path=self.root/name
            path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            raw=(f"FICTIONAL {kind} record {i}; buyer@example.invalid\n").encode()
            path.write_bytes(raw)
            if os.name!="nt":
                path.chmod(0o600)
            self.entries.append({
                "id":f"qa-{i:02d}", "kind":kind, "path":name,
                "sha256":hashlib.sha256(raw).hexdigest(),
            })
        self.inv=self.root/"backup-inventory.json"
        self.write_inv()
        self.archive=self.staging/"complete-case-TEST.cbak"

    def write_inv(self):
        data={
            "schema":backup.INPUT_SCHEMA,
            "case_id":"CB-FAKE-OWNER-REVIEW-2026",
            "files":self.entries,
            "customer_release_authorized":False,
            "external_send_authorized":False,
        }
        self.inv.write_text(json.dumps(data),encoding="utf-8")
        if os.name!="nt":
            self.inv.chmod(0o600)

    def create(self):
        return backup.create_complete_backup(self.root,self.inv,self.archive,TEST_KEY)

    def test_entire_case_backup_encrypts_all_required_kinds_and_restores_exact_bytes(self):
        result=self.create()
        self.assertEqual(result["file_count"],len(KINDS))
        self.assertFalse(result["offdevice_copy_verified"])
        self.assertFalse(result["independent_restore_verified"])
        self.assertFalse(result["recovery_key_custody_verified"])
        self.assertFalse(result["customer_release_authorized"])
        self.assertEqual(result["backup_sha256"],
                         hashlib.sha256(self.archive.read_bytes()).hexdigest())
        self.assertNotIn(b"buyer@example.invalid",self.archive.read_bytes())
        self.assertNotIn(b"FICTIONAL REPORT",self.archive.read_bytes())
        verified=backup.verify_complete_backup(self.archive,TEST_KEY)
        self.assertEqual(verified["file_count"],len(KINDS))
        self.assertFalse(verified["offdevice_restore_proven"])
        dest=self.recovered/"independent-new-path"
        restored=backup.restore_complete_backup(self.archive,dest,TEST_KEY)
        self.assertIn("RECONCILIATION_REQUIRED",restored["status"])
        self.assertFalse(restored["independent_offdevice_restore_proven"])
        self.assertFalse(restored["customer_release_authorized"])
        self.assertEqual(len(restored["restored_files"]),len(KINDS))
        for entry in self.entries:
            source=self.root/entry["path"]
            output=dest/entry["path"]
            self.assertEqual(output.read_bytes(),source.read_bytes())
            self.assertEqual(restored["restored_files"][entry["id"]],entry["sha256"])
            if os.name!="nt":
                self.assertEqual(output.stat().st_mode & 0o077,0)
        with self.assertRaises(ValueError):
            backup.restore_complete_backup(self.archive,dest,TEST_KEY)

    def test_changed_ciphertext_or_wrong_key_cannot_create_destination(self):
        self.create()
        with self.assertRaises(InvalidTag):
            backup.restore_complete_backup(
                self.archive,self.recovered/"wrong-key",
                b"FICTIONAL_DIFFERENT_WRONG_LONG_KEY_2026",
            )
        self.assertFalse((self.recovered/"wrong-key").exists())
        modified=bytearray(self.archive.read_bytes())
        modified[-19] ^= 0x40
        self.archive.write_bytes(modified)
        if os.name!="nt":
            self.archive.chmod(0o600)
        with self.assertRaises(InvalidTag):
            backup.restore_complete_backup(
                self.archive,self.recovered/"tampered",TEST_KEY,
            )
        self.assertFalse((self.recovered/"tampered").exists())

    def test_missing_registry_or_shared_authorization_ledger_blocks_backup(self):
        for kind in ("REGISTRY_SNAPSHOT","AUTHORIZATION_LEDGER_SNAPSHOT",
                     "HISTORY","REPORT","RESOURCE_INVENTORY"):
            original=self.entries
            self.entries=[r for r in original if r["kind"]!=kind]
            self.write_inv()
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                self.create()
            self.assertFalse(self.archive.exists())
            self.entries=original
        self.write_inv()

    def test_changed_sha_duplicate_ids_and_case_source_link_are_refused(self):
        self.entries[0]["sha256"]="f"*64
        self.write_inv()
        with self.assertRaises(ValueError):
            self.create()
        self.entries[0]["sha256"]=hashlib.sha256(
            (self.root/self.entries[0]["path"]).read_bytes()
        ).hexdigest()
        self.entries[1]["id"]=self.entries[0]["id"]
        self.write_inv()
        with self.assertRaises(ValueError):
            self.create()
        self.entries[1]["id"]="qa-01"
        self.entries[1]["path"]="../escape.bin"
        self.write_inv()
        with self.assertRaises(ValueError):
            self.create()

    def test_archive_destination_must_be_fresh_and_encrypted(self):
        self.create()
        with self.assertRaises(ValueError):
            self.create()
        with self.assertRaises(ValueError):
            backup.restore_complete_backup(
                self.archive,self.root,TEST_KEY,
            )

    def test_source_path_symlink_is_rejected(self):
        if os.name=="nt":
            self.skipTest("Windows symlink privilege is not guaranteed")
        entry=self.entries[0]
        original=self.root/entry["path"]
        original.unlink()
        original.symlink_to(self.root/self.entries[1]["path"])
        with self.assertRaises(ValueError):
            self.create()

    def test_external_approval_is_not_inferred_from_plaintext_inventory(self):
        self.write_inv()
        document=json.loads(self.inv.read_text())
        document["external_send_authorized"]=True
        self.inv.write_text(json.dumps(document))
        if os.name!="nt":
            self.inv.chmod(0o600)
        with self.assertRaises(ValueError):
            self.create()


if __name__=="__main__":
    unittest.main()
