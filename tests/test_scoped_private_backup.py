"""Fake-source tests for portable encrypted per-pursuit backup, no cloud access."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from tests.test_scoped_source import fixture, live_style_capture
from scripts import scoped_private_backup as backup

try:
    from cryptography.exceptions import InvalidTag
    import cryptography
    CRYPTO = True
except ImportError:
    CRYPTO = False

PASSPHRASE = b"TEST_ONLY_recovery_phrase_2026_private_not_a_real_secret"


@unittest.skipUnless(CRYPTO, "Pinned cryptography dependency is required for backup QA")
class ScopedBackupTests(unittest.TestCase):
    def make_backup(self, root: Path):
        case_file, scoped_root, case = fixture(root)
        live_style_capture(case, scoped_root)
        backup_dir = root / "encrypted"
        backup_dir.mkdir(mode=0o700)
        archive = backup_dir / "case.cbak"
        result = backup.create_backup(case_file, scoped_root, archive, PASSPHRASE)
        return case_file, scoped_root, archive, result

    def test_create_verify_and_independent_path_restore_rehashes_all_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case_path, scoped, archive, result = self.make_backup(root)
            self.assertEqual(result["status"], "SCOPED_LOCAL_ENCRYPTED_BACKUP_CREATED")
            self.assertFalse(result["offdevice_copy_verified"])
            self.assertFalse(result["independent_restore_verified"])
            self.assertFalse(result["customer_release_authorized"])
            self.assertEqual(result["backup_sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertNotIn(b"buyer@example.com", archive.read_bytes())
            checked = backup.verify_backup(archive, PASSPHRASE)
            self.assertEqual(checked["case_tag"], result["case_tag"])
            self.assertFalse(checked["independent_offdevice_restore_proven"])
            output = root / "fresh-restore"
            restored = backup.restore_backup(archive, output, PASSPHRASE)
            self.assertFalse(restored["independent_offdevice_restore_proven"])
            self.assertEqual((output / "intake-case.json").read_bytes(), case_path.read_bytes())
            original = scoped / ("case-" + result["case_tag"])
            replayed = output / "evidence"
            names = sorted(f.name for f in original.iterdir())
            self.assertEqual(sorted(f.name for f in replayed.iterdir()), names)
            for item in original.iterdir():
                self.assertEqual((replayed / item.name).read_bytes(), item.read_bytes())
                if os.name != "nt":
                    self.assertEqual((replayed / item.name).stat().st_mode & 0o077, 0)
            with self.assertRaises(ValueError):
                backup.restore_backup(archive, output, PASSPHRASE)

    def test_wrong_passphrase_and_modified_ciphertext_never_create_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, _, archive, _ = self.make_backup(root)
            with self.assertRaises(InvalidTag):
                backup.verify_backup(archive, b"wrong_and_incorrect_recovery_password_88888")
            original = archive.read_bytes()
            altered = bytearray(original)
            altered[-11] ^= 0x41
            archive.write_bytes(altered)
            with self.assertRaises(InvalidTag):
                backup.restore_backup(archive, root / "should-never-exist", PASSPHRASE)
            self.assertFalse((root / "should-never-exist").exists())
            archive.write_bytes(original)
            self.assertTrue(backup.verify_backup(archive, PASSPHRASE)["file_count"] >= 2)

    def test_forbidden_public_paths_unknown_files_and_missing_original_reject_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case_file, scoped, archive, _ = self.make_backup(root)
            with self.assertRaises(ValueError):
                backup.create_backup(case_file, scoped, archive, PASSPHRASE)
            another_dir = root / "encrypted" / "extra.cbak"
            case_dir = next(scoped.iterdir())
            malicious = case_dir / "customer-copy.txt"
            malicious.write_text("fake customer notes")
            with self.assertRaises(ValueError):
                backup.create_backup(case_file, scoped, another_dir, PASSPHRASE)
            malicious.unlink()
            with self.assertRaises(ValueError):
                backup.create_backup(case_file, scoped,
                                     Path(__file__).resolve().parents[1] / "bad.cbak",
                                     PASSPHRASE)

    def test_corrupt_source_filename_cannot_silently_pass_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case_file, scoped, _, _ = self.make_backup(root)
            case_folder = next(scoped.iterdir())
            source = next(case_folder.glob("sam-current-*.json"))
            content = json.loads(source.read_text())
            content["customer_release_authorized"] = True
            source.write_text(json.dumps(content))
            source.chmod(0o600)
            # This input is a valid named file but its contents have been modified.
            # A safe backup must NOT preserve a forged claim as accepted evidence.
            with self.assertRaises(ValueError):
                backup.create_backup(case_file, scoped, root / "encrypted" / "tamper.cbak", PASSPHRASE)


if __name__ == "__main__":
    unittest.main()
