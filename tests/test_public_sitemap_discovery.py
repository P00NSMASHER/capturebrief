"""Offline canonical sitemap QA for high-intent CaptureBrief proof pages."""
from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://capturebrief.netlify.app"
SITEMAP_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def canonical_locs() -> list[str]:
    tree = ET.parse(ROOT / "sitemap.xml")
    return [entry.text or "" for entry in tree.findall(".//s:loc", SITEMAP_NS)]


class PublicSitemapProofDiscoveryTests(unittest.TestCase):
    def test_both_homepage_proof_examples_are_canonical_and_listed(self):
        homepage = (ROOT / "index.html").read_text(encoding="utf-8")
        locations = canonical_locs()
        for file in ("decision-evidence-sample.html", "sample.html"):
            with self.subTest(proof=file):
                url = f"{ORIGIN}/{file}"
                self.assertIn(f'href="{file}"', homepage)
                proof = (ROOT / file).read_text(encoding="utf-8")
                self.assertIn('name="robots" content="index,follow"', proof)
                self.assertIn(f'rel="canonical" href="{url}"', proof)
                self.assertIn(url, locations)

    def test_sitemap_has_unique_public_canonicals_and_excludes_receipts(self):
        locations = canonical_locs()
        self.assertEqual(len(locations), len(set(locations)), "Sitemap has duplicate URLs")
        self.assertGreaterEqual(len(locations), 6)
        for url in locations:
            with self.subTest(url=url):
                parsed = urlsplit(url)
                self.assertEqual((parsed.scheme, parsed.netloc), ("https", "capturebrief.netlify.app"))
                self.assertFalse(parsed.query or parsed.fragment or parsed.username or parsed.password)
                self.assertTrue(parsed.path == "/" or (ROOT / parsed.path.lstrip("/")).is_file())
        self.assertNotIn(f"{ORIGIN}/thanks.html", locations, "Noindex submission receipt must not be surfaced")
        receipt = (ROOT / "thanks.html").read_text(encoding="utf-8")
        self.assertIn('name="robots" content="noindex"', receipt)

    def test_sitemap_is_part_of_real_public_build_and_robot_entrypoint(self):
        build = (ROOT / "netlify-build.sh").read_text(encoding="utf-8")
        self.assertIn('"sitemap.xml"', build)
        self.assertIn('"decision-evidence-sample.html"', build)
        robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
        self.assertIn(f"Sitemap: {ORIGIN}/sitemap.xml", robots)


if __name__ == "__main__":
    unittest.main()
