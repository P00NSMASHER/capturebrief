"""Buyer copy and intake contracts for the source/rule/history upgrade."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.tags = []; self.feed(text)
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class TraceSiteTests(unittest.TestCase):
    def test_existing_intake_contract_is_preserved(self):
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        page = Page(text)
        forms = [a for tag, a in page.tags if tag == "form"]
        self.assertEqual(1, len(forms))
        self.assertEqual("pursuit-qa-intake", forms[0]["name"])
        self.assertEqual("POST", forms[0]["method"])
        self.assertEqual("/thanks.html", forms[0]["action"])
        self.assertEqual("true", forms[0]["data-netlify"])
        fields = {a.get("name"): a for tag, a in page.tags if tag in {"input", "select", "textarea"}}
        for name in ["email", "company", "public_opportunity", "current_posture", "assumption_1", "public_only_confirmation"]:
            self.assertIn("required", fields[name], name)
        for n in range(2, 6):
            self.assertIn(f"assumption_{n}", fields)
            self.assertNotIn("required", fields[f"assumption_{n}"])
        self.assertFalse(any(a.get("type") == "file" for tag, a in page.tags))

    def test_offer_not_changed_by_positioning(self):
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        for phrase in ["$149", "No automatic renewal", "before any charge", "Public-source only", "Human-supervised", "14-day", "relevant rule version"]:
            self.assertIn(phrase, text)

    def test_primary_sample_points_to_history(self):
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count('href="decision-history.html"'), 4)
        self.assertTrue((ROOT / "decision-history.html").is_file())
        self.assertIn("bid decision rests on", text)

    def test_sample_is_unambiguously_fictional(self):
        text = (ROOT / "decision-history.html").read_text(encoding="utf-8")
        for phrase in ["Fictional product example", "synthetic", "not a live solicitation", "DEMO-01", "human-supervised", "does not by itself prove source authenticity", "No automatic renewal"]:
            self.assertIn(phrase, text)
        self.assertIn("<details>", text)
        self.assertIn('name="viewport"', text)


if __name__ == "__main__":
    unittest.main()
