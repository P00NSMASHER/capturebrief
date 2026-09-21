import copy
import unittest
from datetime import datetime, timedelta, timezone

from capturebrief_core.authority import validate_current_action_receipts
from capturebrief_core.data_services import ACTIVE_DATA_SERVICES_PAGE, ACTIVE_DOWNLOAD, ARCHIVE_DOWNLOAD
from capturebrief_core.history import validate_history_receipts
from capturebrief_core.model import canonical_json, history_set_digest, sha256_hex
from capturebrief_core.current_api import SEARCH_URL

NOW=datetime(2026,9,21,15,0,tzinfo=timezone.utc)


def ds_receipt():
    actions=["a1","a2"]
    payload={
        "source_contract":"SAM_DATA_SERVICES_EXTRACT",
        "family":{"solicitation_number":"SOL-1","aac_code":"AAC1","office":"OFFICE","seed_notice_id":"a2"},
        "scope":{
            "start_fy":2026,
            "end_fy":2026,
            "scope_confirmed":True,
            "required_archive_fys":[2026],
            "supplied_archive_fys":[2026],
            "missing_archive_fys":[],
            "active_extract_present":True,
        },
        "actions":[
            {"notice_id":"a1","observations":[{"row_sha256":"a"*64}]},
            {"notice_id":"a2","observations":[{"row_sha256":"b"*64}]},
        ],
        "source_snapshots":[
            {"source_kind":"ACTIVE","fiscal_year":None,"source_url":ACTIVE_DOWNLOAD,"extract_sha256":"c"*64,"rows_scanned":100},
            {"source_kind":"ARCHIVE","fiscal_year":2026,"source_url":ARCHIVE_DOWNLOAD.format(fy=2026),"extract_sha256":"d"*64,"rows_scanned":200},
        ],
        "ordering_authoritative":False,
        "current_action_authoritative":False,
    }
    return {
        "source_surface":"SAM_DATA_SERVICES",
        "source_url":ACTIVE_DATA_SERVICES_PAGE,
        "observed_at":NOW.isoformat(),
        "status":"COMPLETE",
        "action_ids":actions,
        "history_set_sha256":history_set_digest(actions),
        "evidence_payload_sha256":sha256_hex(canonical_json(payload)),
        "evidence_payload":payload,
        "automation_mode":"APPROVED_EXTRACT",
    }


def rehash(receipt):
    receipt["evidence_payload_sha256"]=sha256_hex(canonical_json(receipt["evidence_payload"]))
    return receipt


def api_receipt():
    history=["a1","a2"]
    evidence={
        "source_contract":"SAM_GET_OPPORTUNITIES_V2",
        "notice_id":"a2",
        "solicitation_number":"SOL-1",
        "posted_date":"2026-09-20",
        "active":"Yes",
        "resource_links":["https://sam.gov/api/prod/opps/v3/opportunities/resources/files/r1/download"],
        "api_payload_sha256":"e"*64,
        "api_response_sha256":"f"*64,
        "pagination":{"total_records":1,"returned_records":1,"limit":100,"offset":0,"complete":True},
    }
    return {
        "asserted_action_id":"a2",
        "semantics":"CURRENT_ACTIVE",
        "observed_family_status":"ACTIVE",
        "source_url":SEARCH_URL,
        "observed_at":NOW.isoformat(),
        "expires_at":(NOW+timedelta(hours=4)).isoformat(),
        "evidence_payload":evidence,
        "evidence_payload_sha256":sha256_hex(canonical_json(evidence)),
        "history_set_sha256":history_set_digest(history),
        "automation_mode":"APPROVED_API",
    }


class ReceiptContractTests(unittest.TestCase):
    def test_valid_data_services_contract_passes(self):
        r=ds_receipt()
        verdict,findings=validate_history_receipts(["a2","a1"],[r])
        self.assertEqual(verdict,"HISTORY_COMPLETE",[f.code for f in findings])

    def test_rehashed_bulk_currentness_claim_is_rejected(self):
        r=copy.deepcopy(ds_receipt())
        r["evidence_payload"]["current_action_authoritative"]=True
        rehash(r)
        verdict,findings=validate_history_receipts(["a1","a2"],[r])
        self.assertEqual(verdict,"HISTORY_UNRESOLVED")
        self.assertIn("HISTORY_DATA_SERVICES_CURRENTNESS_MUST_NOT_BE_AUTHORITATIVE",{f.code for f in findings})

    def test_rehashed_archive_coverage_gap_is_rejected(self):
        r=copy.deepcopy(ds_receipt())
        scope=r["evidence_payload"]["scope"]
        scope["start_fy"]=2025
        scope["required_archive_fys"]=[2025,2026]
        scope["supplied_archive_fys"]=[2026]
        scope["missing_archive_fys"]=[]
        rehash(r)
        verdict,findings=validate_history_receipts(["a1","a2"],[r])
        self.assertEqual(verdict,"HISTORY_UNRESOLVED")
        codes={f.code for f in findings}
        self.assertTrue({"HISTORY_DATA_SERVICES_ARCHIVE_COVERAGE_INCOMPLETE","HISTORY_DATA_SERVICES_SNAPSHOT_ARCHIVES_INCOMPLETE"} & codes)

    def test_rehashed_unapproved_snapshot_url_is_rejected(self):
        r=copy.deepcopy(ds_receipt())
        r["evidence_payload"]["source_snapshots"][1]["source_url"]="https://sam.gov/api/prod/opps/v3/opportunities/a1/resources"
        rehash(r)
        verdict,findings=validate_history_receipts(["a1","a2"],[r])
        self.assertEqual(verdict,"HISTORY_UNRESOLVED")
        self.assertIn("HISTORY_DATA_SERVICES_SNAPSHOT_SOURCE_INVALID",{f.code for f in findings})

    def test_valid_approved_api_contract_passes(self):
        r=api_receipt()
        verdict,action,findings=validate_current_action_receipts(["a1","a2"],"ACTIVE",[r],now=NOW)
        self.assertEqual((verdict,action),("CURRENT_VERIFIED","a2"),[f.code for f in findings])

    def test_rehashed_wrong_api_contract_is_rejected(self):
        r=copy.deepcopy(api_receipt())
        r["evidence_payload"]["source_contract"]="FAKE"
        r["evidence_payload_sha256"]=sha256_hex(canonical_json(r["evidence_payload"]))
        verdict,action,findings=validate_current_action_receipts(["a1","a2"],"ACTIVE",[r],now=NOW)
        self.assertEqual((verdict,action),("CURRENT_UNKNOWN",None))
        self.assertIn("RECEIPT_APPROVED_API_CONTRACT_INVALID",{f.code for f in findings})

    def test_rehashed_missing_raw_response_proof_is_rejected(self):
        r=copy.deepcopy(api_receipt())
        r["evidence_payload"].pop("api_response_sha256")
        r["evidence_payload_sha256"]=sha256_hex(canonical_json(r["evidence_payload"]))
        verdict,action,findings=validate_current_action_receipts(["a1","a2"],"ACTIVE",[r],now=NOW)
        self.assertEqual((verdict,action),("CURRENT_UNKNOWN",None))
        self.assertIn("RECEIPT_APPROVED_API_RESPONSE_HASH_INVALID",{f.code for f in findings})

    def test_rehashed_incomplete_pagination_is_rejected(self):
        r=copy.deepcopy(api_receipt())
        r["evidence_payload"]["pagination"]["total_records"]=2
        r["evidence_payload_sha256"]=sha256_hex(canonical_json(r["evidence_payload"]))
        verdict,action,findings=validate_current_action_receipts(["a1","a2"],"ACTIVE",[r],now=NOW)
        self.assertEqual((verdict,action),("CURRENT_UNKNOWN",None))
        self.assertIn("RECEIPT_APPROVED_API_PAGINATION_INCOMPLETE",{f.code for f in findings})

    def test_rehashed_unapproved_resource_link_is_rejected(self):
        r=copy.deepcopy(api_receipt())
        r["evidence_payload"]["resource_links"]=["https://sam.gov/opp/a2/view"]
        r["evidence_payload_sha256"]=sha256_hex(canonical_json(r["evidence_payload"]))
        verdict,action,findings=validate_current_action_receipts(["a1","a2"],"ACTIVE",[r],now=NOW)
        self.assertEqual((verdict,action),("CURRENT_UNKNOWN",None))
        self.assertIn("RECEIPT_APPROVED_API_RESOURCE_LINK_INVALID",{f.code for f in findings})

    def test_human_supervised_receipt_remains_supported(self):
        r=api_receipt()
        r.pop("automation_mode")
        r["source_url"]="https://sam.gov/opp/a2/view"
        # Human-supervised receipts keep the generic first-party/evidence checks.
        verdict,action,_=validate_current_action_receipts(["a1","a2"],"ACTIVE",[r],now=NOW)
        self.assertEqual((verdict,action),("CURRENT_VERIFIED","a2"))


if __name__=="__main__":
    unittest.main()
