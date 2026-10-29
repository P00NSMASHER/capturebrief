"""No-network, fictional-only private GitHub backup-custody security tests."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import github_private_custody as custody


class FakePrivateGitHub:
    """Small deterministic REST simulation: never contacts GitHub."""
    def __init__(self):
        self.visible = True
        self.private = True
        self.branch = "main"
        self.fork = False
        self.size = 5
        self.push = True
        self.files = {}
        self.writes = 0
        self.corrupt_readback = False
        self.forbidden_token = False

    def __call__(self, method, path, token, body=None):
        if token != "FICTIONAL_GITHUB_TEST_TOKEN_NO_ACCESS":
            self.forbidden_token = True
            raise AssertionError("Only the synthetic credential belongs in CI")
        if path == custody.API_PREFIX and method == "GET":
            if not self.visible:
                return 404, None
            return 200, {
                "full_name": custody.DESTINATION_REPOSITORY,
                "private": self.private,
                "visibility": "private" if self.private else "public",
                "default_branch": self.branch,
                "archived": False,
                "disabled": False,
                "fork": self.fork,
                "size": self.size,
                "permissions": {"push": self.push},
            }
        if method == "GET" and path.startswith(custody.API_PREFIX + "/contents/"):
            digest = path.rsplit("/", 1)[1].split(".cbak")[0]
            if path not in self.files:
                return 404, None
            raw = self.files[path]
            if self.corrupt_readback:
                raw = raw[:1] + b"MUTATED" + raw[2:]
            return 200, {
                "type": "file", "size": len(raw), "encoding": "base64",
                "content": base64.b64encode(raw).decode("ascii"),
                "path": path.split("/contents/")[1].split("?")[0],
            }
        if method == "PUT" and path.startswith(custody.API_PREFIX + "/contents/"):
            if body is None or body.get("branch") != "main" or "sha" in body:
                raise AssertionError("Provider must only publish new immutable ciphertext")
            read_path = path + "?ref=main"
            if read_path in self.files:
                raise AssertionError("An old ciphertext must never be replaced")
            raw = base64.b64decode(body["content"], validate=True)
            self.files[read_path] = raw
            self.writes += 1
            return 201, {"content": {"path": path.split("/contents/")[1]}}
        raise AssertionError("Unexpected network request: " + method + " " + path)


class GitHubPrivateCustodyTests(unittest.TestCase):
    TOKEN = "FICTIONAL_GITHUB_TEST_TOKEN_NO_ACCESS"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "owner-private"
        self.root.mkdir(mode=0o700)
        self.source = self.root / "fictional-case.cbak"
        self.raw = custody.MAGIC + b"NOT_ACTUAL_AES_ENCRYPTED_FAKE_TEST_ONLY"
        self.source.write_bytes(self.raw)
        if os.name != "nt":
            self.source.chmod(0o600)
        self.provider = FakePrivateGitHub()

    def test_permitplate_provider_reused_without_sharing_its_private_repository(self):
        result = custody.inspect_private_destination(
            self.TOKEN, transport=self.provider
        )
        self.assertTrue(result["same_provider_as_permitplate"])
        self.assertTrue(result["separate_from_permitplate_state"])
        self.assertTrue(result["private_repo_verified"])
        self.assertEqual(result["destination"], "P00NSMASHER/capturebrief-state")
        self.assertNotEqual(custody.DESTINATION_REPOSITORY, "P00NSMASHER/permitplate-state")
        self.assertEqual(self.provider.writes, 0)
        self.assertFalse(result["production_backup_present"])

    def test_dedicated_repository_missing_public_wrong_branch_or_permission_blocks(self):
        for change in (
            {"visible": False}, {"private": False}, {"branch": "gh-pages"},
            {"fork": True}, {"size": custody.MAX_REPOSITORY_KB + 1},
            {"push": False},
        ):
            with self.subTest(case=change):
                fake = FakePrivateGitHub()
                for k, v in change.items():
                    setattr(fake, k, v)
                with self.assertRaises(custody.PrivateStorageBlocked):
                    custody.inspect_private_destination(
                        self.TOKEN, transport=fake
                    )
                self.assertEqual(fake.writes, 0)

    def test_upload_idempotently_verifies_exact_ciphertext_and_downloads_new_path(self):
        original = custody.store_encrypted_backup(
            self.source, self.TOKEN, transport=self.provider
        )
        digest = hashlib.sha256(self.raw).hexdigest()
        self.assertEqual(original["sha256"], digest)
        self.assertEqual(original["bytes"], len(self.raw))
        self.assertTrue(original["new_write"])
        self.assertEqual(self.provider.writes, 1)
        self.assertFalse(original["production_restore_verified"])
        self.assertFalse(original["customer_release_authorized"])
        self.assertEqual(
            custody.store_encrypted_backup(
                self.source, self.TOKEN, transport=self.provider
            )["new_write"], False
        )
        self.assertEqual(self.provider.writes, 1)
        dest = self.root / "new-independent-ciphertext.cbak"
        obtained = custody.retrieve_encrypted_backup(
            digest, dest, self.TOKEN, transport=self.provider
        )
        self.assertEqual(dest.read_bytes(), self.raw)
        self.assertFalse(obtained["independent_device_restore_verified"])
        self.assertFalse(obtained["external_send_performed"])
        with self.assertRaises(custody.PrivateStorageBlocked):
            custody.retrieve_encrypted_backup(
                digest, dest, self.TOKEN, transport=self.provider
            )
        self.assertEqual(self.provider.writes, 1)
        if os.name != "nt":
            self.assertEqual(dest.stat().st_mode & 0o077, 0)

    def test_tampered_remote_bytes_wrong_digest_and_missing_backup_block(self):
        valid = custody.store_encrypted_backup(
            self.source, self.TOKEN, transport=self.provider
        )
        self.provider.corrupt_readback = True
        with self.assertRaises(custody.PrivateStorageBlocked):
            custody.store_encrypted_backup(
                self.source, self.TOKEN, transport=self.provider
            )
        download = self.root / "should-not-exist.cbak"
        with self.assertRaises(custody.PrivateStorageBlocked):
            custody.retrieve_encrypted_backup(
                valid["sha256"], download, self.TOKEN, transport=self.provider
            )
        self.assertFalse(download.exists())
        self.provider.corrupt_readback = False
        with self.assertRaises(custody.PrivateStorageBlocked):
            custody.retrieve_encrypted_backup(
                "f" * 64, download, self.TOKEN, transport=self.provider
            )
        self.assertFalse(download.exists())

    def test_unencrypted_public_symlink_large_and_wrong_extension_source_rejected(self):
        base = self.source.read_bytes()
        self.source.write_bytes(b"PLAIN PRIVATE CUSTOMER CONTENT")
        with self.assertRaises(custody.PrivateStorageBlocked):
            custody.store_encrypted_backup(
                self.source, self.TOKEN, transport=self.provider
            )
        self.source.write_bytes(custody.MAGIC + b"B" * custody.MAX_ENCRYPTED_BYTES)
        with self.assertRaises(custody.PrivateStorageBlocked):
            custody.store_encrypted_backup(
                self.source, self.TOKEN, transport=self.provider
            )
        self.source.write_bytes(base)
        if os.name != "nt":
            self.source.chmod(0o600)
        alias = self.root / "alias.cbak"
        try:
            alias.symlink_to(self.source)
        except (OSError, NotImplementedError):
            self.skipTest("Local symlinks are unavailable")
        with self.assertRaises(Exception):
            custody.store_encrypted_backup(
                alias, self.TOKEN, transport=self.provider
            )
        self.assertEqual(self.provider.writes, 0)

    def test_cli_without_capturebrief_token_fails_closed_without_leak(self):
        env = os.environ.copy()
        env.pop("CAPTUREBRIEF_STATE_TOKEN", None)
        cmd = [sys.executable, "scripts/github_private_custody.py", "preflight"]
        result = subprocess.run(
            cmd, env=env, cwd=Path(__file__).resolve().parents[1],
            text=True, capture_output=True, timeout=20
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            json.loads(result.stdout)["status"], "PRIVATE_CLOUD_BACKUP_BLOCKED"
        )
        self.assertNotIn("GITHUB_TEST_TOKEN", result.stdout + result.stderr)
        self.assertEqual(self.provider.writes, 0)

    def test_bad_digest_and_oversized_repository_metadata_rejected(self):
        for value in ("", "0" * 63, "ab/../1" + "f" * 55, None):
            with self.subTest(value=value):
                with self.assertRaises(custody.PrivateStorageBlocked):
                    custody._remote_path(value)
        self.provider.size = 80000
        with self.assertRaises(custody.PrivateStorageBlocked):
            custody.store_encrypted_backup(
                self.source, self.TOKEN, transport=self.provider
            )
        self.assertEqual(self.provider.writes, 0)


if __name__ == "__main__":
    unittest.main()
