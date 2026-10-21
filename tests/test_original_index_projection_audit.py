"""Synthetic-only adversarial tests for deep original -> SQLite row integrity."""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from contextlib import closing
from pathlib import Path

from capturebrief_core.data_services import ACTIVE_DOWNLOAD, ARCHIVE_DOWNLOAD
from capturebrief_core.history_index import OPERATOR_FILE, ingest_extract_file
from scripts.audit_original_index_projection import (
    IndexSourceMismatch, _original_sha_and_size, audit_row_projection,
)
from tests.test_history_index import FIELDS, NOW, row, write_csv


class OriginalProjectionAuditTests(unittest.TestCase):
    def fake_source(self, root: Path, *, year=2027, rows=None):
        db = root / "FICTIONAL-source-index.sqlite"
        original = root / "FICTIONAL.csv"
        if rows is None:
            rows = [row("fictional-id-1"), row("fictional-id-2")]
        write_csv(original, rows)
        slot = f"ARCHIVE:{year}"
        result = ingest_extract_file(
            db, original, source_url=ARCHIVE_DOWNLOAD.format(fy=year),
            source_kind="ARCHIVE", fiscal_year=year,
            observed_at=NOW, collection_mode=OPERATOR_FILE,
        )
        self.assertEqual(result["rows_scanned"], len(rows))
        return db, original, slot

    def test_every_genuine_fake_row_matches_complete_sqlite_projection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db, original, slot = self.fake_source(root)
            report = audit_row_projection(db, slot=slot, snapshot_root=root)
            self.assertEqual(
                report["status"],
                "EXACT_PRIVATE_SOURCE_ROW_PROJECTION_PASS_UNAPPROVED",
            )
            self.assertEqual(report["rows_checked"], 2)
            self.assertTrue(report["exact_row_fields_verified"])
            self.assertTrue(report["source_original_sha256_verified"])
            for flag in (
                "private_sqlite_mutated", "source_original_bytes_retained_by_audit",
                "independent_publisher_review_approved", "FY2027_catalog_approved",
                "encrypted_offdevice_restore_verified",
                "customer_release_authorized",
            ):
                self.assertIs(report[flag], False, flag)
            self.assertEqual(
                report["source_original_sha256"],
                ingest_extract_file(
                    db, original, source_url=ARCHIVE_DOWNLOAD.format(fy=2027),
                    source_kind="ARCHIVE", fiscal_year=2027,
                    observed_at=NOW, collection_mode=OPERATOR_FILE,
                )["extract_sha256"],
            )

    def test_unmodified_original_does_not_excuse_mutated_sqlite_notice_fields(self):
        # The normal fast source index integrity gate checks original digest,
        # source count and nonblank NoticeId but does not scan each displayed
        # SQLite field back against the original. This independent deep
        # audit must detect field substitutions with count unchanged.
        fields = (
            ("notice_id", "fake-reassigned-identity"),
            ("solicitation_norm", "WRONG-NUMBER"),
            ("aac_code", "MISMATCHED-AAC"),
            ("office", "WRONG OFFICE"),
            ("posted_date", "01/01/1970"),
            ("row_sha256", "0" * 64),
            ("link", "https://example.invalid/counterfeit-source"),
        )
        for field, bad in fields:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                db, _, slot = self.fake_source(root)
                with closing(sqlite3.connect(db)) as conn, conn:
                    conn.execute(
                        f"UPDATE opportunity_rows SET {field}=? "
                        "WHERE snapshot_id=(SELECT snapshot_id FROM current_sources "
                        "WHERE slot=?) AND row_number=1",
                        (bad, slot),
                    )
                with self.assertRaises(IndexSourceMismatch):
                    audit_row_projection(db, slot=slot, snapshot_root=root)

    def test_missing_extra_and_reordered_sqlite_rows_block_exactness(self):
        for variant in ("delete", "extra"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                db, _, slot = self.fake_source(root)
                with closing(sqlite3.connect(db)) as conn, conn:
                    if variant == "delete":
                        conn.execute(
                            "DELETE FROM opportunity_rows WHERE row_number=1 "
                            "AND snapshot_id=(SELECT snapshot_id FROM "
                            "current_sources WHERE slot=?)", (slot,),
                        )
                    else:
                        conn.execute(
                            "UPDATE opportunity_rows SET row_number=99 "
                            "WHERE row_number=2 AND snapshot_id=(SELECT "
                            "snapshot_id FROM current_sources WHERE slot=?)",
                            (slot,),
                        )
                with self.assertRaises(IndexSourceMismatch):
                    audit_row_projection(db, slot=slot, snapshot_root=root)

    def test_header_only_csv_source_year_is_real_even_with_zero_actions(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            db, _, slot=self.fake_source(root,year=1969,rows=[])
            r=audit_row_projection(db,slot=slot,snapshot_root=root)
            self.assertEqual(r["rows_checked"],0)
            self.assertTrue(r["source_original_sha256_verified"])
            self.assertFalse(r["FY2027_catalog_approved"])

    def test_sqlite_pointer_outside_explicit_private_root_is_never_read(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            inside=root/"index"
            outside=root/"separately-protected-public-origin"
            inside.mkdir()
            outside.mkdir()
            db, _, slot=self.fake_source(outside)
            with self.assertRaises(IndexSourceMismatch):
                audit_row_projection(db,slot=slot,snapshot_root=inside)
            # Operator-allowed root resolves correctly, but grants no FY
            # publisher/catalog approval to this synthetic row.
            self.assertEqual(
                audit_row_projection(db,slot=slot,snapshot_root=outside)["rows_checked"],
                2,
            )

    def test_missing_index_never_created_by_read_only_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            db=root/"uncreated.sqlite"
            with self.assertRaises((IndexSourceMismatch,FileNotFoundError)):
                audit_row_projection(db,slot="ARCHIVE:2027",snapshot_root=root)
            self.assertFalse(db.exists())

    def test_unapproved_future_year_and_unknown_slot_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            db, _, _ = self.fake_source(root)
            for slot in ("ARCHIVE:2028","ARCHIVE:2030","ARCHIVE:2027;DROP TABLE",
                         "ARCHIVE:1","ARCHIVE:2100", "", None):
                with self.subTest(slot=slot),self.assertRaises(IndexSourceMismatch):
                    audit_row_projection(db,slot=slot,snapshot_root=root)

    def test_exact_source_fingerprint_is_mandatory_even_if_index_rows_match(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            db, source, slot = self.fake_source(root)
            data=source.read_bytes()
            source.write_bytes(data.replace(b"fictional-id-1",b"fictional-id-X"))
            with self.assertRaises(IndexSourceMismatch):
                audit_row_projection(db,slot=slot,snapshot_root=root)



    def test_source_swap_between_hash_and_sqlite_comparison_fails_closed(self):
        # The local original is A when its SHA is checked, but switches to
        # B (the tampered SQLite projection) before the CSV scan. A single
        # pre-scan hash would falsely certify a forged source projection.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db, original, slot = self.fake_source(
                root, rows=[row("fictional-id-1")],
            )
            indexed_bytes = original.read_bytes()  # B: indexed CSV
            authentic_bytes = indexed_bytes.replace(
                b"fictional-id-1", b"fictional-id-X",
            )  # A: locally fingerprinted original
            self.assertNotEqual(authentic_bytes, indexed_bytes)
            self.assertEqual(len(authentic_bytes), len(indexed_bytes))
            original.write_bytes(authentic_bytes)
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute(
                    "UPDATE source_snapshots SET extract_sha256=?, size_bytes=? "
                    "WHERE snapshot_id=(SELECT snapshot_id FROM current_sources WHERE slot=?)",
                    (hashlib.sha256(authentic_bytes).hexdigest(), len(authentic_bytes), slot),
                )

            changed = False

            def switch_after_first_verified_hash(path):
                nonlocal changed
                digest, size = _original_sha_and_size(path)
                if not changed:
                    original.write_bytes(indexed_bytes)
                    changed = True
                return digest, size

            with patch(
                "scripts.audit_original_index_projection._original_sha_and_size",
                side_effect=switch_after_first_verified_hash,
            ):
                with self.assertRaises(IndexSourceMismatch):
                    audit_row_projection(db, slot=slot, snapshot_root=root)
            self.assertTrue(changed)



if __name__ == "__main__":
    unittest.main()
