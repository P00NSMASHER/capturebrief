from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone

from capturebrief_core.decision_trace import canonical, digest, freeze_text_snapshot, passage
from capturebrief_core.deviation_applicability import review_deviation_applicability
from capturebrief_core.deviation_review import prepare_deviation_text, review_deviation_authority
from capturebrief_core.deviation_sync import (
    attach_deviation_artifact_receipt,
    build_deviation_candidate_proposal,
    capture_deviation_artifact,
    fetch_pinned_deviation_manifest,
)
from capturebrief_core.watch_baseline import WATCH_SCHEMA, _public_state, compare_watch_baseline

NOW=datetime(2026,9,21,18,40,tzinfo=timezone.utc)
URL="https://www.acquisition.gov/cftc-part12.pdf"
PDF1=b"%PDF-1.7\n"+b"a"*128
PDF2=b"%PDF-1.7\n"+b"b"*140
GUIDE="Current CFTC FAR Overhaul deviations include the Part 12 memorandum.\n"
SOL="This solicitation requires offerors to follow the CFTC Part 12 class deviation identified in the acquisition package.\n"
MEMO=(
    "CFTC Class Deviation\n"
    "Effective September 1, 2026.\n"
    "For covered acquisitions, the agency deviates from FAR Part 12 as described below.\n"
)

def catalog(rev="c"*40):
    return {
        "schema_version":"1.0",
        "sources":[{
            "source_id":"acqagent-rfo-deviations",
            "namespace":"CLASS_DEVIATION",
            "repository":"acqagent/rfo-deviations",
            "repository_url":"https://github.com/acqagent/rfo-deviations",
            "revision":rev,
            "snapshot_label":"test",
            "path_pattern":"manifest.csv + source PDFs",
        }],
    }

def csv_bytes():
    text=(
        "on_disk_filename,url_hash,original_filename,agency,part_number,is_dod,source_url,pdf_size_bytes\n"
        f"a.pdf,{digest(URL)[:16]},CFTC_Part12.pdf,CFTC,12,0,{URL},{len(PDF1)}\n"
    )
    return text.encode()

class DeviationWatchTests(unittest.TestCase):
    def manifest_fetcher(self,url,max_bytes):
        return csv_bytes(),url

    def pdf1_fetcher(self,url,max_bytes):
        return PDF1,url

    def base_case(self):
        manifest,mreceipt=fetch_pinned_deviation_manifest(
            catalog(),observed_at="2026-09-21T18:00:00Z",fetcher=self.manifest_fetcher
        )
        proposal=build_deviation_candidate_proposal(
            manifest,mreceipt,agency="CFTC",part_numbers=[12],
            proposed_by="Reviewer",proposed_at="2026-09-21T18:05:00Z",
        )
        ident=proposal["candidates"][0]["deviation_source_id"]
        case={
            "case_id":"CB-WATCH-DEVIATION",
            "family_id":"FAM-WATCH-1",
            "packet":{"deviation_candidate_proposal":proposal},
            "sources":[],
            "assumptions":[
                {
                    "assumption_id":"A1",
                    "text":"The CFTC Part 12 deviation applies to this bid.",
                    "evidence_state":"UNPROVEN",
                    "decision_class":"VERIFY_NOW",
                    "finding":"Deviation applicability remains a reviewed dependency.",
                    "next_action":"Monitor the reviewed deviation and solicitation basis.",
                    "owner":"Reviewer",
                    "source_ids":["sol"],
                    "reopen_triggers":[],
                },
                {
                    "assumption_id":"A2",
                    "text":"The solicitation due date remains unchanged.",
                    "evidence_state":"SUPPORTED",
                    "decision_class":"MONITOR_ONLY",
                    "finding":"The retained solicitation supports the due-date assumption.",
                    "next_action":"Monitor solicitation changes.",
                    "owner":"Reviewer",
                    "source_ids":["sol"],
                    "reopen_triggers":[],
                },
            ],
        }
        pdf_receipt,_=capture_deviation_artifact(
            case,ident,observed_at="2026-09-21T18:10:00Z",fetcher=self.pdf1_fetcher
        )
        case=attach_deviation_artifact_receipt(case,pdf_receipt)
        case,_=prepare_deviation_text(
            case,ident,text=MEMO,prepared_by="Reviewer",
            prepared_at="2026-09-21T18:15:00Z",
            mapping_note="Reviewed extraction against captured official PDF.",
        )

        guide_source={
            "source_id":"guide","title":"Deviation guide","authority":"SUPPORTING",
            "artifact_state":"PUBLIC","url":"https://www.acquisition.gov/far-overhaul/far-part-deviation-guide",
            "observed_at":"2026-09-21T18:20:00Z","content_sha256":digest(GUIDE),
        }
        sol_source={
            "source_id":"sol","title":"Solicitation","authority":"CONTROLLING",
            "artifact_state":"PUBLIC","url":"https://sam.gov/opp/example/view",
            "observed_at":"2026-09-21T18:18:00Z","content_sha256":digest(SOL),
        }
        guide=freeze_text_snapshot(
            source=guide_source,source_key="GUIDE:CFTC",kind="CONTEXT",
            version_label="2026-09-21",text=GUIDE,capture_method="REVIEWED_EXTRACTION",
            captured_by="Reviewer",mapping_note="Current public deviation guide."
        )
        sol=freeze_text_snapshot(
            source=sol_source,source_key="SOL:FAM-WATCH-1",kind="SOLICITATION",
            version_label="Current solicitation",text=SOL,capture_method="NATIVE_TEXT",
            captured_by="Reviewer",mapping_note="Retained solicitation text."
        )
        case["sources"].extend([guide_source,sol_source])
        sol_pass=passage(sol,1,1,locator="Solicitation deviation requirement")
        case["decision_trace"]={
            "schema_version":"1.0","family_id":"FAM-WATCH-1",
            "decision_at":"2026-09-21T18:35:00Z","synthetic":False,
            "snapshots":[guide,sol],"rule_versions":[],
            "reviews":[
                {
                    "assumption_id":"A1","evidence_state":"UNPROVEN",
                    "finding":"Deviation applicability remains a reviewed dependency.",
                    "citations":[sol_pass],
                    "rule_scope":{"status":"UNRESOLVED","rationale":"Deviation review pending."},
                    "rule_links":[],
                    "changes":[],
                    "reviewed_by":"Reviewer","reviewed_at":"2026-09-21T18:19:00Z",
                    "evidence_request":"Confirm deviation authority and applicability.",
                },
                {
                    "assumption_id":"A2","evidence_state":"SUPPORTED",
                    "finding":"The retained solicitation supports the due-date assumption.",
                    "citations":[sol_pass],
                    "rule_scope":{"status":"NOT_RELEVANT","rationale":"This assumption does not depend on a procurement rule."},
                    "rule_links":[],
                    "changes":[],
                    "reviewed_by":"Reviewer","reviewed_at":"2026-09-21T18:19:00Z",
                },
            ],
        }
        case,_=review_deviation_authority(case,{
            "reviewed_by":"Reviewer","reviewed_at":"2026-09-21T18:25:00Z",
            "decisions":[{
                "deviation_source_id":ident,
                "memo_passage":{"line_start":1,"line_end":3,"locator":"Memo opening"},
                "effective_from":"2026-09-01",
                "effective_date_passage":{"line_start":2,"line_end":2,"locator":"Effective-date sentence"},
                "currentness":"CURRENT",
                "currentness_rationale":"The retained current guide lists this memo.",
                "currentness_basis_passage":{
                    "snapshot_id":guide["snapshot_id"],"line_start":1,"line_end":1,
                    "locator":"Current deviation guide",
                },
            }],
        })
        case,_=review_deviation_applicability(case,{
            "reviewed_by":"Reviewer","reviewed_at":"2026-09-21T18:30:00Z",
            "decisions":[{
                "deviation_source_id":ident,"assumption_id":"A1",
                "applicability":"APPLIES","basis":"SOLICITATION_TEXT",
                "rationale":"The solicitation explicitly identifies the reviewed deviation.",
                "scope_rationale":"A1 depends on this class deviation.",
                "basis_passage":sol_pass,
            }],
        })
        return case,ident

    def baseline(self,case):
        state=_public_state(case,now=NOW)
        payload={
            "schema_version":WATCH_SCHEMA,
            "case_id":case["case_id"],"family_id":case["family_id"],
            "created_at":"2026-09-21T18:40:00Z",
            "watch_until":"2026-10-05T18:40:00Z",
            "case_sha256":digest(canonical(case)),
            "state":state,
            "contains_raw_case":False,
            "contains_source_text":False,
            "automatic_decision_change":False,
        }
        return {**payload,"baseline_sha256":digest(canonical(payload))}

    def test_unchanged_deviation_evidence_has_no_watch_events(self):
        case,_=self.base_case()
        result=compare_watch_baseline(self.baseline(case),case,now=NOW)
        self.assertEqual(result["events"],[])
        self.assertEqual(result["reopened_assumptions"],[])

    def test_baseline_keeps_only_privacy_safe_deviation_fingerprints(self):
        case,ident=self.base_case()
        baseline=self.baseline(case)
        state=baseline["state"]
        self.assertIn(ident,state["deviation_artifacts"])
        self.assertIn("pdf_sha256",state["deviation_artifacts"][ident])
        encoded=canonical(state).decode()
        self.assertNotIn(MEMO.strip(),encoded)
        self.assertNotIn(SOL.strip(),encoded)
        self.assertNotIn(URL,encoded)
        self.assertNotIn("%PDF",encoded)

    def test_changed_official_pdf_reopens_only_dependent_assumption(self):
        case,ident=self.base_case()
        baseline=self.baseline(case)
        before_rule_links=copy.deepcopy(case["decision_trace"]["reviews"][0]["rule_links"])

        receipt,_=capture_deviation_artifact(
            case,ident,observed_at="2026-09-21T18:45:00Z",
            fetcher=lambda url,max_bytes:(PDF2,url),
        )
        after=attach_deviation_artifact_receipt(case,receipt)
        result=compare_watch_baseline(
            baseline,after,
            now=datetime(2026,9,21,18,50,tzinfo=timezone.utc),
        )
        types={x["type"] for x in result["events"]}
        self.assertIn("DEVIATION_ARTIFACT_CHANGED",types)
        self.assertEqual([x["assumption_id"] for x in result["reopened_assumptions"]],["A1"])
        self.assertIn(
            "DEVIATION:"+ident,
            result["reopened_assumptions"][0]["matched_dependencies"],
        )
        self.assertTrue(result["requires_human_review"])
        self.assertTrue(result["previous_decision_preserved"])
        self.assertFalse(result["automatic_decision_change"])
        self.assertEqual(after["decision_trace"]["reviews"][0]["rule_links"],before_rule_links)
        self.assertEqual(after["assumptions"][0]["evidence_state"],"UNPROVEN")
        self.assertEqual(after["assumptions"][1]["evidence_state"],"SUPPORTED")

    def test_new_pinned_proposal_reopens_prior_deviation_dependency(self):
        case,ident=self.base_case()
        baseline=self.baseline(case)

        new_catalog=catalog("d"*40)
        manifest,receipt=fetch_pinned_deviation_manifest(
            new_catalog,observed_at="2026-09-22T12:00:00Z",fetcher=self.manifest_fetcher
        )
        new_proposal=build_deviation_candidate_proposal(
            manifest,receipt,agency="CFTC",part_numbers=[12],
            proposed_by="Reviewer",proposed_at="2026-09-22T12:05:00Z",
        )
        after=copy.deepcopy(case)
        after["packet"].setdefault("deviation_candidate_proposal_history",[]).append(
            after["packet"]["deviation_candidate_proposal"]
        )
        after["packet"]["deviation_candidate_proposal"]=new_proposal
        result=compare_watch_baseline(
            baseline,after,
            now=datetime(2026,9,22,12,10,tzinfo=timezone.utc),
        )
        types={x["type"] for x in result["events"]}
        self.assertIn("DEVIATION_PROPOSAL_CHANGED",types)
        self.assertEqual([x["assumption_id"] for x in result["reopened_assumptions"]],["A1"])
        self.assertIn(
            "DEVIATION:"+ident,
            result["reopened_assumptions"][0]["matched_dependencies"],
        )
        self.assertFalse(result["automatic_decision_change"])
        self.assertTrue(result["previous_decision_preserved"])

if __name__=="__main__":
    unittest.main()
