import copy, hashlib, json, unittest
from datetime import datetime, timedelta, timezone

from capturebrief_core import audit_case, make_history_receipt, normalize_manifest_payload, compare_cases, confirm_reference_scan, propose_reference_scan
from capturebrief_core.model import history_set_digest

NOW=datetime(2026,9,21,13,0,tzinfo=timezone.utc)

def reviewed_reference(label="Current solicitation"):
    proposal=propose_reference_scan([{"source_id":"sam","text":"Human review source text."}],observed_at=NOW.isoformat())
    review={
        "reviewer":"CaptureBrief reviewer",
        "reviewed_at":NOW.isoformat(),
        "attests_complete":True,
        "reviewed_source_ids":["sam"],
        "candidate_decisions":[],
        "manual_additions":[{"label":label,"kind":"MANUAL","source_id":"sam","reason":"Reviewer identified a required dependency."}],
    }
    scan,refs=confirm_reference_scan(proposal,review)
    return scan,refs[0]

def authority_receipt(history,action):
    payload={"status":"ACTIVE","action":action,"history":list(history)}
    dg=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {"asserted_action_id":action,"semantics":"CURRENT_ACTIVE","observed_family_status":"ACTIVE","source_url":"https://sam.gov/opportunities/example","observed_at":(NOW-timedelta(minutes=1)).isoformat(),"expires_at":(NOW+timedelta(hours=1)).isoformat(),"evidence_payload":payload,"evidence_payload_sha256":dg,"history_set_sha256":history_set_digest(history)}

def manifest(action,rid):
    raw={"_embedded":{"opportunityAttachmentList":[{"attachments":[{"resourceId":rid,"name":f"{rid}.pdf","size":10,"mimeType":"application/pdf","accessStatus":"public","exportControlled":"0","deletedFlag":"0","fileExists":"1","type":"file"}]}]}}
    r=normalize_manifest_payload(action,raw,observed_at=NOW.isoformat()); r["payload_hash_verified"]=True; return r

def case():
    h=["a1","a2"]
    history_payload={"actions":h,"surface":"SAM history"}
    hr=make_history_receipt(h,source_url="https://sam.gov/opp/example/view",observed_at=NOW.isoformat(),source_surface="SAM_HISTORY",payload=history_payload)
    scan,ref=reviewed_reference()
    ref.update({"resolution":"RESOLVED_TO_RESOURCE","source_object_state":"VERIFIED_SOURCE_OBJECT","resource_id":"r2","byte_state":"BYTES_VERIFIED_HASHED","byte_sha256":"b"*64})
    return {
        "case_schema_version":"0.2","case_id":"CB-2","family_id":"DEMO","current_posture":"GO",
        "packet":{
            "family_status":"ACTIVE","history_action_ids":h,"history_receipts":[hr],
            "manifest_receipts":[manifest("a1","r1"),manifest("a2","r2")],
            "reference_scan":scan,
            "references":[ref],
            "artifacts":[{"artifact_id":"r2","name":"r2.pdf","state":"PUBLIC","required_for_analysis":True,"sha256":"b"*64,"source_object_state":"VERIFIED_SOURCE_OBJECT","byte_state":"BYTES_VERIFIED_HASHED"}],
            "external_dependencies":[]
        },
        "current_action_receipts":[authority_receipt(h,"a2")],
        "sources":[{"source_id":"sam","url":"https://sam.gov/opp/example/view","authority":"CONTROLLING_CURRENT","artifact_state":"PUBLIC","observed_at":NOW.isoformat(),"content_sha256":"c"*64}],
        "assumptions":[{"assumption_id":"A1","text":"Current solicitation controls","evidence_state":"SUPPORTED","decision_class":"MONITOR_ONLY","finding":"Verified","source_ids":["sam"],"reopen_triggers":["CURRENT_ACTION_CHANGE","MANIFEST:a2","RESOURCE:r2",f"REFERENCE:{ref['reference_id']}"]}]
    }

class HistoryAuditTests(unittest.TestCase):
    def test_v02_ready_case(self):
        r=audit_case(case(),now=NOW); self.assertEqual(r.release_state,"READY_FOR_HUMAN_RELEASE",[x.code for x in r.findings])

    def test_boolean_manifest_complete_cannot_fake_coverage(self):
        c=case(); c["packet"]["manifest_receipts"]=c["packet"]["manifest_receipts"][:1]; c["packet"]["manifest_complete"]=True
        codes={x.code for x in audit_case(c,now=NOW).findings}; self.assertIn("MANIFEST_ACTION_UNOBSERVED",codes); self.assertIn("MANIFEST_BOOLEAN_CANNOT_OVERRIDE_RECEIPTS",codes)

    def test_history_is_receipt_driven(self):
        c=case(); c["packet"]["history_receipts"]=[]; c["packet"]["history_complete"]=True
        codes={x.code for x in audit_case(c,now=NOW).findings}; self.assertIn("HISTORY_UNRESOLVED",codes)

    def test_history_receipt_set_mismatch_blocks(self):
        c=case(); c["packet"]["history_action_ids"]=["a1","a2","a3"]
        codes={x.code for x in audit_case(c,now=NOW).findings}; self.assertIn("HISTORY_RECEIPT_SET_MISMATCH",codes)

    def test_historical_source_object_without_bytes_blocks(self):
        c=case(); c["packet"]["artifacts"].append({"artifact_id":"old-amendment","state":"UNAVAILABLE","required_for_analysis":True,"source_object_state":"INFERRED_SOURCE_OBJECT","byte_state":"BYTES_UNAVAILABLE_AT_OBSERVATION"})
        self.assertIn("HISTORICAL_BYTES_UNAVAILABLE",{x.code for x in audit_case(c,now=NOW).findings})

    def test_reference_scan_must_be_complete(self):
        c=case(); c["packet"]["reference_scan"]["status"]="PARTIAL"
        self.assertIn("REFERENCE_SCAN_UNRESOLVED",{x.code for x in audit_case(c,now=NOW).findings})

    def test_watch_reopens_resource_specific_assumption(self):
        b=case(); a=copy.deepcopy(b)
        old=a["packet"]["manifest_receipts"][1]
        raw={"_embedded":{"opportunityAttachmentList":[{"attachments":[{"resourceId":"r2","name":"r2.pdf","size":20,"mimeType":"application/pdf","accessStatus":"public","exportControlled":"0","deletedFlag":"0","fileExists":"1","type":"file"}]}]}}
        new=normalize_manifest_payload("a2",raw,observed_at=(NOW+timedelta(minutes=5)).isoformat()); new["payload_hash_verified"]=True
        a["packet"]["manifest_receipts"][1]=new
        d=compare_cases(b,a); keys={x["key"] for x in d["events"]}; self.assertIn("RESOURCE:r2",keys); self.assertEqual({x["assumption_id"] for x in d["reopened_assumptions"]},{"A1"})

    def test_old_schema_fails_closed(self):
        c=case(); c.pop("case_schema_version")
        self.assertIn("CASE_SCHEMA_VERSION_UNSUPPORTED",{x.code for x in audit_case(c,now=NOW).findings})

if __name__=="__main__": unittest.main()
