import unittest

from capturebrief_core.case_artifacts import CaseArtifactError, apply_api_byte_receipt
from capturebrief_core.case_references import apply_reference_resolution, apply_reference_review_result
from capturebrief_core.manifest import normalize_manifest_payload
from capturebrief_core.references import confirm_reference_scan, propose_reference_scan

NOW="2026-09-21T17:15:00+00:00"
RID="r1"
LINK=f"https://sam.gov/api/prod/opps/v3/opportunities/resources/files/{RID}/download"
API_HASH="e"*64
RESPONSE_HASH="f"*64
BYTE_HASH="a"*64


def manifest():
    raw={"_embedded":{"opportunityAttachmentList":[{"attachments":[{
        "resourceId":RID,"name":"Attachment 4.pdf","size":6,"mimeType":"application/pdf",
        "accessStatus":"public","exportControlled":"0","deletedFlag":"0","fileExists":"1","type":"file",
    }]}]}}
    r=normalize_manifest_payload("action-current",raw,observed_at=NOW)
    r["payload_hash_verified"]=True
    return r


def case():
    return {
        "case_id":"CB-BYTE",
        "packet":{
            "current_api_observation":{
                "source_contract":"SAM_GET_OPPORTUNITIES_V2",
                "notice_id":"action-current",
                "solicitation_number":"SOL-1",
                "observed_at":NOW,
                "api_payload_sha256":API_HASH,
                "api_response_sha256":RESPONSE_HASH,
                "pagination":{"total_records":1,"returned_records":1,"limit":100,"offset":0,"complete":True},
                "resource_link_count":1,
            },
            "current_resource_links":[LINK],
            "manifest_receipts":[manifest()],
            "reference_scan":{"status":"PENDING"},
            "references":[],
            "artifacts":[{
                "artifact_id":RID,
                "name":f"SAM current resource {RID}",
                "state":"PUBLIC",
                "required_for_analysis":False,
                "sha256":None,
                "byte_state":"BYTES_NOT_YET_CHECKED",
                "source_object_state":"VERIFIED_SOURCE_OBJECT",
                "resource_url":LINK,
                "source_action_id":"action-current",
                "source_ids":["sam-current-api"],
            }],
        },
        "sources":[{"source_id":"notice-current","url":"https://sam.gov/opp/action-current/view"}],
        "assumptions":[],
    }


def receipt(byte_hash=BYTE_HASH,api_hash=API_HASH,response_hash=RESPONSE_HASH,link=LINK):
    return {
        "source_contract":"SAM_GET_OPPORTUNITIES_RESOURCE_LINK",
        "automation_mode":"APPROVED_API",
        "source_url":link,
        "final_url_retained":False,
        "final_delivery_host":"objects.example",
        "final_url_sha256":"c"*64,
        "redirect_used":True,
        "observed_at":NOW,
        "byte_state":"BYTES_VERIFIED_HASHED",
        "sha256":byte_hash,
        "size":6,
        "api_payload_sha256":api_hash,
        "api_response_sha256":response_hash,
    }


def review_result():
    proposal=propose_reference_scan([{"source_id":"notice","text":"Review Attachment 4."}],observed_at=NOW)
    scan,refs=confirm_reference_scan(proposal,{
        "reviewer":"CaptureBrief reviewer",
        "reviewed_at":NOW,
        "attests_complete":True,
        "reviewed_source_ids":["notice"],
        "candidate_decisions":[
            {"candidate_id":proposal["payload"]["candidates"][0]["candidate_id"],"decision":"TRACK","reason":None}
        ],
        "manual_additions":[],
    })
    return {"reference_scan":scan,"references":refs}


class CaseArtifactTests(unittest.TestCase):
    def test_valid_api_byte_receipt_updates_artifact_and_retains_receipt(self):
        updated,transition=apply_api_byte_receipt(case(),receipt())
        artifact=updated["packet"]["artifacts"][0]
        self.assertEqual(transition["status"],"BYTE_RECEIPT_APPLIED")
        self.assertEqual(artifact["sha256"],BYTE_HASH)
        self.assertEqual(artifact["byte_state"],"BYTES_VERIFIED_HASHED")
        self.assertEqual(artifact["byte_size"],6)
        self.assertEqual(len(updated["packet"]["byte_receipts"]),1)

    def test_receipt_must_bind_to_current_api_payload_and_resource_link(self):
        with self.assertRaises(CaseArtifactError):
            apply_api_byte_receipt(case(),receipt(api_hash="f"*64))
        other="https://sam.gov/api/prod/opps/v3/opportunities/resources/files/other/download"
        with self.assertRaises(CaseArtifactError):
            apply_api_byte_receipt(case(),receipt(link=other))

    def test_receipt_must_bind_to_exact_raw_api_response_and_not_retain_signed_url(self):
        with self.assertRaises(CaseArtifactError):
            apply_api_byte_receipt(case(),receipt(response_hash="d"*64))
        leaked=receipt()
        leaked["final_url"]="https://objects.example/file?X-Amz-Signature=secret"
        with self.assertRaises(CaseArtifactError):
            apply_api_byte_receipt(case(),leaked)

    def test_replay_is_idempotent_and_conflict_is_rejected(self):
        once,_=apply_api_byte_receipt(case(),receipt())
        twice,transition=apply_api_byte_receipt(once,receipt())
        self.assertEqual(transition["status"],"BYTE_RECEIPT_ALREADY_APPLIED")
        self.assertEqual(len(twice["packet"]["byte_receipts"]),1)
        with self.assertRaises(CaseArtifactError):
            apply_api_byte_receipt(once,receipt(byte_hash="b"*64))

    def test_byte_receipt_then_reference_resolution_closes_and_marks_artifact_required(self):
        with_bytes,_=apply_api_byte_receipt(case(),receipt())
        reviewed,_=apply_reference_review_result(with_bytes,review_result())
        ref_id=reviewed["packet"]["references"][0]["reference_id"]
        resolved,transition=apply_reference_resolution(reviewed,ref_id,{
            "resolution":"RESOLVED_TO_RESOURCE",
            "resource_id":RID,
            "byte_sha256":BYTE_HASH,
            "reviewer":"CaptureBrief reviewer",
            "reviewed_at":NOW,
            "reason":"Human reviewer matched Attachment 4 to the retained resource and verified byte receipt.",
        })
        self.assertEqual(transition["reference_closure"],"REFERENCE_CLOSURE_COMPLETE")
        artifact=next(a for a in resolved["packet"]["artifacts"] if a["artifact_id"]==RID)
        self.assertTrue(artifact["required_for_analysis"])
        self.assertEqual(artifact["sha256"],BYTE_HASH)


if __name__=="__main__":
    unittest.main()
