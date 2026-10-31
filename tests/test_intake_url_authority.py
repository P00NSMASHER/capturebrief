"""Public opportunity URL authority must remain browser-safe and reviewer-readable.

All fixtures are synthetic. No network access, buyer data or payment paths.
"""
from __future__ import annotations

import unittest

from capturebrief_core.intake import IntakeError, build_case_from_intake
from capturebrief_core.request_draft import create_unverified_case
from tests.test_request_draft import draft

WHEN = "2026-10-31T12:00:00+00:00"


def _intake(url: str) -> dict[str, str]:
    return {
        "company": "Fictional Acquisition Corp",
        "email": "reviewer@example.com",
        "public_opportunity": url,
        "current_posture": "HOLD",
        "public_only_confirmation": "yes",
        "assumption_1": "The currently posted notice may have changed.",
    }


class IntakeUrlAuthorityTests(unittest.TestCase):
    def test_valid_public_sources_retain_exact_literal_and_no_claimed_proof(self):
        for url in (
            "https://sam.gov/opp/123/view",
            "https://sam.gov:443/opp/123/view?tab=details#attachments",
            "http://agency.example.org/public/rfq?id=2",
        ):
            with self.subTest(url=url):
                case = build_case_from_intake(_intake(url), submitted_at=WHEN)
                self.assertEqual(case["intake"]["public_opportunity"], url)
                self.assertEqual(case["sources"], [])
                self.assertEqual(case["assumptions"][0]["evidence_state"], "UNPROVEN")

    def test_malformed_port_and_browser_differential_urls_fail_closed(self):
        samples = (
            "https://sam.gov:not-a-port/opp/123",
            "https://sam.gov:65536/opp/123",
            "https://sam.gov:0/opp/123",
            "https://sam.gov:/opp/123",
            "https://sam.gov\\other/opp/123",
            "https://sam.gov/path with spaces",
            "https://sam.gov/a\tb",
            "https://sam.gov/a\nb",
            "https://sam.gov/a\u2028b",
            "https://sam.gov/a\x7fb",
        )
        for url in samples:
            with self.subTest(url=repr(url)):
                with self.assertRaises(IntakeError):
                    build_case_from_intake(_intake(url), submitted_at=WHEN)

    def test_clipboard_draft_inherits_the_same_url_gate(self):
        for url in ("https://sam.gov:bad/opp", "https://sam.gov/a\tb"):
            with self.subTest(url=repr(url)), self.assertRaises(IntakeError):
                create_unverified_case(draft(public_url=url), submitted_at=WHEN)

    def test_legacy_local_and_ip_denials_unchanged(self):
        for url in (
            "https://localhost:443/private",
            "https://127.0.0.1/private",
            "https://user:password@sam.gov/opp/123",
            "https://internal.local/opp/123",
        ):
            with self.subTest(url=url), self.assertRaises(IntakeError):
                build_case_from_intake(_intake(url), submitted_at=WHEN)


if __name__ == "__main__":
    unittest.main()
