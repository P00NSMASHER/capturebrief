"""Fictional-only offline verification of the live private-cloud drill.

All GitHub access is mocked. A public fake token and public fictional case
data are used; no production secrets, customers, paid services or sends.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import qa_live_capturebrief_state_secret as qa
from scripts import github_private_custody as custody
from tests.test_github_private_custody import FakePrivateGitHub

try:
    import cryptography  # noqa: F401
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class LivePrivateStateSmokeOfflineTests(unittest.TestCase):
    TOKEN = "FICTIONAL_GITHUB_TEST_TOKEN_NO_ACCESS"

    def run_offline(self, provider, callback):
        def inspect(t):
            return custody.inspect_private_destination(t, transport=provider)

        def upload(path, token):
            return custody.store_encrypted_backup(path, token, transport=provider)

        def retrieve(sha, path, token):
            return custody.retrieve_encrypted_backup(
                sha, path, token, transport=provider
            )

        with (
            patch.dict(os.environ, {"CAPTUREBRIEF_STATE_TOKEN": self.TOKEN}),
            patch.object(qa, "inspect_private_destination", side_effect=inspect),
            patch.object(qa, "store_encrypted_backup", side_effect=upload),
            patch.object(qa, "retrieve_encrypted_backup", side_effect=retrieve),
        ):
            return callback()

    @unittest.skipUnless(CRYPTO_AVAILABLE, "Pinned cryptography required for encrypted test")
    def test_actual_AES_GCM_fake_uploaded_retrieved_restored_and_rehashed(self):
        fake = FakePrivateGitHub()
        def exercise():
            initial = qa.preflight()
            self.assertTrue(initial["private_repository_verified"])
            self.assertFalse(initial["write_access_exercised"])
            sent = qa.encrypt_upload()
            self.assertEqual(sent["file_count"], 13)
            self.assertFalse(sent["customer_release_authorized"])
            self.assertEqual(fake.writes, 1)
            original_bytes = next(iter(fake.files.values()))
            self.assertNotIn(b"buyer@example.invalid", original_bytes)
            self.assertEqual(
                hashlib.sha256(original_bytes).hexdigest(), sent["sha256"]
            )
            restored = qa.independently_restore(sent["sha256"])
            self.assertEqual(restored["file_count"], 13)
            self.assertTrue(restored["independent_runner"])
            self.assertFalse(restored["production_recovery_key_proven"])
            self.assertFalse(restored["customer_release_authorized"])
            self.assertEqual(fake.writes, 1)
        self.run_offline(fake, exercise)

    @unittest.skipUnless(CRYPTO_AVAILABLE, "Pinned cryptography required for encrypted test")
    def test_missing_secret_or_invalid_private_destination_cannot_upload(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            qa.preflight()
        fake = FakePrivateGitHub()
        fake.private = False
        def blocked():
            with self.assertRaises(custody.PrivateStorageBlocked):
                qa.encrypt_upload()
        self.run_offline(fake, blocked)
        self.assertEqual(fake.writes, 0)

    @unittest.skipUnless(CRYPTO_AVAILABLE, "Pinned cryptography required for encrypted test")
    def test_tampered_remote_ciphertext_blocks_independent_restore(self):
        fake = FakePrivateGitHub()
        def exercise():
            sent = qa.encrypt_upload()
            fake.corrupt_readback = True
            with self.assertRaises(custody.PrivateStorageBlocked):
                qa.independently_restore(sent["sha256"])
            self.assertEqual(fake.writes, 1)
        self.run_offline(fake, exercise)

    def test_cross_runner_restore_requires_lowercase_exact_digest(self):
        with self.assertRaises(ValueError):
            qa.independently_restore("123")
        with self.assertRaises(ValueError):
            qa.independently_restore("A" * 64)
        with self.assertRaises(ValueError):
            qa.independently_restore("f" * 63 + "/")

    def test_cli_without_secret_fails_closed_with_sanitized_status(self):
        env = os.environ.copy()
        env.pop("CAPTUREBRIEF_STATE_TOKEN", None)
        out = subprocess.run(
            [sys.executable, "scripts/qa_live_capturebrief_state_secret.py",
             "preflight"],
            env=env, cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, check=False, timeout=20,
        )
        self.assertEqual(out.returncode, 2)
        body = json.loads(out.stdout)
        self.assertEqual(body["status"], qa.ERROR_STATUS)
        self.assertFalse(body["external_send_performed"])
        self.assertFalse(body["customer_release_authorized"])
        self.assertNotIn("ghp_", out.stdout + out.stderr)
        self.assertNotIn("github_pat_", out.stdout + out.stderr)
        self.assertNotIn("buyer@", out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
