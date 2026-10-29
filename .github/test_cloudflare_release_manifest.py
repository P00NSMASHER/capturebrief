"""Network-free, adversarial complete-manifest release acceptance tests."""
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("GITHUB_SHA", "a" * 40)
import cloudflare_light_smoke as smoke


class CloudflareCompleteManifestTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        old = os.getcwd()
        os.chdir(tmp.name)
        self.addCleanup(os.chdir, old)
        rows = []
        for name in (*smoke.SOURCES, "assets/brand/fictional-extra.webp"):
            path = Path("dist") / name
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = (b"at most ten businesses\nPreparing an email draft does not send an inquiry\n"
                   if name == "index.html" else ("FICTIONAL:" + name).encode())
            path.write_bytes(raw)
            rows.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest(),
                         "bytes": len(raw)})
        self.expected = {
            "buildInfoVersion": "CaptureBrief-standalone-build-v1.0.0",
            "company": "CaptureBrief", "operator": "JP Enterprises",
            "canonical": smoke.BASE, "group": "https://group.retallyrecovery.com/",
            "purchasePolicy": "SCOPE_FIRST_PENDING_SOURCE_READINESS",
            "sourceRepository": "P00NSMASHER/capturebrief", "sourceBranch": "gh-pages",
            "sourceCommit": smoke.EXPECTED_SHA, "deployContext": "cloudflare-pages",
            "builtAt": "2026-10-29T10:00:00Z",
            "publicFileCount": len(rows), "sourceContentFingerprint": "1" * 64,
            "publicSourceFingerprint": "2" * 64, "files": rows,
        }
        Path("dist/build-info.json").write_text(json.dumps(self.expected), encoding="utf-8")

    def inspect(self, manifest):
        def read(path):
            return (Path("dist") / path).read_bytes(), {}
        with patch.object(smoke, "fetch", side_effect=read), patch.object(
                smoke, "assert_private_not_published", return_value=None):
            return smoke.inspect_release(manifest)

    def test_positive_exact_local_manifest(self):
        output = self.inspect(copy.deepcopy(self.expected))
        self.assertEqual(output["form_posts"], 0)
        self.assertFalse(output["external_send_authorized"])

    def test_removed_noncritical_asset_stays_blocked_even_if_count_adjusted(self):
        forged = copy.deepcopy(self.expected)
        forged["files"].pop()
        forged["publicFileCount"] -= 1
        with self.assertRaises(AssertionError):
            self.inspect(forged)

    def test_altered_noncritical_asset_digest_stays_blocked(self):
        forged = copy.deepcopy(self.expected)
        forged["files"][-1]["sha256"] = "f" * 64
        with self.assertRaises(AssertionError):
            self.inspect(forged)

    def test_mismatched_source_and_artifact_fingerprints_stay_blocked(self):
        for name in ("sourceContentFingerprint", "publicSourceFingerprint"):
            with self.subTest(name=name):
                forged = copy.deepcopy(self.expected)
                forged[name] = "f" * 64
                with self.assertRaises(AssertionError):
                    self.inspect(forged)

    def test_build_timestamp_variance_is_allowed(self):
        actual = copy.deepcopy(self.expected)
        actual["builtAt"] = "2026-10-29T10:09:01Z"
        self.assertEqual(self.inspect(actual)["source_count"], len(smoke.SOURCES))


if __name__ == "__main__":
    unittest.main()
