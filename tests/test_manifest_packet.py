import copy, hashlib, json, unittest
from datetime import datetime, timezone

from capturebrief_core.manifest import ManifestShapeError, normalize_manifest_payload, validate_manifest_receipts, MANIFEST_PARSER_VERSION
from capturebrief_core.packet import diff_manifest_receipts, validate_reference_closure

NOW="2026-09-21T13:00:00+00:00"

def refscan():
    data={"source_ids":["sam"],"references_extracted":[]}
    raw=json.dumps(data,sort_keys=True,separators=(",",":")).encode()
    return {"status":"COMPLETE","scan_sha256":hashlib.sha256(raw).hexdigest(),"parser_version":"refs-v1","payload":data}

def payload(items):
    if items is None:
        return {"_links":{"self":{"href":"x"}}}
    return {"_embedded":{"opportunityAttachmentList":[{"attachments":items}]}}

def item(rid,name="sol.pdf",**kw):
    x={"resourceId":rid,"name":name,"mimeType":"application/pdf","size":100,"accessStatus":"public","exportControlled":"0","deletedFlag":"0","fileExists":"1","type":"file"}
    x.update(kw); return x

class ManifestPacketTests(unittest.TestCase):
    def test_empty_manifest_is_successful_observation(self):
        r=normalize_manifest_payload("a1",payload(None),observed_at=NOW)
        self.assertEqual(r["status"],"CHECKED_EMPTY"); self.assertEqual(r["items"],[])

    def test_strict_resource_id_required(self):
        with self.assertRaises(ManifestShapeError): normalize_manifest_payload("a1",payload([{"name":"x"}]),observed_at=NOW)

    def test_access_and_deletion_states(self):
        raw=[
            item("public"),
            item("deleted",deletedFlag="1"),
            item("restricted",accessStatus="restricted"),
            item("export",exportControlled="1"),
            item("gone",fileExists="0"),
            {"resourceId":"link","type":"link","description":"PIEE","uri":"https://piee.eb.mil/example","accessStatus":"public","exportControlled":"0","deletedFlag":"0","size":0},
        ]
        r=normalize_manifest_payload("a1",payload(raw),observed_at=NOW)
        states={x["resource_id"]:x["artifact_state"] for x in r["items"]}
        self.assertEqual(states,{"public":"PUBLIC","deleted":"DELETED","restricted":"RESTRICTED","export":"EXPORT_CONTROLLED","gone":"UNAVAILABLE","link":"EXTERNAL"})

    def test_manifest_completeness_is_per_action(self):
        r1=normalize_manifest_payload("a1",payload([item("r1")]),observed_at=NOW); r1["payload_hash_verified"]=True
        verdict,summary,findings=validate_manifest_receipts(["a1","a2"],[r1])
        self.assertEqual(verdict,"MANIFEST_UNRESOLVED"); self.assertEqual(summary["missing_actions"],["a2"]); self.assertIn("MANIFEST_ACTION_UNOBSERVED",{f.code for f in findings})

    def test_conflicting_receipts_fail_closed(self):
        r1=normalize_manifest_payload("a1",payload([item("r1")]),observed_at=NOW); r1["payload_hash_verified"]=True
        r2=normalize_manifest_payload("a1",payload([item("r2")]),observed_at=NOW); r2["payload_hash_verified"]=True
        verdict,_,findings=validate_manifest_receipts(["a1"],[r1,r2])
        self.assertEqual(verdict,"MANIFEST_UNRESOLVED"); self.assertIn("MANIFEST_SOURCE_DISAGREEMENT",{f.code for f in findings})

    def test_same_filename_new_resource_is_replacement_not_overwrite(self):
        b=normalize_manifest_payload("a1",payload([item("old","Product Description.pdf",size=140000)]),observed_at=NOW)
        a=normalize_manifest_payload("a1",payload([item("new","Product Description.pdf",size=272000)]),observed_at=NOW)
        types={x["type"] for x in diff_manifest_receipts(b,a)}
        self.assertIn("REPLACED_SAME_FILENAME",types); self.assertIn("DISAPPEARED_AFTER_COMPLETE_OBSERVATION",types); self.assertIn("ADDED",types)

    def test_explicit_delete_is_distinct(self):
        b=normalize_manifest_payload("a1",payload([item("r1")]),observed_at=NOW)
        a=normalize_manifest_payload("a1",payload([item("r1",deletedFlag="1")]),observed_at=NOW)
        self.assertIn("EXPLICITLY_DELETED",{x["type"] for x in diff_manifest_receipts(b,a)})

    def test_reference_missing_from_complete_manifest_blocks(self):
        r=normalize_manifest_payload("a1",payload([item("r1","Amend 0004.docx")]),observed_at=NOW); r["payload_hash_verified"]=True
        packet={"manifest_receipts":[r],"reference_scan":refscan(),"references":[{"reference_id":"ref-1","label":"Amend 0001","resolution":"UNRESOLVED","source_object_state":"UNRESOLVED_SOURCE_OBJECT","byte_state":"BYTES_NOT_YET_CHECKED"}]}
        verdict,findings=validate_reference_closure(packet)
        self.assertEqual(verdict,"REFERENCE_CLOSURE_UNRESOLVED"); self.assertIn("REFERENCED_ARTIFACT_UNRESOLVED",{f.code for f in findings})

    def test_verified_reference_needs_bytes(self):
        r=normalize_manifest_payload("a1",payload([item("r1")]),observed_at=NOW); r["payload_hash_verified"]=True
        packet={"manifest_receipts":[r],"reference_scan":refscan(),"references":[{"reference_id":"ref-1","resolution":"RESOLVED_TO_RESOURCE","source_object_state":"VERIFIED_SOURCE_OBJECT","resource_id":"r1","byte_state":"BYTES_UNAVAILABLE_AT_OBSERVATION"}]}
        _,findings=validate_reference_closure(packet)
        self.assertIn("REFERENCE_BYTES_NOT_VERIFIED",{f.code for f in findings})

    def test_source_backed_supersession_closes_reference(self):
        r=normalize_manifest_payload("a1",payload([item("r4","Amend 0004.docx")]),observed_at=NOW); r["payload_hash_verified"]=True
        packet={"manifest_receipts":[r],"reference_scan":refscan(),"references":[{"reference_id":"ref-1","resolution":"SUPERSEDED_BY","source_object_state":"UNRESOLVED_SOURCE_OBJECT","byte_state":"BYTES_UNAVAILABLE_AT_OBSERVATION","successor_resource_id":"r4","supersession_source_id":"notice-current"}]}
        verdict,findings=validate_reference_closure(packet)
        self.assertEqual(verdict,"REFERENCE_CLOSURE_COMPLETE"); self.assertFalse(findings)

    def test_external_dependency_is_preserved_not_download_claimed(self):
        r=normalize_manifest_payload("a1",payload([{"resourceId":"link","type":"link","description":"PIEE","uri":"https://piee.eb.mil/x","accessStatus":"public","exportControlled":"0","deletedFlag":"0","size":0}]),observed_at=NOW); r["payload_hash_verified"]=True
        packet={"manifest_receipts":[r],"reference_scan":refscan(),"references":[{"reference_id":"ref-x","resolution":"EXTERNAL_DEPENDENCY","source_object_state":"VERIFIED_SOURCE_OBJECT","byte_state":"BYTES_EXTERNAL_DEPENDENCY","url":"https://piee.eb.mil/x","reason":"Controlling package is off-SAM"}]}
        verdict,findings=validate_reference_closure(packet)
        self.assertEqual(verdict,"REFERENCE_CLOSURE_COMPLETE"); self.assertFalse(findings)

if __name__=="__main__": unittest.main()
