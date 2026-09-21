import io
import json
import unittest

from capturebrief_core.current_search import (
    CurrentSearchError,
    build_current_search_plan,
    fetch_and_apply_current,
    fetch_current_from_plan,
)
from capturebrief_core.data_services import (
    ACTIVE_DOWNLOAD,
    ARCHIVE_DOWNLOAD,
    issue_history_receipt_from_snapshots,
)

NOW="2026-09-21T16:45:00+00:00"
A1="a"*32
A2="b"*32
LINK="https://sam.gov/api/prod/opps/v3/opportunities/resources/files/r1/download"


def history_receipt(*, missing_date=False, old_action=False):
    first_date=None if missing_date else ("01/15/2025" if old_action else "09/15/2026")
    snapshots=[
        {
            "source_kind":"ACTIVE","fiscal_year":None,"source_url":ACTIVE_DOWNLOAD,
            "extract_sha256":"c"*64,"rows_scanned":10,
            "matches":[
                {"notice_id":A2,"solicitation_number":"SOL-1","posted_date":"09/20/2026","notice_type":"Solicitation","active":"Yes","aac_code":"AAC1","office":"OFFICE","link":f"https://sam.gov/opp/{A2}/view","row_sha256":"2"*64},
                {"notice_id":A1,"solicitation_number":"SOL-1","posted_date":first_date,"notice_type":"Solicitation","active":"Yes","aac_code":"AAC1","office":"OFFICE","link":f"https://sam.gov/opp/{A1}/view","row_sha256":"1"*64},
            ],
        },
        {
            "source_kind":"ARCHIVE","fiscal_year":2026,"source_url":ARCHIVE_DOWNLOAD.format(fy=2026),
            "extract_sha256":"d"*64,"rows_scanned":20,"matches":[],
        },
    ]
    return issue_history_receipt_from_snapshots(
        snapshots,solicitation_number="SOL-1",seed_notice_id=A2,
        scope_start_fy=2026,scope_end_fy=2026,scope_confirmed=True,observed_at=NOW
    )


def case(*, missing_date=False, old_action=False):
    r=history_receipt(missing_date=missing_date,old_action=old_action)
    return {
        "case_schema_version":"0.2","case_id":"CB-SEARCH","family_id":"SAM:SOL-1:AAC1",
        "current_posture":"GO",
        "packet":{
            "family_status":"UNKNOWN","history_action_ids":[A1,A2],"history_receipts":[r],
            "manifest_receipts":[],"reference_scan":{"status":"PENDING"},"references":[],
            "artifacts":[],"external_dependencies":[],
        },
        "current_action_receipts":[],"sources":[],"assumptions":[],
    }


class FakeResponse:
    def __init__(self,payload):
        self._io=io.BytesIO(json.dumps(payload).encode())
    def read(self,n=-1): return self._io.read(n)
    def __enter__(self): return self
    def __exit__(self,*args): return False


def api_payload(notice=A2):
    return {
        "opportunitiesData":[{
            "noticeId":notice,
            "solicitationNumber":"SOL-1",
            "postedDate":"2026-09-20",
            "active":"Yes",
            "resourceLinks":[LINK],
        }]
    }


class CurrentSearchTests(unittest.TestCase):
    def test_plan_uses_history_dates_only_as_non_authoritative_windows(self):
        plan=build_current_search_plan(case())
        self.assertEqual(plan["solicitation_number"],"SOL-1")
        self.assertTrue(plan["date_coverage_complete"])
        self.assertFalse(plan["currentness_authoritative"])
        self.assertFalse(plan["ordering_authoritative"])
        self.assertEqual(len(plan["windows"]),1)
        self.assertEqual(plan["windows"][0]["posted_from"],"09/15/2026")
        self.assertEqual(plan["windows"][0]["posted_to"],"09/20/2026")
        self.assertFalse(plan["windows"][0]["date_basis_authoritative"])

    def test_history_spanning_more_than_one_year_splits_windows(self):
        plan=build_current_search_plan(case(old_action=True))
        self.assertEqual(len(plan["windows"]),2)
        for window in plan["windows"]:
            self.assertFalse(window["date_basis_authoritative"])

    def test_missing_posted_date_blocks_automated_search(self):
        plan=build_current_search_plan(case(missing_date=True))
        self.assertFalse(plan["date_coverage_complete"])
        self.assertIn(A1,plan["missing_posted_date_notice_ids"])
        with self.assertRaises(CurrentSearchError):
            fetch_current_from_plan(plan,api_key="test",opener=lambda req,timeout=30: FakeResponse(api_payload()))

    def test_fetch_plan_returns_documented_current_observation_and_receipt(self):
        plan=build_current_search_plan(case())
        result=fetch_current_from_plan(
            plan,api_key="test",
            opener=lambda req,timeout=30: FakeResponse(api_payload())
        )
        self.assertEqual(result["status"],"CURRENT_OBSERVATION_FOUND")
        self.assertEqual(result["observation"]["record"]["noticeId"],A2)
        self.assertEqual(result["receipt"]["asserted_action_id"],A2)

    def test_zero_api_match_does_not_infer_terminal_status(self):
        plan=build_current_search_plan(case())
        result=fetch_current_from_plan(
            plan,api_key="test",
            opener=lambda req,timeout=30: FakeResponse({"opportunitiesData":[]})
        )
        self.assertEqual(result["status"],"NO_ACTIVE_MATCH")
        self.assertFalse(result["currentness_authoritative"])
        self.assertIn("does not prove",result["meaning"])

    def test_fetch_and_apply_current_completes_current_transition(self):
        updated,result=fetch_and_apply_current(
            case(),api_key="test",
            opener=lambda req,timeout=30: FakeResponse(api_payload())
        )
        self.assertEqual(result["fetch"]["status"],"CURRENT_OBSERVATION_FOUND")
        self.assertEqual(result["transition"]["status"],"CURRENT_VERIFIED")
        self.assertEqual(updated["packet"]["family_status"],"ACTIVE")
        self.assertEqual(updated["packet"]["current_action_id"],A2)


if __name__=="__main__":
    unittest.main()
