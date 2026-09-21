from __future__ import annotations
import copy
import tempfile
import unittest
from datetime import datetime, timezone
from capturebrief_core.decision_trace import canonical, compare_decision_traces, digest, evaluate_decision_trace, freeze_rule_version, freeze_text_snapshot, passage, trace_work_items
from capturebrief_core.trace_cli import freeze_case
from capturebrief_core.trace_render import render_trace_html, render_trace_markdown
NOW = datetime(2026,9,21,16,tzinfo=timezone.utc)


def demo_case():
    sources=[]
    def make_source(sid,key,title,version,kind,text,day):
        src={"source_id":sid,"title":title,"authority":"SUPPORTING","artifact_state":"PUBLIC","url":f"https://records.example/demo/{sid}","observed_at":f"2026-09-{day:02d}T14:00:00Z","content_sha256":digest(text)}; sources.append(src)
        return freeze_text_snapshot(source=src,source_key=key,kind=kind,version_label=version,text=text,capture_method="NATIVE_TEXT",captured_by="Demo reviewer",mapping_note="Fictional native text",published_at=f"2026-09-{day:02d}T13:00:00Z")
    old=make_source("S1","DEMO-L3","Original solicitation","Original","SOLICITATION","ILLUSTRATIVE\nL.3: Technical response must not exceed 20 pages.",1)
    new=make_source("S2","DEMO-L3","Amendment 02","Amendment 02","AMENDMENT","ILLUSTRATIVE\nAmendment 02 replaces L.3: technical response must not exceed 15 pages.\nDR-7 May 2025 remains incorporated; September 2026 is not incorporated.\nEligibility appendix is referenced but unavailable.",14)
    r1=make_source("R1","DEMO-DR7","Demo rule","May 2025","RULE","ILLUSTRATIVE RULE\nEffective from 2025-05-01.\nApproval required before proposal submission.",2)
    r2=make_source("R2","DEMO-DR7","Demo rule","September 2026","RULE","ILLUSTRATIVE RULE\nEffective from 2026-09-10.\nApproval required before award.",10)
    rules=[freeze_rule_version(namespace="ILLUSTRATIVE",citation="DR-7",edition=e,agency="Demo agency",text_passage=passage(s,3,3,locator="DR-7 p1"),effective_from=d,effective_date_passage=passage(s,2,2,locator="effective date")) for s,e,d in ((r1,"May 2025","2025-05-01"),(r2,"September 2026","2026-09-10"))]
    f1="Page limit changed from 20 to 15 pages."; f2="The packet pins the May 2025 rule edition; newer text is context, not an automatic replacement."; f3="Eligibility remains unverified because the referenced appendix is unavailable."
    assumptions=[
      {"assumption_id":"A1","text":"We can submit 20 pages.","evidence_state":"CONTRADICTED","decision_class":"GATE_CHANGING","finding":f1,"owner":"Proposal lead","next_action":"Revise to 15 pages.","source_ids":["S1","S2"]},
      {"assumption_id":"A2","text":"Use the newest online rule edition.","evidence_state":"CONTRADICTED","decision_class":"GATE_CHANGING","finding":f2,"owner":"Contracts reviewer","next_action":"Use the incorporated edition unless reviewed authority says otherwise.","source_ids":["S2","R1","R2"]},
      {"assumption_id":"A3","text":"We meet every eligibility condition.","evidence_state":"SOURCE_LIMITED","decision_class":"VERIFY_NOW","finding":f3,"owner":"Capture lead","next_action":"Obtain the eligibility appendix or clarification.","source_ids":["S2"]},
    ]
    common={"reviewed_by":"Demo reviewer","reviewed_at":"2026-09-21T14:00:00Z"}
    reviews=[
      {"assumption_id":"A1","evidence_state":"CONTRADICTED","finding":f1,"citations":[{**passage(new,2,2,locator="L.3"),"role":"CONTRADICTS"},{**passage(old,2,2,locator="L.3"),"role":"CONTEXT"}],"rule_scope":{"status":"NOT_RELEVANT","rationale":"Bounded by the solicitation amendment."},"rule_links":[],"changes":[{"from_snapshot_id":old["snapshot_id"],"to_snapshot_id":new["snapshot_id"],"relation":"AMENDS","summary":"20 pages to 15 pages","from_passage":passage(old,2,2,locator="L.3"),"to_passage":passage(new,2,2,locator="L.3"),"authority_passage":passage(new,2,2,locator="L.3")}],**common},
      {"assumption_id":"A2","evidence_state":"CONTRADICTED","finding":f2,"citations":[{**passage(new,3,3,locator="incorporation"),"role":"CONTRADICTS"}],"rule_scope":{"status":"REQUIRED","rationale":"Assumption depends on rule edition."},"rule_links":[{"rule_version_id":rules[0]["rule_version_id"],"family_id":"DEMO-1","applicability":"APPLIES","basis":"INCORPORATED_EDITION","incorporated_edition":"May 2025","rationale":"Amendment retains this edition.","basis_passage":passage(new,3,3,locator="incorporation")},{"rule_version_id":rules[1]["rule_version_id"],"family_id":"DEMO-1","applicability":"DOES_NOT_APPLY","basis":"INCORPORATED_EDITION","incorporated_edition":"September 2026","rationale":"Amendment excludes this edition.","basis_passage":passage(new,3,3,locator="incorporation")}],"changes":[],**common},
      {"assumption_id":"A3","evidence_state":"SOURCE_LIMITED","finding":f3,"citations":[{**passage(new,4,4,locator="attachment note"),"role":"CONTEXT"}],"rule_scope":{"status":"UNRESOLVED","rationale":"Missing appendix."},"rule_links":[],"evidence_request":"Authoritative eligibility appendix or clarification.","changes":[],**common},
    ]
    return {"case_schema_version":"0.2","case_id":"CB-DEMO","family_id":"DEMO-1","current_posture":"HOLD","decision_trace_required":True,"sources":sources,"assumptions":assumptions,"packet":{"family_status":"UNKNOWN","history_action_ids":[],"history_receipts":[],"manifest_receipts":[],"references":[]},"current_action_receipts":[],"decision_trace":{"schema_version":"1.0","family_id":"DEMO-1","synthetic":True,"decision_at":"2026-09-21T14:30:00Z","snapshots":[old,new,r1,r2],"rule_versions":rules,"reviews":reviews}}

class DecisionTraceTests(unittest.TestCase):
    def setUp(self): self.case=demo_case()
    def codes(self): return {f["code"] for f in evaluate_decision_trace(self.case,now=NOW,allow_synthetic=True)["findings"]}
    def test_demo_complete(self): self.assertEqual(evaluate_decision_trace(self.case,now=NOW,allow_synthetic=True)["trace_state"],"ILLUSTRATIVE_TRACE_COMPLETE")
    def test_synthetic_never_release(self): self.assertIn("SYNTHETIC_TRACE_NOT_FOR_RELEASE",{f["code"] for f in evaluate_decision_trace(self.case,now=NOW)["findings"]})
    def test_missing_trace(self): del self.case["decision_trace"]; self.assertIn("TRACE_MISSING",self.codes())
    def test_family_binding(self): self.case["decision_trace"]["family_id"]="OTHER"; self.assertIn("TRACE_FAMILY_MISMATCH",self.codes())
    def test_text_tamper(self): self.case["decision_trace"]["snapshots"][0]["text"]+="x"; self.assertIn("TRACE_TEXT_HASH_MISMATCH",self.codes())
    def test_quote_exactness(self): self.case["decision_trace"]["reviews"][0]["citations"][0]["quote"]="15 pages"; self.assertIn("TRACE_QUOTE_MISMATCH",self.codes())
    def test_source_hash_binding(self): self.case["sources"][0]["content_sha256"]="a"*64; self.assertIn("TRACE_SOURCE_BINDING_MISMATCH",self.codes())
    def test_restricted_source(self): self.case["sources"][0]["artifact_state"]="RESTRICTED"; self.assertIn("TRACE_SOURCE_NOT_PUBLIC",self.codes())
    def test_review_handoff_match(self): self.case["decision_trace"]["reviews"][0]["finding"]="different"; self.assertIn("TRACE_REVIEW_FINDING_MISMATCH",self.codes())
    def test_rule_edition_pinned(self): self.case["decision_trace"]["reviews"][1]["rule_links"][0]["incorporated_edition"]="September 2026"; self.assertIn("TRACE_INCORPORATED_EDITION_MISMATCH",self.codes())
    def test_missing_evidence_request(self): del self.case["decision_trace"]["reviews"][2]["evidence_request"]; self.assertIn("TRACE_EVIDENCE_REQUEST_MISSING",self.codes())
    def test_new_version_reopens_dependent_assumption(self):
        after=copy.deepcopy(self.case); old=after["decision_trace"]["snapshots"][0]; extra=copy.deepcopy(old); extra["version_label"]="Corrected"; extra["snapshot_id"]="SNAP:"+digest(canonical({k:v for k,v in extra.items() if k!="snapshot_id"})); after["decision_trace"]["snapshots"].append(extra)
        self.assertEqual(compare_decision_traces(self.case,after)["reopened_assumptions"][0]["assumption_id"],"A1")
    def test_unrelated_rule_does_not_reopen(self):
        after=copy.deepcopy(self.case); rule=copy.deepcopy(after["decision_trace"]["rule_versions"][0]); rule["rule_key"]="FAR:all:unrelated"; rule["rule_version_id"]="RULE:other"; after["decision_trace"]["rule_versions"].append(rule); self.assertEqual(compare_decision_traces(self.case,after)["reopened_assumptions"],[])
    def test_work_items_are_human_only(self): del self.case["decision_trace"]; tasks=trace_work_items(self.case,now=NOW); self.assertTrue(tasks); self.assertTrue(all(not t["can_auto_execute"] for t in tasks))
    def test_renderers(self):
        markdown=render_trace_markdown(self.case); html=render_trace_html(self.case)
        self.assertIn("Decision evidence",markdown); self.assertIn("Know what your bid decision rests on",html)
        for rendered in (markdown,html):
            self.assertIn("Original solicitation",rendered)
            self.assertIn("Amendment 02",rendered)
            self.assertIn("20 pages",rendered)
            self.assertIn("15 pages",rendered)
    def test_change_passage_pair_is_required(self):
        change=self.case["decision_trace"]["reviews"][0]["changes"][0]
        change.pop("to_passage")
        self.assertIn("TRACE_CHANGE_PASSAGE_PAIR_INCOMPLETE",self.codes())
    def test_change_passage_must_match_declared_version(self):
        change=self.case["decision_trace"]["reviews"][0]["changes"][0]
        change["from_passage"]=copy.deepcopy(change["to_passage"])
        self.assertIn("TRACE_CHANGE_PASSAGE_VERSION_MISMATCH",self.codes())
    def test_legacy_change_without_passages_warns_but_does_not_block(self):
        change=self.case["decision_trace"]["reviews"][0]["changes"][0]
        change.pop("from_passage"); change.pop("to_passage")
        report=evaluate_decision_trace(self.case,now=NOW,allow_synthetic=True)
        self.assertEqual(report["trace_state"],"ILLUSTRATIVE_TRACE_COMPLETE")
        self.assertIn("TRACE_CHANGE_PASSAGES_MISSING",{f["code"] for f in report["findings"]})
        warning=next(f for f in report["findings"] if f["code"]=="TRACE_CHANGE_PASSAGES_MISSING")
        self.assertEqual(warning["severity"],"WARN")
    def test_content_addressed_freeze(self):
        with tempfile.TemporaryDirectory() as d: a=freeze_case(self.case,d); b=freeze_case(self.case,d); self.assertEqual(a,b)

if __name__=="__main__": unittest.main()
