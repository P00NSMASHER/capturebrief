import csv
import io
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from capturebrief_core.archive_catalog import (
    ARCHIVE_CATALOG_YEARS,
    ArchiveCatalogStale,
    catalog_snapshot,
)
from capturebrief_core.data_services import ACTIVE_DOWNLOAD, ARCHIVE_DOWNLOAD
from capturebrief_core.history import validate_history_receipts
from capturebrief_core.history_index import (
    APPROVED_FETCH,
    HistoryIndexError,
    download_extract_to_file,
    fetch_and_ingest_slot,
    index_status,
    ingest_extract_file,
    issue_history_receipt_from_index,
    sync_plan,
)

FIELDS = [
    "NoticeId","Sol#","PostedDate","Type","Active","AAC Code","Office","Link",
    "CGAC","FPDS Code","Department/Ind.Agency","Sub-Tier","BaseType",
]
NOW_DT=datetime(2026,9,21,15,30,tzinfo=timezone.utc)
NOW=NOW_DT.isoformat()


def row(notice, sol="SOL-1", aac="AAC1", posted="09/20/2026", active="Yes", office="OFFICE"):
    return {
        "NoticeId":notice,
        "Sol#":sol,
        "PostedDate":posted,
        "Type":"Solicitation",
        "Active":active,
        "AAC Code":aac,
        "Office":office,
        "Link":f"https://sam.gov/opp/{notice}/view",
        "CGAC":"9700",
        "FPDS Code":"FA1234",
        "Department/Ind.Agency":"DEPT OF DEFENSE",
        "Sub-Tier":"AIR FORCE",
        "BaseType":"Solicitation",
    }


def write_csv(path:Path, rows):
    with path.open("w",encoding="cp1252",newline="") as handle:
        w=csv.DictWriter(handle,fieldnames=FIELDS)
        w.writeheader(); w.writerows(rows)


class FakeResponse:
    def __init__(self,data:bytes):
        self._io=io.BytesIO(data)
        self.headers={"Content-Length":str(len(data))}
    def read(self,n=-1): return self._io.read(n)
    def __enter__(self): return self
    def __exit__(self,*args): return False


class HistoryIndexTests(unittest.TestCase):
    def build_complete_index(self,root:Path,*,collision=False):
        db=root/"history.sqlite"
        snapshots=root/"snapshots"
        active=root/"active.csv"
        active_rows=[row("a2"),row("a1",posted="09/15/2026")]
        if collision:
            active_rows.append(row("z9",aac="AAC2",office="OTHER OFFICE"))
        write_csv(active,active_rows)
        ingest_extract_file(db,active,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",observed_at=NOW,snapshot_dir=snapshots,collection_mode=APPROVED_FETCH)

        for fy in ARCHIVE_CATALOG_YEARS:
            p=root/f"fy{fy}.csv"
            rows=[]
            if fy==2026:
                rows=[row("a1",posted="09/15/2026",active="No"),row("a2",posted="09/20/2026",active="No")]
                if collision:
                    rows.append(row("z9",aac="AAC2",office="OTHER OFFICE",active="No"))
            write_csv(p,rows)
            ingest_extract_file(
                db,p,source_url=ARCHIVE_DOWNLOAD.format(fy=fy),source_kind="ARCHIVE",
                fiscal_year=fy,observed_at=NOW,snapshot_dir=snapshots,collection_mode=APPROVED_FETCH
            )
        return db,snapshots

    def test_full_catalog_index_issues_releasable_history_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db,_=self.build_complete_index(root)
            status=index_status(db,fiscal_year=2026,now=NOW_DT)
            self.assertTrue(status["complete"],status["missing_slots"])
            receipt=issue_history_receipt_from_index(
                db,solicitation_number="SOL-1",seed_notice_id="a2",
                observed_at=NOW,fiscal_year=2026
            )
            self.assertEqual(receipt["status"],"COMPLETE")
            self.assertEqual(set(receipt["action_ids"]),{"a1","a2"})
            scope=receipt["evidence_payload"]["scope"]
            self.assertEqual(scope["mode"],"FULL_CATALOG")
            self.assertEqual(scope["catalog_snapshot"],catalog_snapshot())
            self.assertEqual(scope["required_archive_fys"],list(ARCHIVE_CATALOG_YEARS))
            verdict,findings=validate_history_receipts(receipt["action_ids"],[receipt])
            self.assertEqual(verdict,"HISTORY_COMPLETE",[f.code for f in findings])


    def test_missing_original_bytes_block_complete_even_if_sqlite_status_is_approved(self):
        # Reproduced on actual PAAM-L044: a complete fictional FY2026
        # catalog's SQLite source path was changed to a nonexistent file,
        # yet the old index_status still returned complete=True.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db, _ = self.build_complete_index(root)
            self.assertTrue(index_status(db, fiscal_year=2026, now=NOW_DT)["complete"])
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute(
                    "UPDATE source_snapshots SET local_path=? "
                    "WHERE slot='ARCHIVE:2026'",
                    (str(root / "MISSING_OFFICIAL_ORIGINAL.csv"),),
                )
            status = index_status(db, fiscal_year=2026, now=NOW_DT)
            self.assertFalse(status["complete"])
            self.assertIn("ARCHIVE:2026", status["unverified_slots"])
            self.assertIn(
                "ARCHIVE:2026", status["missing_or_mismatched_source_bytes_slots"],
            )
            self.assertFalse(status["local_original_hashes_verified"])
            self.assertFalse(status["publisher_origin_independently_attested"])
            receipt = issue_history_receipt_from_index(
                db, solicitation_number="SOL-1", seed_notice_id="a2",
                observed_at=NOW, fiscal_year=2026,
            )
            self.assertEqual(receipt["status"], "OBSERVED_ONLY")
            self.assertFalse(receipt["evidence_payload"]["scope"]["coverage_complete"])
            self.assertFalse(
                receipt["evidence_payload"]["retained_original_hashes_verified"],
            )
            self.assertIn(
                "FULL_ARCHIVE_CATALOG_UNVERIFIED",
                receipt["evidence_payload"]["coverage_errors"],
            )


    def test_deleted_index_action_does_not_appear_as_complete_history(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db, _ = self.build_complete_index(root)
            self.assertTrue(index_status(db, fiscal_year=2026, now=NOW_DT)["complete"])
            with closing(sqlite3.connect(db)) as conn, conn:
                current = conn.execute(
                    "SELECT snapshot_id FROM current_sources WHERE slot='ARCHIVE:2026'"
                ).fetchone()[0]
                conn.execute(
                    "DELETE FROM opportunity_rows WHERE snapshot_id=? AND row_number=1",
                    (current,),
                )
            status = index_status(db, fiscal_year=2026, now=NOW_DT)
            self.assertFalse(status["complete"])
            self.assertIn("ARCHIVE:2026", status["indexed_row_count_mismatch_slots"])
            self.assertIn("ARCHIVE:2026", status["unverified_slots"])
            self.assertFalse(status["local_original_hashes_verified"])
            receipt = issue_history_receipt_from_index(
                db, solicitation_number="SOL-1", seed_notice_id="a2",
                observed_at=NOW, fiscal_year=2026,
            )
            self.assertEqual(receipt["status"], "OBSERVED_ONLY")
            self.assertIn(
                "ARCHIVE:2026",
                receipt["evidence_payload"]["indexed_row_count_mismatch_slots"],
            )

    def test_duplicate_notice_id_in_one_current_original_cannot_claim_complete(self):
        # NoticeId identifies the public action. Two rows with the same ID
        # inside one source snapshot require source adjudication, even when
        # the total row count and immutable original file SHA match.
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db,snapshots=self.build_complete_index(root)
            p=root/"duplicate-identifiers-invented.csv"
            write_csv(p, [
                row("a2",sol="SOL-1",aac="AAC1",posted="09/20/2026"),
                row("a2",sol="SOL-1",aac="AAC1",posted="09/21/2026"),
                row("a1",sol="SOL-1",aac="AAC1"),
            ])
            imported=ingest_extract_file(
                db,p,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",
                observed_at=NOW,snapshot_dir=snapshots,
                collection_mode=APPROVED_FETCH,
            )
            self.assertEqual(imported["rows_scanned"],3)
            status=index_status(db,fiscal_year=2026,now=NOW_DT)
            self.assertFalse(status["complete"])
            self.assertIn("ACTIVE",status["indexed_row_count_mismatch_slots"])
            self.assertIn("ACTIVE",status["unverified_slots"])
            receipt=issue_history_receipt_from_index(
                db,solicitation_number="SOL-1",seed_notice_id="a2",
                observed_at=NOW,fiscal_year=2026,
            )
            self.assertEqual(receipt["status"],"OBSERVED_ONLY")
            self.assertIn(
                "FULL_ARCHIVE_CATALOG_UNVERIFIED",
                receipt["evidence_payload"]["coverage_errors"],
            )

    def test_blank_identity_in_mutated_sqlite_projection_is_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db, _ = self.build_complete_index(root)
            with closing(sqlite3.connect(db)) as conn, conn:
                current = conn.execute(
                    "SELECT snapshot_id FROM current_sources WHERE slot='ARCHIVE:2026'"
                ).fetchone()[0]
                conn.execute(
                    "UPDATE opportunity_rows SET notice_id='' "
                    "WHERE snapshot_id=? AND row_number=1",
                    (current,),
                )
            status = index_status(db, fiscal_year=2026, now=NOW_DT)
            self.assertFalse(status["complete"])
            self.assertIn("ARCHIVE:2026", status["indexed_row_count_mismatch_slots"])

    def test_actual_zero_row_archive_does_not_require_fake_action(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db, _ = self.build_complete_index(root)
            status = index_status(db, fiscal_year=2026, now=NOW_DT)
            self.assertTrue(status["complete"], status)
            self.assertNotIn(
                "ARCHIVE:1980",
                status["indexed_row_count_mismatch_slots"],
            )
            self.assertTrue(status["local_original_hashes_verified"])
            self.assertFalse(status["publisher_origin_independently_attested"])

    def test_metadata_and_sha_tampering_never_certify_current_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db, _ = self.build_complete_index(root)
            self.assertTrue(index_status(db, fiscal_year=2026, now=NOW_DT)["complete"])
            with closing(sqlite3.connect(db)) as conn:
                conn.row_factory = sqlite3.Row
                original = dict(conn.execute(
                    "SELECT source_url, source_kind, fiscal_year, "
                    "extract_sha256, size_bytes, observed_at, local_path "
                    "FROM source_snapshots WHERE slot='ARCHIVE:2026'",
                ).fetchone())
            variants = (
                ("source_url", "https://attacker.example/forged.csv"),
                ("source_kind", "ACTIVE"),
                ("fiscal_year", 2025),
                ("extract_sha256", "0" * 64),
                ("size_bytes", original["size_bytes"] + 1),
                ("observed_at", "2026-09-22T16:00:00+00:00"),
                ("local_path", str(root / ".." / "OUTSIDE_PRIVATE_ROOT.csv")),
            )
            for field, bad in variants:
                with self.subTest(field=field):
                    with closing(sqlite3.connect(db)) as conn, conn:
                        conn.execute(
                            f"UPDATE source_snapshots SET {field}=? "
                            "WHERE slot='ARCHIVE:2026'",
                            (bad,),
                        )
                    # Do not hold an SQLite write lock while read-only
                    # status verification initializes and opens the index.
                    status = index_status(db, fiscal_year=2026, now=NOW_DT)
                    self.assertFalse(status["complete"])
                    self.assertIn("ARCHIVE:2026", status["unverified_slots"])
                    with closing(sqlite3.connect(db)) as conn, conn:
                        conn.execute(
                            f"UPDATE source_snapshots SET {field}=? "
                            "WHERE slot='ARCHIVE:2026'",
                            (original[field],),
                        )
            self.assertTrue(index_status(db, fiscal_year=2026, now=NOW_DT)["complete"])

    def test_explicit_external_source_root_must_be_operator_supplied(self):
        # Real operators may separately authorize an off-index private
        # original root. SQLite's untrusted path must not self-authorize it.
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            index_dir = parent / "index"
            archive_dir = parent / "authorized-extracts"
            index_dir.mkdir()
            archive_dir.mkdir()
            db = index_dir / "history.sqlite"
            active = archive_dir / "active.csv"
            write_csv(active, [row("a2")])
            ingest_extract_file(
                db, active, source_url=ACTIVE_DOWNLOAD, source_kind="ACTIVE",
                observed_at=NOW, snapshot_dir=archive_dir,
                collection_mode=APPROVED_FETCH,
            )
            for fy in ARCHIVE_CATALOG_YEARS:
                original = archive_dir / f"archive{fy}.csv"
                write_csv(original, [])
                ingest_extract_file(
                    db, original, source_url=ARCHIVE_DOWNLOAD.format(fy=fy),
                    source_kind="ARCHIVE", fiscal_year=fy, observed_at=NOW,
                    snapshot_dir=archive_dir, collection_mode=APPROVED_FETCH,
                )
            blocked = index_status(db, fiscal_year=2026, now=NOW_DT)
            self.assertFalse(blocked["complete"])
            self.assertIn("ACTIVE", blocked["missing_or_mismatched_source_bytes_slots"])
            approved_root_read = index_status(
                db, fiscal_year=2026, now=NOW_DT, snapshot_root=archive_dir,
            )
            self.assertTrue(approved_root_read["complete"])
            self.assertTrue(approved_root_read["local_original_hashes_verified"])
            self.assertFalse(approved_root_read["publisher_origin_independently_attested"])

    def test_missing_archive_slot_blocks_complete_history(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db,_=self.build_complete_index(root)
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute("DELETE FROM current_sources WHERE slot='ARCHIVE:1980'")
            status=index_status(db,fiscal_year=2026)
            self.assertFalse(status["complete"])
            self.assertIn("ARCHIVE:1980",status["missing_slots"])
            receipt=issue_history_receipt_from_index(
                db,solicitation_number="SOL-1",seed_notice_id="a2",
                observed_at=NOW,fiscal_year=2026
            )
            self.assertEqual(receipt["status"],"OBSERVED_ONLY")
            verdict,_=validate_history_receipts(receipt["action_ids"],[receipt])
            self.assertEqual(verdict,"HISTORY_UNRESOLVED")

    def test_seed_anchors_same_number_to_correct_aac(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db,_=self.build_complete_index(root,collision=True)
            receipt=issue_history_receipt_from_index(
                db,solicitation_number="SOL-1",seed_notice_id="a2",
                observed_at=NOW,fiscal_year=2026
            )
            self.assertEqual(set(receipt["action_ids"]),{"a1","a2"})
            self.assertNotIn("z9",receipt["action_ids"])
            self.assertEqual(receipt["evidence_payload"]["family"]["aac_code"],"AAC1")

    def test_unapproved_fy2027_actions_cannot_pollute_approved_fy2026_receipt(self):
        # Reproduced earlier: inserting an OPERATOR_FILE FY2027 snapshot
        # with the SAME solicitation and AAC caused a FY2026 receipt to
        # include a future notice yet still assert COMPLETE. The scope and
        # emitted evidence must both remain restricted to required FYs.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db, _ = self.build_complete_index(root)
            future = root / "FICTIONAL_FY2027_UNAPPROVED.csv"
            write_csv(
                future,
                [row("fictional-not-approved-2027", sol="SOL-1",
                     aac="AAC1", active="No")],
            )
            ingest_extract_file(
                db, future,
                source_url=ARCHIVE_DOWNLOAD.format(fy=2027),
                source_kind="ARCHIVE", fiscal_year=2027,
                observed_at=NOW, collection_mode="OPERATOR_FILE",
            )
            status = index_status(db, fiscal_year=2026, now=NOW_DT)
            self.assertTrue(status["complete"])
            self.assertIn("ARCHIVE:2027", status["present_slots"])
            receipt = issue_history_receipt_from_index(
                db, solicitation_number="SOL-1", seed_notice_id="a2",
                observed_at=NOW, fiscal_year=2026,
            )
            self.assertEqual(receipt["status"], "COMPLETE")
            self.assertEqual(set(receipt["action_ids"]), {"a1", "a2"})
            self.assertNotIn("fictional-not-approved-2027", receipt["action_ids"])
            scope = receipt["evidence_payload"]["scope"]
            self.assertTrue(scope["out_of_scope_source_snapshots_excluded"])
            self.assertNotIn(2027, scope["supplied_archive_fys"])
            self.assertTrue(all(
                row["fiscal_year"] != 2027
                for row in receipt["evidence_payload"]["source_snapshots"]
            ))
            self.assertTrue(receipt["evidence_payload"]["retained_original_hashes_verified"])
            self.assertFalse(receipt["evidence_payload"]["publisher_origin_independently_attested"])

            # Using the unapproved future notice as seed for FY2026 must
            # not use that row to manufacture an in-scope history family.
            future_seed = issue_history_receipt_from_index(
                db, solicitation_number="SOL-1",
                seed_notice_id="fictional-not-approved-2027",
                observed_at=NOW, fiscal_year=2026,
            )
            self.assertEqual(future_seed["status"], "OBSERVED_ONLY")
            self.assertEqual(future_seed["action_ids"], [])
            self.assertIn(
                "SEED_NOTICE_NOT_IN_CURRENT_INDEX",
                future_seed["evidence_payload"]["coverage_errors"],
            )

    def test_same_aac_different_office_never_claims_complete_history(self):
        # Reproduced directly on PAAM-L044 using synthetic source files:
        # same Sol# + AAC but distinct offices previously included unrelated
        # notice identities in a status=COMPLETE family.
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db,snapshots=self.build_complete_index(root)
            path=root/"different-office-active.csv"
            write_csv(path,[
                row("a2",sol="SOL-1",aac="AAC1",office="OFFICE"),
                row("a1",sol="SOL-1",aac="AAC1",office="OFFICE"),
                row("fictional-other-office",sol="SOL-1",aac="AAC1",office="OTHER OFFICE"),
            ])
            ingest_extract_file(
                db,path,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",
                observed_at=NOW,snapshot_dir=snapshots,
                collection_mode=APPROVED_FETCH,
            )
            self.assertTrue(index_status(db,fiscal_year=2026,now=NOW_DT)["complete"])
            receipt=issue_history_receipt_from_index(
                db,solicitation_number="SOL-1",seed_notice_id="a2",
                observed_at=NOW,fiscal_year=2026,
            )
            self.assertEqual(receipt["status"],"OBSERVED_ONLY")
            self.assertEqual(set(receipt["action_ids"]),{"a1","a2"})
            self.assertNotIn("fictional-other-office",receipt["action_ids"])
            self.assertIn(
                "FAMILY_OFFICE_COLLISION_REQUIRES_REVIEW",
                receipt["evidence_payload"]["coverage_errors"],
            )
            self.assertTrue(receipt["evidence_payload"]["scope"]["coverage_complete"])
            verdict,_=validate_history_receipts(receipt["action_ids"],[receipt])
            self.assertEqual(verdict,"HISTORY_UNRESOLVED")

    def test_same_aac_mixed_missing_office_blocks_complete_history(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);db,snapshots=self.build_complete_index(root)
            path=root/"missing-office-active.csv"
            write_csv(path,[
                row("a2",aac="AAC1",office="OFFICE"),
                row("unknown-office-notice",aac="AAC1",office=""),
            ])
            ingest_extract_file(
                db,path,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",
                observed_at=NOW,snapshot_dir=snapshots,collection_mode=APPROVED_FETCH,
            )
            receipt=issue_history_receipt_from_index(
                db,solicitation_number="SOL-1",seed_notice_id="a2",
                observed_at=NOW,fiscal_year=2026,
            )
            self.assertEqual(receipt["status"],"OBSERVED_ONLY")
            self.assertEqual(set(receipt["action_ids"]),{"a1","a2"})
            self.assertNotIn("unknown-office-notice",receipt["action_ids"])
            self.assertIn(
                "FAMILY_OFFICE_COLLISION_REQUIRES_REVIEW",
                receipt["evidence_payload"]["coverage_errors"],
            )

    def test_unanchored_seed_office_returns_no_cross_office_family(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);db,snapshots=self.build_complete_index(root)
            path=root/"ambiguous-seed-office-active.csv"
            write_csv(path,[
                row("seed-without-office",sol="SOL-1",aac="AAC1",office=""),
                row("other-office-one",sol="SOL-1",aac="AAC1",office="ONE OFFICE"),
                row("other-office-two",sol="SOL-1",aac="AAC1",office="TWO OFFICE"),
            ])
            ingest_extract_file(
                db,path,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",
                observed_at=NOW,snapshot_dir=snapshots,collection_mode=APPROVED_FETCH,
            )
            receipt=issue_history_receipt_from_index(
                db,solicitation_number="SOL-1",seed_notice_id="seed-without-office",
                observed_at=NOW,fiscal_year=2026,
            )
            self.assertEqual(receipt["status"],"OBSERVED_ONLY")
            # The exact seed remains observable, but the two distinct
            # offices cannot be associated or reported as COMPLETE.
            self.assertEqual(receipt["action_ids"],["seed-without-office"])
            self.assertIn(
                "FAMILY_SEED_OFFICE_MISSING",
                receipt["evidence_payload"]["coverage_errors"],
            )
            self.assertIn(
                "FAMILY_OFFICE_COLLISION_REQUIRES_REVIEW",
                receipt["evidence_payload"]["coverage_errors"],
            )

    def test_missing_seed_aac_same_office_other_agency_is_partial(self):
        # Reproduced on PAAM-L044: missing seed AAC, same office and Sol#
        # combined unrelated AAC notice in a COMPLETE family.
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);db,snapshots=self.build_complete_index(root)
            path=root/"missing-seed-aac-active.csv"
            write_csv(path,[
                row("seed-without-aac",sol="SOL-1",aac="",office="OFFICE"),
                row("unrelated-known-aac",sol="SOL-1",aac="OTHER-AAC",office="OFFICE"),
            ])
            ingest_extract_file(db,path,source_url=ACTIVE_DOWNLOAD,
                source_kind="ACTIVE",observed_at=NOW,snapshot_dir=snapshots,
                collection_mode=APPROVED_FETCH)
            self.assertTrue(index_status(db,fiscal_year=2026,now=NOW_DT)["complete"])
            receipt=issue_history_receipt_from_index(db,
                solicitation_number="SOL-1",seed_notice_id="seed-without-aac",
                observed_at=NOW,fiscal_year=2026)
            self.assertEqual(receipt["status"],"OBSERVED_ONLY")
            self.assertEqual(receipt["action_ids"],["seed-without-aac"])
            self.assertNotIn("unrelated-known-aac",receipt["action_ids"])
            self.assertIn("FAMILY_AAC_COLLISION_REQUIRES_REVIEW",
                receipt["evidence_payload"]["coverage_errors"])

    def test_seed_missing_both_aac_and_office_cannot_claim_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);db,snapshots=self.build_complete_index(root)
            path=root/"missing-agency-office-active.csv"
            write_csv(path,[
                row("seed-without-both",sol="SOL-1",aac="",office=""),
                row("other-agency-identity",sol="SOL-1",aac="AAC1",office="OFFICE"),
            ])
            ingest_extract_file(db,path,source_url=ACTIVE_DOWNLOAD,
                source_kind="ACTIVE",observed_at=NOW,snapshot_dir=snapshots,
                collection_mode=APPROVED_FETCH)
            receipt=issue_history_receipt_from_index(db,
                solicitation_number="SOL-1",seed_notice_id="seed-without-both",
                observed_at=NOW,fiscal_year=2026)
            self.assertEqual(receipt["status"],"OBSERVED_ONLY")
            self.assertEqual(receipt["action_ids"],["seed-without-both"])
            self.assertIn("FAMILY_AGENCY_IDENTITY_MISSING",
                receipt["evidence_payload"]["coverage_errors"])

    def test_same_office_and_sol_cannot_complete_without_seed_aac(self):
        # If every current sibling is also missing AAC, the old fallback
        # would mark matching Office/Sol# as a complete multi-notice family.
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db,snapshots=self.build_complete_index(root)
            p=root/"invented-no-aac-active.csv"
            write_csv(p, [
                row("fictional-seed",sol="SOL-1",aac="",office="OFFICE"),
                row("fictional-peer",sol="SOL-1",aac="",office="OFFICE"),
            ])
            ingest_extract_file(
                db,p,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",
                observed_at=NOW,snapshot_dir=snapshots,collection_mode=APPROVED_FETCH,
            )
            # Remove known AAC observations in the prior FY2026 archive;
            # this keeps the full synthetic catalog but isolates all-blank AAC.
            empty=root/"invented-fy2026-with-no-actions.csv"
            write_csv(empty, [])
            ingest_extract_file(
                db,empty,source_url=ARCHIVE_DOWNLOAD.format(fy=2026),
                source_kind="ARCHIVE",fiscal_year=2026,observed_at=NOW,
                snapshot_dir=snapshots,collection_mode=APPROVED_FETCH,
            )
            self.assertTrue(index_status(db,fiscal_year=2026,now=NOW_DT)["complete"])
            receipt=issue_history_receipt_from_index(
                db,solicitation_number="SOL-1",seed_notice_id="fictional-seed",
                observed_at=NOW,fiscal_year=2026,
            )
            self.assertEqual(receipt["status"],"OBSERVED_ONLY")
            self.assertEqual(receipt["action_ids"],["fictional-seed"])
            self.assertIn(
                "FAMILY_AAC_ANCHOR_MISSING",
                receipt["evidence_payload"]["coverage_errors"],
            )

    def test_same_aac_and_sol_cannot_complete_without_seed_office(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);db,snapshots=self.build_complete_index(root)
            p=root/"invented-no-office-active.csv"
            write_csv(p,[
                row("fictional-seed",sol="SOL-1",aac="AAC1",office=""),
                row("fictional-peer",sol="SOL-1",aac="AAC1",office=""),
            ])
            ingest_extract_file(
                db,p,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",
                observed_at=NOW,snapshot_dir=snapshots,collection_mode=APPROVED_FETCH,
            )
            empty=root/"invented-fy2026-with-no-actions.csv"
            write_csv(empty,[])
            ingest_extract_file(
                db,empty,source_url=ARCHIVE_DOWNLOAD.format(fy=2026),
                source_kind="ARCHIVE",fiscal_year=2026,observed_at=NOW,
                snapshot_dir=snapshots,collection_mode=APPROVED_FETCH,
            )
            self.assertTrue(index_status(db,fiscal_year=2026,now=NOW_DT)["complete"])
            receipt=issue_history_receipt_from_index(
                db,solicitation_number="SOL-1",seed_notice_id="fictional-seed",
                observed_at=NOW,fiscal_year=2026,
            )
            self.assertEqual(receipt["status"],"OBSERVED_ONLY")
            self.assertEqual(receipt["action_ids"],["fictional-seed"])
            self.assertIn(
                "FAMILY_SEED_OFFICE_MISSING",
                receipt["evidence_payload"]["coverage_errors"],
            )

    def test_unknown_aac_peer_blocks_complete_even_with_anchored_seed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);db,snapshots=self.build_complete_index(root)
            p=root/"invented-unknown-aac-peer.csv"
            write_csv(p,[
                row("a2",sol="SOL-1",aac="AAC1",office="OFFICE"),
                row("fictional-unanchored-peer",sol="SOL-1",aac="",office="OFFICE"),
            ])
            ingest_extract_file(
                db,p,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",
                observed_at=NOW,snapshot_dir=snapshots,collection_mode=APPROVED_FETCH,
            )
            receipt=issue_history_receipt_from_index(
                db,solicitation_number="SOL-1",seed_notice_id="a2",
                observed_at=NOW,fiscal_year=2026,
            )
            self.assertEqual(receipt["status"],"OBSERVED_ONLY")
            self.assertEqual(set(receipt["action_ids"]),{"a1","a2"})
            self.assertNotIn("fictional-unanchored-peer",receipt["action_ids"])
            self.assertIn(
                "FAMILY_UNANCHORED_AAC_PEER_REQUIRES_REVIEW",
                receipt["evidence_payload"]["coverage_errors"],
            )
            verdict,_=validate_history_receipts(receipt["action_ids"],[receipt])
            self.assertEqual(verdict,"HISTORY_UNRESOLVED")

    def test_seed_is_never_selected_from_bulk(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db,_=self.build_complete_index(root)
            receipt=issue_history_receipt_from_index(
                db,solicitation_number="SOL-1",seed_notice_id="missing",
                observed_at=NOW,fiscal_year=2026
            )
            self.assertEqual(receipt["status"],"OBSERVED_ONLY")
            self.assertEqual(receipt["action_ids"],[])
            self.assertIn("SEED_NOTICE_NOT_IN_CURRENT_INDEX",receipt["evidence_payload"]["coverage_errors"])

    def test_blank_solicitation_cannot_group_unrelated_notices_in_history(self):
        # The real FY2027 original contains seven notices without a Sol#.
        # A blank normalized join could otherwise manufacture a COMPLETE
        # history from distinct notices within the same AAC/office.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db, snapshots = self.build_complete_index(root)
            fixture = root / "blank-sol-number-active.csv"
            write_csv(
                fixture,
                [
                    row("blank-notice-1", sol="", aac="AAC1", office="OFFICE"),
                    row("blank-notice-2", sol="", aac="AAC1", office="OFFICE"),
                ],
            )
            ingested = ingest_extract_file(
                db,
                fixture,
                source_url=ACTIVE_DOWNLOAD,
                source_kind="ACTIVE",
                observed_at=NOW,
                snapshot_dir=snapshots,
                collection_mode=APPROVED_FETCH,
            )
            self.assertEqual(ingested["rows_scanned"], 2)
            self.assertTrue(index_status(db, fiscal_year=2026, now=NOW_DT)["complete"])
            with closing(sqlite3.connect(db)) as conn:
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM opportunity_rows "
                        "WHERE solicitation_norm='' AND snapshot_id=?",
                        (ingested["snapshot_id"],),
                    ).fetchone()[0],
                    2,
                )
            for empty in ("", "   ", "\t", None):
                with self.subTest(raw_solicitation=repr(empty)):
                    with self.assertRaisesRegex(ValueError, "nonempty"):
                        issue_history_receipt_from_index(
                            db,
                            solicitation_number=empty,
                            seed_notice_id="blank-notice-1",
                            observed_at=NOW,
                            fiscal_year=2026,
                        )

    def test_missing_solicitation_guard_precedes_index_creation(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td) / "must-not-create.sqlite"
            with self.assertRaisesRegex(ValueError, "nonempty"):
                issue_history_receipt_from_index(
                    index,
                    solicitation_number=" ",
                    seed_notice_id="blank-notice",
                    observed_at=NOW,
                    fiscal_year=2026,
                )
            self.assertFalse(index.exists())


    def test_missing_notice_id_blocks_entire_original_snapshot_atomically(self):
        # A source row without NoticeId cannot be independently traced to an
        # actual notice action. Never allow a FULL_CATALOG index to look
        # complete after silently importing or dropping such a row.
        for n, raw_notice in enumerate(("", " ", None)):
            with self.subTest(raw_notice=repr(raw_notice)), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                p = root / "invented-missing-notice.csv"
                db = root / "invented-unapproved.sqlite"
                write_csv(
                    p,
                    [row("valid-fake-id"), row(raw_notice, sol="FAKE-SECOND")],
                )
                with self.assertRaisesRegex(HistoryIndexError, "empty NoticeId"):
                    ingest_extract_file(
                        db, p,
                        source_url=ACTIVE_DOWNLOAD,
                        source_kind="ACTIVE",
                        observed_at=NOW,
                        collection_mode="OPERATOR_FILE",
                        snapshot_dir=None,
                    )
                with closing(sqlite3.connect(db)) as conn:
                    for table in ("source_snapshots", "current_sources", "opportunity_rows"):
                        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        self.assertEqual(count, 0, table)

    def test_header_only_archive_year_remains_valid_source_metadata(self):
        # Genuine FY1969 and FY1981 originals are 47-column header-only
        # CSVs, not absent files. Zero legitimate rows is distinct from an
        # actual record whose identity is blank or unverifiable.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "invented-valid-header-only.csv"
            db = root / "invented-unapproved.sqlite"
            write_csv(p, [])
            result = ingest_extract_file(
                db, p,
                source_url=ARCHIVE_DOWNLOAD.format(fy=1981),
                source_kind="ARCHIVE",
                fiscal_year=1981,
                observed_at=NOW,
                collection_mode="OPERATOR_FILE",
                snapshot_dir=None,
            )
            self.assertEqual(result["rows_scanned"], 0)
            self.assertEqual(result["slot"], "ARCHIVE:1981")
            with closing(sqlite3.connect(db)) as conn:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM source_snapshots").fetchone()[0], 1,
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM opportunity_rows").fetchone()[0], 0,
                )


    def test_undecodable_original_bytes_do_not_mutate_notice_identity(self):
        # Reproduced prior failure: the importer converted an undefined
        # cp1252 NoticeId byte (0x81) into U+FFFD, yet indexed the
        # apparently valid row and could certify its altered identity.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "FICTIONAL-publisher-original.csv"
            write_csv(source, [row("VALID_FICTIONAL_ID")])
            pristine = source.read_bytes()
            self.assertIn(b"VALID_FICTIONAL_ID", pristine)
            for label, prefix, invalid in (
                ("undefined-cp1252-byte", b"", b"INVALID_\x81_ID"),
                ("invalid-utf8-bom-body", b"\xef\xbb\xbf", b"INVALID_\xff_ID"),
            ):
                with self.subTest(case=label):
                    db = root / f"{label}.sqlite"
                    source.write_bytes(
                        prefix + pristine.replace(
                            b"VALID_FICTIONAL_ID",
                            invalid,
                        )
                    )
                    with self.assertRaises(UnicodeDecodeError):
                        ingest_extract_file(
                            db, source,
                            source_url=ACTIVE_DOWNLOAD,
                            source_kind="ACTIVE",
                            observed_at=NOW,
                            collection_mode="OPERATOR_FILE",
                            snapshot_dir=None,
                        )
                    with closing(sqlite3.connect(db)) as conn:
                        self.assertEqual(
                            conn.execute("SELECT COUNT(*) FROM source_snapshots").fetchone()[0], 0,
                        )
                        self.assertEqual(
                            conn.execute("SELECT COUNT(*) FROM current_sources").fetchone()[0], 0,
                        )
                        self.assertEqual(
                            conn.execute("SELECT COUNT(*) FROM opportunity_rows").fetchone()[0], 0,
                        )

    def test_valid_cp1252_notice_id_remains_exact_after_strict_decoding(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "invented-cp1252-source.csv"
            db = root / "invented-source.sqlite"
            write_csv(source, [row("FICTIONAL-CAF\u00c9")])
            result = ingest_extract_file(
                db, source,
                source_url=ACTIVE_DOWNLOAD,
                source_kind="ACTIVE",
                observed_at=NOW,
                collection_mode="OPERATOR_FILE",
                snapshot_dir=None,
            )
            self.assertEqual(result["rows_scanned"], 1)
            with closing(sqlite3.connect(db)) as conn:
                value = conn.execute("SELECT notice_id FROM opportunity_rows").fetchone()[0]
            self.assertEqual(value, "FICTIONAL-CAF\u00c9")

    def test_content_addressed_snapshots_are_reused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=root/"history.sqlite"; snapshots=root/"snapshots"; p=root/"active.csv"
            write_csv(p,[row("a2")])
            first=ingest_extract_file(db,p,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",observed_at=NOW,snapshot_dir=snapshots,collection_mode=APPROVED_FETCH)
            second=ingest_extract_file(db,p,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",observed_at=NOW,snapshot_dir=snapshots,collection_mode=APPROVED_FETCH)
            self.assertFalse(first["reused"]); self.assertTrue(second["reused"])
            stored=Path(first["local_path"])
            self.assertTrue(stored.exists())
            self.assertEqual(stored.stem,first["extract_sha256"])
            with closing(sqlite3.connect(db)) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM source_snapshots").fetchone()[0],1)

    def test_replacing_slot_preserves_old_snapshot_but_queries_new_current(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db,snapshots=self.build_complete_index(root)
            p=root/"active-new.csv"
            write_csv(p,[row("a3"),row("a2")])
            ingest_extract_file(db,p,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",observed_at=NOW,snapshot_dir=snapshots,collection_mode=APPROVED_FETCH)
            with closing(sqlite3.connect(db)) as conn:
                active_snapshots=conn.execute("SELECT COUNT(*) FROM source_snapshots WHERE slot='ACTIVE'").fetchone()[0]
            self.assertEqual(active_snapshots,2)
            receipt=issue_history_receipt_from_index(
                db,solicitation_number="SOL-1",seed_notice_id="a3",
                observed_at=NOW,fiscal_year=2026
            )
            self.assertIn("a3",receipt["action_ids"])
            # a1 remains available via archive evidence; stale active rows do not leak through current_sources.
            self.assertEqual(set(receipt["action_ids"]),{"a1","a2","a3"})

    def test_sync_plan_lists_only_missing_catalog_slots(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db,_=self.build_complete_index(root)
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute("DELETE FROM current_sources WHERE slot='ARCHIVE:1970'")
                conn.execute("DELETE FROM current_sources WHERE slot='ACTIVE'")
            plan=sync_plan(db,fiscal_year=2026,now=NOW_DT)
            slots={x["slot"] for x in plan["download_plan"]}
            self.assertEqual(slots,{"ACTIVE","ARCHIVE:1970"})

    def test_streaming_fetch_ingests_only_requested_slot(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=root/"history.sqlite"; dest=root/"fy2026.csv"; snapshots=root/"snapshots"
            buf=io.StringIO()
            writer=csv.DictWriter(buf,fieldnames=FIELDS)
            writer.writeheader(); writer.writerow(row("a2"))
            data=buf.getvalue().encode("cp1252")
            # This fixture is dated September 2026 (FY2026); freeze only the
            # test clock, never the production FY2027 catalog freshness guard.
            with patch("capturebrief_core.history_index.fiscal_year_for_datetime",
                       return_value=2026):
                result=fetch_and_ingest_slot(
                    db,slot="ARCHIVE:2026",destination=dest,snapshot_dir=snapshots,
                    observed_at=NOW,opener=lambda req,timeout=120: FakeResponse(data)
                )
            self.assertEqual(result["ingest"]["slot"],"ARCHIVE:2026")
            self.assertTrue(dest.exists())
            status=index_status(db,fiscal_year=2026)
            self.assertIn("ARCHIVE:2026",status["present_slots"])
            self.assertIn("ACTIVE",status["missing_slots"])
            self.assertGreater(len(status["missing_slots"]),1)

    def test_unverified_fy2027_archive_still_fails_before_download(self):
        # Real FY2027 automation must not reuse a human-reviewed FY2026 catalog.
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=root/"history.sqlite"; dest=root/"fy2026.csv"
            def forbidden_network(*args,**kwargs):
                self.fail("stale catalog must block before a provider request")
            with patch("capturebrief_core.history_index.fiscal_year_for_datetime",
                       return_value=2027):
                with self.assertRaises(ArchiveCatalogStale):
                    fetch_and_ingest_slot(
                        db,slot="ARCHIVE:2026",destination=dest,
                        opener=forbidden_network,
                    )
            self.assertFalse(dest.exists())
            self.assertFalse(db.exists())

    def test_approved_fetch_without_snapshot_dir_retains_immutable_default_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=root/"history.sqlite"; dest=root/"active.csv"
            buf=io.StringIO()
            writer=csv.DictWriter(buf,fieldnames=FIELDS)
            writer.writeheader(); writer.writerow(row("a2"))
            data=buf.getvalue().encode("cp1252")
            result=fetch_and_ingest_slot(
                db,slot="ACTIVE",destination=dest,
                opener=lambda req,timeout=120: FakeResponse(data),
            )
            retained=Path(result["ingest"]["local_path"])
            self.assertTrue(result["retention"]["content_addressed"])
            self.assertFalse(result["retention"]["caller_supplied_snapshot_dir"])
            self.assertEqual(retained.parent,root/"history.sqlite.snapshots")
            self.assertEqual(retained.stem,result["ingest"]["extract_sha256"])
            self.assertEqual(retained.read_bytes(),data)
            self.assertNotEqual(retained,dest)
            with closing(sqlite3.connect(db)) as conn:
                stored=conn.execute(
                    "SELECT local_path FROM source_snapshots WHERE snapshot_id=?",
                    (result["ingest"]["snapshot_id"],),
                ).fetchone()[0]
            self.assertEqual(Path(stored),retained)

    def test_content_addressed_snapshot_conflict_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=root/"history.sqlite"; p=root/"active.csv"; snapshots=root/"snapshots"
            write_csv(p,[row("a2")])
            import hashlib
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            snapshots.mkdir()
            conflicting=snapshots/f"{digest}.csv"
            conflicting.write_bytes(b"different")
            with self.assertRaises(HistoryIndexError) as ctx:
                ingest_extract_file(
                    db,p,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",
                    observed_at=NOW,snapshot_dir=snapshots,collection_mode=APPROVED_FETCH,
                )
            self.assertIn("content-addressed snapshot retention failed",str(ctx.exception))
            self.assertEqual(conflicting.read_bytes(),b"different")

    def test_data_services_redirect_to_unapproved_host_is_rejected(self):
        class RedirectResponse(FakeResponse):
            def geturl(self):
                return "https://example.com/export.csv"

        with tempfile.TemporaryDirectory() as td:
            root=Path(td); dest=root/"active.csv"; dest.write_bytes(b"previous")
            with self.assertRaises(RuntimeError):
                download_extract_to_file(
                    dest,
                    source_url=ACTIVE_DOWNLOAD,
                    opener=lambda req,timeout=120: RedirectResponse(b"abc"),
                )
            self.assertEqual(dest.read_bytes(),b"previous")
            self.assertFalse((root/"active.csv.download.lock").exists())

    def test_truncated_content_length_is_rejected_before_publication(self):
        class TruncatedResponse(FakeResponse):
            def __init__(self):
                self._io=io.BytesIO(b"abc")
                self.headers={"Content-Length":"9"}

        with tempfile.TemporaryDirectory() as td:
            root=Path(td); dest=root/"active.csv"; dest.write_bytes(b"previous")
            with self.assertRaises(HistoryIndexError) as ctx:
                download_extract_to_file(
                    dest,
                    source_url=ACTIVE_DOWNLOAD,
                    opener=lambda req,timeout=120: TruncatedResponse(),
                )
            self.assertIn("does not match Content-Length",str(ctx.exception))
            self.assertEqual(dest.read_bytes(),b"previous")
            self.assertEqual(list(root.glob(".active.csv.*.download")),[])
            self.assertFalse((root/"active.csv.download.lock").exists())

    def test_invalid_content_length_is_rejected_before_publication(self):
        class InvalidLengthResponse(FakeResponse):
            def __init__(self):
                self._io=io.BytesIO(b"abc")
                self.headers={"Content-Length":"not-an-integer"}

        with tempfile.TemporaryDirectory() as td:
            root=Path(td); dest=root/"active.csv"
            with self.assertRaises(HistoryIndexError):
                download_extract_to_file(
                    dest,
                    source_url=ACTIVE_DOWNLOAD,
                    opener=lambda req,timeout=120: InvalidLengthResponse(),
                )
            self.assertFalse(dest.exists())
            self.assertEqual(list(root.glob(".active.csv.*.download")),[])

    def test_failed_download_preserves_existing_destination_and_cleans_temp(self):
        class FailingResponse(FakeResponse):
            def __init__(self):
                super().__init__(b"abcdef")
                self.calls=0
            def read(self,n=-1):
                self.calls += 1
                if self.calls==1:
                    return b"abc"
                raise OSError("simulated transport/read failure")

        with tempfile.TemporaryDirectory() as td:
            root=Path(td); dest=root/"active.csv"; dest.write_bytes(b"previous-complete-file")
            with self.assertRaises(OSError):
                download_extract_to_file(
                    dest,
                    source_url=ACTIVE_DOWNLOAD,
                    opener=lambda req,timeout=120: FailingResponse(),
                )
            self.assertEqual(dest.read_bytes(),b"previous-complete-file")
            self.assertEqual(list(root.glob(".active.csv.*.download")),[])
            self.assertFalse((root/"active.csv.download.lock").exists())

    def test_operator_import_is_present_but_not_releasable(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=root/"history.sqlite"; p=root/"active.csv"
            write_csv(p,[row("a2")])
            ingest_extract_file(db,p,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",observed_at=NOW)
            status=index_status(db,fiscal_year=2026,now=NOW_DT)
            self.assertIn("ACTIVE",status["present_slots"])
            self.assertIn("ACTIVE",status["unverified_slots"])
            self.assertFalse(status["complete"])
            plan=sync_plan(db,fiscal_year=2026,now=NOW_DT)
            task=next(x for x in plan["download_plan"] if x["slot"]=="ACTIVE")
            self.assertEqual(task["reason"],"UNVERIFIED")

    def test_stale_approved_sources_require_refresh(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db,_=self.build_complete_index(root)
            stale=(NOW_DT-timedelta(days=10)).isoformat()
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute("UPDATE current_sources SET checked_at=? WHERE slot='ARCHIVE:2026'",(stale,))
                conn.execute("UPDATE current_sources SET checked_at=? WHERE slot='ACTIVE'",(stale,))
            status=index_status(db,fiscal_year=2026,now=NOW_DT)
            self.assertIn("ACTIVE",status["stale_slots"])
            self.assertIn("ARCHIVE:2026",status["stale_slots"])
            self.assertFalse(status["complete"])
            plan=sync_plan(db,fiscal_year=2026,now=NOW_DT)
            reasons={x["slot"]:x["reason"] for x in plan["download_plan"]}
            self.assertEqual(reasons["ACTIVE"],"STALE")
            self.assertEqual(reasons["ARCHIVE:2026"],"STALE")
            receipt=issue_history_receipt_from_index(
                db,solicitation_number="SOL-1",seed_notice_id="a2",
                observed_at=NOW,fiscal_year=2026
            )
            self.assertEqual(receipt["status"],"OBSERVED_ONLY")
            self.assertIn("FULL_ARCHIVE_CATALOG_STALE",receipt["evidence_payload"]["coverage_errors"])

    def test_catalog_must_be_refreshed_after_current_through_fy(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ArchiveCatalogStale):
                index_status(Path(td)/"history.sqlite",fiscal_year=2027)


if __name__=="__main__":
    unittest.main()
