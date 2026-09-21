import copy
import unittest
from datetime import datetime, timezone

from capturebrief_core.manifest import normalize_manifest_payload
from capturebrief_core.reference_match import (
    attach_reference_match_proposal,
    propose_reference_matches,
    reference_match_proposal_is_current,
)
from capturebrief_core.references import confirm_reference_scan, propose_reference_scan
from capturebrief_core.workqueue import build_work_queue

NOW="2026-09-21T17:30:00+00:00"
NOW_DT=datetime.fromisoformat(NOW)


def manifest(items):
    raw={"_embedded":{"opportunityAttachmentList":[{"attachments":items}]}}
    receipt=normalize_manifest_payload("action-current",raw,observed_at=NOW)
    receipt["payload_hash_verified"]=True
    return receipt


def item(rid,name,deleted="0",size=100):
    return {
        "resourceId":rid,"name":name,"size":size,"mimeType":"application/pdf",
        "accessStatus":"public","exportControlled":"0","deletedFlag":deleted,
        "fileExists":"1","type":"file",
    }


def reviewed_ref(text="Review Attachment 4."):
    proposal=propose_reference_scan([{"source_id":"notice","text":text}],observed_at=NOW)
    scan,refs=confirm_reference_scan(proposal,{
        "reviewer":"CaptureBrief reviewer",
        "reviewed_at":NOW,
        "attests_complete":True,
        "reviewed_source_ids":["notice"],
        "candidate_decisions":[
            {"candidate_id":c["candidate_id"],"decision":"TRACK","reason":None}
            for c in proposal["payload"]["candidates"]
        ],
        "manual_additions":[],
    })
    return scan,refs


def case(resources=None,text="Review Attachment 4."):
    scan,refs=reviewed_ref(text)
    resources=resources or [item("r4","Attachment 4 - Past Performance.pdf")]
    return {
        "case_id":"CB-MATCH","family_id":"DEMO","current_posture":"GO",
        "packet":{
            "family_status":"UNKNOWN",
            "history_action_ids":["action-current"],
            "history_receipts":[],
            "manifest_receipts":[manifest(resources)],
            "reference_scan":scan,
            "references":refs,
            "artifacts":[{
                "artifact_id":"r4","name":"Attachment 4 - Past Performance.pdf",
                "state":"PUBLIC","required_for_analysis":False,
                "sha256":"a"*64,"byte_state":"BYTES_VERIFIED_HASHED",
                "source_object_state":"VERIFIED_SOURCE_OBJECT",
            }] if any(x["resourceId"]=="r4" for x in resources) else [],
            "external_dependencies":[],
        },
        "current_action_receipts":[],
        "sources":[],
        "assumptions":[],
    }


class ReferenceMatchTests(unittest.TestCase):
    def test_attachment_number_and_tokens_surface_likely_resource_but_never_auto_resolve(self):
        proposal=propose_reference_matches(case())
        row=proposal["matches"][0]
        self.assertFalse(row["can_auto_resolve"])
        self.assertEqual(row["candidates"][0]["resource_id"],"r4")
        self.assertGreaterEqual(row["candidates"][0]["score"],80)
        self.assertIn("NUMBER_ANCHOR_MATCH",row["candidates"][0]["match_reasons"])
        self.assertEqual(row["candidates"][0]["byte_state"],"BYTES_VERIFIED_HASHED")
        self.assertFalse(proposal["can_auto_resolve"])

    def test_conflicting_attachment_number_is_not_proposed(self):
        c=case(resources=[item("r5","Attachment 5 - Price List.pdf")])
        proposal=propose_reference_matches(c)
        self.assertEqual(proposal["matches"][0]["candidate_count"],0)

    def test_same_filename_different_resource_ids_is_explicitly_ambiguous(self):
        resources=[
            item("old","Product Description.pdf",deleted="1",size=140000),
            item("new","Product Description.pdf",deleted="0",size=272000),
        ]
        c=case(resources=resources,text="Review Product Description.pdf.")
        # Manual addition because generic filename is intentionally outside the narrow parser.
        proposal=propose_reference_scan([{"source_id":"notice","text":"Use Product Description.pdf."}],observed_at=NOW)
        scan,refs=confirm_reference_scan(proposal,{
            "reviewer":"CaptureBrief reviewer","reviewed_at":NOW,"attests_complete":True,
            "reviewed_source_ids":["notice"],"candidate_decisions":[],
            "manual_additions":[{
                "label":"Product Description.pdf","kind":"MANUAL","source_id":"notice",
                "reason":"Reviewer identified the named product description as required.",
            }],
        })
        c["packet"]["reference_scan"]=scan; c["packet"]["references"]=refs
        match=propose_reference_matches(c)["matches"][0]
        self.assertTrue(match["ambiguous_top_score"])
        self.assertEqual(set(match["same_name_ambiguity_resource_ids"]),{"old","new"})
        states={x["resource_id"]:x["risk_flags"] for x in match["candidates"]}
        self.assertIn("DELETED_OR_TOMBSTONED",states["old"])
        self.assertNotIn("DELETED_OR_TOMBSTONED",states["new"])
        self.assertFalse(match["can_auto_resolve"])

    def test_attached_match_proposal_is_hash_bound_and_stales_on_manifest_change(self):
        c=case()
        attached,transition=attach_reference_match_proposal(c)
        self.assertEqual(transition["status"],"REFERENCE_MATCH_PROPOSAL_ATTACHED")
        self.assertTrue(reference_match_proposal_is_current(attached))
        changed=copy.deepcopy(attached)
        changed["packet"]["manifest_receipts"][0]["items"].append({
            "resource_id":"extra","name":"Attachment 4 alternate.pdf","artifact_state":"PUBLIC"
        })
        self.assertFalse(reference_match_proposal_is_current(changed))

    def test_work_queue_proposes_matches_before_human_resolution(self):
        c=case()
        queue=build_work_queue(c,now=NOW_DT)
        keys={t["task_key"] for t in queue["tasks"]}
        self.assertIn("reference-matches:propose",keys)
        ref_id=c["packet"]["references"][0]["reference_id"]
        self.assertNotIn(f"reference:{ref_id}",keys)

        attached,_=attach_reference_match_proposal(c)
        queue2=build_work_queue(attached,now=NOW_DT)
        keys2={t["task_key"] for t in queue2["tasks"]}
        self.assertNotIn("reference-matches:propose",keys2)
        self.assertIn(f"reference:{ref_id}",keys2)
        task=next(t for t in queue2["tasks"] if t["task_key"]==f"reference:{ref_id}")
        self.assertFalse(task["can_auto_execute"])
        self.assertGreaterEqual(task["metadata"]["candidate_count"],1)
        self.assertFalse(task["metadata"]["can_auto_resolve"])


if __name__=="__main__":
    unittest.main()
