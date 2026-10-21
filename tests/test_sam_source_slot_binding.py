"""Invented source bytes only: exact SAM Data Services slot/provenance safety."""
from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from capturebrief_core.data_services import (
    ACTIVE_DOWNLOAD, ARCHIVE_DOWNLOAD, DataServicesError,
    issue_history_receipt_from_snapshots, scan_extract_bytes,
)
from tests.test_source_policy_data_services import HEADER, row
from capturebrief_core.history_index import ingest_extract_file
from tests.test_history_index import row as index_row, write_csv

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
                    ORIGINAL,
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

    def test_receipt_builder_rejects_mislabeled_snapshot_even_without_scanner(self):
        active=scan_extract_bytes(
            ORIGINAL,source_url=ACTIVE_DOWNLOAD,
            source_kind="ACTIVE",solicitation_number="FICTIONAL-SOL",
        )
        archive=scan_extract_bytes(
            ORIGINAL,source_url=ARCHIVE_DOWNLOAD.format(fy=2026),
            source_kind="ARCHIVE",fiscal_year=2026,
            solicitation_number="FICTIONAL-SOL",
        )
        forged=dict(archive)
        forged["source_url"]=ACTIVE_DOWNLOAD
        with self.assertRaises(DataServicesError):
            issue_history_receipt_from_snapshots(
                [active,forged],solicitation_number="FICTIONAL-SOL",
                seed_notice_id="FICTIONAL-1",
                scope_start_fy=2026,scope_end_fy=2026,
                scope_confirmed=True,observed_at="2026-09-21T13:00:00+00:00",
            )

    def test_receipt_builder_rejects_duplicate_archive_slots(self):
        active=scan_extract_bytes(
            ORIGINAL,source_url=ACTIVE_DOWNLOAD,
            source_kind="ACTIVE",solicitation_number="FICTIONAL-SOL",
        )
        archive=scan_extract_bytes(
            ORIGINAL,source_url=ARCHIVE_DOWNLOAD.format(fy=2026),
            source_kind="ARCHIVE",fiscal_year=2026,
            solicitation_number="FICTIONAL-SOL",
        )
        with self.assertRaises(DataServicesError):
            issue_history_receipt_from_snapshots(
                [active,archive,dict(archive)],solicitation_number="FICTIONAL-SOL",
                seed_notice_id="FICTIONAL-1",
                scope_start_fy=2026,scope_end_fy=2026,
                scope_confirmed=True,observed_at="2026-09-21T13:00:00+00:00",
            )

    def test_receipt_cannot_claim_unapproved_fy2027_scope_complete(self):
        active=scan_extract_bytes(
            ORIGINAL,source_url=ACTIVE_DOWNLOAD,
            source_kind="ACTIVE",solicitation_number="FICTIONAL-SOL",
        )
        archive=scan_extract_bytes(
            ORIGINAL,source_url=ARCHIVE_DOWNLOAD.format(fy=2027),
            source_kind="ARCHIVE",fiscal_year=2027,
            solicitation_number="FICTIONAL-SOL",
        )
        report=issue_history_receipt_from_snapshots(
            [active,archive],solicitation_number="FICTIONAL-SOL",
            seed_notice_id="FICTIONAL-1",
            scope_start_fy=2027,scope_end_fy=2027,
            scope_confirmed=True,observed_at="2026-10-20T13:00:00+00:00",
        )
        self.assertEqual(report["status"],"OBSERVED_ONLY")
        self.assertFalse(
            report["evidence_payload"]["scope"]["production_archive_catalog_approved"],
        )

    def test_manually_injected_unmatched_notice_cannot_pollute_receipt(self):
        active=scan_extract_bytes(
            ORIGINAL,source_url=ACTIVE_DOWNLOAD,
            source_kind="ACTIVE",solicitation_number="FICTIONAL-SOL",
        )
        forged={**active,"matches":[
            {**active["matches"][0],
             "solicitation_number":"DIFFERENT-FICTIONAL-SOL"},
        ]}
        with self.assertRaises(DataServicesError):
            issue_history_receipt_from_snapshots(
                [forged],solicitation_number="FICTIONAL-SOL",
                seed_notice_id="FICTIONAL-1",
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



    def test_disk_ingest_rejects_source_slot_impersonation_before_any_index_write(self):
        # The disk-based indexed pipeline must not be weaker than the
        # in-memory scanner. A valid SAM-class URL is not proof of a FY slot.
        cases = (
            ("active-mislabeled-archive", ACTIVE_DOWNLOAD, "ARCHIVE", 2026),
            ("archive-mislabeled-active", ARCHIVE_DOWNLOAD.format(fy=2026), "ACTIVE", None),
            ("archive-fy-mismatch", ARCHIVE_DOWNLOAD.format(fy=2027), "ARCHIVE", 2026),
            ("archive-typed-string-year", ARCHIVE_DOWNLOAD.format(fy=2026), "ARCHIVE", "2026"),
            ("archive-boolean-year", ARCHIVE_DOWNLOAD.format(fy=2026), "ARCHIVE", True),
            ("active-with-year", ACTIVE_DOWNLOAD, "ACTIVE", 2026),
        )
        for label, url, kind, year in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                csv_path = root / "fictional-original.csv"
                write_csv(csv_path, [index_row("fictional-action")])
                index_path = root / "history.sqlite"
                snapshot_dir = root / "snapshots"
                with self.assertRaises((ValueError, DataServicesError)):
                    ingest_extract_file(
                        index_path, csv_path, source_url=url, source_kind=kind,
                        fiscal_year=year, snapshot_dir=snapshot_dir,
                        collection_mode="APPROVED_FETCH",
                        observed_at="2026-09-21T13:00:00+00:00",
                    )
                self.assertFalse(index_path.exists(), label)
                self.assertFalse(snapshot_dir.exists(), label)

    def test_disk_ingest_accepts_exact_original_slots_without_catalog_promotion(self):
        for kind, year, url, expected in (
            ("ACTIVE", None, ACTIVE_DOWNLOAD, "ACTIVE"),
            ("ARCHIVE", 2026, ARCHIVE_DOWNLOAD.format(fy=2026), "ARCHIVE:2026"),
        ):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                csv_path = root / "fictional-original.csv"
                write_csv(csv_path, [index_row("fictional-action")])
                ingested = ingest_extract_file(
                    root / "history.sqlite", csv_path, source_url=url,
                    source_kind=kind, fiscal_year=year,
                    collection_mode="OPERATOR_FILE",
                    observed_at="2026-09-21T13:00:00+00:00",
                )
                self.assertEqual(ingested["slot"], expected)
                self.assertEqual(ingested["rows_scanned"], 1)



if __name__=="__main__":
    unittest.main()
