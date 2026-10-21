"""All fixtures are FAKE: no production secrets, source access, or customer cases."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import fy2027_encrypted_backup as m

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

PASSWORD = b"offline-test-ONLY-recovery-phrase-with-extra-entropy"


def make_fixture(root: Path, *, alter: dict | None = None) -> tuple[Path, str, int]:
    source = root / "original"
    source.mkdir()
    raw = b"NoticeId,Sol#,PostedDate\nFAKE,FAKE-123,2026-10-19\n" * 100
    digest = hashlib.sha256(raw).hexdigest()
    original = source / f"FY2027-{digest}.csv"
    original.write_bytes(raw)
    receipt = {
        "schema": "capturebrief-fy2027-private-candidate-retention-v1",
        "source_listing": m.LISTING, "source_url": m.SOURCE_URL,
        "prior_ci_sha256": m.ORIGINAL_SHA256, "prior_ci_run": m.PROVENANCE,
        "observed_at": "2026-10-19T19:44:20.903250Z",
        "downloaded_sha256": digest, "downloaded_bytes": len(raw),
        "retained_original_file": True, "local_file_sha256_verified": True,
        "official_delivery_host": "falextracts.s3.amazonaws.com",
        "redirect_used": True, "source_etag": "FAKE-ETAG",
        "source_last_modified": "2026-10-19T15:00:00Z",
        "operator_path": str(original), "test_override": True,
        "catalog_approved": False, "full_archive_history_verified": False,
        "human_source_review_complete": False,
        "case_release_authorized": False, "external_send_authorized": False,
    }
    receipt.update(alter or {})
    (source / f"FY2027-{digest}.receipt.json").write_bytes(m._canonical_record(receipt))
    return source, digest, len(raw)


@unittest.skipUnless(CRYPTO_AVAILABLE, "isolated backup CI must install pinned cryptography dependency")
class FY2027OfflineEncryptedBackupTests(unittest.TestCase):
    def test_create_verify_restore_exact_original_and_receipt_with_no_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, digest, count = make_fixture(root)
            backup_dir = root / "operator-backups"
            backup_dir.mkdir()
            backup = backup_dir / "private-fy2027.cbak"
            result = m.create_backup(source, backup, PASSWORD,
                                     expected_sha256=digest, expected_bytes=count)
            self.assertEqual(result["status"], "LOCAL_ENCRYPTED_BACKUP_CANDIDATE")
            self.assertFalse(result["offdevice_copy_verified"])
            self.assertFalse(result["independent_restore_test_passed"])
            self.assertFalse(result["independent_key_escrow_verified"])
            self.assertFalse(result["source_catalog_approved"])
            self.assertFalse(result["customer_release_authorized"])
            self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(),
                             result["backup_sha256"])
            self.assertNotIn(b"FAKE-123", backup.read_bytes())
            verified = m.verify_backup(backup, PASSWORD, expected_sha256=digest,
                                       expected_bytes=count)
            self.assertTrue(verified["receipt_integrity_verified"])
            self.assertFalse(verified["independent_offdevice_restore_proven"])
            restored = root / "restore"
            restored.mkdir()
            receipt_before = (source / f"FY2027-{digest}.receipt.json").read_bytes()
            restored_result = m.restore_backup(backup, restored, PASSWORD,
                                                expected_sha256=digest, expected_bytes=count)
            self.assertTrue(restored_result["receipt_bytes_preserved"])
            self.assertFalse(restored_result["independent_offdevice_restore_proven"])
            self.assertEqual((restored / f"FY2027-{digest}.receipt.json").read_bytes(),
                             receipt_before)
            restored_source = restored / f"FY2027-{digest}.csv"
            self.assertEqual(hashlib.sha256(restored_source.read_bytes()).hexdigest(), digest)
            self.assertFalse(bool(restored_source.stat().st_mode & stat.S_IWUSR),
                             "Recovered source must be read-only on Windows and Linux")
            # A replay with the same original bytes is idempotent and preserves receipt.
            m.restore_backup(backup, restored, PASSWORD, expected_sha256=digest,
                             expected_bytes=count)
            self.assertEqual((restored / f"FY2027-{digest}.receipt.json").read_bytes(),
                             receipt_before)

    def test_wrong_passphrase_and_tampered_authenticated_backup_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, digest, count = make_fixture(root)
            backup = root / "safe.cbak"
            m.create_backup(source, backup, PASSWORD, expected_sha256=digest,
                            expected_bytes=count)
            with self.assertRaises(InvalidTag):
                m.verify_backup(backup, b"wrong-passphrase-with-16bytes", expected_sha256=digest,
                                expected_bytes=count)
            raw = bytearray(backup.read_bytes())
            raw[-21] ^= 0x01
            backup.write_bytes(raw)
            with self.assertRaises(InvalidTag):
                m.verify_backup(backup, PASSWORD, expected_sha256=digest,
                                expected_bytes=count)
            restored = root / "restore"
            restored.mkdir()
            with self.assertRaises(InvalidTag):
                m.restore_backup(backup, restored, PASSWORD,
                                 expected_sha256=digest, expected_bytes=count)
            self.assertEqual(list(restored.iterdir()), [])

    def test_header_version_kdf_nonce_length_and_truncation_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, digest, count = make_fixture(root)
            backup = root / "safe.cbak"
            m.create_backup(source, backup, PASSWORD, expected_sha256=digest,
                            expected_bytes=count)
            raw = backup.read_bytes()
            prefix = len(m.MAGIC)
            n = struct.unpack(">I", raw[prefix:prefix + 4])[0]
            head = json.loads(raw[prefix + 4:prefix + 4 + n])
            for mod in ("kdf", "scrypt_cost", "nonce", "extra", "claims"):
                item = dict(head)
                if mod == "kdf":
                    item["kdf"] = "pbkdf2"
                elif mod == "scrypt_cost":
                    item["n"] = 2**25  # must reject before spending huge resources
                elif mod == "nonce":
                    item["nonce_b64"] = "YQ=="
                elif mod == "extra":
                    item["rogue"] = "field"
                else:
                    item["customer_release_authorized"] = True
                new_head = json.dumps(item, sort_keys=True, separators=(",", ":")).encode()
                mutant = m.MAGIC + struct.pack(">I", len(new_head)) + new_head + raw[prefix + 4 + n:]
                backup.write_bytes(mutant)
                with self.subTest(mod=mod), self.assertRaises(ValueError):
                    m.verify_backup(backup, PASSWORD,
                                    expected_sha256=digest, expected_bytes=count)
            for bad in (b"", raw[:10], raw[:-10], raw[:prefix] + b"\xff\xff\xff\xff" + raw[prefix+4:]):
                backup.write_bytes(bad)
                with self.subTest(length=len(bad)), self.assertRaises((ValueError, InvalidTag)):
                    m.verify_backup(backup, PASSWORD,
                                    expected_sha256=digest, expected_bytes=count)

    def test_tampered_source_and_retention_receipt_cannot_be_packaged(self):
        for change in ("catalog_approved", "external_send_authorized", "wrong_sha",
                       "canonical_receipt", "duplicate_field", "original_bytes"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                extra = {}
                if change == "catalog_approved":
                    extra = {"catalog_approved": True}
                elif change == "external_send_authorized":
                    extra = {"external_send_authorized": True}
                elif change == "wrong_sha":
                    extra = {"downloaded_sha256": "0" * 64}
                source, digest, count = make_fixture(root, alter=extra)
                receipt_path = source / f"FY2027-{digest}.receipt.json"
                if change == "canonical_receipt":
                    receipt_path.write_bytes(receipt_path.read_bytes().replace(b"\n", b"\r\n"))
                elif change == "duplicate_field":
                    receipt_path.write_bytes(receipt_path.read_bytes().replace(
                        b'"catalog_approved": false,', b'"catalog_approved": false, "catalog_approved": false,'))
                elif change == "original_bytes":
                    src = source / f"FY2027-{digest}.csv"
                    src.write_bytes(src.read_bytes().replace(b"FAKE-123", b"FAKE-789"))
                with self.assertRaises(ValueError):
                    m.create_backup(source, root / "safe.cbak", PASSWORD,
                                    expected_sha256=digest, expected_bytes=count)
                self.assertFalse((root / "safe.cbak").exists())

    def test_source_symlink_output_conflicts_and_restore_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, digest, count = make_fixture(root)
            backup = root / "safe.cbak"
            backup.write_bytes(b"do not replace")
            with self.assertRaises(FileExistsError):
                m.create_backup(source, backup, PASSWORD,
                                expected_sha256=digest, expected_bytes=count)
            self.assertEqual(backup.read_bytes(), b"do not replace")
            backup.unlink()
            try:
                (root / "source-link").symlink_to(source, target_is_directory=True)
            except (OSError, NotImplementedError):
                pass
            else:
                with self.assertRaises(ValueError):
                    m.create_backup(root / "source-link", backup, PASSWORD,
                                    expected_sha256=digest, expected_bytes=count)
            m.create_backup(source, backup, PASSWORD, expected_sha256=digest,
                            expected_bytes=count)
            restored = root / "restore"
            restored.mkdir()
            destination = restored / f"FY2027-{digest}.csv"
            destination.write_bytes(b"unchanged existing confidential source")
            with self.assertRaises(ValueError):
                m.restore_backup(backup, restored, PASSWORD,
                                 expected_sha256=digest, expected_bytes=count)
            self.assertEqual(destination.read_bytes(), b"unchanged existing confidential source")
            self.assertEqual(len(list(restored.iterdir())), 1)

    def test_no_interactive_secret_or_secret_file_inside_public_repo(self):
        with self.assertRaises(ValueError):
            m._read_secret(None) if not sys.stdin.isatty() else m._private_path(m.REPO / "test.key", directory=False)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "passphrase.txt"
            p.write_bytes(PASSWORD)
            if os.name == "nt":
                # Simple mode bits do not prove restricted inherited NTFS ACLs.
                # Never read a plaintext secret file on Windows by default.
                with self.assertRaisesRegex(ValueError, "Windows passphrase files"):
                    m._read_secret(str(p))
            else:
                p.chmod(0o644)
                with self.assertRaises(ValueError):
                    m._read_secret(str(p))
                p.chmod(0o600)
                self.assertEqual(m._read_secret(str(p)), PASSWORD)


if __name__ == "__main__":
    unittest.main()
