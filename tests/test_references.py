import copy
import unittest

from capturebrief_core.packet import validate_reference_closure
from capturebrief_core.references import (
    ReferenceReviewError,
    confirm_reference_scan,
    propose_reference_scan,
)

NOW="2026-09-21T16:00:00+00:00"


def review_for(proposal, *, track_all=True, manual_additions=None):
    decisions=[]
    for candidate in proposal["payload"]["candidates"]:
        decisions.append({
            "candidate_id": candidate["candidate_id"],
            "decision": "TRACK" if track_all else "IGNORE_NOT_DEPENDENCY",
            "reason": None if track_all else "Reviewer determined this mention is contextual, not a required dependency.",
        })
    return {
        "reviewer":"CaptureBrief reviewer",
        "reviewed_at":NOW,
        "attests_complete":True,
        "reviewed_source_ids":[x["source_id"] for x in proposal["payload"]["sources"]],
        "candidate_decisions":decisions,
        "manual_additions":manual_additions or [],
    }


class ReferencePipelineTests(unittest.TestCase):
    def test_proposal_surfaces_named_dependencies_but_never_claims_complete(self):
        text=(
            "Review Amendment 0001 and Attachment 4 before responding. "
            "The technical drawings are in Drawing A-101. Submit through PIEE. "
            "Agency background is at https://example.gov/context."
        )
        proposal=propose_reference_scan([{"source_id":"notice","text":text}],observed_at=NOW)
        self.assertEqual(proposal["status"],"PROPOSED")
        self.assertFalse(proposal["can_claim_completeness"])
        kinds={x["kind"] for x in proposal["payload"]["candidates"]}
        self.assertTrue({"AMENDMENT","ATTACHMENT","DRAWING","EXTERNAL_SYSTEM","EXTERNAL_URL"}<=kinds)

        packet={"reference_scan":proposal,"references":[],"manifest_receipts":[]}
        verdict,findings=validate_reference_closure(packet)
        self.assertEqual(verdict,"REFERENCE_CLOSURE_UNRESOLVED")
        self.assertIn("REFERENCE_SCAN_UNRESOLVED",{f.code for f in findings})

    def test_every_candidate_requires_human_decision(self):
        proposal=propose_reference_scan(
            [{"source_id":"notice","text":"Review Amendment 0001 and Attachment 4."}],
            observed_at=NOW,
        )
        review=review_for(proposal)
        review["candidate_decisions"]=review["candidate_decisions"][:-1]
        with self.assertRaises(ReferenceReviewError):
            confirm_reference_scan(proposal,review)

    def test_ignored_candidate_requires_reason(self):
        proposal=propose_reference_scan(
            [{"source_id":"notice","text":"Background available at https://example.gov/context."}],
            observed_at=NOW,
        )
        review=review_for(proposal,track_all=False)
        review["candidate_decisions"][0]["reason"]=""
        with self.assertRaises(ReferenceReviewError):
            confirm_reference_scan(proposal,review)

    def test_human_review_can_add_parser_miss(self):
        proposal=propose_reference_scan(
            [{"source_id":"notice","text":"Use the current solicitation as the controlling baseline."}],
            observed_at=NOW,
        )
        scan,references=confirm_reference_scan(
            proposal,
            review_for(proposal,manual_additions=[{
                "label":"Current solicitation",
                "kind":"MANUAL",
                "source_id":"notice",
                "reason":"Reviewer identified the controlling solicitation as a required dependency.",
            }]),
        )
        self.assertEqual(scan["status"],"COMPLETE")
        self.assertEqual(scan["review_mode"],"HUMAN_CONFIRMED")
        self.assertEqual(len(references),1)
        self.assertTrue(references[0]["manual_addition"])
        self.assertEqual(references[0]["resolution"],"UNRESOLVED")

    def test_confirmed_but_unresolved_reference_stays_blocked(self):
        proposal=propose_reference_scan(
            [{"source_id":"notice","text":"Review Attachment 4."}],
            observed_at=NOW,
        )
        scan,references=confirm_reference_scan(proposal,review_for(proposal))
        packet={"reference_scan":scan,"references":references,"manifest_receipts":[]}
        verdict,findings=validate_reference_closure(packet)
        self.assertEqual(verdict,"REFERENCE_CLOSURE_UNRESOLVED")
        codes={f.code for f in findings}
        self.assertIn("REFERENCED_ARTIFACT_UNRESOLVED",codes)
        self.assertNotIn("REFERENCE_SCAN_NOT_HUMAN_CONFIRMED",codes)
        self.assertNotIn("REFERENCE_SET_HASH_MISMATCH",codes)

    def test_reference_can_close_only_with_verified_resource_and_bytes(self):
        proposal=propose_reference_scan(
            [{"source_id":"notice","text":"Review Attachment 4."}],
            observed_at=NOW,
        )
        scan,references=confirm_reference_scan(proposal,review_for(proposal))
        ref=references[0]
        ref.update({
            "resolution":"RESOLVED_TO_RESOURCE",
            "source_object_state":"VERIFIED_SOURCE_OBJECT",
            "resource_id":"resource-4",
            "byte_state":"BYTES_VERIFIED_HASHED",
            "byte_sha256":"a"*64,
        })
        packet={
            "reference_scan":scan,
            "references":references,
            "manifest_receipts":[{"items":[{"resource_id":"resource-4"}]}],
        }
        verdict,findings=validate_reference_closure(packet)
        self.assertEqual(verdict,"REFERENCE_CLOSURE_COMPLETE",[f.code for f in findings])

    def test_reference_set_tampering_after_review_is_detected(self):
        proposal=propose_reference_scan(
            [{"source_id":"notice","text":"Review Attachment 4."}],
            observed_at=NOW,
        )
        scan,references=confirm_reference_scan(proposal,review_for(proposal))
        tampered=copy.deepcopy(references)
        tampered.append({
            "reference_id":"ref-injected",
            "label":"Injected",
            "resolution":"UNRESOLVED",
            "source_object_state":"UNRESOLVED_SOURCE_OBJECT",
            "byte_state":"BYTES_NOT_YET_CHECKED",
        })
        packet={"reference_scan":scan,"references":tampered,"manifest_receipts":[]}
        verdict,findings=validate_reference_closure(packet)
        self.assertEqual(verdict,"REFERENCE_CLOSURE_UNRESOLVED")
        codes={f.code for f in findings}
        self.assertIn("REFERENCE_SET_HASH_MISMATCH",codes)
        self.assertIn("REFERENCE_SET_TRACKED_IDS_MISMATCH",codes)

    def test_reviewed_source_coverage_must_equal_proposal_sources(self):
        proposal=propose_reference_scan(
            [
                {"source_id":"notice","text":"Review Attachment 4."},
                {"source_id":"solicitation","text":"See Amendment 0001."},
            ],
            observed_at=NOW,
        )
        review=review_for(proposal)
        review["reviewed_source_ids"]=["notice"]
        with self.assertRaises(ReferenceReviewError):
            confirm_reference_scan(proposal,review)


if __name__=="__main__":
    unittest.main()
