"""Offline adversarial response-header tests for the FY2027 unapproved archive retainer."""
from __future__ import annotations

from pathlib import Path
import unittest

from scripts import retain_compressed_sam_archive_candidate as m
from tests.test_compressed_archive_candidate import FakeFullResponse, private_tempdir, sample_bytes


class SourceRangeHeaderTests(unittest.TestCase):
    def test_http_200_with_content_range_is_not_full_original(self):
        data = sample_bytes()
        for value in (
            f"bytes 0-{len(data)-1}/{len(data)}",
            "bytes 0-99/*",
            "bytes invalid",
        ):
            with self.subTest(value=value), private_tempdir() as tmp:
                response = FakeFullResponse(m.ARCHIVE_DOWNLOAD.format(fy=2027), data)
                response.headers["Content-Range"] = value
                root = Path(tmp) / "private"
                with self.assertRaises(ValueError):
                    m.retain_compressed_candidate(
                        2027, root, opener=lambda req, timeout: response,
                        expected_size=len(data),
                    )
                self.assertEqual(response.read_calls, [])
                self.assertTrue(response.closed)
                self.assertEqual(list(root.iterdir()), [])

if __name__ == "__main__":
    unittest.main()
