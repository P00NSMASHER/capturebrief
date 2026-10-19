"""Offline source-index gate regressions. All data and provider labels are FAKE."""
from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from capturebrief_core.archive_catalog import ARCHIVE_CATALOG_YEARS, ArchiveCatalogStale
from capturebrief_core.data_services import ACTIVE_DOWNLOAD, ARCHIVE_DOWNLOAD
from capturebrief_core.history_index import APPROVED_FETCH, init_index
from scripts.source_coverage_audit import inspect_private_index

NOW = datetime(2026, 9, 21, 15, 30, tzinfo=timezone.utc)


def make_index(root: Path, *, missing: str | None = None,
               age_minutes: int = 0) -> tuple[Path, dict[str, Path]]:
    """Fake indexed byte receipts for integrity tests, NEVER publisher proof."""
    db = root / "history.sqlite"
    init_index(db)
    paths: dict[str, Path] = {}
    checked_at = (NOW - timedelta(minutes=age_minutes)).isoformat()
    all_slots: list[tuple[str, str, int | None]] = [
        ("ACTIVE", ACTIVE_DOWNLOAD, None),
        *((f"ARCHIVE:{fy}", ARCHIVE_DOWNLOAD.format(fy=fy), fy)
          for fy in ARCHIVE_CATALOG_YEARS),
    ]
    with sqlite3.connect(db) as conn:
        for slot, url, fy in all_slots:
            if slot == missing:
                continue
            path = root / (slot.replace(":", "-") + ".csv")
            data = ("NoticeId,Sol#,PostedDate\n" + slot + ",SOL-FAKE,09/21/2026\n").encode()
            path.write_bytes(data)
            paths[slot] = path
            digest = hashlib.sha256(data).hexdigest()
            cur = conn.execute(
                "INSERT INTO source_snapshots "
                "(slot,source_kind,fiscal_year,source_url,extract_sha256,"
                "size_bytes,observed_at,local_path,rows_scanned) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (slot, "ACTIVE" if fy is None else "ARCHIVE", fy, url,
                 digest, len(data), checked_at, str(path), 1),
            )
            conn.execute(
                "INSERT INTO current_sources "
                "(slot,snapshot_id,checked_at,collection_mode) VALUES(?,?,?,?)",
                (slot, cur.lastrowid, checked_at, APPROVED_FETCH),
            )
        conn.commit()
    return db, paths


class SourceCoverageAuditTests(unittest.TestCase):
    def test_missing_index_read_cannot_create_database(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "never-created.db"
            with self.assertRaises((FileNotFoundError, OSError)):
                inspect_private_index(missing, fiscal_year=2026, now=NOW)
            self.assertFalse(missing.exists())

    def test_metadata_only_cannot_claim_local_hashes_or_publisher(self):
        with tempfile.TemporaryDirectory() as td:
            db, _ = make_index(Path(td))
            before = db.read_bytes()
            check = inspect_private_index(db, fiscal_year=2026, now=NOW)
            self.assertTrue(check["metadata_complete"])
            self.assertFalse(check["file_hashes_checked"])
            self.assertFalse(check["local_file_hashes_match"])
            self.assertFalse(check["publisher_authenticity_independently_established"])
            self.assertFalse(check["human_catalog_approval_supplied"])
            self.assertEqual(check["required_slot_count"], len(ARCHIVE_CATALOG_YEARS) + 1)
            self.assertEqual(db.read_bytes(), before, "read-only inspection modified the database")

    def test_streamed_local_hashes_match_but_not_publisher_authenticity(self):
        with tempfile.TemporaryDirectory() as td:
            db, paths = make_index(Path(td))
            result = inspect_private_index(db, fiscal_year=2026,
                                           now=NOW, verify_bytes=True)
            self.assertTrue(result["metadata_complete"])
            self.assertTrue(result["local_file_hashes_match"])
            self.assertEqual(result["fresh_slot_count"], len(paths))
            self.assertFalse(result["publisher_authenticity_independently_established"])

    def test_one_missing_slot_blocks_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            db, _ = make_index(Path(td), missing="ARCHIVE:2026")
            result = inspect_private_index(db, fiscal_year=2026,
                                           now=NOW, verify_bytes=True)
            self.assertFalse(result["metadata_complete"])
            self.assertIn("ARCHIVE:2026", result["missing_slots"])
            self.assertFalse(result["local_file_hashes_match"])

    def test_tampered_retained_bytes_fail_hash_verification(self):
        with tempfile.TemporaryDirectory() as td:
            db, paths = make_index(Path(td))
            source = paths["ARCHIVE:2025"]
            old = source.read_bytes()
            source.write_bytes(old.replace(b"SOL-FAKE", b"SOL-FORG"))
            result = inspect_private_index(db, fiscal_year=2026,
                                           now=NOW, verify_bytes=True)
            self.assertIn("ARCHIVE:2025", result["hash_mismatch_slots"])
            self.assertFalse(result["local_file_hashes_match"])

    def test_missing_file_and_stale_fetch_are_separate_blockers(self):
        with tempfile.TemporaryDirectory() as td:
            db, paths = make_index(Path(td))
            paths["ARCHIVE:1970"].unlink()
            with sqlite3.connect(db) as conn:
                past = (NOW - timedelta(days=30)).isoformat()
                conn.execute("UPDATE current_sources SET checked_at=? "
                             "WHERE slot='ACTIVE'", (past,))
                conn.commit()
            result = inspect_private_index(db, fiscal_year=2026,
                                           now=NOW, verify_bytes=True)
            self.assertIn("ARCHIVE:1970", result["missing_or_wrong_size_file_slots"])
            self.assertIn("ACTIVE", result["stale_slots"])
            self.assertFalse(result["metadata_complete"])

    def test_forged_approved_mode_or_wrong_source_contract_is_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            db, _ = make_index(Path(td))
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE current_sources SET collection_mode='OPERATOR_FILE' "
                             "WHERE slot='ACTIVE'")
                conn.execute("UPDATE source_snapshots SET source_url='https://evil.example/x' "
                             "WHERE slot='ARCHIVE:2026'")
                conn.commit()
            result = inspect_private_index(db, fiscal_year=2026, now=NOW)
            self.assertEqual(set(result["unverified_slots"]),
                             {"ACTIVE", "ARCHIVE:2026"})

    def test_future_dated_or_inconsistent_observation_does_not_pass(self):
        with tempfile.TemporaryDirectory() as td:
            db, _ = make_index(Path(td))
            with sqlite3.connect(db) as conn:
                future = (NOW + timedelta(hours=1)).isoformat()
                conn.execute("UPDATE current_sources SET checked_at=? "
                             "WHERE slot='ACTIVE'", (future,))
                conn.execute("UPDATE source_snapshots SET observed_at=? "
                             "WHERE slot='ARCHIVE:2026'", (future,))
                conn.commit()
            result = inspect_private_index(db, fiscal_year=2026, now=NOW)
            self.assertIn("ACTIVE", result["stale_slots"])
            self.assertIn("ARCHIVE:2026", result["unverified_slots"])

    def test_unapproved_fy2027_blocks_even_complete_fy2026_index(self):
        with tempfile.TemporaryDirectory() as td:
            db, _ = make_index(Path(td))
            before = db.read_bytes()
            with self.assertRaises(ArchiveCatalogStale):
                inspect_private_index(db, fiscal_year=2027,
                                      now=datetime(2026, 10, 19, tzinfo=timezone.utc),
                                      verify_bytes=True)
            self.assertEqual(db.read_bytes(), before)

    def test_invalid_public_and_symlink_index_paths_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            db, _ = make_index(Path(td))
            link = Path(td) / "symlink.db"
            try:
                link.symlink_to(db)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink unavailable on this runner")
            with self.assertRaisesRegex(ValueError, "private regular"):
                inspect_private_index(link, fiscal_year=2026, now=NOW)


if __name__ == "__main__":
    unittest.main()
