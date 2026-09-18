import unittest

from opportunity_record import SourceRef, DeadlineFact, OpportunityRecord, compare_records, validate_record

SRC = SourceRef('sam.gov','https://sam.gov/opp/example','2026-09-18T22:00:00Z','a'*64)

def record(**overrides):
    values = dict(
        provider='native', notice_id='NOTICE-1', solicitation_number='SOL-1', set_aside='Small Business',
        response_deadline=DeadlineFact('Responses due September 30, 2026 at 2:00 PM ET','2026-09-30T14:00:00-04:00','ET',SRC),
        amendment_ids=('A0001',), source_manifest=(SRC,),
        field_sources={'identity':SRC,'response_deadline':SRC,'set_aside':SRC,'amendments':SRC},
    )
    values.update(overrides)
    return OpportunityRecord(**values)

class OpportunityRecordTests(unittest.TestCase):
    def test_valid_record(self):
        result=validate_record(record())
        self.assertTrue(result.valid)
        self.assertEqual(result.review_reasons,())

    def test_unknown_deadline_must_be_explicit(self):
        bad=validate_record(record(response_deadline=None, field_sources={'identity':SRC,'set_aside':SRC,'amendments':SRC}))
        self.assertIn('critical_unknown_not_declared:response_deadline',bad.blockers)
        good=validate_record(record(response_deadline=None, explicit_unknowns=frozenset({'response_deadline'}), field_sources={'identity':SRC,'set_aside':SRC,'amendments':SRC}))
        self.assertNotIn('critical_unknown_not_declared:response_deadline',good.blockers)
        self.assertIn('response_deadline_unknown',good.review_reasons)

    def test_timezone_gap_is_review_not_invented(self):
        deadline=DeadlineFact('Responses due September 30, 2026 at 2:00 PM','2026-09-30T14:00:00',None,SRC)
        result=validate_record(record(response_deadline=deadline))
        self.assertTrue(result.valid)
        self.assertIn('response_deadline_timezone_unresolved',result.review_reasons)

    def test_critical_provenance_is_required(self):
        result=validate_record(record(field_sources={'identity':SRC}))
        self.assertIn('critical_field_missing_provenance:response_deadline',result.blockers)
        self.assertIn('critical_field_missing_provenance:set_aside',result.blockers)
        self.assertIn('critical_field_missing_provenance:amendments',result.blockers)

    def test_unsafe_source_query_is_rejected(self):
        secret=SourceRef('sam.gov','https://sam.gov/opp/example?api_key=secret','2026-09-18T22:00:00Z')
        result=validate_record(record(source_manifest=(secret,)))
        self.assertIn('source_manifest:0:unsafe_source_url',result.blockers)

    def test_conflicting_deadlines_surface(self):
        other=record(provider='candidate',response_deadline=DeadlineFact('Due Oct 1','2026-10-01T14:00:00-04:00','ET',SRC))
        conflicts=compare_records([record(),other])
        self.assertIn('response_deadline',{c.field for c in conflicts})

    def test_identity_and_set_aside_conflicts_surface(self):
        other=record(provider='candidate',notice_id='NOTICE-OTHER',solicitation_number=None,set_aside='Unrestricted')
        conflicts=compare_records([record(),other])
        self.assertEqual({'identity','set_aside'},{c.field for c in conflicts})

if __name__=='__main__':
    unittest.main()
