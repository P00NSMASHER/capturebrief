"""Offline private-retention QA using fictional CSV bytes; never contacts SAM.gov."""
from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from capturebrief_core.archive_catalog import (
    ARCHIVE_CATALOG_CURRENT_THROUGH_FY,
    catalog_years_for_fiscal_year,
    ArchiveCatalogStale,
)
from capturebrief_core.source_policy import SourcePolicyError
from scripts.retain_fy2027_candidate import (
    MAX_TRANSFER_BYTES,
    SOURCE_URL,
    REPO,
    retain_exact_fy2027,
)

FAKE_CSV = (
    b"NoticeId,Sol#,PostedDate,Type,Active,AAC Code,Office,Link\n"
    b"fictional00000000000000000000,SOL-TEST,10/01/2026,"
    b"Solicitation,Yes,AAC,Unit,https://sam.gov/opp/fictional/view\n"
)
FAKE_SHA = hashlib.sha256(FAKE_CSV).hexdigest()
FIXED = datetime(2026, 10, 19, 15, 0, tzinfo=timezone.utc)
OFFICIAL_S3 = (
    "https://s3.amazonaws.com/falextracts/Contract%20Opportunities/"
    "Archived%20Data/FY2027_archived_opportunities.csv"
)


class FakeResponse:
    def __init__(self, contents=FAKE_CSV, url=OFFICIAL_S3, declared=None):
        self.contents = io.BytesIO(contents)
        self.url = url
        self.headers = {
            "Content-Length": str(len(contents) if declared is None else declared),
            "ETag": "test-only-etag",
            "Last-Modified": "Mon, 19 Oct 2026 15:00:00 GMT",
        }

    def read(self, n=-1):
        return self.contents.read(n)

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Fy2027PrivateCandidateTests(unittest.TestCase):
    def test_fake_public_source_is_retained_immutably_but_not_authorized(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "private-sources"
            result = retain_exact_fy2027(
                root,
                opener=lambda req, timeout=120: FakeResponse(),
                expected_sha256=FAKE_SHA,
                expected_bytes=len(FAKE_CSV),
                observed_at=FIXED,
            )
            target = Path(result["original_file"])
            receipt = json.loads(Path(result["receipt_file"]).read_text())
            self.assertEqual(target.read_bytes(), FAKE_CSV)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), FAKE_SHA)
            self.assertEqual(target.name, f"FY2027-{FAKE_SHA}.csv")
            self.assertTrue(receipt["retained_original_file"])
            self.assertTrue(receipt["local_file_sha256_verified"])
            self.assertTrue(receipt["test_override"])
            self.assertFalse(receipt["catalog_approved"])
            self.assertFalse(receipt["full_archive_history_verified"])
            self.assertFalse(receipt["case_release_authorized"])
            self.assertFalse(receipt["external_send_authorized"])
            self.assertEqual(receipt["source_url"], SOURCE_URL)
            self.assertEqual(receipt["official_delivery_host"], "s3.amazonaws.com")
            self.assertFalse(result["external_send_authorized"])
            self.assertEqual(ARCHIVE_CATALOG_CURRENT_THROUGH_FY, 2026)
            with self.assertRaises(ArchiveCatalogStale):
                catalog_years_for_fiscal_year(2027)

            receipt_bytes_before = Path(result["receipt_file"]).read_bytes()
            again = retain_exact_fy2027(
                root,
                opener=lambda req, timeout=120: FakeResponse(),
                expected_sha256=FAKE_SHA,
                expected_bytes=len(FAKE_CSV),
                observed_at=FIXED + timedelta(minutes=45),
            )
            self.assertEqual(result, again)
            self.assertEqual(Path(result["receipt_file"]).read_bytes(),
                             receipt_bytes_before,
                             "A later recheck cannot invent a fresh original observation")
            self.assertEqual(len(list(root.glob("FY2027-*.csv"))), 1)

    def test_current_sam_signed_redirect_original_retained_without_secret_query(self):
        with tempfile.TemporaryDirectory() as td:
            date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            params = urlencode({
                "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
                "X-Amz-Date": date,
                "X-Amz-SignedHeaders": "host",
                "X-Amz-Credential": "A"*20 + "/" + date[:8] +
                                    "/us-east-1/s3/aws4_request",
                "X-Amz-Expires": "300",
                "X-Amz-Signature": "b"*64,
            })
            signed = (
                "https://falextracts.s3.amazonaws.com/Contract%20Opportunities/"
                "Archived%20Data/FY2027_archived_opportunities.csv?" + params
            )
            result = retain_exact_fy2027(
                Path(td) / "signed-original",
                opener=lambda req, timeout=120: FakeResponse(url=signed),
                expected_sha256=FAKE_SHA, expected_bytes=len(FAKE_CSV),
                observed_at=FIXED,
            )
            receipt = json.loads(Path(result["receipt_file"]).read_text(encoding="utf-8"))
            self.assertEqual(receipt["official_delivery_host"],
                             "falextracts.s3.amazonaws.com")
            self.assertEqual(receipt["downloaded_sha256"], FAKE_SHA)
            self.assertFalse(receipt["human_source_review_complete"])
            self.assertNotIn("X-Amz-Signature", str(receipt))
            self.assertNotIn("b"*64, str(receipt))
            self.assertEqual(Path(result["original_file"]).read_bytes(), FAKE_CSV)

    def test_changed_source_hash_does_not_publish_candidate_or_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "private"
            for expected_sha, expected_size in (
                ("0"*64, len(FAKE_CSV)),
                (FAKE_SHA, len(FAKE_CSV) + 1),
            ):
                with self.subTest(sha=expected_sha, size=expected_size):
                    with self.assertRaises(ValueError):
                        retain_exact_fy2027(
                            root, opener=lambda req, timeout=120: FakeResponse(),
                            expected_sha256=expected_sha,
                            expected_bytes=expected_size,
                            observed_at=FIXED,
                        )
                    self.assertEqual(list(root.glob("FY2027-*.csv")), [])
                    self.assertEqual(list(root.glob("*.receipt.json")), [])
                    self.assertEqual(list(root.glob(".fy2027-transfer-*")), [])

    def test_tampered_prior_retention_receipt_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "private"
            initial = retain_exact_fy2027(
                root, opener=lambda req, timeout=120: FakeResponse(),
                expected_sha256=FAKE_SHA, expected_bytes=len(FAKE_CSV),
                observed_at=FIXED,
            )
            path = Path(initial["receipt_file"])
            original_bytes = path.read_bytes()
            original = json.loads(original_bytes)
            for altered_key, altered_value in (
                ("catalog_approved", True),
                ("downloaded_bytes", 1),
                ("operator_path", "/public/other-file.csv"),
                ("prior_ci_sha256", "0"*64),
            ):
                forged = dict(original)
                forged[altered_key] = altered_value
                path.write_text(json.dumps(forged, indent=2, sort_keys=True) + "\n")
                with self.subTest(key=altered_key), self.assertRaises(ValueError):
                    retain_exact_fy2027(
                        root, opener=lambda req, timeout=120: FakeResponse(),
                        expected_sha256=FAKE_SHA, expected_bytes=len(FAKE_CSV),
                        observed_at=FIXED + timedelta(hours=1),
                    )
            # Restore the EXACT original bytes: Windows text-mode output
            # otherwise converts LF to CRLF and correctly fails immutable
            # receipt byte verification.
            path.write_bytes(original_bytes)
            again = retain_exact_fy2027(
                root, opener=lambda req, timeout=120: FakeResponse(),
                expected_sha256=FAKE_SHA, expected_bytes=len(FAKE_CSV),
                observed_at=FIXED + timedelta(days=1),
            )
            self.assertEqual(initial, again)

    def test_wrong_official_object_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "private"
            reads = []
            class Wrong(FakeResponse):
                def __init__(self):
                    super().__init__(
                        url=OFFICIAL_S3.replace("FY2027_", "FY2026_")
                    )
                def read(self, n=-1):
                    reads.append(n)
                    return super().read(n)
            with self.assertRaises(SourcePolicyError):
                retain_exact_fy2027(
                    root,
                    opener=lambda req, timeout=120: Wrong(),
                    expected_sha256=FAKE_SHA,
                    expected_bytes=len(FAKE_CSV),
                    observed_at=FIXED,
                )
            self.assertEqual(reads, [], "Wrong target must not be read")
            self.assertEqual(list(root.glob("FY2027-*.csv")), [])

    def test_missing_or_oversized_expected_digest_fails_before_network(self):
        no_network = lambda req, timeout=120: self.fail("Unexpected source fetch")
        with tempfile.TemporaryDirectory() as td:
            for digest, size in (("A"*64, len(FAKE_CSV)),
                                 (FAKE_SHA, MAX_TRANSFER_BYTES + 1),
                                 ("bad", len(FAKE_CSV)),
                                 (FAKE_SHA, 0)):
                with self.subTest(digest=digest, size=size):
                    with self.assertRaises(ValueError):
                        retain_exact_fy2027(
                            Path(td) / "private", opener=no_network,
                            expected_sha256=digest, expected_bytes=size,
                        )

    def test_public_or_symlink_root_cannot_be_used_as_private_storage(self):
        with self.assertRaisesRegex(ValueError, "private"):
            retain_exact_fy2027(
                REPO / "customer-data",
                opener=lambda req, timeout=120: self.fail("Network must not run"),
                expected_sha256=FAKE_SHA,
                expected_bytes=len(FAKE_CSV),
            )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            actual = root / "actual"
            actual.mkdir()
            alias = root / "symlink"
            try:
                alias.symlink_to(actual, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Runner does not support symlinks")
            with self.assertRaisesRegex(ValueError, "private"):
                retain_exact_fy2027(
                    alias,
                    opener=lambda req, timeout=120: self.fail("Network must not run"),
                    expected_sha256=FAKE_SHA,
                    expected_bytes=len(FAKE_CSV),
                )


if __name__ == "__main__":
    unittest.main()
