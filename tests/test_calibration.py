from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from capturebrief_core.calibration import summarize_calibration_review, validate_calibration_review


def fixture():
    return json.loads(Path("fixtures/calibration_review_example.json").read_text())


class CalibrationTests(unittest.TestCase):
    def test_valid_open_review_stays_internal_and_open(self):
        review=fixture()
        self.assertEqual(validate_calibration_review(review),[])
        summary=summarize_calibration_review(review)
        self.assertTrue(summary["valid"])
        self.assertEqual(summary["calibration_state"],"OPEN_CRITICAL_OR_MATERIAL")
        self.assertFalse(summary["methodology_calibration_complete"])
        self.assertFalse(summary["public_attribution_allowed"])
        self.assertEqual(summary["open_critical_or_material_count"],1)
        self.assertFalse(summary["automatic_product_or_public_claim_change"])

    def test_implemented_accepted_changes_close_review(self):
        review=fixture()
        for finding in review["findings"]:
            finding["disposition"]="ACCEPT"
            finding["disposition_rationale"]="Accepted after internal review."
            finding["implementation_status"]="IMPLEMENTED"
            finding["change_ref"]="github:commit:abc123"
            finding["test_ref"]="test:calibration:"+finding["finding_id"]
        summary=summarize_calibration_review(review)
        self.assertEqual(summary["calibration_state"],"CLOSED")
        self.assertTrue(summary["methodology_calibration_complete"])
        self.assertEqual(summary["implemented_change_count"],2)

    def test_accept_without_testable_implementation_does_not_close(self):
        review=fixture()
        finding=review["findings"][0]
        finding["disposition"]="ACCEPT"
        finding["disposition_rationale"]="Accepted."
        summary=summarize_calibration_review(review)
        self.assertEqual(summary["calibration_state"],"OPEN_CRITICAL_OR_MATERIAL")
        self.assertEqual(summary["open_finding_count"],2)

    def test_public_attribution_requires_separate_evidence(self):
        review=fixture()
        review["public_attribution_approved"]=True
        self.assertIn("public_attribution_evidence_ref",validate_calibration_review(review))
        review["public_attribution_evidence_ref"]="approval:public-attribution:001"
        self.assertEqual(validate_calibration_review(review),[])
        self.assertTrue(summarize_calibration_review(review)["public_attribution_allowed"])

    def test_reject_requires_reason_and_no_change(self):
        review=fixture()
        finding=review["findings"][0]
        finding["disposition"]="REJECT"
        finding["implementation_status"]="NO_CHANGE"
        self.assertTrue(any("disposition_rationale" in x for x in validate_calibration_review(review)))
        finding["disposition_rationale"]="Not supported after reproducing the sample."
        self.assertEqual(validate_calibration_review(review),[])

    def test_duplicate_finding_id_fails(self):
        review=fixture()
        review["findings"][1]["finding_id"]=review["findings"][0]["finding_id"]
        self.assertTrue(any("finding_id" in x for x in validate_calibration_review(review)))


if __name__=="__main__":
    unittest.main()
