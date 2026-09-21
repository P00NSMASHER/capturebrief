import copy
import unittest

from capturebrief_core.case_references import (
    CaseReferenceError,
    apply_reference_resolution,
    apply_reference_review_result,
)
from capturebrief_core.manifest import normalize_manifest_payload
from capturebrief_core.references import confirm_reference_scan, propose_reference_scan
from capturebrief_core.watch import compare_cases

NOW="2026-09-21T17:00:00+00:00"
RID="resource-4"
HASH="a"*64


def manifest():
    raw={"_embedded":{"opportunityAttachmentList":[{"attachments":[{
        "resourceId":RID,"name":"Attachment 4.pdf","size":100,
        "mimeType":"application/pdf","accessStatus":"public","exportControlled":"0",
        "deletedFlag":"0","fileExists":"1","type":"file",
    }]}]}}
    r=normalize_manifest_payload("action-current",raw,observed_at=NOW)
    r["payload_hash_verified"]=True
    return r


def review_result(two=False):
    text="Review Attachment 4."
    if two:
        text+=" Also review Amendment 0001."
    proposal=propose_reference_scan([{"source_id":"notice","text":text}],observed_at=NOW)
    decisions=[
        {"candidate_id":c["candidate_id"],"decision":"TRACK","reason":None}
        for c in proposal["payload"]["candidates"]
    ]
    scan,refs=confirm_reference_scan(proposal,{
        "reviewer":"CaptureBrief reviewer",
        "reviewed_at":NOW,
        "attests_complete":True,
        "reviewed_source_ids":["notice"],
        "candidate_decisions":decisions,
        "manual_additions":[],
    })
    return {"reference_scan":scan,"references":refs}


def case(two=False):
    return {
        "case_schema_version":"0.2",
        "case_id":"CB-REF",
        "family_id":"SAM:SOL-1:AAC1",
        "current_posture":"GO",
        "packet":{
            "family_status":"ACTIVE",
            "history_action_ids":["action-current"],
            "history_receipts":[],
            "manifest_receipts":[manifest()],
            "reference_scan":{"status":"PENDING"},
            "references":[],
            "artifacts":[{
                "artifact_id":RID,
                "name":"Attachment 4.pdf",
                "state":"PUBLIC",
                "required_for_analysis":True,
                "sha256":HASH,
                "source_object_state":"VERIFIED_SOURCE_OBJECT",
                "byte_state":"BYTES_VERIFIED_HASHED",
            }],
            "external_dependencies":[],
        },
        "current_action_receipts":[],
        "sources":[{
            "source_id":"notice-current",
            "url":"https://sam.gov/opp/action-current/view",
            "authority":"CONTROLLING_CURRENT",
            "artifact_state":"PUBLIC",
            "observed_at":NOW,
            "content_sha256":"b"*64,
        }],
        "assumptions":[],
    }


def resource_decision(byte_hash=HASH):
    return {
        "resolution":"RESOLVED_TO_RESOURCE",
        "resource_id":RID,
        "byte_sha256":byte_hash,
        "reviewer":"CaptureBrief reviewer",
        "reviewed_at":NOW,
        "reason":"Human reviewer matched the confirmed dependency to the retained manifest resource and byte receipt.",
    }


class CaseReferenceTransitionTests(unittest.TestCase):
    def test_review_result_applies_without_resolving_references(self):
        updated,transition=apply_reference_review_result(case(),review_result())
        self.assertEqual(transition["status"],"REFERENCE_REVIEW_APPLIED")
        self.assertEqual(updated["packet"]["reference_scan"]["status"],"COMPLETE")
        self.assertTrue(updated["packet"]["references"])
        self.assertTrue(all(r["resolution"]=="UNRESOLVED" for r in updated["packet"]["references"]))

    def test_review_result_rejects_pre_resolved_smuggling(self):
        result=review_result()
        result["references"][0].update({
            "resolution":"RESOLVED_TO_RESOURCE",
            "resource_id":RID,
            "source_object_state":"VERIFIED_SOURCE_OBJECT",
            "byte_state":"BYTES_VERIFIED_HASHED",
            "byte_sha256":HASH,
        })
        with self.assertRaises(CaseReferenceError):
            apply_reference_review_result(case(),result)

    def test_verified_resource_resolution_requires_matching_artifact_hash(self):
        reviewed,_=apply_reference_review_result(case(),review_result())
        ref_id=reviewed["packet"]["references"][0]["reference_id"]
        resolved,transition=apply_reference_resolution(reviewed,ref_id,resource_decision())
        ref=next(r for r in resolved["packet"]["references"] if r["reference_id"]==ref_id)
        self.assertEqual(ref["resolution"],"RESOLVED_TO_RESOURCE")
        self.assertEqual(ref["byte_sha256"],HASH)
        self.assertEqual(ref["resolution_review"]["contract"],"CAPTUREBRIEF_REFERENCE_RESOLUTION_V1")
        self.assertEqual(transition["reference_closure"],"REFERENCE_CLOSURE_COMPLETE")

        with self.assertRaises(CaseReferenceError):
            apply_reference_resolution(reviewed,ref_id,resource_decision("c"*64))

    def test_same_review_can_be_replayed_after_resolution_without_rollback(self):
        rr=review_result()
        reviewed,_=apply_reference_review_result(case(),rr)
        ref_id=reviewed["packet"]["references"][0]["reference_id"]
        resolved,_=apply_reference_resolution(reviewed,ref_id,resource_decision())
        replayed,transition=apply_reference_review_result(resolved,rr)
        self.assertEqual(transition["status"],"REFERENCE_REVIEW_ALREADY_APPLIED")
        ref=next(r for r in replayed["packet"]["references"] if r["reference_id"]==ref_id)
        self.assertEqual(ref["resolution"],"RESOLVED_TO_RESOURCE")

    def test_supersession_requires_retained_source(self):
        reviewed,_=apply_reference_review_result(case(),review_result())
        ref_id=reviewed["packet"]["references"][0]["reference_id"]
        bad={
            "resolution":"SUPERSEDED_BY",
            "successor_resource_id":RID,
            "supersession_source_id":"missing-source",
            "reviewer":"CaptureBrief reviewer",
            "reviewed_at":NOW,
            "reason":"Later controlling document explicitly supersedes this reference.",
        }
        with self.assertRaises(CaseReferenceError):
            apply_reference_resolution(reviewed,ref_id,bad)

        good={**bad,"supersession_source_id":"notice-current"}
        resolved,transition=apply_reference_resolution(reviewed,ref_id,good)
        self.assertEqual(transition["reference_closure"],"REFERENCE_CLOSURE_COMPLETE")
        self.assertEqual(resolved["packet"]["references"][0]["resolution"],"SUPERSEDED_BY")

    def test_external_dependency_resolution_requires_explicit_nonpublic_state(self):
        reviewed,_=apply_reference_review_result(case(),review_result())
        ref_id=reviewed["packet"]["references"][0]["reference_id"]
        decision={
            "resolution":"EXTERNAL_DEPENDENCY",
            "url":"https://piee.eb.mil/example",
            "byte_state":"BYTES_EXTERNAL_DEPENDENCY",
            "reviewer":"CaptureBrief reviewer",
            "reviewed_at":NOW,
            "reason":"Controlling package is hosted in an external procurement system.",
        }
        resolved,transition=apply_reference_resolution(reviewed,ref_id,decision)
        self.assertEqual(transition["reference_closure"],"REFERENCE_CLOSURE_COMPLETE")
        self.assertEqual(resolved["packet"]["references"][0]["url"],decision["url"])

    def test_resolution_change_reopens_only_matching_assumption_trigger(self):
        rr=review_result()
        reviewed,_=apply_reference_review_result(case(),rr)
        ref_id=reviewed["packet"]["references"][0]["reference_id"]
        before=copy.deepcopy(reviewed)
        before["assumptions"]=[
            {"assumption_id":"A1","reopen_triggers":[f"REFERENCE:{ref_id}"]},
            {"assumption_id":"A2","reopen_triggers":["REFERENCE:other"]},
        ]
        after, _=apply_reference_resolution(before,ref_id,resource_decision())
        diff=compare_cases(before,after)
        reopened={x["assumption_id"] for x in diff["reopened_assumptions"]}
        self.assertEqual(reopened,{"A1"})


if __name__=="__main__":
    unittest.main()
