"""Invented source bytes only: exact SAM Data Services slot/provenance safety."""
from __future__ import annotations

import unittest

from capturebrief_core.data_services import (
    ACTIVE_DOWNLOAD, ARCHIVE_DOWNLOAD, DataServicesError,
    issue_history_receipt_from_snapshots, scan_extract_bytes,
)
from tests.test_source_policy_data_services import HEADER, row

ORIGINAL = (HEADER + row("FICTIONAL-1", "FICTIONAL-SOL")).encode("ascii")


class DataServicesSourceBindingTests(unittest.TestCase):
    def test_mislabeling_official_original_as_other_source_slot_is_denied(self):
        wrong = (
            ("archive-claimed-from-active",ACTIVE_DOWNLOAD,"ARCHIVE",2026),
            ("active-claimed-from-archive",ARCHIVE_DOWNLOAD.format(fy=2026),"ACTIVE",None),
            ("archive-fiscal-year-mismatch",ARCHIVE_DOWNLOAD.format(fy=2027),"ARCHIVE",2026),
            ("archive-without-fiscal-year",ARCHIVE_DOWNLOAD.format(fy=2027),"ARCHIVE",None),
            ("active-with-fiscal-year",ACTIVE_DOWNLOAD,"ACTIVE",2026),
            ("archive-year-flag-not-number",ARCHIVE_DOWNLOAD.format(fy=2026),"ARCHIVE","2026"),
            ("archive-fiscal-year-bool",ARCHIVE_DOWNLOAD.format(fy=2026),"ARCHIVE",True),
        )
        for label,url,kind,year in wrong:
            with self.subTest(label=label),self.assertRaises((ValueError,DataServicesError)):
                scan_extract_bytes(
                    b"intentionally-invalid-synthetic-csv",
                    source_url=url,source_kind=kind,
                    fiscal_year=year,solicitation_number="FICTIONAL-SOL",
                )

    def test_direct_official_active_archive_label_accepts_only_matching_url(self):
        for kind,year,url in (
            ("ACTIVE",None,ACTIVE_DOWNLOAD),
            ("ARCHIVE",2026,ARCHIVE_DOWNLOAD.format(fy=2026)),
            ("ARCHIVE",2027,ARCHIVE_DOWNLOAD.format(fy=2027)),
        ):
            with self.subTest(kind=kind,year=year):
                result=scan_extract_bytes(
                    ORIGINAL,source_url=url,source_kind=kind,
                    fiscal_year=year,solicitation_number="FICTIONAL-SOL",
                )
                self.assertEqual(result["source_kind"],kind)
                self.assertEqual(result["fiscal_year"],year)
                self.assertEqual(len(result["matches"]),1)
                self.assertEqual(result["matches"][0]["notice_id"],"FICTIONAL-1")

    def test_duplicate_primary_notice_identifiers_in_one_original_are_denied(self):
        # Repeated NoticeId may occur across distinct source snapshots, but
        # two rows in one immutable original are not two independent actions.
        duplicate = (HEADER +
                     row("FICTIONAL-SAME-NOTICE","FICTIONAL-SOL") +
                     row("FICTIONAL-SAME-NOTICE","FICTIONAL-SOL")).encode("ascii")
        with self.assertRaises(DataServicesError):
            scan_extract_bytes(
                duplicate,source_url=ARCHIVE_DOWNLOAD.format(fy=2026),
                source_kind="ARCHIVE",fiscal_year=2026,
                solicitation_number="FICTIONAL-SOL",
            )

    def test_duplicate_notice_id_outside_target_still_invalidates_original(self):
        duplicate = (HEADER +
                     row("FICTIONAL-ONE","OTHER-SOL") +
                     row("FICTIONAL-ONE","OTHER-SOL") +
                     row("FICTIONAL-TRUSTED","FICTIONAL-SOL")).encode("ascii")
        with self.assertRaises(DataServicesError):
            scan_extract_bytes(
                duplicate,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",
                solicitation_number="FICTIONAL-SOL",
            )

    def test_same_active_original_cannot_be_relabelled_as_full_archive_coverage(self):
        active=scan_extract_bytes(
            ORIGINAL,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",
            solicitation_number="FICTIONAL-SOL",
        )
        # Before repair this scan returned source_kind ARCHIVE merely because
        # its caller supplied a string, even though its source URL was ACTIVE.
        with self.assertRaises((ValueError,DataServicesError)):
            forged=scan_extract_bytes(
                ORIGINAL,source_url=ACTIVE_DOWNLOAD,source_kind="ARCHIVE",
                fiscal_year=2026,solicitation_number="FICTIONAL-SOL",
            )
            issue_history_receipt_from_snapshots(
                [active,forged],solicitation_number="FICTIONAL-SOL",
                seed_notice_id="FICTIONAL-1",scope_start_fy=2026,
                scope_end_fy=2026,scope_confirmed=True,
                observed_at="2026-09-21T13:00:00+00:00",
            )

    def test_valid_header_only_archived_original_is_allowed(self):
        result=scan_extract_bytes(
            HEADER.encode("ascii"),
            source_url=ARCHIVE_DOWNLOAD.format(fy=1981),
            source_kind="ARCHIVE",fiscal_year=1981,
            solicitation_number="FICTIONAL-SOL",
        )
        self.assertEqual(result["rows_scanned"],0)
        self.assertEqual(result["matches"],[])


if __name__=="__main__":
    unittest.main()
