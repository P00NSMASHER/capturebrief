"""Fictional-only regressions for the PermitPlate-style REAL SAM readback.

The production main job uses actual GSA originals and current SAM API.
No test asserts that one latest API record certifies a full amendment history.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from capturebrief_core.data_services import DataServicesError, FamilyAmbiguous
from scripts import benchmark_sam_public_case as benchmark

NOW = datetime(2026, 10, 29, 15, 0, tzinfo=timezone.utc)
COLS = ["NoticeId", "Sol#", "PostedDate", "Type", "Active",
        "AAC Code", "Office", "Link"]


def record(notice, *, active="Yes", sol=benchmark.SOLICITATION,
           aac="TEST-AAC", office="TEST-OFFICE"):
    return {
        "NoticeId": notice, "Sol#": sol,
        "PostedDate": "10/26/2026", "Type": "k", "Active": active,
        "AAC Code": aac, "Office": office,
        "Link": f"https://sam.gov/opp/{notice}/view",
    }


def csv_bytes(*records):
    target = io.StringIO(newline="")
    writer = csv.DictWriter(target, fieldnames=COLS)
    writer.writeheader()
    for row in records:
        writer.writerow(row)
    return target.getvalue().encode("utf-8")


def fixture():
    seed = benchmark.SEED
    second = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    active = csv_bytes(record(seed), record("ffffffffffffffffffffffffffffffff",
                                            sol="OTHER-TEST-NOTICE"))
    archive = csv_bytes(record(second, active="No"))
    probe = {
        "status": "PUBLIC_API_OBSERVATION_VERIFIED",
        "api_access_verified": True,
        "latest_active_observation_verified": True,
        "api_key_present_in_runtime": True,
        "public_probe_solicitation": benchmark.SOLICITATION,
        "source_endpoint": "https://api.sam.gov/opportunities/v2/search",
        "full_history_verified": False,
        "customer_delivery_verified": False,
        "external_send_authorized": False,
        "observed_at": NOW.isoformat(),
        "pagination": {
            "complete": True, "total_records": 1,
            "returned_records": 1, "offset": 0,
        },
        "notice_id_sha256": hashlib.sha256(seed.encode()).hexdigest(),
        "resource_link_count": 1,
    }
    return active, archive, probe


class SAMPublicCaseCrossreadbackTests(unittest.TestCase):
    def test_real_data_surface_contract_but_not_history_or_customer_delivery(self):
        active, archive, probe = fixture()
        out = benchmark.evaluate_public_case(active_bytes=active, archive_bytes=archive,
                                             probe=probe, checked_at=NOW)
        self.assertEqual(out["candidate_action_count"], 2)
        self.assertEqual(out["source_slot_count"], 2)
        self.assertEqual(out["extracts"][0]["rows_replayed"], 2)
        self.assertEqual(out["extracts"][1]["rows_replayed"], 1)
        self.assertTrue(out["seed_in_official_active_original"])
        self.assertTrue(out["independent_current_api_correlated"])
        self.assertFalse(out["full_historical_action_set_verified"])
        self.assertFalse(out["history_cancellations_and_deletions_verified"])
        self.assertFalse(out["full_attachment_manifest_verified"])
        self.assertFalse(out["incorporated_rules_applicability_verified"])
        self.assertFalse(out["independent_human_source_review_complete"])
        self.assertFalse(out["production_offdevice_recovery_verified"])
        self.assertFalse(out["customer_release_authorized"])
        self.assertFalse(out["external_send_authorized"])

    def test_one_observed_action_never_claims_no_amendments(self):
        active, _, probe = fixture()
        archive = csv_bytes(record("eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
                                   active="No", sol="UNRELATED"))
        out = benchmark.evaluate_public_case(active_bytes=active, archive_bytes=archive,
                                             probe=probe, checked_at=NOW)
        self.assertEqual(out["candidate_action_count"], 1)
        self.assertFalse(out["full_historical_action_set_verified"])

    def test_current_api_wrong_notice_incomplete_stale_or_unauthorized_blocks(self):
        a, b, p = fixture()
        mutations = [
            {"notice_id_sha256": "0" * 64},
            {"status": "PUBLIC_API_OBSERVATION_UNAVAILABLE"},
            {"api_key_present_in_runtime": False},
            {"api_access_verified": False},
            {"full_history_verified": True},
            {"external_send_authorized": True},
            {"pagination": {"complete": False, "total_records": 1,
                            "returned_records": 1, "offset": 0}},
            {"pagination": {"complete": True, "total_records": 2,
                            "returned_records": 1, "offset": 0}},
            {"observed_at": (NOW-timedelta(minutes=6)).isoformat()},
            {"observed_at": (NOW+timedelta(seconds=10)).isoformat()},
        ]
        for change in mutations:
            item = {**p, **change}
            with self.subTest(change=change), self.assertRaises(benchmark.RealSourceBlocked):
                benchmark.evaluate_public_case(active_bytes=a, archive_bytes=b,
                                               probe=item, checked_at=NOW)

    def test_missing_seed_inactive_seed_wrong_link_and_wrong_solicitation_block(self):
        _, archive, probe = fixture()
        seeds = [
            record("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"),
            record(benchmark.SEED, active="No"),
            {**record(benchmark.SEED), "Link": "https://sam.gov/opp/other/view"},
            record(benchmark.SEED, sol="ANOTHER-SOL"),
        ]
        for seed in seeds:
            with self.subTest(seed=seed), self.assertRaises(
                (benchmark.RealSourceBlocked, DataServicesError)
            ):
                benchmark.evaluate_public_case(
                    active_bytes=csv_bytes(seed),
                    archive_bytes=archive, probe=probe, checked_at=NOW,
                )

    def test_full_original_duplicate_id_and_truncated_csv_are_rejected(self):
        _, archive, probe = fixture()
        with self.assertRaises(DataServicesError):
            benchmark.evaluate_public_case(
                active_bytes=csv_bytes(record(benchmark.SEED),
                                       record(benchmark.SEED)),
                archive_bytes=archive, probe=probe, checked_at=NOW,
            )
        with self.assertRaises(DataServicesError):
            benchmark.evaluate_public_case(
                active_bytes=b"NoticeId,Sol#\n" + benchmark.SEED.encode() + b",X\n",
                archive_bytes=archive, probe=probe, checked_at=NOW,
            )
        with self.assertRaises(benchmark.RealSourceBlocked):
            benchmark.evaluate_public_case(
                active_bytes=b"",
                archive_bytes=archive, probe=probe, checked_at=NOW,
            )

    def test_ambiguous_archive_agency_or_office_is_not_silent_history(self):
        active, _, probe = fixture()
        archive = csv_bytes(record("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                                   active="No", aac="OTHER-AAC"))
        with self.assertRaises((benchmark.RealSourceBlocked, FamilyAmbiguous)):
            benchmark.evaluate_public_case(active_bytes=active, archive_bytes=archive,
                                           probe=probe, checked_at=NOW)

    def test_without_runtime_api_key_cli_writes_nothing_and_keeps_hold(self):
        a, b, _ = fixture()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/"active.csv").write_bytes(a)
            (root/"archive.csv").write_bytes(b)
            env = os.environ.copy()
            env.pop("SAM_API_KEY", None)
            run = subprocess.run(
                [sys.executable, "scripts/benchmark_sam_public_case.py",
                 "--active-original", str(root/"active.csv"),
                 "--fy2027-original", str(root/"archive.csv"),
                 "--out", str(root/"receipt.json")],
                cwd=Path(__file__).resolve().parents[1],
                env=env, text=True, capture_output=True, timeout=20,
            )
            self.assertEqual(run.returncode, 2)
            self.assertFalse((root/"receipt.json").exists())
            self.assertIn("OFFICIAL_CASE_SOURCE_CROSSREADBACK_BLOCKED", run.stdout)
            self.assertNotIn("api_key=", run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
