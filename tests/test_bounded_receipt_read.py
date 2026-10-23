"""Regression: private gzip candidate receipts must have bounded reads."""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import retain_compressed_sam_archive_candidate as m
from tests.test_compressed_archive_candidate import (
    FakeFullResponse, private_tempdir, sample_bytes,
)


class BoundedReceiptReadTests(unittest.TestCase):
    def _retained(self, root):
        original = sample_bytes()
        retained = m.retain_compressed_candidate(
            2027, root,
            opener=lambda request, timeout: FakeFullResponse(request.full_url, original),
            expected_size=len(original),
        )
        return retained, original

    def test_oversized_receipt_fails_before_read_bytes(self):
        with private_tempdir() as td:
            root = Path(td) / "private"
            retained, _ = self._retained(root)
            receipt = root / f"FY2027-{retained['original_sha256']}.gzip-candidate.receipt.json"
            receipt.write_bytes(b" " * (m.MAX_MANIFEST_BYTES + 1))
            with patch.object(Path, "read_bytes",
                              side_effect=AssertionError("unbounded receipt read")):
                with self.assertRaisesRegex(ValueError, "size bound"):
                    m.verify_compressed_candidate(
                        2027, root, original_sha256=retained["original_sha256"],
                        synthetic_test=True,
                    )

    def test_truncated_or_concatenated_gzip_fails_with_updated_receipt(self):
        for mode in ("truncated", "concatenated"):
            with self.subTest(mode=mode), private_tempdir() as td:
                root = Path(td) / "private"
                retained, _ = self._retained(root)
                archive = root / f"FY2027-{retained['original_sha256']}.csv.gz"
                receipt = root / f"FY2027-{retained['original_sha256']}.gzip-candidate.receipt.json"
                old = archive.read_bytes()
                altered = old[:-8] if mode == "truncated" else old + old
                archive.chmod(0o600)
                archive.write_bytes(altered)
                archive.chmod(0o444)
                fields = json.loads(receipt.read_bytes())
                fields["gzip_sha256"] = hashlib.sha256(altered).hexdigest()
                fields["gzip_bytes"] = len(altered)
                receipt.write_bytes(m._canonical(fields))
                with self.assertRaises((EOFError, OSError, ValueError)):
                    m.verify_compressed_candidate(
                        2027, root, original_sha256=retained["original_sha256"],
                        synthetic_test=True,
                    )

    def test_duplicate_manifest_fields_fail_closed(self):
        with private_tempdir() as td:
            root = Path(td) / "private"
            retained, _ = self._retained(root)
            receipt = root / f"FY2027-{retained['original_sha256']}.gzip-candidate.receipt.json"
            raw = receipt.read_bytes()
            self.assertIn(b'"catalog_approved": false', raw)
            receipt.write_bytes(raw.replace(
                b'"catalog_approved": false',
                b'"catalog_approved": false, "catalog_approved": false', 1,
            ))
            with self.assertRaises(ValueError):
                m.verify_compressed_candidate(
                    2027, root, original_sha256=retained["original_sha256"],
                    synthetic_test=True,
                )


if __name__ == "__main__":
    unittest.main()
