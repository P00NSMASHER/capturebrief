"""Independent bounded replay from a prior authenticated, fictional/public SAM case."""
import copy
import unittest

from scripts.replay_verified_public_case_pdf import _verify_prior_proof, PINNED_INPUT_BACKUP_SHA256

class ReplayProofContracts(unittest.TestCase):
    def sample(self):
        return {
          "status": "PUBLIC_PILOT_CASE_SOURCE_AND_BACKUP_REHEARSAL",
          "solicitation_number": "2031JW27Q00011",
          "source": "SCOPED_SAM_SOURCE_OBSERVED_REVIEW_REQUIRED",
          "selected_notice_matches_latest_api": True,
          "backup_is_test_key_only": True,
          "backup_sha256": PINNED_INPUT_BACKUP_SHA256,
          "client_identity_verified": False,
          "customer_release_authorized": False,
          "payment_authorized": False,
          "external_send_authorized": False,
          "source_history_complete_and_independently_reviewed": False,
          "independently_retained_production_recovery_key": False,
          "official_document": {"status": "BLOCKED_OFFICIAL_PDF_REDIRECT_TRANSPORT_REVIEW_REQUIRED"},
          "official_history": {"status": "HISTORY_ENDPOINT_UNAVAILABLE_OR_UNAUTHORIZED"}
        }

    def test_accepts_only_exact_prior_authenticated_public_rehearsal(self):
        self.assertTrue(_verify_prior_proof(self.sample()))
        for key,value in (
          ("backup_sha256", "0"*64),("solicitation_number","OTHER"),
          ("client_identity_verified",True),("customer_release_authorized",True),
          ("payment_authorized",True),("source_history_complete_and_independently_reviewed",True),
          ("independently_retained_production_recovery_key",True),
          ("selected_notice_matches_latest_api",False),
          ("backup_is_test_key_only",False)
        ):
            bad=copy.deepcopy(self.sample())
            bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                _verify_prior_proof(bad)
        bad=copy.deepcopy(self.sample())
        bad["extra_secret"]="not allowed"
        with self.assertRaises(ValueError):
            _verify_prior_proof(bad)

if __name__=="__main__":
    unittest.main()
