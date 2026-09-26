from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from opportunity_record import controlling_source_readiness, validate_record
from providers.capture_mcp_sam import adapt_opportunity

RETRIEVED="2026-09-18T23:00:00Z"

def row(**overrides):
    value={
        "id":"abc-123",
        "title":"Cloud support",
        "solicitationNumber":"FAKE-26-R-001",
        "department":"Department of Example",
        "subTier":"Example Subtier",
        "office":"Example Office",
        "postedDate":"2026-09-18",
        "type":"Solicitation",
        "baseType":"Combined Synopsis/Solicitation",
        "setAside":"Small Business Set-Aside",
        "responseDeadLine":"2026-10-01T17:00:00-04:00",
        "naicsCode":"541512",
        "classificationCode":"DA10",
        "active":"Yes",
        "links":{"self":"https://sam.gov/opp/abc-123/view"},
    }
    value.update(overrides)
    return value

class CaptureMcpSamAdapterTests(unittest.TestCase):
    def test_complete_summary_maps_only_supported_facts(self):
        record=adapt_opportunity(row(),retrieved_at=RETRIEVED)
        result=validate_record(record)
        self.assertTrue(result.valid)
        self.assertEqual(record.notice_id,"abc-123")
        self.assertEqual(record.solicitation_number,"FAKE-26-R-001")
        self.assertEqual(record.naics,("541512",))
        self.assertEqual(record.psc,("DA10",))
        self.assertEqual(record.response_deadline.normalized_value,"2026-10-01T17:00:00-04:00")
        self.assertIn("amendments",record.explicit_unknowns)
        self.assertIn("attachments",record.explicit_unknowns)
        self.assertEqual(record.provider_metadata,{"provider_role":"discovery_only","baseType":"Combined Synopsis/Solicitation","subTier":"Example Subtier","active":"Yes"})

    def test_summary_is_not_controlling_source_eligible(self):
        record=adapt_opportunity(row(),retrieved_at=RETRIEVED)
        readiness=controlling_source_readiness(record)
        self.assertFalse(readiness.eligible)
        self.assertIn("controlling_source_unknown:amendments",readiness.blockers)
        self.assertIn("controlling_source_unknown:attachments",readiness.blockers)

    def test_missing_set_aside_and_deadline_are_explicit_unknowns(self):
        record=adapt_opportunity(row(setAside=None,responseDeadLine=None),retrieved_at=RETRIEVED)
        result=validate_record(record)
        self.assertTrue(result.valid)
        self.assertIn("set_aside_unknown",result.review_reasons)
        self.assertIn("response_deadline_unknown",result.review_reasons)

    def test_deadline_without_timezone_stays_reviewable_not_normalized(self):
        record=adapt_opportunity(row(responseDeadLine="October 1, 2026 at 5:00 PM"),retrieved_at=RETRIEVED)
        self.assertIsNone(record.response_deadline.normalized_value)
        self.assertIsNone(record.response_deadline.timezone_wording)
        self.assertIn("response_deadline_timezone_unresolved",validate_record(record).review_reasons)

    def test_explicit_timezone_abbreviation_is_preserved_without_fake_conversion(self):
        record=adapt_opportunity(row(responseDeadLine="October 1, 2026 at 17:00 EDT"),retrieved_at=RETRIEVED)
        self.assertEqual(record.response_deadline.timezone_wording,"EDT")
        self.assertIsNone(record.response_deadline.normalized_value)

    def test_credentials_and_arbitrary_provider_fields_are_not_retained(self):
        record=adapt_opportunity(row(api_key="SECRET",rawPayload={"secret":"x"},totalRecords=999),retrieved_at=RETRIEVED)
        self.assertNotIn("api_key",record.provider_metadata)
        self.assertNotIn("rawPayload",record.provider_metadata)
        self.assertNotIn("totalRecords",record.provider_metadata)

    def test_source_query_credentials_fail_closed(self):
        with self.assertRaises(ValueError):
            adapt_opportunity(row(links={"self":"https://sam.gov/opp/abc/view?api_key=SECRET"}),retrieved_at=RETRIEVED)

    def test_non_sam_provenance_fails_closed(self):
        with self.assertRaises(ValueError):
            adapt_opportunity(row(links={"self":"https://example.com/opp/abc"}),retrieved_at=RETRIEVED)

    def test_missing_source_provenance_fails_closed(self):
        with self.assertRaises(ValueError):
            adapt_opportunity(row(links={}),retrieved_at=RETRIEVED)

if __name__=="__main__":
    unittest.main()
