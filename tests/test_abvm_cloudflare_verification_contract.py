"""Regression guard for token-authored Pages releases bypassing push-triggered QA.

GitHub intentionally suppresses other Actions push triggers for GITHUB_TOKEN
commits. This contract ensures the ABVM pack publisher runs the real
read-only Cloudflare artifact check in its *own* workflow after publication.
The actual edge/source verdict is provided by cloudflare_light_smoke.py.
"""
from pathlib import Path
import unittest


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github" / "workflows" / "abvm-school-pack.yml"
)


class ABVMCloudflareVerificationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_production_verifier_runs_after_token_authored_publish(self):
        publish = self.workflow.index("git push origin HEAD:gh-pages")
        verifier = self.workflow.index(
            "- name: Verify exact CaptureBrief Cloudflare release after ABVM refresh"
        )
        self.assertLess(publish, verifier)
        self.assertIn("python .github/cloudflare_light_smoke.py", self.workflow[verifier:])

    def test_verifier_uses_actual_pages_revision_not_main_event_sha(self):
        verify_step = self.workflow.split(
            "- name: Verify exact CaptureBrief Cloudflare release after ABVM refresh",
            1,
        )[1]
        self.assertIn('export GITHUB_SHA="$(git rev-parse HEAD)"', verify_step)
        self.assertIn("node build-standalone-site.test.js", verify_step)
        self.assertIn("node build-standalone-site.js", verify_step)
        self.assertIn("test_cloudflare_edge_integrity -v", verify_step)

    def test_fail_closed_without_contact_or_checkout(self):
        verify_step = self.workflow.split(
            "- name: Verify exact CaptureBrief Cloudflare release after ABVM refresh",
            1,
        )[1]
        self.assertIn("set -euo pipefail", verify_step)
        self.assertNotIn("continue-on-error:", verify_step)
        self.assertNotIn("|| true", verify_step)
        for prohibited in ("SAM_API_KEY", "stripe", "mailto:", "curl -X POST"):
            self.assertNotIn(prohibited, verify_step)
        self.assertIn("timeout-minutes: 12", self.workflow)


if __name__ == "__main__":
    unittest.main()
