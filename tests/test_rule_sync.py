from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from capturebrief_core.rule_registry import load_source_catalog, list_rule_versions
from capturebrief_core.rule_sync import (
    MAX_DITA_BYTES,
    build_pinned_dita_request,
    fetch_pinned_gsa_rule,
    sync_pinned_gsa_rule,
)

DITA = b'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE dita
  PUBLIC "-//OASIS//DTD DITA Composite//EN" "ditabase.dtd">
<dita><concept id="FAR_52_204_21">
<title><ph props="autonumber">52.204-21</ph> Basic Safeguarding of Covered Contractor Information Systems.</title>
<conbody outputclass="clause">
<p id="prescription">As prescribed in 4.1903, insert the following clause:</p>
<p id="heading" outputclass="Ctr_SmCaps">Basic Safeguarding of Covered Contractor Information Systems (Nov 2021)</p>
<p id="a">Synthetic test paragraph.</p>
</conbody></concept></dita>'''


class RuleSyncTests(unittest.TestCase):
    def setUp(self):
        self.catalog_path = Path(__file__).parents[1] / "RULE-SOURCE-CATALOG.json"
        self.catalog = load_source_catalog(self.catalog_path)
        self.temp = tempfile.TemporaryDirectory()
        self.registry = Path(self.temp.name) / "rules.sqlite"

    def tearDown(self):
        self.temp.cleanup()

    def request(self):
        return build_pinned_dita_request(
            self.catalog,
            source_id="gsa-far-dita",
            citation="52.204-21",
        )

    def fetcher(self, url, max_bytes):
        req = self.request()
        self.assertEqual(url, req["raw_url"])
        self.assertEqual(max_bytes, MAX_DITA_BYTES)
        self.assertIn(req["revision"], url)
        self.assertNotIn("/main/", url)
        return DITA, url

    def test_request_is_exact_revision_and_no_caller_url(self):
        req = self.request()
        self.assertTrue(req["raw_url"].startswith("https://raw.githubusercontent.com/GSA/GSA-Acquisition-FAR/"))
        self.assertIn("/da52ccbbe114e1f031a7f4c59195c508dbfa485f/", req["raw_url"])
        self.assertTrue(req["raw_url"].endswith("/dita/52.204-21.dita"))
        self.assertFalse(req["mutable_ref_used"])
        self.assertFalse(req["caller_url_used"])
        self.assertEqual(req["agency"], "FAR Council")

    def test_fetch_derives_embedded_edition(self):
        record, receipt = fetch_pinned_gsa_rule(
            self.catalog,
            source_id="gsa-far-dita",
            citation="52.204-21",
            observed_at="2026-09-21T17:00:00Z",
            fetcher=self.fetcher,
        )
        self.assertEqual(record["edition"], "Nov 2021")
        self.assertEqual(record["edition_basis"], "EMBEDDED_RULE_TEXT")
        self.assertEqual(record["source_revision"], "da52ccbbe114e1f031a7f4c59195c508dbfa485f")
        self.assertEqual(receipt["source_sha256"], record["source_sha256"])
        self.assertFalse(receipt["mutable_ref_used"])
        self.assertFalse(receipt["caller_url_used"])
        self.assertFalse(receipt["credentials_used"])

    def test_sync_is_idempotent(self):
        first = sync_pinned_gsa_rule(
            self.registry, self.catalog_path,
            source_id="gsa-far-dita", citation="52.204-21",
            observed_at="2026-09-21T17:00:00Z", fetcher=self.fetcher,
        )
        second = sync_pinned_gsa_rule(
            self.registry, self.catalog_path,
            source_id="gsa-far-dita", citation="52.204-21",
            observed_at="2026-09-21T17:00:00Z", fetcher=self.fetcher,
        )
        self.assertEqual(first["registry_result"], "INSERTED")
        self.assertEqual(second["registry_result"], "EXISTS")
        self.assertEqual(len(list_rule_versions(self.registry, citation="52.204-21")), 1)

    def test_redirect_or_url_change_is_rejected(self):
        def redirect(url, max_bytes):
            return DITA, "https://example.com/52.204-21.dita"
        with self.assertRaises(ValueError):
            fetch_pinned_gsa_rule(
                self.catalog, source_id="gsa-far-dita", citation="52.204-21",
                observed_at="2026-09-21T17:00:00Z", fetcher=redirect,
            )

    def test_oversized_response_is_rejected(self):
        def huge(url, max_bytes):
            return b"x" * (MAX_DITA_BYTES + 1), url
        with self.assertRaises(ValueError):
            fetch_pinned_gsa_rule(
                self.catalog, source_id="gsa-far-dita", citation="52.204-21",
                observed_at="2026-09-21T17:00:00Z", fetcher=huge,
            )

    def test_wrong_citation_in_fetched_file_is_rejected(self):
        wrong = DITA.replace(b"52.204-21", b"52.204-22")
        def fetch(url, max_bytes):
            return wrong, url
        with self.assertRaises(ValueError):
            fetch_pinned_gsa_rule(
                self.catalog, source_id="gsa-far-dita", citation="52.204-21",
                observed_at="2026-09-21T17:00:00Z", fetcher=fetch,
            )

    def test_path_injection_citation_is_rejected(self):
        with self.assertRaises(ValueError):
            build_pinned_dita_request(
                self.catalog, source_id="gsa-far-dita",
                citation="../../52.204-21",
            )

    def test_mutable_revision_in_catalog_is_rejected(self):
        catalog = copy.deepcopy(self.catalog)
        next(x for x in catalog["sources"] if x["source_id"] == "gsa-far-dita")["revision"] = "main"
        with self.assertRaises(ValueError):
            build_pinned_dita_request(catalog, source_id="gsa-far-dita", citation="52.204-21")

    def test_arbitrary_repository_is_rejected(self):
        catalog = copy.deepcopy(self.catalog)
        row = next(x for x in catalog["sources"] if x["source_id"] == "gsa-far-dita")
        row["repository"] = "someone/random-far"
        row["repository_url"] = "https://github.com/someone/random-far"
        with self.assertRaises(ValueError):
            build_pinned_dita_request(catalog, source_id="gsa-far-dita", citation="52.204-21")

    def test_non_dita_catalog_source_is_rejected(self):
        with self.assertRaises(ValueError):
            build_pinned_dita_request(
                self.catalog, source_id="acqagent-rfo-deviations", citation="52.204-21",
            )


if __name__ == "__main__":
    unittest.main()
