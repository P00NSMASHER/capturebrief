"""Offline, synthetic-only capacity and fail-closed network-before-write QA."""
from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import source_disk_budget as budget
from scripts import retain_compressed_sam_archive_candidate as retention
from tests.test_compressed_archive_candidate import private_tempdir, sample_bytes, FakeFullResponse


class PrivateDiskBudgetTests(unittest.TestCase):
    def test_limit_uses_original_worst_case_not_sample_proxy(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            original=1_277_614_651  # Frozen FY2023 declared size.
            worst=original+max(budget.MIN_GZIP_OVERHEAD_BYTES,
                               (original+99)//100)
            floor=budget.UNALLOCATED_RESERVE_BYTES
            # Publication briefly needs TWO compressed copies: the gzip
            # streaming temp plus ensure_exact_file's independent temp copy.
            required=(budget.MAX_SIMULTANEOUS_GZIP_COPIES * worst
                      + floor + budget.PUBLICATION_METADATA_ALLOWANCE_BYTES)
            for free, outcome in ((required-1,False),(required,True),
                                  (required+8192,True)):
                with self.subTest(free=free):
                    result=budget.inspect_source_capacity(
                        d,original,disk_usage=lambda _:SimpleNamespace(free=free))
                    self.assertIs(result["single_source_disk_capacity_pass"],outcome)
                    self.assertEqual(result["required_free_bytes"],required)
                    self.assertEqual(result["unallocated_safety_reserve_bytes"],4*1024**3)
                    self.assertEqual(result["simultaneous_gzip_publication_copies"],2)
                    self.assertEqual(result["peak_publication_working_bytes"],
                                     2*worst+budget.PUBLICATION_METADATA_ALLOWANCE_BYTES)
                    for prohibited in (
                        "all_34_year_archive_fits",
                        "active_extract_index_and_working_space_built",
                        "disk_encryption_verified",
                        "encrypted_offdevice_backup_and_independent_key_verified",
                        "human_publisher_catalog_approval", "source_index_updated",
                        "customer_release_authorized",
                    ):
                        self.assertIs(result[prohibited],False,prohibited)

    def test_invalid_or_unknown_capacity_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            for bad in (None,"999999999999",1.5,-1,True):
                with self.subTest(free=bad),self.assertRaises(ValueError):
                    budget.inspect_source_capacity(
                        d,12345,disk_usage=lambda _:SimpleNamespace(free=bad))
            for bytes_ in (None,0,-1,1.0,"100",True,
                           budget.MAX_ANNUAL_ORIGINAL_BYTES+1):
                with self.subTest(bytes=bytes_),self.assertRaises(ValueError):
                    budget.inspect_source_capacity(
                        d,bytes_,disk_usage=lambda _:SimpleNamespace(free=2**40))
            with self.assertRaises(ValueError):
                budget.inspect_source_capacity(d/"missing",100)

    def test_storage_refusal_precedes_any_public_fetch_or_temp_source_bytes(self):
        original=sample_bytes()
        called=[]
        def fake_opener(request, *, timeout):
            called.append(request.full_url)
            return FakeFullResponse(request.full_url,original)
        with private_tempdir() as td:
            root=Path(td)/"private"
            worst=len(original)+max(budget.MIN_GZIP_OVERHEAD_BYTES,
                 (len(original)+99)//100)
            needed=(2*worst+budget.PUBLICATION_METADATA_ALLOWANCE_BYTES
                    + budget.UNALLOCATED_RESERVE_BYTES)
            for free in (0,needed-1):
                with self.subTest(free=free),patch.object(
                    budget.shutil,"disk_usage",
                    return_value=SimpleNamespace(free=free)
                ):
                    with self.assertRaisesRegex(ValueError,
                                                "Insufficient private disk reserve"):
                        retention.retain_compressed_candidate(
                            2027,root,opener=fake_opener,
                            expected_size=len(original),
                        )
                    self.assertEqual(called,[])
                    self.assertEqual(list(root.iterdir()),[])

    def test_capacity_preflight_is_non_authorizing_even_when_sufficient(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            passed=budget.inspect_source_capacity(
                d,1607260,
                disk_usage=lambda _:SimpleNamespace(free=100*2**30),
            )
            self.assertTrue(passed["single_source_disk_capacity_pass"])
            self.assertFalse(passed["customer_release_authorized"])
            self.assertFalse(passed["disk_encryption_verified"])
            self.assertFalse(passed["encrypted_offdevice_backup_and_independent_key_verified"])

    def test_no_unapproved_year_or_unreadable_path_can_pass_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            cli=budget.REPO/"scripts"/"source_disk_budget.py"
            for year in ("2028","2029","2030"):
                result=subprocess.run(
                    [sys.executable,str(cli),
                     "--private-root",tmp,"--year",year],
                    text=True,capture_output=True,check=False,
                )
                self.assertEqual(result.returncode,2)
                report=json.loads(result.stdout)
                self.assertIs(report["customer_release_authorized"],False)
                self.assertIs(report["single_source_disk_capacity_pass"],False)


    def test_competing_same_root_candidate_is_rejected_before_network(self):
        """Simulate overlapping on-demand original fetches in one private root."""
        fake=sample_bytes()
        opened=[]
        def opener(request, *, timeout):
            opened.append(request.full_url)
            return FakeFullResponse(request.full_url,fake)
        with private_tempdir() as td:
            d=Path(td)/"private"
            retention._private_dir(d)  # real NTFS/POSIX security checks
            hold=d/".archive-retention"
            with retention.exclusive_path_lock(hold,timeout_seconds=0):
                with self.assertRaises(TimeoutError):
                    retention.retain_compressed_candidate(
                        2027,d,opener=opener,expected_size=len(fake),
                    )
                self.assertEqual(opened,[])
                self.assertEqual(sorted(p.name for p in d.iterdir()),
                                 [".archive-retention.lock"])
            self.assertEqual(list(d.iterdir()),[])

    def test_reserve_checked_under_lock_and_removed_after_denial(self):
        fake=sample_bytes()
        calls=[]
        with private_tempdir() as td:
            d=Path(td)/"private"
            worst=len(fake)+max(budget.MIN_GZIP_OVERHEAD_BYTES,
                 (len(fake)+99)//100)
            need=(2*worst+budget.PUBLICATION_METADATA_ALLOWANCE_BYTES
                  + budget.UNALLOCATED_RESERVE_BYTES)
            with patch.object(budget.shutil,"disk_usage",
                              return_value=SimpleNamespace(free=need-1)):
                with self.assertRaisesRegex(ValueError,"Insufficient private disk reserve"):
                    retention.retain_compressed_candidate(
                        2027,d,
                        opener=lambda req, timeout: calls.append(req.full_url),
                        expected_size=len(fake),
                    )
            self.assertEqual(calls,[])
            self.assertEqual(list(d.iterdir()),[])



    def test_crash_leftover_root_lock_requires_manual_recovery(self):
        fake = sample_bytes()
        called = []
        with private_tempdir() as td:
            root = Path(td) / "private"
            retention._private_dir(root)
            stale = root / ".archive-retention.lock"
            stale.write_text("synthetic untrusted lock\n", encoding="utf-8")
            with self.assertRaises(TimeoutError):
                retention.retain_compressed_candidate(
                    2027, root, expected_size=len(fake),
                    opener=lambda req, timeout: called.append(req.full_url),
                )
            self.assertFalse(called)
            self.assertTrue(stale.is_file())
            self.assertEqual(sorted(p.name for p in root.iterdir()),
                             [".archive-retention.lock"])

    def test_valid_incompressible_original_exceeds_old_4k_ceiling(self):
        # Deterministic fake original of high entropy; no real SAM bytes.
        # Deflate stored-block overhead is >4 KiB for a legitimate large
        # incompressible file. Keep one shared 1%/256KiB upper bound from
        # the disk preflight through final immutable source publication.
        fake = hashlib.shake_256(
            b"CAPTUREBRIEF_FAKE_HIGH_ENTROPY_ORIGINAL"
        ).digest(16 * 1024 * 1024)
        seen = []
        def opener(request, *, timeout):
            seen.append(request.full_url)
            return FakeFullResponse(request.full_url, fake)
        with private_tempdir() as td:
            dest = Path(td) / "private"
            with patch.object(
                budget.shutil, "disk_usage",
                return_value=SimpleNamespace(free=100 * 2**30),
            ):
                result = retention.retain_compressed_candidate(
                    2027, dest, opener=opener,
                    expected_size=len(fake),
                )
            self.assertEqual(len(seen), 1)
            self.assertEqual(result["original_sha256"],
                             hashlib.sha256(fake).hexdigest())
            self.assertGreater(result["gzip_bytes"], len(fake) + 4096)
            self.assertLessEqual(
                result["gzip_bytes"],
                budget.worst_case_gzip_bytes(len(fake)),
            )
            verify = retention.verify_compressed_candidate(
                2027, dest,
                original_sha256=result["original_sha256"],
                synthetic_test=True,
            )
            self.assertEqual(
                verify["status"],
                "PRIVATE_GZIP_CANDIDATE_BYTE_INTEGRITY_PASS_ONLY",
            )
            self.assertFalse(verify["customer_release_authorized"])
            self.assertFalse(verify["offdevice_backup_verified"])
            self.assertFalse(list(dest.glob("*.tmp")))


if __name__=="__main__":
    unittest.main()
