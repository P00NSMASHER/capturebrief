import copy,hashlib,json,unittest
from datetime import datetime,timedelta,timezone
from capturebrief_core import audit_case,compare_cases
from capturebrief_core.model import history_set_digest
NOW=datetime(2026,9,21,12,0,tzinfo=timezone.utc)
def case():
    h=["a1","a2"]; payload={"action":"a2"}; dg=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {"case_id":"CB-1","family_id":"DEMO","current_posture":"GO","packet":{"family_status":"ACTIVE","history_action_ids":h,"history_complete":True,"manifest_complete":True,"manifest_sha256":"b"*64,"artifacts":[{"artifact_id":"solicitation","name":"sol.pdf","state":"PUBLIC","sha256":"a"*64}],"external_dependencies":[]},"current_action_receipts":[{"asserted_action_id":"a2","semantics":"CURRENT_ACTIVE","observed_family_status":"ACTIVE","source_url":"https://sam.gov/opportunities/example","observed_at":(NOW-timedelta(minutes=1)).isoformat(),"expires_at":(NOW+timedelta(hours=1)).isoformat(),"evidence_payload":payload,"evidence_payload_sha256":dg,"history_set_sha256":history_set_digest(h)}],"sources":[{"source_id":"sam","url":"https://sam.gov/opportunities/example","authority":"CONTROLLING_CURRENT","artifact_state":"PUBLIC","observed_at":NOW.isoformat(),"content_sha256":"c"*64}],"assumptions":[{"assumption_id":"A1","text":"Current packet controls","evidence_state":"SUPPORTED","decision_class":"MONITOR_ONLY","finding":"Verified","source_ids":["sam"],"reopen_triggers":["CURRENT_ACTION_CHANGE","PACKET_MANIFEST_CHANGE","ARTIFACT:solicitation"]}]}
class AuditWatchTests(unittest.TestCase):
    def test_clean_ready(self): self.assertEqual(audit_case(case(),now=NOW).release_state,"READY_FOR_HUMAN_RELEASE")
    def test_manifest_blocks(self):
        c=case(); c["packet"]["manifest_complete"]=False; r=audit_case(c,now=NOW); self.assertEqual(r.release_state,"FAIL_CLOSED"); self.assertIn("MANIFEST_UNRESOLVED",{x.code for x in r.findings})
    def test_public_artifact_hash_required(self):
        c=case(); c["packet"]["artifacts"][0]["sha256"]=None; self.assertIn("PUBLIC_ARTIFACT_HASH_MISSING",{x.code for x in audit_case(c,now=NOW).findings})
    def test_unknown_cannot_be_resolved_gate_fact(self):
        c=case(); c["assumptions"][0].update({"evidence_state":"UNPROVEN","decision_class":"GATE_CHANGING","next_action":"Verify","owner":"lead"}); self.assertIn("UNKNOWN_MUST_BE_VERIFY_NOW",{x.code for x in audit_case(c,now=NOW).findings})
    def test_restricted_safe_stop(self):
        c=case(); c["sources"][0]["artifact_state"]="RESTRICTED"; self.assertIn("NONPUBLIC_SOURCE_ASSERTION",{x.code for x in audit_case(c,now=NOW).findings})
    def test_action_items_need_owner_and_action(self):
        c=case(); c["assumptions"][0].update({"evidence_state":"UNPROVEN","decision_class":"VERIFY_NOW"}); codes={x.code for x in audit_case(c,now=NOW).findings}; self.assertTrue({"ACTION_ITEM_MISSING_NEXT_ACTION","ACTION_ITEM_UNOWNED"}<=codes)
    def test_handoff_cap_and_deadline_timezone(self):
        c=case(); c["assumptions"]=[]
        for i in range(6): c["assumptions"].append({"assumption_id":f"A{i}","text":"x","evidence_state":"UNPROVEN","decision_class":"VERIFY_NOW","finding":"x","next_action":"verify","owner":"lead","source_ids":["sam"],"reopen_triggers":[]})
        self.assertIn("HANDOFF_TOO_LARGE",{x.code for x in audit_case(c,now=NOW).findings})
        c=case(); c["assumptions"][0]["deadline"]="2026-09-30T17:00:00"; self.assertIn("DEADLINE_TIMEZONE_MISSING",{x.code for x in audit_case(c,now=NOW).findings})
    def test_change_watch_is_targeted(self):
        b=case(); a=copy.deepcopy(b); a["packet"]["artifacts"][0]["sha256"]="d"*64; a["assumptions"].append({"assumption_id":"A2","reopen_triggers":["ARTIFACT:other"]})
        d=compare_cases(b,a); ids={x["assumption_id"] for x in d["reopened_assumptions"]}; self.assertIn("A1",ids); self.assertNotIn("A2",ids)
        a=copy.deepcopy(b); a["packet"]["manifest_sha256"]="e"*64; d=compare_cases(b,a); self.assertIn("PACKET_MANIFEST_CHANGE",{x["key"] for x in d["events"]})
if __name__=="__main__": unittest.main()
