"""Current candidate bytes may change; historical evidence and release gates may not."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from capturebrief_core.archive_catalog import ArchiveCatalogStale, catalog_years_for_fiscal_year
from scripts.refresh_sam_source_candidate import refresh_candidate
from scripts.pilot_preflight import inspect
from tests.test_retain_fy2027_candidate import FAKE_CSV, FakeResponse
from datetime import datetime, timezone


class SourceCandidateRefreshTests(unittest.TestCase):
    def test_changed_originals_and_identical_retry_preserve_prior_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "candidate"
            one = refresh_candidate(root, slot="ARCHIVE:2027", max_bytes=4096,
                                    opener=lambda *a, **kw: FakeResponse())
            first_files = {p: p.read_bytes() for p in root.rglob("*.json")}
            changed = FAKE_CSV.replace(b"SOL-TEST", b"SOL-CHANGED")
            two = refresh_candidate(root, slot="ARCHIVE:2027", max_bytes=4096,
                                    opener=lambda *a, **kw: FakeResponse(contents=changed))
            three = refresh_candidate(root, slot="ARCHIVE:2027", max_bytes=4096,
                                      opener=lambda *a, **kw: FakeResponse(contents=changed))
            self.assertNotEqual(one["source_sha256"], two["source_sha256"])
            self.assertEqual(two["source_sha256"], hashlib.sha256(changed).hexdigest())
            self.assertTrue(three["candidate_snapshot_reused"])
            self.assertEqual(len(list((root / "originals").glob("*.csv"))), 2)
            self.assertEqual(len(list((root / "observations").glob("*.json"))), 3)
            with sqlite3.connect(root / "candidate-source-index.sqlite") as db:
                self.assertEqual(db.execute("SELECT collection_mode FROM current_sources").fetchone()[0], "OPERATOR_FILE")
            for path, original in first_files.items():
                self.assertEqual(path.read_bytes(), original)
            for record in (one, two, three):
                self.assertTrue(record["synthetic_transport"])
                self.assertTrue(record["exact_source_projection_verified"])
                for key in ("catalog_approved", "production_index_updated", "offdevice_restore_verified",
                            "independent_human_source_review_complete", "customer_release_authorized"):
                    self.assertIs(record[key], False)
            with self.assertRaises(ArchiveCatalogStale):
                catalog_years_for_fiscal_year(2027)

    def test_rejects_unobserved_slot_before_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            for slot in ("ARCHIVE:2028", "ARCHIVE:2030", "ARCHIVE:02027", "OTHER"):
                with self.subTest(slot=slot), self.assertRaises(ValueError):
                    refresh_candidate(Path(temporary) / "candidate", slot=slot, max_bytes=4096,
                                      opener=lambda *a, **kw: self.fail("must not fetch"))

    def test_existing_production_directory_cannot_be_adopted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "production.sqlite").write_bytes(b"untouched")
            with self.assertRaises(ValueError):
                refresh_candidate(root, slot="ARCHIVE:2027", max_bytes=4096,
                                  opener=lambda *a, **kw: self.fail("must not fetch"))
            self.assertEqual((root / "production.sqlite").read_bytes(), b"untouched")
            self.assertFalse((root / "CANDIDATE-ONLY.json").exists())

    def test_malformed_new_source_does_not_replace_valid_index_slot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "candidate"
            first = refresh_candidate(root, slot="ARCHIVE:2027", max_bytes=4096,
                                      opener=lambda *a, **kw: FakeResponse())
            with self.assertRaises(Exception):
                refresh_candidate(root, slot="ARCHIVE:2027", max_bytes=4096,
                                  opener=lambda *a, **kw: FakeResponse(contents=b"wrong,headers\n1,2\n"))
            with sqlite3.connect(root / "candidate-source-index.sqlite") as db:
                value = db.execute("SELECT extract_sha256 FROM source_snapshots s JOIN current_sources c ON s.snapshot_id=c.snapshot_id").fetchone()[0]
            self.assertEqual(value, first["source_sha256"])
            self.assertEqual(len(list((root / "observations").glob("*.json"))), 1)

    def test_free_admission_has_no_payment_or_watch_requirement(self):
        now = datetime(2026, 10, 27, tzinfo=timezone.utc)
        free = inspect(now=now, stage="admission", offer="free")
        paid = inspect(now=now, stage="admission")
        self.assertEqual(free["gates"]["payment"]["status"], "NO_PAYMENT_FOR_FREE_CHECK")
        self.assertEqual(free["gates"]["watch"]["status"], "NOT_INCLUDED_IN_FREE_CHECK")
        self.assertEqual(free["gates"]["delivery"]["status"], "POST_ADMISSION_FREE_REPORT")
        self.assertIn("trial_identity", free["pre_pilot_gates"])
        self.assertNotIn("payment", free["pre_pilot_gates"])
        self.assertNotIn("watch", free["post_pilot_gates"])
        self.assertEqual(free["gates"]["catalog"], paid["gates"]["catalog"])
        self.assertEqual(free["gates"]["source_index"], paid["gates"]["source_index"])
        self.assertEqual(paid["gates"]["payment"]["status"], "STRIPE_LIVE_RECORD_VERIFICATION_REQUIRED")
        self.assertFalse(free["approved_to_accept_payment_or_send_customer_material"])
        with self.assertRaises(ValueError):
            inspect(now=now, stage="completion", offer="free")
        with self.assertRaises(ValueError):
            inspect(now=now, stage="admission", offer="other")


if __name__ == "__main__":
    unittest.main()
