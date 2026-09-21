import hashlib
import io
import unittest
from datetime import datetime

from capturebrief_core.case_capture import CaseCaptureError, capture_current_artifact
from capturebrief_core.workqueue import build_work_queue

NOW="2026-09-21T17:45:00+00:00"
NOW_DT=datetime.fromisoformat(NOW)
RID="r1"
LINK=f"https://sam.gov/api/prod/opps/v3/opportunities/resources/files/{RID}/download"
API_HASH="e"*64
DATA=b"captured-current-resource"


class FakeResponse:
    def __init__(self,data=DATA):
        self._io=io.BytesIO(data)
        self.headers={"Content-Length":str(len(data))}
    def read(self,n=-1): return self._io.read(n)
    def geturl(self): return "https://objects.example/file"
    def __enter__(self): return self
    def __exit__(self,*args): return False


def case():
    return {
        "case_id":"CB-CAPTURE",
        "family_id":"SAM:SOL-1:AAC1",
        "current_posture":"GO",
        "packet":{
            "family_status":"ACTIVE",
            "history_action_ids":[],
            "history_receipts":[],
            "manifest_receipts":[],
            "reference_scan":{"status":"PENDING"},
            "references":[],
            "current_api_observation":{
                "source_contract":"SAM_GET_OPPORTUNITIES_V2",
                "notice_id":"action-current",
                "solicitation_number":"SOL-1",
                "observed_at":NOW,
                "api_payload_sha256":API_HASH,
                "resource_link_count":1,
            },
            "current_resource_links":[LINK],
            "artifacts":[{
                "artifact_id":RID,
                "name":"Current resource",
                "state":"PUBLIC",
                "required_for_analysis":True,
                "sha256":None,
                "byte_state":"BYTES_NOT_YET_CHECKED",
                "source_object_state":"VERIFIED_SOURCE_OBJECT",
                "resource_url":LINK,
                "source_action_id":"action-current",
                "source_ids":["sam-current-api"],
            }],
            "external_dependencies":[],
        },
        "current_action_receipts":[],
        "sources":[],
        "assumptions":[],
    }


class CaseCaptureTests(unittest.TestCase):
    def test_capture_current_artifact_downloads_hashes_and_applies_receipt(self):
        updated,transition,content=capture_current_artifact(
            case(),RID,opener=lambda req,timeout=30: FakeResponse()
        )
        expected=hashlib.sha256(DATA).hexdigest()
        self.assertEqual(content,DATA)
        self.assertEqual(transition["status"],"CURRENT_ARTIFACT_CAPTURED")
        self.assertEqual(transition["sha256"],expected)
        artifact=updated["packet"]["artifacts"][0]
        self.assertEqual(artifact["sha256"],expected)
        self.assertEqual(artifact["byte_state"],"BYTES_VERIFIED_HASHED")
        self.assertEqual(len(updated["packet"]["byte_receipts"]),1)

    def test_capture_replay_does_not_redownload_verified_artifact(self):
        updated,_,_=capture_current_artifact(
            case(),RID,opener=lambda req,timeout=30: FakeResponse()
        )
        called=False
        def should_not_call(*args,**kwargs):
            nonlocal called
            called=True
            raise AssertionError("network should not be called")
        replayed,transition,content=capture_current_artifact(updated,RID,opener=should_not_call)
        self.assertFalse(called)
        self.assertIsNone(content)
        self.assertEqual(transition["status"],"ARTIFACT_ALREADY_CAPTURED")
        self.assertEqual(replayed["packet"]["artifacts"][0]["sha256"],updated["packet"]["artifacts"][0]["sha256"])

    def test_retained_link_count_or_resource_membership_mismatch_blocks_capture(self):
        c=case(); c["packet"]["current_api_observation"]["resource_link_count"]=2
        with self.assertRaises(CaseCaptureError):
            capture_current_artifact(c,RID,opener=lambda req,timeout=30: FakeResponse())

        c=case(); c["packet"]["current_resource_links"]=[]
        with self.assertRaises(CaseCaptureError):
            capture_current_artifact(c,RID,opener=lambda req,timeout=30: FakeResponse())

    def test_work_queue_can_authorize_bytes_from_retained_case_observation(self):
        c=case()
        queue=build_work_queue(c,now=NOW_DT)
        task=next(t for t in queue["tasks"] if t["task_key"]==f"bytes:{RID}")
        self.assertTrue(task["can_auto_execute"])
        self.assertEqual(task["actor"],"AUTOMATED_APPROVED_SOURCE")


if __name__=="__main__":
    unittest.main()
