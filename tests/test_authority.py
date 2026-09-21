import hashlib,json,unittest
from datetime import datetime,timedelta,timezone
from capturebrief_core.authority import validate_current_action_receipts
from capturebrief_core.model import history_set_digest
NOW=datetime(2026,9,21,12,0,tzinfo=timezone.utc)
def receipt(history,action,status="ACTIVE",semantics="CURRENT_ACTIVE"):
    payload={"status":status,"action":action,"history":list(history)}
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {"asserted_action_id":action,"semantics":semantics,"observed_family_status":status,"source_url":"https://sam.gov/opportunities/example","observed_at":(NOW-timedelta(minutes=5)).isoformat(),"expires_at":(NOW+timedelta(hours=4)).isoformat(),"evidence_payload":payload,"evidence_payload_sha256":digest,"history_set_sha256":history_set_digest(history)}
class AuthorityTests(unittest.TestCase):
    def test_real_nonlexical_current_action(self):
        h=["838bdb200ad14374a300c9debd2a86cf","a9d281564bc540ab8ef09af4c64c2a53","cf21df787f6d480897b037d1af47aa7d","0f367577ad68477b947384888441974e"]
        v,a,_=validate_current_action_receipts(h,"ACTIVE",[receipt(h,h[-1])],now=NOW); self.assertEqual((v,a),("CURRENT_VERIFIED",h[-1]))
    def test_permutation_and_opaque_id_invariant(self):
        for h,a in [(["c","a","b"],"b"),(["x-3","x-1","x-2"],"x-2")]:
            v,got,_=validate_current_action_receipts(h,"ACTIVE",[receipt(h,a)],now=NOW); self.assertEqual((v,got),("CURRENT_VERIFIED",a))
    def test_stale_and_out_of_set_fail_closed(self):
        h=["a","b"]; r=receipt(h,"b"); r["expires_at"]=(NOW-timedelta(seconds=1)).isoformat()
        self.assertEqual(validate_current_action_receipts(h,"ACTIVE",[r],now=NOW)[0],"CURRENT_UNKNOWN")
        self.assertEqual(validate_current_action_receipts(h,"ACTIVE",[receipt(h,"c")],now=NOW)[0],"CURRENT_UNKNOWN")
    def test_conflict_fails_closed(self):
        h=["a","b"]; self.assertEqual(validate_current_action_receipts(h,"ACTIVE",[receipt(h,"a"),receipt(h,"b")],now=NOW)[0],"CURRENT_ACTION_SOURCE_DISAGREEMENT")
    def test_terminal_semantics(self):
        h=["a","end"]
        self.assertEqual(validate_current_action_receipts(h,"CANCELLED",[receipt(h,"end","CANCELLED","TERMINAL_CANCELLED")],now=NOW)[0],"TERMINAL_CANCELLED_VERIFIED")
        self.assertEqual(validate_current_action_receipts(h,"ARCHIVED",[receipt(h,"end","ARCHIVED","TERMINAL_ARCHIVED")],now=NOW)[0],"TERMINAL_ARCHIVED_VERIFIED")
        self.assertEqual(validate_current_action_receipts(h,"CANCELLED",[receipt(h,"end","CANCELLED","CURRENT_ACTIVE")],now=NOW)[0],"CURRENT_UNKNOWN")
    def test_inactive_never_guesses(self):
        h=["a","b"]; self.assertEqual(validate_current_action_receipts(h,"INACTIVE",[receipt(h,"b","INACTIVE")],now=NOW)[0],"CURRENT_UNKNOWN")
    def test_payload_hash_must_verify(self):
        h=["a","b"]; r=receipt(h,"b"); r["evidence_payload_sha256"]="0"*64
        self.assertEqual(validate_current_action_receipts(h,"ACTIVE",[r],now=NOW)[0],"CURRENT_UNKNOWN")
if __name__=="__main__": unittest.main()
