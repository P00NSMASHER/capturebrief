from __future__ import annotations

import copy
import unittest

from capturebrief_core.decision_trace import freeze_text_snapshot
from capturebrief_core.deviation_review import (
    current_deviation_authority_reviews,
    current_deviation_text_preparations,
    deviation_authority_work_items,
    prepare_deviation_text,
    review_deviation_authority,
)
from capturebrief_core.deviation_sync import (
    attach_deviation_artifact_receipt,
    build_deviation_candidate_proposal,
    capture_deviation_artifact,
    fetch_pinned_deviation_manifest,
)
from capturebrief_core.rule_registry import digest
from capturebrief_core.workqueue import build_work_queue

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
    "Use the attached replacement text.\n"
)
GUIDE_TEXT=(
    "Current CFTC FAR Overhaul deviations include the Part 12 memorandum.\n"
    "This guide was observed for the current pursuit review.\n"
)

class DeviationAuthorityReviewTests(unittest.TestCase):
    def manifest_fetcher(self,url,max_bytes):
        return CSV.encode(),url

    def pdf_fetcher(self,url,max_bytes):
        return PDF,url

    def captured_case(self):
        manifest,receipt=fetch_pinned_deviation_manifest(
            CATALOG,observed_at="2026-09-21T18:00:00Z",fetcher=self.manifest_fetcher
        )
        proposal=build_deviation_candidate_proposal(
            manifest,receipt,agency="CFTC",part_numbers=[12],
            proposed_by="Reviewer",proposed_at="2026-09-21T18:05:00Z",
        )
        case={
            "family_id":"FAM-1",
            "packet":{"deviation_candidate_proposal":proposal},
            "sources":[],
            "assumptions":[{
                "assumption_id":"A1",
                "text":"Our bid follows the applicable Part 12 rules.",
                "evidence_state":"UNPROVEN",
                "decision_class":"VERIFY_NOW",
                "finding":"Deviation applicability still requires review.",
                "next_action":"Review rule authority.",
                "owner":"Reviewer",
                "source_ids":[],
            }],
        }
        ident=proposal["candidates"][0]["deviation_source_id"]
        pdf_receipt,_=capture_deviation_artifact(
            case,ident,observed_at="2026-09-21T18:10:00Z",fetcher=self.pdf_fetcher
        )
        return attach_deviation_artifact_receipt(case,pdf_receipt),ident

    def prepared_case(self):
        case,ident=self.captured_case()
        case,result=prepare_deviation_text(
            case,ident,text=MEMO_TEXT,
            prepared_by="Reviewer",
            prepared_at="2026-09-21T18:15:00Z",
            mapping_note="Human reviewed PDF text against captured artifact bytes.",
        )
        return case,ident,result

    def add_currentness_basis(self,case,observed_at="2026-09-21T18:20:00Z"):
        source={
            "source_id":"deviation-guide",
            "title":"Current deviation guide observation",
            "authority":"SUPPORTING",
            "artifact_state":"PUBLIC",
            "url":"https://www.acquisition.gov/far-overhaul/far-part-deviation-guide",
            "observed_at":observed_at,
            "content_sha256":digest(GUIDE_TEXT),
        }
        snap=freeze_text_snapshot(
            source=source,
            source_key="DEVIATION_GUIDE:CFTC",
            kind="CONTEXT",
            version_label="2026-09-21 observation",
            text=GUIDE_TEXT,
            capture_method="REVIEWED_EXTRACTION",
            captured_by="Reviewer",
            mapping_note="Reviewed public guide text retained for currentness basis.",
        )
        out=copy.deepcopy(case)
        out.setdefault("sources",[]).append(source)
        out["decision_trace"]={"snapshots":[snap]}
        return out,snap

    def test_prepare_requires_captured_pdf(self):
        case,ident=self.captured_case()
        empty=copy.deepcopy(case)
        empty["packet"]["deviation_artifact_receipts"]=[]
        with self.assertRaises(ValueError):
            prepare_deviation_text(
                empty,ident,text=MEMO_TEXT,prepared_by="Reviewer",
                prepared_at="2026-09-21T18:15:00Z",mapping_note="Reviewed extraction.",
            )

    def test_prepare_binds_text_snapshot_to_pdf_sha(self):
        case,ident,result=self.prepared_case()
        prep=current_deviation_text_preparations(case)[ident]
        receipt=case["packet"]["deviation_artifact_receipts"][0]
        self.assertEqual(prep["document_sha256"],receipt["pdf_sha256"])
        self.assertEqual(prep["snapshot"]["document_sha256"],receipt["pdf_sha256"])
        self.assertEqual(prep["source"]["content_sha256"],receipt["pdf_sha256"])
        self.assertEqual(result["currentness"],"UNRESOLVED")
        self.assertEqual(result["applicability"],"UNRESOLVED")

    def test_effective_date_requires_exact_memo_passage(self):
        case,ident,_=self.prepared_case()
        review={
            "reviewed_by":"Reviewer",
            "reviewed_at":"2026-09-21T18:25:00Z",
            "decisions":[{
                "deviation_source_id":ident,
                "memo_passage":{"line_start":1,"line_end":3,"locator":"Memo opening"},
                "effective_from":"2026-09-01",
                "currentness":"UNRESOLVED",
                "currentness_rationale":"Currentness needs a separate public source.",
            }],
        }
        with self.assertRaises(ValueError):
            review_deviation_authority(case,review)

    def test_unresolved_review_is_structured_but_not_applicability(self):
        case,ident,_=self.prepared_case()
        updated,result=review_deviation_authority(case,{
            "reviewed_by":"Reviewer",
            "reviewed_at":"2026-09-21T18:25:00Z",
            "decisions":[{
                "deviation_source_id":ident,
                "memo_passage":{"line_start":1,"line_end":3,"locator":"Memo opening"},
                "effective_from":"2026-09-01",
                "effective_date_passage":{"line_start":2,"line_end":2,"locator":"Effective-date sentence"},
                "currentness":"UNRESOLVED",
                "currentness_rationale":"No independent currentness basis retained yet.",
            }],
        })
        record=current_deviation_authority_reviews(updated)[ident]
        self.assertEqual(record["currentness"],"UNRESOLVED")
        self.assertEqual(record["effective_from"],"2026-09-01")
        self.assertEqual(record["applicability"],"UNRESOLVED")
        self.assertFalse(record["assumption_state_changed"])
        self.assertEqual(updated["assumptions"][0]["evidence_state"],"UNPROVEN")
        self.assertFalse(result["can_auto_apply"])

    def test_current_requires_separate_retained_basis_passage(self):
        case,ident,_=self.prepared_case()
        case,basis=self.add_currentness_basis(case)
        updated,result=review_deviation_authority(case,{
            "reviewed_by":"Reviewer",
            "reviewed_at":"2026-09-21T18:25:00Z",
            "decisions":[{
                "deviation_source_id":ident,
                "memo_passage":{"line_start":1,"line_end":3,"locator":"Memo opening"},
                "effective_from":"2026-09-01",
                "effective_date_passage":{"line_start":2,"line_end":2,"locator":"Effective-date sentence"},
                "currentness":"CURRENT",
                "currentness_rationale":"The retained current guide lists this agency/Part memo.",
                "currentness_basis_passage":{
                    "snapshot_id":basis["snapshot_id"],
                    "line_start":1,"line_end":1,"locator":"Current deviation guide"
                },
            }],
        })
        record=current_deviation_authority_reviews(updated)[ident]
        self.assertEqual(record["currentness"],"CURRENT")
        self.assertEqual(record["currentness_basis_passage"]["quote"],GUIDE_TEXT.splitlines()[0])
        self.assertFalse(record["currentness_authoritative"])
        self.assertEqual(result["applicability"],"UNRESOLVED")

    def test_current_without_basis_is_rejected(self):
        case,ident,_=self.prepared_case()
        with self.assertRaises(ValueError):
            review_deviation_authority(case,{
                "reviewed_by":"Reviewer",
                "reviewed_at":"2026-09-21T18:25:00Z",
                "decisions":[{
                    "deviation_source_id":ident,
                    "memo_passage":{"line_start":1,"line_end":1,"locator":"Memo title"},
                    "currentness":"CURRENT",
                    "currentness_rationale":"Claimed current without separate evidence.",
                }],
            })

    def test_memo_cannot_self_certify_currentness(self):
        case,ident,_=self.prepared_case()
        prep=current_deviation_text_preparations(case)[ident]
        case=copy.deepcopy(case)
        case["decision_trace"]={"snapshots":[prep["snapshot"]]}
        with self.assertRaises(ValueError):
            review_deviation_authority(case,{
                "reviewed_by":"Reviewer",
                "reviewed_at":"2026-09-21T18:25:00Z",
                "decisions":[{
                    "deviation_source_id":ident,
                    "memo_passage":{"line_start":1,"line_end":1,"locator":"Memo title"},
                    "currentness":"CURRENT",
                    "currentness_rationale":"Self-certified.",
                    "currentness_basis_passage":{
                        "snapshot_id":prep["snapshot"]["snapshot_id"],
                        "line_start":1,"line_end":1,"locator":"Memo title",
                    },
                }],
            })

    def test_currentness_basis_cannot_look_ahead(self):
        case,ident,_=self.prepared_case()
        case,basis=self.add_currentness_basis(case,observed_at="2026-09-21T18:40:00Z")
        with self.assertRaises(ValueError):
            review_deviation_authority(case,{
                "reviewed_by":"Reviewer",
                "reviewed_at":"2026-09-21T18:25:00Z",
                "decisions":[{
                    "deviation_source_id":ident,
                    "memo_passage":{"line_start":1,"line_end":1,"locator":"Memo title"},
                    "currentness":"CURRENT",
                    "currentness_rationale":"Future observation must not support earlier review.",
                    "currentness_basis_passage":{
                        "snapshot_id":basis["snapshot_id"],
                        "line_start":1,"line_end":1,"locator":"Guide"
                    },
                }],
            })

    def test_tampered_currentness_basis_snapshot_is_rejected(self):
        case,ident,_=self.prepared_case()
        case,basis=self.add_currentness_basis(case)
        case=copy.deepcopy(case)
        case["decision_trace"]["snapshots"][0]["text"]="tampered"
        with self.assertRaises(ValueError):
            review_deviation_authority(case,{
                "reviewed_by":"Reviewer",
                "reviewed_at":"2026-09-21T18:25:00Z",
                "decisions":[{
                    "deviation_source_id":ident,
                    "memo_passage":{"line_start":1,"line_end":1,"locator":"Memo title"},
                    "currentness":"CURRENT",
                    "currentness_rationale":"Tampered evidence must fail.",
                    "currentness_basis_passage":{
                        "snapshot_id":basis["snapshot_id"],
                        "line_start":1,"line_end":1,"locator":"Guide"
                    },
                }],
            })

    def test_effective_passage_without_effective_date_is_rejected(self):
        case,ident,_=self.prepared_case()
        with self.assertRaises(ValueError):
            review_deviation_authority(case,{
                "reviewed_by":"Reviewer",
                "reviewed_at":"2026-09-21T18:25:00Z",
                "decisions":[{
                    "deviation_source_id":ident,
                    "memo_passage":{"line_start":1,"line_end":1,"locator":"Memo title"},
                    "effective_date_passage":{"line_start":2,"line_end":2,"locator":"Effective sentence"},
                    "currentness":"UNRESOLVED",
                    "currentness_rationale":"No currentness evidence.",
                }],
            })

    def test_superseded_requires_reference(self):
        case,ident,_=self.prepared_case()
        case,basis=self.add_currentness_basis(case)
        with self.assertRaises(ValueError):
            review_deviation_authority(case,{
                "reviewed_by":"Reviewer",
                "reviewed_at":"2026-09-21T18:25:00Z",
                "decisions":[{
                    "deviation_source_id":ident,
                    "memo_passage":{"line_start":1,"line_end":1,"locator":"Memo title"},
                    "currentness":"SUPERSEDED",
                    "currentness_rationale":"External source indicates replacement.",
                    "currentness_basis_passage":{
                        "snapshot_id":basis["snapshot_id"],
                        "line_start":1,"line_end":1,"locator":"Guide"
                    },
                }],
            })

    def test_operator_queue_uses_specific_deviation_authority_tasks(self):
        case,ident=self.captured_case()
        keys={x["task_key"] for x in build_work_queue(case)["tasks"]}
        self.assertIn("deviation-text:"+ident,keys)
        self.assertNotIn("deviations:review-candidates",keys)

        case,ident,_=self.prepared_case()
        keys={x["task_key"] for x in build_work_queue(case)["tasks"]}
        self.assertIn("deviation-authority:"+ident,keys)
        self.assertNotIn("deviations:review-candidates",keys)

    def test_work_items_progress_capture_to_text_to_authority_to_currentness(self):
        case,ident=self.captured_case()
        tasks=deviation_authority_work_items(case)
        self.assertEqual([x["task_key"] for x in tasks],["deviation-text:"+ident])

        case,ident,_=self.prepared_case()
        tasks=deviation_authority_work_items(case)
        self.assertEqual([x["task_key"] for x in tasks],["deviation-authority:"+ident])

        case,_=review_deviation_authority(case,{
            "reviewed_by":"Reviewer",
            "reviewed_at":"2026-09-21T18:25:00Z",
            "decisions":[{
                "deviation_source_id":ident,
                "memo_passage":{"line_start":1,"line_end":1,"locator":"Memo title"},
                "currentness":"UNRESOLVED",
                "currentness_rationale":"Need independent currentness evidence.",
            }],
        })
        tasks=deviation_authority_work_items(case)
        self.assertEqual([x["task_key"] for x in tasks],["deviation-currentness:"+ident])

        case,basis=self.add_currentness_basis(case)
        case,_=review_deviation_authority(case,{
            "reviewed_by":"Reviewer",
            "reviewed_at":"2026-09-21T18:30:00Z",
            "decisions":[{
                "deviation_source_id":ident,
                "memo_passage":{"line_start":1,"line_end":1,"locator":"Memo title"},
                "currentness":"CURRENT",
                "currentness_rationale":"Current guide lists the memo.",
                "currentness_basis_passage":{
                    "snapshot_id":basis["snapshot_id"],
                    "line_start":1,"line_end":1,"locator":"Guide"
                },
            }],
        })
        self.assertEqual(deviation_authority_work_items(case),[])

if __name__=="__main__":
    unittest.main()
