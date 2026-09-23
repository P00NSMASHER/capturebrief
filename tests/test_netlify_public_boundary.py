from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/"dist"

PUBLIC_ROOT={
    "404.html",
    "_headers",
    "_redirects",
    "data-handling.html",
    "decision-evidence-sample.html",
    "favicon.svg",
    "index.html",
    "privacy.html",
    "robots.txt",
    "sample.html",
    "site.webmanifest",
    "sitemap.xml",
    "terms.html",
    "thanks.html",
    "assets",
}
FORBIDDEN={
    "capturebrief_core","tests","fixtures",".github",
    "PRODUCT-CORE.md","RULE-SOURCES.md","RULE-SOURCE-CATALOG.json",
    "DECISION-EVIDENCE.md","OUTCOME-LEDGER.md",
    "BUSINESS-MODEL-v6.md","BUSINESS-MODEL-v7.md",
    "SOURCE-POLICY.md","REFERENCE-REVIEW.md",
}

class NetlifyPublicBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if DIST.exists():
            shutil.rmtree(DIST)
        bash = shutil.which("bash")
        if bash is None:
            raise unittest.SkipTest("Netlify build script requires Bash; Linux CI covers this boundary")
        subprocess.run([bash,"netlify-build.sh"],cwd=ROOT,check=True)

    @classmethod
    def tearDownClass(cls):
        if DIST.exists():
            shutil.rmtree(DIST)

    def test_netlify_publishes_dist_not_repo_root(self):
        config=(ROOT/"netlify.toml").read_text(encoding="utf-8")
        self.assertIn('command = "bash netlify-build.sh"',config)
        self.assertIn('publish = "dist"',config)
        self.assertNotIn('publish = "."',config)

    def test_public_root_is_explicit_whitelist(self):
        actual={p.name for p in DIST.iterdir()}
        self.assertEqual(actual,PUBLIC_ROOT)

    def test_internal_product_files_are_not_published(self):
        for name in FORBIDDEN:
            self.assertFalse((DIST/name).exists(),name)

    def test_public_site_still_contains_intake_and_sample(self):
        index=(DIST/"index.html").read_text(encoding="utf-8")
        sample=(DIST/"decision-evidence-sample.html").read_text(encoding="utf-8")
        self.assertIn('name="pursuit-qa-intake"',index)
        self.assertIn("Know what your bid decision",index)
        self.assertIn("Four separate evidence planes",sample)

    def test_public_assets_are_present(self):
        assets=DIST/"assets"
        self.assertTrue((assets/"styles.css").is_file())
        self.assertTrue((assets/"main.js").is_file())
        self.assertGreater(sum(1 for p in assets.rglob("*") if p.is_file()),2)

if __name__=="__main__":
    unittest.main()
