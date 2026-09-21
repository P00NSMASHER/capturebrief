from __future__ import annotations
import copy, unittest

from capturebrief_core.decision_trace import (
    evaluate_decision_trace, freeze_text_snapshot, passage,
)
from capturebrief_core.deviation_applicability import (
    current_deviation_applicability_reviews,
    deviation_applicability_work_items,
    review_deviation_applicability,
)
from capturebrief_core.deviation_review import (
    prepare_deviation_text, review_deviation_authority,
)
from capturebrief_core.deviation_sync import (
    attach_deviation_artifact_receipt,
    build_deviation_candidate_proposal,
    capture_deviation_artifact,
    fetch_pinned_deviation_manifest,
)
from capturebrief_core.rule_registry import digest

CATALOG={
    "schema_version":"1.0",
    "sources":[{
        "source_id":"acqagent-rfo-deviations",
        "namespace":"CLASS_DEVIATION",
        "repository":"acqagent/rfo-deviations",
        "repository_url":"https://github.com/acqagent/rfo-deviations",
        "revision":"c"*40,
        "snapshot_label":"test",
        "path_pattern":"manifest.csv + source PDFs",
    }],
}
URL="https://www.acquisition.gov/cftc-part12.pdf"
PDF=b"%PDF-1.7\n"+b"x"*128
CSV=(
    "on_disk_filename,url_hash,original_filename,agency,part_number,is_dod,source_url,pdf_size_bytes\n"
    f"a.pdf,{digest(URL)[:16]},CFTC_Part12.pdf,CFTC,12,0,{URL},{len(PDF)}\n"
)
MEMO_TEXT=(
    "CFTC Class Deviation\n"
    "Effective September 1, 2026.\n"
    "For covered acquisitions, the agency deviates from FAR Part 12 as described below.\n"
)
GUIDE_TEXT="Current CFTC FAR Overhaul deviations include the Part 12 memorandum.\n"
SOL_TEXT="This solicitation requires offerors to follow the CFTC Part 12 class deviation identified in the acquisition package.\n"

class DeviationApplicabilityTests(unittest.TestCase):
    def manifest_fetcher(self,url,max_bytes): return CSV.encode(),url
    def pdf_fetcher(self,url,max_bytes): return PDF,url

    def base_case(self):
        manifest,manifest_receipt=fetch_pinned_deviation_manifest(
            CATALOG,observed_at="2026-09-21T18:00:00Z",fetcher=self.manifest_fetcher
        )
        proposal=build_deviation_candidate_proposal(
            manifest,manifest_receipt,agency="CFTC",part_numbers=[12],
            proposed_by="Reviewer",proposed_at="2026-09-21T18:05:00Z",
        )
        ident=proposal["candidates"][0]["deviation_source_id"]
        case={
            "case_id":"CB-1",
            "family_id":"FAM-1",
            "current_posture":"GO",
            "packet":{"deviation_candidate_proposal":proposal},
            "sources":[],
            "assumptions":[{
                "assumption_id":"A1",
                "text":"Our bid follows the applicable Part 12 requirements.",
                "evidence_state":"UNPROVEN",
                "decision_class":"VERIFY_NOW",
                "finding":"Deviation applicability requires review.",
                "next_action":"Confirm the applicable deviation.",
                "owner":"Reviewer",
                "source_ids":["sol"],
            }],
        }
        pdf_receipt,_=capture_deviation_artifact(
            case,ident,observed_at="2026-09-21T18:10:00Z",fetcher=self.pdf_fetcher
        )
        case=attach_deviation_artifact_receipt(case,pdf_receipt)
        case,_=prepare_deviation_text(
            case,ident,text=MEMO_TEXT,prepared_by="Reviewer",
            prepared_at="2026-09-21T18:15:00Z",
            mapping_note="Reviewed extraction against captured PDF.",
        )

        guide_source={
            "source_id":"guide","title":"Current deviation guide","authority":"SUPPORTING",
            "artifact_state":"PUBLIC","url":"https://www.acquisition.gov/far-overhaul/far-part-deviation-guide",
            "observed_at":"2026-09-21T18:20:00Z","content_sha256":digest(GUIDE_TEXT),
        }
        sol_source={
            "source_id":"sol","title":"Solicitation","authority":"CONTROLLING",
            "artifact_state":"PUBLIC","url":"https://sam.gov/opp/example/view",
            "observed_at":"2026-09-21T18:18:00Z","content_sha256":digest(SOL_TEXT),
        }
        guide=freeze_text_snapshot(
            source=guide_source,source_key="GUIDE:CFTC",kind="CONTEXT",
            version_label="2026-09-21",text=GUIDE_TEXT,capture_method="REVIEWED_EXTRACTION",
            captured_by="Reviewer",mapping_note="Current public guide observation."
        )
        sol=freeze_text_snapshot(
            source=sol_source,source_key="SOL:FAM-1",kind="SOLICITATION",
            version_label="Current solicitation",text=SOL_TEXT,capture_method="NATIVE_TEXT",
            captured_by="Reviewer",mapping_note="Retained solicitation text."
        )
        case["sources"].extend([guide_source,sol_source])
        case["decision_trace"]={
            "schema_version":"1.0","family_id":"FAM-1","decision_at":"2026-09-21T18:35:00Z",
            "synthetic":False,"snapshots":[guide,sol],"rule_versions":[],
            "reviews":[{
                "assumption_id":"A1","evidence_state":"UNPROVEN",
                "finding":"Deviation applicability requires review.",
                "reviewed_by":"Reviewer","reviewed_at":"2026-09-21T18:19:00Z",
                "citations":[passage(sol,1,1,locator="Solicitation deviation requirement")],
                "rule_scope":{"status":"UNRESOLVED","rationale":"Deviation rule review pending."},
                "rule_links":[],
                "evidence_request":"Confirm the deviation authority and solicitation-specific applicability.",
            }],
        }
        return case,ident,guide,sol

    def authority_case(self,currentness="CURRENT"):
        case,ident,guide,sol=self.base_case()
        decision={
            "deviation_source_id":ident,
            "memo_passage":{"line_start":1,"line_end":3,"locator":"Deviation memo opening"},
            "effective_from":"2026-09-01",
            "effective_date_passage":{"line_start":2,"line_end":2,"locator":"Memo effective-date sentence"},
            "currentness":currentness,
            "currentness_rationale":"Reviewed against the retained current deviation guide.",
        }
        if currentness!="UNRESOLVED":
            decision["currentness_basis_passage"]={
                "snapshot_id":guide["snapshot_id"],"line_start":1,"line_end":1,
                "locator":"Current deviation guide",
            }
        if currentness=="SUPERSEDED":
            decision["superseding_reference"]="replacement-memo-2026"
        case,_=review_deviation_authority(case,{
            "reviewed_by":"Reviewer","reviewed_at":"2026-09-21T18:25:00Z",
            "decisions":[decision],
        })
        return case,ident,guide,sol

    def app_review(self,ident,sol,**overrides):
        row={
            "deviation_source_id":ident,"assumption_id":"A1",
            "applicability":"APPLIES","basis":"SOLICITATION_TEXT",
            "rationale":"The solicitation expressly identifies the reviewed CFTC Part 12 deviation.",
            "scope_rationale":"Class-deviation applicability is material to this bid assumption.",
            "basis_passage":passage(sol,1,1,locator="Solicitation deviation requirement"),
        }
        row.update(overrides)
        return {"reviewed_by":"Reviewer","reviewed_at":"2026-09-21T18:30:00Z","decisions":[row]}

    def test_resolved_applicability_enters_decision_evidence_without_mutating_assumption(self):
        case,ident,guide,sol=self.authority_case("CURRENT")
        before=copy.deepcopy(case["assumptions"][0])
        updated,result=review_deviation_applicability(case,self.app_review(ident,sol))
        self.assertEqual(updated["assumptions"][0],before)
        self.assertFalse(result["assumption_state_changed"])
        self.assertFalse(result["can_auto_apply"])

        record=current_deviation_applicability_reviews(updated)[ident]
        self.assertEqual(record["applicability"],"APPLIES")
        rule=next(x for x in updated["decision_trace"]["rule_versions"] if x["rule_version_id"]==record["rule_version_id"])
        self.assertEqual(rule["namespace"],"CLASS_DEVIATION")
        self.assertEqual(rule["effective_from"],"2026-09-01")
        self.assertTrue(rule["revision_ref"].startswith("DEVART:"))

        link=updated["decision_trace"]["reviews"][0]["rule_links"][0]
        self.assertEqual(link["applicability"],"APPLIES")
        self.assertEqual(link["basis"],"SOLICITATION_TEXT")
        self.assertEqual(link["basis_passage"]["quote"],SOL_TEXT.strip())
        trace=evaluate_decision_trace(updated,now=__import__("datetime").datetime.fromisoformat("2026-09-21T18:40:00+00:00"))
        self.assertEqual(trace["trace_state"],"TRACE_COMPLETE")

    def test_resolved_applicability_requires_resolved_authority_currentness(self):
        case,ident,guide,sol=self.authority_case("UNRESOLVED")
        with self.assertRaises(ValueError):
            review_deviation_applicability(case,self.app_review(ident,sol))

    def test_resolved_applicability_requires_separate_pursuit_basis(self):
        case,ident,guide,sol=self.authority_case("CURRENT")
        review=self.app_review(ident,sol)
        review["decisions"][0]["basis_passage"]=None
        with self.assertRaises(ValueError):
            review_deviation_applicability(case,review)

    def test_unresolved_applicability_cannot_hide_under_resolved_assumption(self):
        case,ident,guide,sol=self.authority_case("CURRENT")
        case=copy.deepcopy(case)
        case["assumptions"][0]["evidence_state"]="SUPPORTED"
        case["decision_trace"]["reviews"][0]["evidence_state"]="SUPPORTED"
        review=self.app_review(
            ident,sol,applicability="UNRESOLVED",basis="UNRESOLVED",basis_passage=None
        )
        with self.assertRaises(ValueError):
            review_deviation_applicability(case,review)

    def test_superseded_deviation_cannot_apply_without_explicit_solicitation_or_amendment_basis(self):
        case,ident,guide,sol=self.authority_case("SUPERSEDED")
        review=self.app_review(ident,sol,basis="DEVIATION_REVIEW")
        with self.assertRaises(ValueError):
            review_deviation_applicability(case,review)

    def test_basis_quote_must_match_retained_source(self):
        case,ident,guide,sol=self.authority_case("CURRENT")
        review=self.app_review(ident,sol)
        review["decisions"][0]["basis_passage"]["quote"]="different"
        with self.assertRaises(ValueError):
            review_deviation_applicability(case,review)

    def test_packet_review_does_not_count_if_decision_evidence_link_is_removed(self):
        case,ident,guide,sol=self.authority_case("CURRENT")
        updated,_=review_deviation_applicability(case,self.app_review(ident,sol))
        self.assertIn(ident,current_deviation_applicability_reviews(updated))
        tampered=copy.deepcopy(updated)
        tampered["decision_trace"]["reviews"][0]["rule_links"]=[]
        self.assertNotIn(ident,current_deviation_applicability_reviews(tampered))
        tasks=deviation_applicability_work_items(tampered)
        self.assertEqual([x["task_key"] for x in tasks],["deviation-applicability:"+ident])

    def test_work_item_opens_only_after_authority_currentness_is_resolved(self):
        unresolved,ident,guide,sol=self.authority_case("UNRESOLVED")
        self.assertEqual(deviation_applicability_work_items(unresolved),[])
        current,ident,guide,sol=self.authority_case("CURRENT")
        tasks=deviation_applicability_work_items(current)
        self.assertEqual([x["task_key"] for x in tasks],["deviation-applicability:"+ident])
        self.assertEqual(tasks[0]["actor"],"HUMAN_REVIEW")
        self.assertFalse(tasks[0]["can_auto_execute"])

if __name__=="__main__":
    unittest.main()
