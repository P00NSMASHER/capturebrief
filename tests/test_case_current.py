import unittest
from datetime import datetime, timezone

from capturebrief_core.case_current import CaseCurrentError, apply_current_api_observation
from capturebrief_core.current_api import SEARCH_URL
from capturebrief_core.data_services import ACTIVE_DOWNLOAD, ARCHIVE_DOWNLOAD, issue_history_receipt_from_snapshots
from capturebrief_core.workqueue import build_work_queue

NOW="2026-09-21T16:30:00+00:00"
NOW_DT=datetime.fromisoformat(NOW)
A1="a"*32
A2="b"*32
RESOURCE="r1"
LINK=f"https://sam.gov/api/prod/opps/v3/opportunities/resources/files/{RESOURCE}/download"


def history_receipt():
    snapshots=[
        {
            "source_kind":"ACTIVE","fiscal_year":None,"source_url":ACTIVE_DOWNLOAD,
            "extract_sha256":"c"*64,"rows_scanned":10,
            "matches":[
                {"notice_id":A2,"solicitation_number":"SOL-1","posted_date":"09/20/2026","notice_type":"Solicitation","active":"Yes","aac_code":"AAC1","office":"OFFICE","link":f"https://sam.gov/opp/{A2}/view","row_sha256":"2"*64},
                {"notice_id":A1,"solicitation_number":"SOL-1","posted_date":"09/15/2026","notice_type":"Solicitation","active":"Yes","aac_code":"AAC1","office":"OFFICE","link":f"https://sam.gov/opp/{A1}/view","row_sha256":"1"*64},
            ],
        },
        {
            "source_kind":"ARCHIVE","fiscal_year":2026,"source_url":ARCHIVE_DOWNLOAD.format(fy=2026),
            "extract_sha256":"d"*64,"rows_scanned":20,
            "matches":[
                {"notice_id":A1,"solicitation_number":"SOL-1","posted_date":"09/15/2026","notice_type":"Solicitation","active":"No","aac_code":"AAC1","office":"OFFICE","link":f"https://sam.gov/opp/{A1}/view","row_sha256":"3"*64},
            ],
        },
    ]
    return issue_history_receipt_from_snapshots(
        snapshots,solicitation_number="SOL-1",seed_notice_id=A2,
        scope_start_fy=2026,scope_end_fy=2026,scope_confirmed=True,observed_at=NOW
    )


def case():
    receipt=history_receipt()
    return {
        "case_schema_version":"0.2",
        "case_id":"CB-CURRENT",
        "family_id":"SAM:SOL-1:AAC1",
        "current_posture":"GO",
        "packet":{
            "family_status":"UNKNOWN",
            "history_action_ids":[A1,A2],
            "history_receipts":[receipt],
            "manifest_receipts":[],
            "reference_scan":{"status":"PENDING"},
            "references":[],
            "artifacts":[],
            "external_dependencies":[],
        },
        "current_action_receipts":[],
        "sources":[{
            "source_id":"sam-data-services-history","url":receipt["source_url"],
            "authority":"SUPPORTING","artifact_state":"PUBLIC","observed_at":NOW,
            "content_sha256":receipt["evidence_payload_sha256"],
        }],
        "assumptions":[{
            "assumption_id":"A1","text":"Deadline unchanged","evidence_state":"UNPROVEN",
            "decision_class":"VERIFY_NOW","finding":"Not tested","next_action":"Verify",
            "owner":"CaptureBrief reviewer","source_ids":[],"reopen_triggers":["CURRENT_ACTION_CHANGE"],
        }],
    }


def observation(sol="SOL-1",notice=A2,links=None):
    links=[LINK] if links is None else links
    return {
        "record":{
            "noticeId":notice,
            "solicitationNumber":sol,
            "postedDate":"2026-09-20",
            "active":"Yes",
            "resourceLinks":links,
        },
        "source_url":SEARCH_URL,
        "observed_at":NOW,
        "payload_sha256":"e"*64,
        "source_contract":"SAM_GET_OPPORTUNITIES_V2",
        "automation_mode":"APPROVED_API",
        "resource_links":links,
    }


class CaseCurrentTests(unittest.TestCase):
    def test_apply_current_api_observation_updates_case_without_supporting_assumptions(self):
        updated,transition=apply_current_api_observation(case(),observation())
        self.assertEqual(updated["packet"]["family_status"],"ACTIVE")
        self.assertEqual(updated["packet"]["current_action_id"],A2)
        self.assertEqual(transition["status"],"CURRENT_VERIFIED")
        self.assertEqual(len(updated["current_action_receipts"]),1)
        self.assertIn("sam-current-api",{s["source_id"] for s in updated["sources"]})
        artifact=next(x for x in updated["packet"]["artifacts"] if x["artifact_id"]==RESOURCE)
        self.assertEqual(artifact["resource_url"],LINK)
        self.assertEqual(artifact["source_object_state"],"VERIFIED_SOURCE_OBJECT")
        self.assertFalse(artifact["required_for_analysis"])
        self.assertEqual(updated["assumptions"][0]["evidence_state"],"UNPROVEN")
        self.assertEqual(updated["assumptions"][0]["source_ids"],[])

    def test_transition_is_idempotent(self):
        first,_=apply_current_api_observation(case(),observation())
        second,_=apply_current_api_observation(first,observation())
        self.assertEqual(len(second["current_action_receipts"]),1)
        self.assertEqual(sum(s["source_id"]=="sam-current-api" for s in second["sources"]),1)
        self.assertEqual(sum(a["artifact_id"]==RESOURCE for a in second["packet"]["artifacts"]),1)

    def test_api_notice_must_belong_to_complete_history(self):
        with self.assertRaises(CaseCurrentError):
            apply_current_api_observation(case(),observation(notice="c"*32))

    def test_api_solicitation_must_match_history_family(self):
        with self.assertRaises(CaseCurrentError):
            apply_current_api_observation(case(),observation(sol="OTHER-SOL"))

    def test_unapproved_resource_link_blocks_transition(self):
        bad=f"https://sam.gov/opp/{A2}/view"
        with self.assertRaises(CaseCurrentError):
            apply_current_api_observation(case(),observation(links=[bad]))

    def test_current_transition_removes_family_and_current_authority_tasks(self):
        updated,_=apply_current_api_observation(case(),observation())
        queue=build_work_queue(updated,api_observation=observation(),now=NOW_DT)
        keys={task["task_key"] for task in queue["tasks"]}
        self.assertNotIn("family:status",keys)
        self.assertNotIn("current:authority",keys)
        self.assertIn(f"manifest:{A1}",keys)
        self.assertIn(f"manifest:{A2}",keys)
        self.assertIn("references:propose",keys)


if __name__=="__main__":
    unittest.main()
