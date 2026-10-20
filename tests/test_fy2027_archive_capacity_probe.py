"""Entirely synthetic tests for FY2027 source-size planning; no live downloads."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from scripts.fy2027_archive_capacity_probe import (
    CANDIDATE_YEARS, inspect_archive_header, probe_many,
)


class FakeResponse:
    def __init__(self, url, *, status=206, headers=None, body=b"F"):
        self._url=url
        self.status=status
        self.headers=headers or {"Content-Range": "bytes 0-0/12345", "Content-Length": "1"}
        self._body=body
        self.read_calls=[]
        self.closed=False
    def geturl(self): return self._url
    def read(self, count):
        self.read_calls.append(count)
        if count>2: raise AssertionError("A metadata probe attempted to read more than two bytes")
        b=self._body[:count]
        self._body=self._body[count:]
        return b
    def __enter__(self): return self
    def __exit__(self, *args):
        self.closed=True
        return False


class SourceCapacityTests(unittest.TestCase):
    def test_exact_unapproved_34_year_candidate_without_future_years(self):
        self.assertEqual(len(CANDIDATE_YEARS), 34)
        self.assertEqual(CANDIDATE_YEARS[:4], (1969, 1970, 1980, 1981))
        self.assertEqual(CANDIDATE_YEARS[-1], 2027)
        self.assertNotIn(2028, CANDIDATE_YEARS)
        self.assertNotIn(2029, CANDIDATE_YEARS)
        self.assertNotIn(2030, CANDIDATE_YEARS)

    def test_one_byte_only_and_no_public_release(self):
        generated=[]
        def opener(request, *, timeout):
            self.assertEqual(request.get_header("Range"), "bytes=0-0")
            self.assertTrue(request.full_url.startswith(
                "https://sam.gov/api/prod/fileextractservices/v1/api/download/"))
            response=FakeResponse(request.full_url)
            generated.append(response)
            return response
        r=inspect_archive_header(2027, opener=opener)
        self.assertEqual(r["origin_object_bytes"], 12345)
        self.assertEqual(r["bytes_downloaded"], 1)
        self.assertEqual(r["transport_host"], "sam.gov")
        self.assertEqual(generated[0].read_calls, [2])
        self.assertTrue(generated[0].closed)
        self.assertFalse(r["publisher_original_verified"])
        self.assertFalse(r["catalog_approved"])

    def test_partial_size_claim_requires_exact_range_headers(self):
        for headers, body in (
            ({"Content-Range": "bytes 0-1/100", "Content-Length": "2"}, b"x"),
            ({"Content-Range": "bytes 0-0/*", "Content-Length": "1"}, b"x"),
            ({"Content-Range": "bytes 0-0/0", "Content-Length": "1"}, b"x"),
            ({"Content-Range": "bytes 0-0/100", "Content-Length": "2"}, b"x"),
            ({"Content-Range": "bytes 0-0/100", "Content-Length": "1"}, b"xx"),
            ({"Content-Range": "bytes 0-0/100000000001", "Content-Length": "1"}, b"x"),
        ):
            def opener(req, *, timeout):
                return FakeResponse(req.full_url, headers=headers, body=body)
            with self.subTest(headers=headers, body=body), self.assertRaises(ValueError):
                inspect_archive_header(2027, opener=opener)

    def test_range_ignored_never_consumes_full_csv(self):
        opened=[]
        def opener(req, *, timeout):
            response=FakeResponse(req.full_url, status=200,
                                  headers={"Content-Length": "900000000"}, body=b"body")
            opened.append(response)
            return response
        r=inspect_archive_header(2027, opener=opener)
        self.assertEqual(r["status"], "RANGE_NOT_PROVEN")
        self.assertIsNone(r["origin_object_bytes"])
        self.assertEqual(opened[0].read_calls, [])
        self.assertTrue(opened[0].closed)

    def test_unapproved_redirect_rejected_and_secret_error_is_redacted(self):
        def spoofed(req, *, timeout):
            return FakeResponse("https://evil.example/public?X-Amz-Credential=SENSITIVE_SECRET")
        summary=probe_many([2027], opener=spoofed)
        rec=summary["single_byte_observations"][0]
        self.assertEqual(rec["status"], "SOURCE_METADATA_UNAVAILABLE")
        self.assertEqual(rec["error_type"], "SourcePolicyError")
        self.assertNotIn("SENSITIVE_SECRET", repr(summary))
        self.assertFalse(summary["FY2027_full_catalog_certified"])
        self.assertFalse(summary["external_send_authorized"])

    def test_publisher_claims_never_depend_on_full_synthetic_metadata(self):
        def opener(req, *, timeout):
            return FakeResponse(req.full_url)
        r=probe_many(list(CANDIDATE_YEARS), opener=opener)
        self.assertTrue(r["complete_metadata_coverage"])
        self.assertEqual(r["requested_year_count"], 34)
        self.assertEqual(r["confirmed_metadata_years_sum_bytes"], 34 * 12345)
        self.assertEqual(r["total_archive_bytes_only_if_all_metadata_confirmed"], 34 * 12345)
        for key in ("original_bytes_retained", "independent_human_catalog_reviewed",
                    "publisher_originals_verified", "active_extract_budget_included",
                    "disk_space_checked", "source_index_updated", "FY2027_full_catalog_certified",
                    "external_send_authorized", "customer_release_authorized"):
            self.assertFalse(r[key], key)

    def test_partial_subset_must_not_claim_complete_history(self):
        def opener(req, *, timeout):
            return FakeResponse(req.full_url)
        r=probe_many([1969, 2027], opener=opener)
        self.assertEqual(r["confirmed_one_byte_metadata_count"], 2)
        self.assertFalse(r["complete_metadata_coverage"])
        self.assertIsNone(r["total_archive_bytes_only_if_all_metadata_confirmed"])

    def test_year_scope_injection_and_duplicates_rejected(self):
        for years in ([2028], [2029], [2030], [1970,1970], [], ["2027"], [2027.0]):
            with self.subTest(years=years), self.assertRaises(ValueError):
                probe_many(years)
        with self.assertRaises(ValueError):
            inspect_archive_header(2028)


    def test_frozen_all_year_public_metadata_receipt_is_not_source_approval(self):
        path = Path(__file__).resolve().parents[1] / (
            "research/fy2027_archive_capacity_observation_20261020.json"
        )
        receipt = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            receipt["source_actions_run"],
            "https://github.com/P00NSMASHER/capturebrief/actions/runs/39350338311",
        )
        years = receipt["year_size_bytes"]
        self.assertEqual(len(years), 34)
        self.assertEqual(sorted(map(int, (key[2:] for key in years))),
                         sorted(CANDIDATE_YEARS))
        self.assertEqual(sum(years.values()), 20333624076)
        self.assertEqual(receipt["archive_size_sum_bytes"], 20333624076)
        self.assertEqual(receipt["bytes_read_per_year"], 1)
        self.assertTrue(receipt["archive_metadata_years_complete"])
        for blocked in (
            "original_source_files_retrieved", "active_extract_included",
            "sqlite_index_size_included", "backup_storage_included",
            "disk_encryption_verified",
            "source_publisher_authenticity_independently_established",
            "independent_human_catalog_approval", "source_index_updated",
            "full_catalog_claim_authorized", "customer_release_authorized",
        ):
            self.assertIs(receipt[blocked], False, blocked)


if __name__ == "__main__":
    unittest.main()
