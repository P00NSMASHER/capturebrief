"""Guard independent real-case rehearsal from fake original and false release."""
from __future__ import annotations
import io
import json
import unittest
from urllib.error import HTTPError

from scripts import verify_federal_pilot_public_case as case

class Response:
    def __init__(self, payload: bytes, url=case.PUBLIC_FILE):
        self.payload=payload; self.url=url
        self.headers={"Content-Length":str(len(payload))}
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def geturl(self): return self.url
    def read(self,n): return self.payload[:n]

class PublicCaseProofTests(unittest.TestCase):
    def test_one_exact_public_notice_instead_of_unknown_url(self):
        self.assertEqual(case.SOL,"2031JW27Q00011")
        self.assertEqual(case.NOTICE,"0d961fc227d34d4da9a895f941e48a1e")
        self.assertTrue(case.PUBLIC_FILE.startswith("https://sam.gov/api/prod/opps/v3/"))
        self.assertIn(case.RESOURCE,case.PUBLIC_FILE)

    def test_only_genuine_bounded_official_pdf_is_eligible_for_retention(self):
        body=b"%PDF-1.4\n" + b"x"*700 + b"\n%%EOF\n"
        data, receipt=case.fetch_official_pdf(opener=lambda req,timeout: Response(body))
        self.assertEqual(data,body)
        self.assertEqual(receipt["source_host"],"sam.gov")
        self.assertFalse(receipt["publisher_human_reviewed"])
        for supplied in (b"<html>"+b"x"*700, b"%PDF-1.4\n"+b"x"*700):
            with self.assertRaises(RuntimeError):
                case.fetch_official_pdf(opener=lambda req,timeout: Response(supplied))
        with self.assertRaises(RuntimeError):
            case.fetch_official_pdf(opener=lambda req,timeout: Response(body,"https://evil.example/pdf"))

    def test_official_pdf_redirect_is_blocked_and_safely_described(self):
        from urllib.request import Request
        request = Request(case.PUBLIC_FILE)
        fake_signed_url = ("https://signed.example.invalid/private?X-Amz-Credential=HIDDEN_SECRET"
                           "&X-Amz-Signature=MORE_SECRET")
        with self.assertRaises(case.OfficialPdfRedirectBlocked) as caught:
            case.SameHost().redirect_request(request, None, 302, "Redirect", {}, fake_signed_url)
        err = caught.exception
        self.assertEqual(err.destination_host, "signed.example.invalid")
        self.assertEqual(err.response_code, 302)
        self.assertNotIn("HIDDEN_SECRET", str(err))
        self.assertNotIn("MORE_SECRET", str(err))
        self.assertNotIn("HIDDEN_SECRET", json.dumps(err.safe_projection()))

    def test_history_missing_unauthorized_and_wrong_family_never_approves(self):
        def payload(value):
            def open_(req,timeout):
                self.assertIn("api.sam.gov",req.full_url)
                return Response(json.dumps(value).encode(),url="https://api.sam.gov/prod/opportunity/v1/api/history/"+case.NOTICE)
            return open_
        for candidate in ({"history":[]},{"history":[{"opportunityId":"0"*32}]},
                          {"history":[{"opportunityId":case.NOTICE},{"opportunityId":case.NOTICE}]}):
            outcome=case.try_official_history("FAKE_KEY",opener=payload(candidate))
            self.assertFalse(outcome["complete_first_party_history_verified"])
        result=case.try_official_history("FAKE_KEY",opener=payload({"history":[{"opportunityId":case.NOTICE}]}))
        self.assertEqual(result["status"],"HISTORY_OBSERVED_REVIEW_REQUIRED")
        self.assertFalse(result["complete_first_party_history_verified"])

    def test_provider_failure_never_prints_credential_bearing_error(self):
        def bad(req,timeout):
            raise HTTPError(req.full_url,403,"Access denied",None,None)
        result=case.try_official_history("SUPER_PRIVATE_FAKE_KEY",opener=bad)
        self.assertEqual(result["status"],"HISTORY_ENDPOINT_UNAVAILABLE_OR_UNAUTHORIZED")
        self.assertNotIn("SUPER_PRIVATE_FAKE_KEY",json.dumps(result))
        self.assertFalse(result["complete_first_party_history_verified"])

    def test_test_key_is_not_an_operator_recovery_key(self):
        self.assertGreater(len(case.DEMO_KEY),20)
        self.assertIn(b"DEMO_PUBLIC",case.DEMO_KEY)
        self.assertFalse(hasattr(case, "CUSTOMER_DELIVERY_AUTHORIZED"))

if __name__=="__main__":
    unittest.main()
