"""Adversarial regression for the real GitHub Pages publication scope.

Previous CI falsely expected generated Cloudflare dist/privacy.html on GitHub
Pages. The genuine red check returned HTTP 404 for that non-source path.
"""
import tempfile
import unittest
from pathlib import Path

from capturebrief_publication_paths import discover_source_html


class PublicationSourcePathsTests(unittest.TestCase):
    def test_generated_cloudflare_html_never_becomes_shared_pages_requirement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in (
                "index.html", "decision-evidence.html", "permitplate/index.html",
                "abvm/index.html", "examples/source.html", "dist/index.html",
                "dist/privacy.html", "dist/nested/index.html", "qa-output/live.html",
                ".github/internal.html", ".git/injected.html", "dist-safety/index.html",
            ):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(name, encoding="utf-8")
            paths = discover_source_html(root, already_expected=("index.html", "decision-evidence.html"))
            self.assertEqual(paths, [
                "abvm/index.html", "dist-safety/index.html",
                "examples/source.html", "permitplate/index.html",
            ])

    def test_post_build_artifacts_do_not_change_expected_source_population(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text("public", encoding="utf-8")
            baseline = discover_source_html(root)
            (root / "dist").mkdir()
            (root / "dist" / "privacy.html").write_text("generated", encoding="utf-8")
            (root / "dist" / "index.html").write_text("generated", encoding="utf-8")
            self.assertEqual(discover_source_html(root), baseline)
            self.assertEqual(baseline, ["index.html"])

    def test_only_exact_top_level_build_roots_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("docs/dist/index.html", "dist/index.html", "qa-output/test.html", "support.html"):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("test", encoding="utf-8")
            self.assertEqual(discover_source_html(root), ["docs/dist/index.html", "support.html"])


if __name__ == "__main__":
    unittest.main()
