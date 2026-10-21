from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.package_public_release import PUBLIC_FILES, PUBLIC_SOURCE_PATHS, package_release


class PublicReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.output = Path(self.temp.name) / "release"
        self.git("init", "--quiet")
        self.git("config", "user.name", "Release Test")
        self.git("config", "user.email", "release-test@example.invalid")
        for name in {PUBLIC_SOURCE_PATHS.get(name, name) for name in PUBLIC_FILES}:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Test public content: " + name, encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "test public fixture")
        self.sha = self.git("rev-parse", "HEAD").strip()
        dist = self.root / "dist"
        dist.mkdir()
        for name in PUBLIC_FILES:
            dest = dist / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.root / PUBLIC_SOURCE_PATHS.get(name, name), dest)

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True, text=True).stdout

    def package(self):
        return package_release(self.root, self.output, self.sha)

    def symlink_or_skip(self, path, target, *, target_is_directory=False):
        try:
            path.symlink_to(target, target_is_directory=target_is_directory)
        except OSError as exc:
            if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
                self.skipTest("symbolic-link creation is not enabled for this Windows session")
            raise

    def test_exact_public_files_and_hashes(self):
        receipt = self.package()
        payload = self.output / receipt["archive"]
        self.assertEqual(hashlib.sha256(payload.read_bytes()).hexdigest(), receipt["archive_sha256"])
        self.assertFalse(receipt["deployed"])
        with zipfile.ZipFile(payload) as z:
            self.assertEqual(set(z.namelist()), PUBLIC_FILES | {"release-manifest.json"})
            manifest = json.loads(z.read("release-manifest.json"))
            self.assertEqual(manifest["source_commit"], self.sha)
            for row in manifest["files"]:
                data = z.read(row["path"])
                self.assertEqual(row["sha256"], hashlib.sha256(data).hexdigest())
                self.assertEqual(row["bytes"], len(data))

    def test_x402_discovery_aliases_are_pinned_to_the_only_approved_sources(self):
        self.assertEqual({
            ".well-known/x402": "x402/pa-entity/.well-known/x402",
            "openapi.json": "x402/pa-entity/openapi.json",
        }, PUBLIC_SOURCE_PATHS)
        receipt = self.package()
        with zipfile.ZipFile(self.output / receipt["archive"]) as archive:
            for alias, source in PUBLIC_SOURCE_PATHS.items():
                self.assertEqual(archive.read(alias), archive.read(source))
                self.assertEqual(archive.read(alias), (self.root / source).read_bytes())
            self.assertFalse(receipt["deployed"])
            self.assertFalse(receipt["contains_internal_product_files"])

    def test_tampered_x402_discovery_alias_or_canonical_file_is_rejected(self):
        for path in ("openapi.json", ".well-known/x402",
                     "x402/pa-entity/openapi.json",
                     "x402/pa-entity/.well-known/x402"):
            with self.subTest(path=path):
                target = self.root / "dist" / path
                original = target.read_bytes()
                try:
                    target.write_bytes(b"unexpected x402 copy")
                    with self.assertRaisesRegex(ValueError, "pinned source"):
                        self.package()
                finally:
                    target.write_bytes(original)

    def test_extra_x402_discovery_path_does_not_expand_public_allowlist(self):
        path = self.root / "dist" / "x402" / "unreviewed-secret.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
        with self.assertRaisesRegex(ValueError, "allowlist mismatch"):
            self.package()

    def test_edited_x402_origin_cannot_be_packaged_from_old_commit(self):
        source = self.root / "x402/pa-entity/openapi.json"
        source.write_text("changed uncommitted discovery content")
        with self.assertRaisesRegex(ValueError, "uncommitted changes"):
            self.package()

    def test_rebuild_is_byte_deterministic(self):
        first = self.package()
        second = package_release(self.root, Path(self.temp.name)/"again", self.sha)
        self.assertEqual(first["archive_sha256"], second["archive_sha256"])

    def test_internal_file_is_rejected(self):
        (self.root / "dist" / "OUTBOUND-COMMUNICATIONS.md").write_text("internal policy")
        with self.assertRaises(ValueError):
            self.package()

    def test_unreviewed_asset_is_rejected(self):
        (self.root / "dist" / "assets" / "customer.json").write_text("{}")
        with self.assertRaises(ValueError):
            self.package()

    def test_missing_asset_is_rejected(self):
        (self.root / "dist" / "assets" / "main.js").unlink()
        with self.assertRaises(ValueError):
            self.package()

    def test_changed_built_bytes_are_rejected(self):
        (self.root / "dist" / "index.html").write_text("unreviewed page")
        with self.assertRaises(ValueError):
            self.package()

    def test_symlink_file_is_rejected(self):
        path = self.root / "dist" / "index.html"
        path.unlink()
        self.symlink_or_skip(path, self.root / "index.html")
        with self.assertRaises(ValueError):
            self.package()

    def test_symlink_dist_is_rejected(self):
        (self.root / "dist").rename(self.root / "staged")
        self.symlink_or_skip(
            self.root / "dist", self.root / "staged", target_is_directory=True
        )
        with self.assertRaises(ValueError):
            self.package()

    def test_wrong_commit_is_rejected(self):
        with self.assertRaises(ValueError):
            package_release(self.root, self.output, "a" * 40)

    def test_dirty_tracked_source_is_rejected(self):
        (self.root / "index.html").write_text("not committed")
        with self.assertRaises(ValueError):
            self.package()

    def test_does_not_overwrite_prior_release(self):
        first = self.package()
        with self.assertRaises(FileExistsError):
            self.package()
        self.assertEqual(hashlib.sha256((self.output / first["archive"]).read_bytes()).hexdigest(),
                         first["archive_sha256"])


if __name__ == "__main__":
    unittest.main()
