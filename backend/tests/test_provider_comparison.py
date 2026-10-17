from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from opportunity_record import DeadlineFact,OpportunityRecord,SourceRef
from provider_comparison import compare_candidate
from providers.capture_mcp_sam import adapt_opportunity

WHEN="2026-09-18T23:00:00Z"
SRC=SourceRef("native","https://sam.gov/opp/abc-123/view",WHEN,"a"*64)

def native(**overrides):
    values=dict(
        provider="native",
        notice_id="abc-123",
        solicitation_number="FAKE-26-R-001",
        title="Cloud support",
        agency="Department of Example",
        office="Example Office",
        notice_type="Solicitation",
        naics=("541512",),
        psc=("DA10",),
        set_aside="Small Business Set-Aside",
        response_deadline=DeadlineFact("2026-10-01T17:00:00-04:00","2026-10-01T17:00:00-04:00","-04:00",SRC),
        amendment_ids=("A0001",),
        attachment_ids=("RFP.pdf",),
        field_sources={"identity":SRC,"response_deadline":SRC,"set_aside":SRC,"amendments":SRC},
        source_manifest=(SRC,),
    )
    values.update(overrides)
    return OpportunityRecord(**values)

def summary(**overrides):
    row={
        "id":"abc-123","title":"Cloud support","solicitationNumber":"FAKE-26-R-001",
        "department":"Department of Example","subTier":"Example Subtier","office":"Example Office",
        "postedDate":"2026-09-18","type":"Solicitation","baseType":"Solicitation",
        "setAside":"Small Business Set-Aside","responseDeadLine":"2026-10-01T17:00:00-04:00",
        "naicsCode":"541512","classificationCode":"DA10","active":"Yes",
        "links":{"self":"https://sam.gov/opp/abc-123/view"},
    }
    row.update(overrides)
    return adapt_opportunity(row,retrieved_at=WHEN)

class ProviderComparisonTests(unittest.TestCase):
    def test_matching_summary_is_compatible_but_discovery_only(self):
        result=compare_candidate(native(),summary())
        self.assertEqual(result.status,"compatible_discovery_only")
        self.assertEqual(result.conflicts,())
        self.assertIn("controlling_source_unknown:amendments",result.candidate_blockers)
        self.assertIn("controlling_source_unknown:attachments",result.candidate_blockers)

    def test_deadline_conflict_blocks_candidate(self):
        result=compare_candidate(native(),summary(responseDeadLine="2026-10-02T17:00:00-04:00"))
        self.assertEqual(result.status,"conflict")
        self.assertIn("response_deadline",result.conflicts)

    def test_set_aside_conflict_blocks_candidate(self):
        result=compare_candidate(native(),summary(setAside="Unrestricted"))
        self.assertEqual(result.status,"conflict")
        self.assertIn("set_aside",result.conflicts)

    def test_identity_conflict_blocks_candidate(self):
        result=compare_candidate(native(),summary(id="other-notice",solicitationNumber=None,links={"self":"https://sam.gov/opp/other-notice/view"}))
        self.assertEqual(result.status,"conflict")
        self.assertIn("identity",result.conflicts)

if __name__=="__main__":
    unittest.main()
