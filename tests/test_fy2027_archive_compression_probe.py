"""Offline invented-byte tests only. No live SAM reads in unit tests."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import fy2027_archive_compression_probe as m


class FakeSourceResponse:
    def __init__(self, url, *, status=206, start=0, end=127, total=10_000,
                 headers=None, body=None):
        self.url = url
        self.status = status
        self.headers = (headers if headers is not None else {
            "Content-Range": f"bytes {start}-{end}/{total}",
            "Content-Length": str(end - start + 1),
            "Content-Encoding": "identity",
        })
        self.body = (body if body is not None else b"A" * (end - start + 1))
        self.calls = []
        self.closed = False

    def geturl(self):
        return self.url

    def read(self, size):
        self.calls.append(size)
        value = self.body[:size]
        self.body = self.body[size:]
        return value

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True
        return False


def public_source(req, *, timeout):
    header = req.get_header("Range")
    prefix = "bytes="
    if not header.startswith(prefix):
        raise AssertionError("Sampled original lacks required Range")
    start, end = (int(x) for x in header[len(prefix):].split("-"))
    return FakeSourceResponse(req.full_url, start=start, end=end,
                              total=10_000, body=b"A" * (end - start + 1))


class BoundedGzipSampleTests(unittest.TestCase):
    def test_exact_frozen_unapproved_source_size_contract(self):
        sizes = m.frozen_unapproved_sizes()
        self.assertEqual(len(sizes), 34)
        self.assertEqual(sizes[2026], 1023490271)
        self.assertEqual(sizes[2027], 1607260)
        self.assertEqual(sum(sizes.values()), 20333624076)
        self.assertNotIn(2028, sizes)
        self.assertNotIn(2029, sizes)

    def test_three_stratified_ranges_never_include_full_original(self):
        for size in (1, 2, 3, 4, 5, 685, 1607260, 100_000_000):
            for max_window in (1, 128, 4096, m.MAX_WINDOW_BYTES):
                spans = m._windows(size, max_window=max_window)
                if size <= 4:
                    self.assertEqual(spans, [])
                for start, end in spans:
                    self.assertGreaterEqual(start, 0)
                    self.assertLess(end, size)
                    self.assertLessEqual(end - start + 1, max_window)
                self.assertLess(sum(end - start + 1 for start, end in spans),
                                size)

    def test_only_three_range_reads_with_authenticated_first_party_transport(self):
        opened = []
        def opener(req, *, timeout):
            self.assertEqual(req.get_header("Accept-encoding"), "identity")
            range_spec = req.get_header("Range").removeprefix("bytes=")
            start, end = (int(v) for v in range_spec.split("-"))
            response = FakeSourceResponse(req.full_url, start=start, end=end,
                                          total=10_000)
            opened.append(response)
            return response

        output = m.sample_year(2026, size=10_000, opener=opener, max_window=128)
        self.assertEqual(output["status"], "BOUNDED_GZIP_SAMPLE_OBSERVED_UNREVIEWED")
        self.assertEqual(output["sampled_bytes"], 384)
        self.assertEqual(output["sample_range_count"], 3)
        self.assertLess(output["sampled_gzip_bytes"], output["sampled_bytes"])
        self.assertLess(output["estimated_gzip_ratio_sample_only"], 0.5)
        self.assertFalse(output["publisher_original_verified"])
        self.assertEqual(len(opened), 3)
        for response in opened:
            self.assertTrue(response.closed)
            self.assertEqual(response.calls, [129])

    def test_http_200_and_bad_range_rejected_before_reading_content(self):
        scenarios = [
            {"status": 200},
            {"headers": {"Content-Range": "bytes 0-63/10000", "Content-Length": "64"}},
            {"headers": {"Content-Range": "bytes 0-127/9999", "Content-Length": "128"}},
            {"headers": {"Content-Range": "bytes 0-127/10000", "Content-Length": "10000000"}},
            {"headers": {"Content-Range": "bytes 0-127/10000", "Content-Encoding": "gzip"}},
        ]
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                opened = []
                def opener(req, *, timeout):
                    obj = FakeSourceResponse(req.full_url, start=0, end=127,
                                             total=10_000, **scenario)
                    opened.append(obj)
                    return obj
                with self.assertRaises(ValueError):
                    m._sample_range(2026, 0, 127, total=10_000, opener=opener)
                self.assertTrue(opened[0].closed)
                self.assertEqual(opened[0].calls, [])

    def test_unauthorized_redirect_refused_before_reading_sample(self):
        opened = []
        def opener(req, *, timeout):
            response = FakeSourceResponse(
                "https://evil.example/source?X-Amz-Credential=SECRET",
                start=0, end=127, total=10_000,
            )
            opened.append(response)
            return response
        result = m.sample_many([2027], opener=opener, max_window=128)
        self.assertEqual(result["sampled_year_count"], 0)
        self.assertEqual(result["year_observations"][0]["status"],
                         "RANGE_SAMPLE_UNAVAILABLE")
        self.assertNotIn("SECRET", repr(result))
        self.assertEqual(opened[0].calls, [])
        self.assertTrue(opened[0].closed)

    def test_subset_sampling_cannot_become_storage_or_release_proof(self):
        # Use the real frozen FY2027 size for metadata and test only with
        # matching generated fake range headers.
        sizes = m.frozen_unapproved_sizes()
        def opener(req, *, timeout):
            year = int(req.full_url.rsplit("FY", 1)[1][:4])
            start, end = (int(v) for v in req.get_header("Range")
                          .removeprefix("bytes=").split("-"))
            return FakeSourceResponse(req.full_url, start=start, end=end,
                                      total=sizes[year])
        result = m.sample_many([2023, 2026], opener=opener, max_window=128)
        self.assertEqual(result["sampled_year_count"], 2)
        self.assertEqual(result["sampled_source_bytes"], 768)
        self.assertIsInstance(result["subset_sample_derived_gzip_proxy_bytes"], int)
        self.assertFalse(result["subset_proxy_is_guaranteed_upper_bound"])
        for key in (
            "complete_archive_coverage", "complete_archive_compressed_bytes_proven",
            "fit_on_paam_l044_proven", "original_bytes_durably_retained",
            "source_index_updated", "human_catalog_approval",
            "disk_encryption_verified", "offdevice_backup_verified",
            "external_send_authorized", "customer_release_authorized",
        ):
            self.assertIs(result[key], False, key)

    def test_bad_years_and_unbounded_requests_fail_closed(self):
        invalid = [[2028], [2030], [2027, 2027], [2027.0], ["2027"],
                   list(m.CANDIDATE_YEARS[:11]), []]
        for years in invalid:
            with self.subTest(years=years), self.assertRaises(ValueError):
                m.sample_many(years)
        with self.assertRaises(ValueError):
            m.sample_many([2027], max_window=m.MAX_WINDOW_BYTES + 1)
        with self.assertRaises(ValueError):
            m._sample_range(2027, 0, 131072, total=10_000_000)
        with self.assertRaises(ValueError):
            m._sample_range(2027, 6, 3, total=10_000)

    def test_forged_metadata_snapshot_rejected_before_network(self):
        obj = json.loads(m.OBSERVATION.read_text(encoding="utf-8"))
        for mutation in ("catalog", "sum", "future", "missing"):
            forged = json.loads(json.dumps(obj))
            if mutation == "catalog":
                forged["independent_human_catalog_approval"] = True
            elif mutation == "sum":
                forged["archive_size_sum_bytes"] += 1
            elif mutation == "future":
                forged["year_size_bytes"]["FY2028"] = 600
            else:
                del forged["year_size_bytes"]["FY1981"]
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "forged.json"
                path.write_text(json.dumps(forged), encoding="utf-8")
                with patch.object(m, "OBSERVATION", path), self.assertRaises(ValueError):
                    m.frozen_unapproved_sizes()


if __name__ == "__main__":
    unittest.main()
