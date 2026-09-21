import csv
import tempfile
from datetime import datetime
import unittest
from pathlib import Path

from capturebrief_core.archive_catalog import ARCHIVE_CATALOG_YEARS
from capturebrief_core.data_services import ACTIVE_DOWNLOAD, ARCHIVE_DOWNLOAD
from capturebrief_core.history_index import APPROVED_FETCH, ingest_extract_file, index_status
from capturebrief_core.history_sync import sync_missing_slots
from capturebrief_core.intake import build_case_from_intake
from capturebrief_core.opportunity_ref import parse_opportunity_reference
from capturebrief_core.resolver import attach_history_resolution, resolve_reference_from_index

FIELDS = [
    "NoticeId","Sol#","PostedDate","Type","Active","AAC Code","Office","Link",
    "CGAC","FPDS Code","Department/Ind.Agency","Sub-Tier","BaseType",
]
NOW="2026-09-21T16:00:00+00:00"
A1="a"*32
A2="b"*32


def row(notice, sol="SOL-1", aac="AAC1", posted="09/20/2026", active="Yes", office="OFFICE"):
    return {
        "NoticeId":notice,"Sol#":sol,"PostedDate":posted,"Type":"Solicitation","Active":active,
        "AAC Code":aac,"Office":office,"Link":f"https://sam.gov/opp/{notice}/view",
        "CGAC":"9700","FPDS Code":"FA1234","Department/Ind.Agency":"DEPT OF DEFENSE",
        "Sub-Tier":"AIR FORCE","BaseType":"Solicitation",
    }


def write_csv(path:Path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="cp1252",newline="") as handle:
        w=csv.DictWriter(handle,fieldnames=FIELDS)
        w.writeheader(); w.writerows(rows)


def approved_ingest(db, path, *, source_url, source_kind, fiscal_year=None, snapshots=None):
    return ingest_extract_file(
        db,path,source_url=source_url,source_kind=source_kind,fiscal_year=fiscal_year,
        observed_at=NOW,snapshot_dir=snapshots,collection_mode=APPROVED_FETCH
    )


def build_index(root:Path, *, complete=True):
    db=root/"history.sqlite"; snapshots=root/"snapshots"
    active=root/"active.csv"; write_csv(active,[row(A2),row(A1,posted="09/15/2026")])
    approved_ingest(db,active,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",snapshots=snapshots)
    years=ARCHIVE_CATALOG_YEARS if complete else (2026,)
    for fy in years:
        p=root/f"fy{fy}.csv"
        rows=[row(A1,active="No"),row(A2,active="No")] if fy==2026 else []
        write_csv(p,rows)
        approved_ingest(db,p,source_url=ARCHIVE_DOWNLOAD.format(fy=fy),source_kind="ARCHIVE",fiscal_year=fy,snapshots=snapshots)
    return db


class ResolutionSyncTests(unittest.TestCase):
    def test_reference_parser_extracts_action_without_claiming_authority(self):
        url=f"https://sam.gov/workspace/contract/opp/{A2}/view"
        parsed=parse_opportunity_reference(url)
        self.assertEqual(parsed["reference_type"],"SAM_ACTION_URL")
        self.assertEqual(parsed["action_id"],A2)
        self.assertFalse(parsed["source_authoritative"])

    def test_action_url_resolves_complete_history_from_full_index(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=build_index(root,complete=True)
            result=resolve_reference_from_index(
                db,f"https://sam.gov/opp/{A2}/view",fiscal_year=2026,observed_at=NOW
            )
            self.assertEqual(result["status"],"RESOLVED")
            self.assertEqual(result["seed_notice_id"],A2)
            self.assertEqual(result["solicitation_number"],"SOL-1")
            self.assertEqual(set(result["history_receipt"]["action_ids"]),{A1,A2})
            self.assertFalse(result["currentness_inferred"])

    def test_bare_solicitation_number_never_selects_seed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=build_index(root,complete=True)
            result=resolve_reference_from_index(db,"SOL-1",fiscal_year=2026,observed_at=NOW)
            self.assertEqual(result["status"],"NEEDS_SEED_NOTICE_ID")
            self.assertNotIn("history_receipt",result)
            candidates=result["candidate_families"]
            self.assertEqual(len(candidates),1)
            self.assertEqual(set(candidates[0]["notice_ids"]),{A1,A2})
            self.assertFalse(result["currentness_inferred"])

    def test_incomplete_catalog_stays_partial_even_with_valid_seed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=build_index(root,complete=False)
            result=resolve_reference_from_index(db,A2,fiscal_year=2026,observed_at=NOW)
            self.assertEqual(result["status"],"RESOLVED_PARTIAL_COVERAGE")
            self.assertEqual(result["history_receipt"]["status"],"OBSERVED_ONLY")
            self.assertFalse(result["coverage"]["complete"])

    def test_attach_history_resolution_enriches_case_without_linking_assumptions(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=build_index(root,complete=True)
            intake={
                "email":"buyer@example.com","company":"Example Federal",
                "public_opportunity":f"https://sam.gov/opp/{A2}/view",
                "current_posture":"GO","assumption_1":"Deadline is unchanged.",
                "public_only_confirmation":"yes",
            }
            case=build_case_from_intake(intake,submitted_at=NOW)
            resolved,resolution=attach_history_resolution(case,db,fiscal_year=2026,observed_at=NOW)
            self.assertEqual(resolution["status"],"RESOLVED")
            self.assertEqual(set(resolved["packet"]["history_action_ids"]),{A1,A2})
            self.assertEqual(resolved["packet"]["family_status"],"UNKNOWN")
            self.assertEqual(resolved["assumptions"][0]["source_ids"],[])
            self.assertTrue(resolved["family_id"].startswith("SAM:SOL-1:AAC1"))
            self.assertIn("sam-data-services-history",{s["source_id"] for s in resolved["sources"]})

    def test_stale_index_cannot_resolve_as_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=build_index(root,complete=True)
            import sqlite3
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE current_sources SET checked_at='2026-08-01T00:00:00+00:00' WHERE slot='ACTIVE'")
            result=resolve_reference_from_index(db,A2,fiscal_year=2026,observed_at=NOW)
            self.assertEqual(result["status"],"RESOLVED_PARTIAL_COVERAGE")
            self.assertIn("ACTIVE",result["coverage"]["stale_slots"])
            self.assertIn("FULL_ARCHIVE_CATALOG_STALE",result["history_receipt"]["evidence_payload"]["coverage_errors"])

    def test_sync_runner_defaults_to_one_remediation_slot(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=root/"history.sqlite"; downloads=root/"downloads"; snapshots=root/"snapshots"
            calls=[]
            def fake_fetcher(index_path, *, slot, destination, snapshot_dir, observed_at, max_bytes):
                calls.append(slot)
                p=Path(destination)
                if slot=="ACTIVE":
                    write_csv(p,[row(A2)])
                    return {"ingest":approved_ingest(index_path,p,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",snapshots=snapshot_dir)}
                fy=int(slot.split(":",1)[1])
                write_csv(p,[])
                return {"ingest":approved_ingest(index_path,p,source_url=ARCHIVE_DOWNLOAD.format(fy=fy),source_kind="ARCHIVE",fiscal_year=fy,snapshots=snapshot_dir)}
            result=sync_missing_slots(db,downloads,snapshot_dir=snapshots,fiscal_year=2026,observed_at=NOW,fetcher=fake_fetcher)
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0],"ACTIVE")
            self.assertEqual(result["requested_reasons"]["ACTIVE"],"MISSING")
            self.assertFalse(result["complete"])
            self.assertIn("ACTIVE",result["index_status"]["fresh_slots"])

    def test_explicit_full_sync_can_complete_catalog_with_resumable_fetcher(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=root/"history.sqlite"; downloads=root/"downloads"; snapshots=root/"snapshots"
            def fake_fetcher(index_path, *, slot, destination, snapshot_dir, observed_at, max_bytes):
                p=Path(destination)
                if slot=="ACTIVE":
                    write_csv(p,[row(A2)])
                    return {"ingest":approved_ingest(index_path,p,source_url=ACTIVE_DOWNLOAD,source_kind="ACTIVE",snapshots=snapshot_dir)}
                fy=int(slot.split(":",1)[1])
                write_csv(p,[row(A1,active="No")] if fy==2026 else [])
                return {"ingest":approved_ingest(index_path,p,source_url=ARCHIVE_DOWNLOAD.format(fy=fy),source_kind="ARCHIVE",fiscal_year=fy,snapshots=snapshot_dir)}
            result=sync_missing_slots(db,downloads,snapshot_dir=snapshots,fiscal_year=2026,max_slots=None,observed_at=NOW,fetcher=fake_fetcher)
            self.assertTrue(result["complete"],result["remaining_slots"])
            self.assertEqual(result["remaining_count"],0)
            self.assertTrue(index_status(db,fiscal_year=2026,now=datetime.fromisoformat(NOW))["complete"])


if __name__=="__main__":
    unittest.main()
