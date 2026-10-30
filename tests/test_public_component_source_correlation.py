"""Adversarial, public/fictional-only component-correlation regression.

A live-source component check must prove that the product parsed the SAME
first-party CSV row, not merely preserve a NoticeId while changing agency,
office, dates, source slot, or the original-row hash.
"""
from __future__ import annotations

import copy
import csv
import io
import unittest
from unittest.mock import patch

from capturebrief_core.data_services import scan_extract_bytes
from scripts import validate_live_public_sources as source_qa


FIELDS = ["NoticeId", "Sol#", "PostedDate", "Type", "Active",
          "AAC Code", "Office", "Link"]


def fictional_original() -> bytes:
    data = io.StringIO(newline="")
    writer = csv.DictWriter(data, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for n, symbol in enumerate("abc", 1):
        writer.writerow({
            "NoticeId": f"FICTIONAL-{symbol}",
            "Sol#": f"FICTIONAL-SOL-{symbol}",
            "PostedDate": f"2026-10-{n:02d}",
            "Type": "Solicitation" if n == 1 else "Amendment",
            "Active": "Yes", "AAC Code": "AAC-EXAMPLE",
            "Office": "PUBLIC-TEST-OFFICE",
            "Link": "https://sam.gov/opp/" + symbol * 32 + "/view",
        })
    return data.getvalue().encode("utf-8")


class PublicComponentSourceCorrelationTests(unittest.TestCase):
    def test_unmodified_fictional_archive_is_a_component_pass_not_delivery(self):
        result = source_qa.validate_archive(
            1999, downloader=lambda url, **kwargs: fictional_original(),
        )
        self.assertEqual(result["status"], "REAL_HISTORICAL_EXTRACT_COMPONENT_PASS")
        self.assertEqual(result["solicitation_groups_checked"], 3)
        self.assertEqual(result["matched_rows_checked"], 3)
        self.assertFalse(result["current_pursuit_verified"])
        self.assertFalse(result["approved_catalog_source"])

    def test_forged_row_fields_and_source_receipt_cannot_pass_on_notice_ids(self):
        original_scan = scan_extract_bytes
        mutators = {
            "different-agency": lambda result: result["matches"][0].__setitem__(
                "aac_code", "FOREIGN-AGENCY"),
            "different-office": lambda result: result["matches"][0].__setitem__(
                "office", "UNRELATED-OFFICE"),
            "changed-posted-date": lambda result: result["matches"][0].__setitem__(
                "posted_date", "2040-01-01"),
            "changed-action-type": lambda result: result["matches"][0].__setitem__(
                "notice_type", "Cancellation"),
            "changed-source-row-hash": lambda result: result["matches"][0].__setitem__(
                "row_sha256", "0" * 64),
            "wrong-snapshot-digest": lambda result: result.__setitem__(
                "extract_sha256", "0" * 64),
            "wrong-original-slot": lambda result: result.__setitem__(
                "fiscal_year", 2000),
            "wrong-official-url": lambda result: result.__setitem__(
                "source_url", "https://example.test/fake.csv"),
        }
        for name, mutate in mutators.items():
            with self.subTest(tamper=name):
                def corrupted(*args, **kwargs):
                    receipt = copy.deepcopy(original_scan(*args, **kwargs))
                    mutate(receipt)
                    return receipt
                with patch.object(source_qa, "scan_extract_bytes",
                                  side_effect=corrupted):
                    with self.assertRaises(ValueError):
                        source_qa.validate_archive(
                            1999,
                            downloader=lambda url, **kwargs: fictional_original(),
                        )


if __name__ == "__main__":
    unittest.main()
