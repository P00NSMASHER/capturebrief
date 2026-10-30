"""Adversarial URL-source contract: raw publisher URL bytes must remain canonical.

No HTTP calls, API tokens, real cases, storage writes or external sends.
"""
from __future__ import annotations

import unittest

from capturebrief_core.data_services import ACTIVE_DOWNLOAD
from capturebrief_core.source_policy import (
    SourcePolicyError, classify_sam_url, require_approved_automation,
    require_approved_extract_delivery,
)


class RawSourceURLPolicyTests(unittest.TestCase):
    def test_exact_first_party_urls_still_classify(self):
        self.assertEqual(
            classify_sam_url("https://api.sam.gov/opportunities/v2/search"),
            "SAM_PUBLIC_API",
        )
        self.assertEqual(classify_sam_url(ACTIVE_DOWNLOAD),
                         "SAM_DATA_SERVICES_EXTRACT")
        self.assertEqual(require_approved_extract_delivery(ACTIVE_DOWNLOAD, ACTIVE_DOWNLOAD),
                         "sam.gov")

    def test_python_parser_must_not_sanitize_raw_source_before_allowlist(self):
        clean = "https://api.sam.gov/opportunities/v2/search"
        bad = (
            "\x01" + clean,  # leading C0 is silently stripped by urllib.parse
            " " + clean,     # leading space is also silently stripped
            clean + "\r",   # trailing CR silently stripped
            clean.replace("/search", "/se\tarch"),
            clean.replace("api.sam.gov", "api.sam.\ngov"),
        )
        for raw in bad:
            with self.subTest(repr=repr(raw)):
                self.assertEqual(classify_sam_url(raw), "UNAPPROVED")
                with self.assertRaises(SourcePolicyError):
                    require_approved_automation(raw)

    def test_extract_entrypoint_cannot_promote_sanitized_raw_host(self):
        altered = ACTIVE_DOWNLOAD.replace("https://sam.gov", "https://sa\nm.gov")
        self.assertNotEqual(altered, ACTIVE_DOWNLOAD)
        self.assertEqual(classify_sam_url(altered), "UNAPPROVED")
        with self.assertRaises(SourcePolicyError):
            require_approved_extract_delivery(altered, altered)

    def test_url_like_object_cannot_impersonate_an_approved_raw_string(self):
        class MisleadingURL:
            def __str__(self):
                return "https://api.sam.gov/opportunities/v2/search"

        self.assertEqual(classify_sam_url(MisleadingURL()), "UNAPPROVED")
        with self.assertRaises(SourcePolicyError):
            require_approved_automation(MisleadingURL())


if __name__ == "__main__":
    unittest.main()
