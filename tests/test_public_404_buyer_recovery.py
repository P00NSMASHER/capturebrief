"""Source-bound 404 buyer recovery contract; no network or external dependencies."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.links = []

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "meta" and fields.get("name"):
            self.meta[fields["name"].lower()] = fields.get("content", "")
        if tag == "a":
            self.links.append(fields)


class Public404BuyerRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.not_found = PageParser()
        cls.not_found.feed((ROOT / "404.html").read_text(encoding="utf-8"))
        cls.home = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.sample = (ROOT / "decision-evidence-sample.html").read_text(encoding="utf-8")

    def test_missing_page_is_not_indexable(self):
        directives = {s.strip().lower() for s in self.not_found.meta.get("robots", "").split(",")}
        self.assertIn("noindex", directives)
        self.assertNotIn("index", directives)

    def test_recovery_links_promote_current_primary_public_proof(self):
        sample_links = [a for a in self.not_found.links if "sample.html" in a.get("href", "")]
        self.assertGreaterEqual(len(sample_links), 2)
        self.assertTrue(all(a.get("href") == "decision-evidence-sample.html" for a in sample_links))
        self.assertTrue((ROOT / "decision-evidence-sample.html").is_file())
        self.assertIn('href="decision-evidence-sample.html"', self.home)
        self.assertIn('rel="canonical" href="https://capturebrief.netlify.app/decision-evidence-sample.html"', self.sample)
        self.assertIn("Illustrative format — not a real solicitation.", self.sample)

    def test_recovery_request_targets_real_form_not_email(self):
        requests = [a for a in self.not_found.links if a.get("href") == "index.html#request"]
        self.assertGreaterEqual(len(requests), 2)
        self.assertTrue(all("by email" not in a.get("aria-label", "").lower() for a in requests))
        self.assertIn('<form name="pursuit-qa-intake"', self.home)
        self.assertIn('id="request"', self.home)


if __name__ == "__main__":
    unittest.main()
