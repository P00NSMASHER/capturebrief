"""Synthetic-only QA for unapproved FY2027 private-index coverage planning."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from capturebrief_core.archive_catalog import ArchiveCatalogStale
from capturebrief_core.data_services import ARCHIVE_DOWNLOAD
from capturebrief_core.history_index import APPROVED_FETCH
from scripts.source_coverage_audit import (
    inspect_private_index, inspect_unapproved_fy2027_candidate_index,
)
from tests.test_source_coverage_audit import make_index

NOW = datetime(2026, 10, 19, 20, 0, tzinfo=timezone.utc)
ADDED = (1969, 1981, 2027)


def fake_candidate_index(root: Path) -> tuple[Path, dict[int, Path]]:
    db, _ = make_index(root)
    stamp = NOW.isoformat()
    new_files: dict[int, Path] = {}
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("UPDATE current_sources SET checked_at=?", (stamp,))
        conn.execute("UPDATE source_snapshots SET observed_at=?", (stamp,))
        for fy in ADDED:
            slot = f"ARCHIVE:{fy}"
            p = root / f"{slot.replace(':', '-')}.csv"
            data = f"FAKE-not-real-source,FY{fy}\n".encode("ascii")
            p.write_bytes(data)
            new_files[fy] = p
            cur = conn.execute(
                "INSERT INTO source_snapshots "
                "(slot,source_kind,fiscal_year,source_url,extract_sha256,"
                "size_bytes,observed_at,local_path,rows_scanned) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (slot, "ARCHIVE", fy, ARCHIVE_DOWNLOAD.format(fy=fy),
                 hashlib.sha256(data).hexdigest(), len(data), stamp, str(p), 1),
            )
            conn.execute(
                "INSERT INTO current_sources "
                "(slot,snapshot_id,checked_at,collection_mode) VALUES(?,?,?,?)",
                (slot, cur.lastrowid, stamp, APPROVED_FETCH),
            )
        conn.commit()
    return db, new_files


class FY2027UnapprovedCandidateCoverageTests(unittest.TestCase):
    def test_existing_fy2026_private_index_explicitly_lacks_three_candidate_years(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = make_index(Path(tmp))
            before = db.read_bytes()
            result = inspect_unapproved_fy2027_candidate_index(
                db, now=NOW, verify_bytes=True,
            )
            self.assertEqual(result["required_slot_count"], 35)
            self.assertEqual(
                result["missing_slots"],
                ["ARCHIVE:1969", "ARCHIVE:1981", "ARCHIVE:2027"],
            )
            self.assertFalse(result["candidate_metadata_complete"])
            self.assertFalse(result["candidate_local_file_hashes_match"])
            self.assertFalse(result["approved_full_catalog_coverage"])
            self.assertFalse(result["customer_release_authorized"])
            self.assertEqual(before, db.read_bytes())
            with self.assertRaises(ArchiveCatalogStale):
                inspect_private_index(db, fiscal_year=2027, now=NOW)

    def test_even_perfect_fake_35_slot_hashes_cannot_authorize_fy2027(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, paths = fake_candidate_index(Path(tmp))
            before = db.read_bytes()
            result = inspect_unapproved_fy2027_candidate_index(
                db, now=NOW, verify_bytes=True,
            )
            self.assertEqual(result["fresh_slot_count"], 35)
            self.assertEqual(result["required_slot_count"], 35)
            self.assertTrue(result["candidate_metadata_complete"])
            self.assertTrue(result["candidate_local_file_hashes_match"])
            self.assertFalse(result["candidate_catalog_approved"])
            self.assertFalse(result["human_catalog_approval_supplied"])
            self.assertFalse(result["publisher_authenticity_independently_established"])
            self.assertFalse(result["approved_full_catalog_coverage"])
            self.assertFalse(result["customer_release_authorized"])
            self.assertFalse(result["source_files_downloaded_by_this_tool"])
            self.assertRegex(result["candidate_observation_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(before, db.read_bytes())

            paths[2027].write_bytes(b"tampered but equal length X")
            rejected = inspect_unapproved_fy2027_candidate_index(
                db, now=NOW, verify_bytes=True,
            )
            self.assertIn("ARCHIVE:2027", rejected["hash_mismatch_slots"])
            self.assertFalse(rejected["candidate_local_file_hashes_match"])

    def test_unavailable_index_does_not_get_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.sqlite"
            with self.assertRaises((OSError, FileNotFoundError)):
                inspect_unapproved_fy2027_candidate_index(
                    missing, now=NOW, verify_bytes=True,
                )
            self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
