"""Offline synthetic-only tests for lossless compressed-original candidate retention."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import retain_compressed_sam_archive_candidate as m


@contextmanager
def private_tempdir():
    """Fixture inside per-user private AppData, not broad GitHub runner D: temp."""
    # Windows hosted runners often grant built-in Users access to their
    # shared D:\\a\\_temp directory. Genuine source retention correctly
    # refuses those broad ACLs; test invented bytes under the user profile.
    parent = os.environ.get("LOCALAPPDATA") if os.name == "nt" else None
    if os.name == "nt" and (not parent or not Path(parent).is_dir()):
        raise RuntimeError("Windows private user AppData is unavailable")
    with tempfile.TemporaryDirectory(prefix="cb-private-test-", dir=parent) as base:
        yield base


class FakeFullResponse:
    def __init__(self, url: str, data: bytes, *, status=200,
                 declared=None, transfer_encoding="identity"):
        self.url = url
        self.data = data
        self.status = status
        self.headers = {
            "Content-Length": str(len(data)) if declared is None else str(declared),
            "Content-Encoding": transfer_encoding,
        }
        self.read_calls = []
        self.closed = False

    def geturl(self):
        return self.url

    def read(self, amount: int):
        self.read_calls.append(amount)
        result = self.data[:amount]
        self.data = self.data[amount:]
        return result

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True
        return False


def sample_bytes() -> bytes:
    return (b"NoticeId,Sol#,PostedDate\n" +
            (b"FAKE-NOT-A-REAL-ORIGINAL,123-TEST,2026-10-19\n" * 1000))


class CompressedCandidateOfflineTests(unittest.TestCase):
    def test_genuine_lossless_fake_original_streamed_with_immutable_receipt(self):
        original = sample_bytes()
        calls = []
        def opener(req, *, timeout):
            obj = FakeFullResponse(req.full_url, original)
            calls.append(obj)
            return obj

        with private_tempdir() as tmp:
            d = Path(tmp) / "private"
            observed = datetime(2026, 10, 19, 19, 0, tzinfo=timezone.utc)
            a = m.retain_compressed_candidate(
                2027, d, opener=opener, expected_size=len(original),
                observed_at=observed,
            )
            self.assertEqual(a["status"], "PRIVATE_COMPRESSED_ORIGINAL_CANDIDATE_NOT_APPROVED")
            self.assertEqual(a["original_sha256"], hashlib.sha256(original).hexdigest())
            self.assertTrue(a["archive_created"])
            self.assertTrue(a["receipt_created"])
            self.assertFalse(a["source_index_updated"])
            self.assertFalse(a["catalog_approved"])
            self.assertFalse(a["customer_release_authorized"])
            compressed = d / f"FY2027-{a['original_sha256']}.csv.gz"
            receipt = d / f"FY2027-{a['original_sha256']}.gzip-candidate.receipt.json"
            self.assertTrue(compressed.is_file())
            self.assertEqual(gzip.decompress(compressed.read_bytes()), original)
            self.assertEqual(compressed.stat().st_size, a["gzip_bytes"])
            self.assertLess(a["compression_ratio"], 1)
            self.assertEqual(sorted(p.suffix for p in d.iterdir()), [".gz", ".json"])
            r = json.loads(receipt.read_bytes())
            self.assertTrue(r["synthetic_test_override"])
            self.assertFalse(r["catalog_approved"])
            self.assertFalse(r["offdevice_backup_verified"])
            self.assertFalse(r["customer_release_authorized"])
            initial_receipt = receipt.read_bytes()

            v = m.verify_compressed_candidate(
                2027, d, original_sha256=a["original_sha256"],
                synthetic_test=True,
            )
            self.assertEqual(v["status"], "PRIVATE_GZIP_CANDIDATE_BYTE_INTEGRITY_PASS_ONLY")
            self.assertFalse(v["catalog_approved"])

            second = m.retain_compressed_candidate(
                2027, d, opener=opener, expected_size=len(original),
                observed_at=datetime(2026, 10, 20, 1, 0, tzinfo=timezone.utc),
            )
            self.assertFalse(second["archive_created"])
            self.assertFalse(second["receipt_created"])
            self.assertEqual(second["first_original_observed_at"], "2026-10-19T19:00:00Z")
            self.assertEqual(receipt.read_bytes(), initial_receipt)
            for fake in calls:
                self.assertTrue(fake.closed)
                self.assertLessEqual(max(fake.read_calls), m.BLOCK_BYTES)
            self.assertFalse(list(d.glob("*.tmp")))
            self.assertFalse(list(d.glob("*.csv")))

    def test_changed_or_truncated_content_cannot_publish_archive_or_receipt(self):
        original = sample_bytes()
        variants = (
            {"data": original[:100], "declared": len(original)},
            {"data": original, "declared": len(original) + 1},
            {"data": original + b"x", "declared": len(original)},
            {"data": original, "status": 206},
            {"data": original, "transfer_encoding": "gzip"},
        )
        for variant in variants:
            with self.subTest(variant=sorted(variant)), private_tempdir() as tmp:
                opened = []
                def opener(req, *, timeout):
                    obj = FakeFullResponse(req.full_url, **variant)
                    opened.append(obj)
                    return obj
                d = Path(tmp) / "private"
                with self.assertRaises(ValueError):
                    m.retain_compressed_candidate(
                        2027, d, opener=opener, expected_size=len(original),
                    )
                self.assertEqual(list(d.iterdir()), [])
                self.assertTrue(opened[0].closed)
                if variant.get("status") == 206 or variant.get("transfer_encoding") == "gzip":
                    self.assertEqual(opened[0].read_calls, [])

    def test_malicious_redirect_refused_without_reading_or_leaking_link(self):
        data = sample_bytes()
        response = FakeFullResponse(
            "https://evil.example/signed?X-Amz-Credential=SENSITIVE_SECRET", data,
        )
        with private_tempdir() as td:
            result = None
            try:
                m.retain_compressed_candidate(
                    2027, Path(td)/"private", expected_size=len(data),
                    opener=lambda req, timeout: response,
                )
            except Exception as exc:
                result = exc
            self.assertIsNotNone(result)
            self.assertNotIn("SENSITIVE_SECRET", str(result))
            self.assertEqual(response.read_calls, [])
            self.assertTrue(response.closed)

    def test_conflicting_immutable_receipt_and_archive_fail_without_replacement(self):
        original = sample_bytes()
        def opener(req, *, timeout):
            return FakeFullResponse(req.full_url, original)
        with private_tempdir() as td:
            d = Path(td)/"private"
            out = m.retain_compressed_candidate(
                2027, d, opener=opener, expected_size=len(original),
            )
            receipt = d / f"FY2027-{out['original_sha256']}.gzip-candidate.receipt.json"
            compressed = d / f"FY2027-{out['original_sha256']}.csv.gz"
            orig_receipt = receipt.read_bytes()
            # Mutating an approval claim must not be silently corrected.
            receipt.write_bytes(orig_receipt.replace(
                b'"catalog_approved": false', b'"catalog_approved": true'
            ))
            with self.assertRaises(ValueError):
                m.retain_compressed_candidate(
                    2027, d, opener=opener, expected_size=len(original),
                )
            self.assertNotEqual(receipt.read_bytes(), orig_receipt)
            receipt.write_bytes(orig_receipt)
            orig_archive = compressed.read_bytes()
            compressed.chmod(0o600)
            compressed.write_bytes(orig_archive[:-1] + b"x")
            with self.assertRaises((ValueError, OSError)):
                m.verify_compressed_candidate(
                    2027, d, original_sha256=out["original_sha256"],
                    synthetic_test=True,
                )

    def test_interrupted_midstream_source_leaves_no_archive_or_receipt(self):
        original = sample_bytes()
        class Interrupted(FakeFullResponse):
            def read(self, amount):
                if self.read_calls:
                    raise ConnectionResetError("invented transport disconnect")
                return super().read(min(amount, 128))
        with private_tempdir() as td:
            root = Path(td) / "private"
            response = Interrupted(m.ARCHIVE_DOWNLOAD.format(fy=2027), original)
            with self.assertRaises(ConnectionResetError):
                m.retain_compressed_candidate(
                    2027, root,
                    opener=lambda req, timeout: response,
                    expected_size=len(original),
                )
            self.assertTrue(response.closed)
            self.assertEqual(list(root.iterdir()), [])

    def test_partial_publication_recovers_only_from_identical_original(self):
        original = sample_bytes()
        with private_tempdir() as td:
            root = Path(td) / "private"
            def opener(req, *, timeout):
                return FakeFullResponse(req.full_url, original)
            publisher = m.ensure_exact_file
            def interrupted_publish(*args, **kwargs):
                publisher(*args, **kwargs)
                raise RuntimeError("synthetic crash after archive, before receipt")
            with patch.object(m, "ensure_exact_file", side_effect=interrupted_publish):
                with self.assertRaises(RuntimeError):
                    m.retain_compressed_candidate(
                        2027, root, opener=opener, expected_size=len(original),
                    )
            sha = hashlib.sha256(original).hexdigest()
            self.assertTrue((root / f"FY2027-{sha}.csv.gz").is_file())
            self.assertFalse((root / f"FY2027-{sha}.gzip-candidate.receipt.json").exists())
            self.assertFalse(list(root.glob("*.tmp")))
            replay = m.retain_compressed_candidate(
                2027, root, opener=opener, expected_size=len(original),
            )
            self.assertFalse(replay["archive_created"])
            self.assertTrue(replay["receipt_created"])
            m.verify_compressed_candidate(2027, root, original_sha256=sha,
                                          synthetic_test=True)

    def test_verify_missing_private_root_must_not_create_it(self):
        with private_tempdir() as td:
            missing = Path(td) / "read-only-verifier-should-not-create"
            with self.assertRaises(ValueError):
                m.verify_compressed_candidate(
                    2027, missing, original_sha256="0" * 64,
                )
            self.assertFalse(missing.exists())

    def test_malformed_canonical_receipt_timestamp_fails_closed(self):
        original = sample_bytes()
        with private_tempdir() as td:
            root = Path(td) / "private"
            def opener(req, *, timeout):
                return FakeFullResponse(req.full_url, original)
            retained = m.retain_compressed_candidate(
                2027, root, opener=opener, expected_size=len(original),
            )
            receipt = root / f"FY2027-{retained['original_sha256']}.gzip-candidate.receipt.json"
            data = json.loads(receipt.read_bytes())
            data["original_observed_at"] = "not-a-real-timeZ"
            receipt.write_bytes(m._canonical(data))
            with self.assertRaisesRegex(ValueError, "timestamp"):
                m.retain_compressed_candidate(
                    2027, root, opener=opener, expected_size=len(original),
                )
            self.assertEqual(json.loads(receipt.read_bytes())["original_observed_at"],
                             "not-a-real-timeZ")

    def test_writable_previous_archive_is_not_silently_accepted(self):
        original = sample_bytes()
        with private_tempdir() as td:
            root = Path(td) / "private"
            def opener(req, *, timeout):
                return FakeFullResponse(req.full_url, original)
            result = m.retain_compressed_candidate(
                2027, root, opener=opener, expected_size=len(original),
            )
            archive = root / f"FY2027-{result['original_sha256']}.csv.gz"
            receipt = root / f"FY2027-{result['original_sha256']}.gzip-candidate.receipt.json"
            before_receipt = receipt.read_bytes()
            archive.chmod(0o600)  # Simulates a crash before Windows read-only sealing.
            with self.assertRaisesRegex(ValueError, "read-only"):
                m.verify_compressed_candidate(
                    2027, root, original_sha256=result["original_sha256"],
                    synthetic_test=True,
                )
            with self.assertRaisesRegex(ValueError, "read-only"):
                m.retain_compressed_candidate(
                    2027, root, opener=opener, expected_size=len(original),
                )
            self.assertEqual(receipt.read_bytes(), before_receipt)
            self.assertFalse(list(root.glob("*.tmp")))

    def test_no_prod_override_no_future_years_and_no_public_git_destinations(self):
        with private_tempdir() as td:
            d = Path(td)/"private"
            with self.assertRaises(ValueError):
                m.retain_compressed_candidate(2028, d)
            with self.assertRaises(ValueError):
                m.retain_compressed_candidate(2029, d)
            with self.assertRaises(ValueError):
                m.retain_compressed_candidate(2027, d, expected_size=20)
            with self.assertRaises(ValueError):
                m.retain_compressed_candidate(2027, d,
                    opener=lambda req, timeout: None, expected_size=m.MAX_ORIGINAL_BYTES+1)
            with self.assertRaises(ValueError):
                m._private_dir(m.ROOT / "not-an-allowed-source-directory")
            with self.assertRaises(ValueError):
                m._private_dir(d / "OneDrive" / "source")

    def test_restore_gate_cannot_certify_synthetic_or_promote_review_flags(self):
        data=sample_bytes()
        def opener(req, *, timeout):
            return FakeFullResponse(req.full_url, data)
        with private_tempdir() as td:
            d=Path(td)/"private"
            result=m.retain_compressed_candidate(
                2027, d, opener=opener, expected_size=len(data),
            )
            with self.assertRaises(ValueError):
                m.verify_compressed_candidate(
                    2027, d, original_sha256=result["original_sha256"],
                )
            receipt=d/f"FY2027-{result['original_sha256']}.gzip-candidate.receipt.json"
            raw=receipt.read_bytes()
            receipt.write_bytes(raw.replace(
                b'"offdevice_backup_verified": false',
                b'"offdevice_backup_verified": true',
            ))
            with self.assertRaises(ValueError):
                m.verify_compressed_candidate(
                    2027, d, original_sha256=result["original_sha256"],
                    synthetic_test=True,
                )


    @unittest.skipIf(os.name == "nt", "POSIX directory bits do not model NTFS ACLs")
    def test_private_directory_with_world_or_group_read_is_rejected(self):
        with private_tempdir() as td:
            p = Path(td) / "world-readable-archive"
            p.mkdir()
            p.chmod(0o755)
            with self.assertRaisesRegex(ValueError, "group/other"):
                m._private_dir(p)
            p.chmod(0o700)
            self.assertEqual(m._private_dir(p), p.resolve())



if __name__ == "__main__":
    unittest.main()
