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

    def test_redirect_diagnostic_discloses_only_safe_source_path_digest_and_known_query_names(self):
        from urllib.request import Request
        from urllib.parse import urlsplit
        import hashlib
        target = ("https://iae-fbo-attachments.s3.amazonaws.com/example-public-source.pdf?"
                  "X-Amz-Signature=SECRET_DO_NOT_ECHO"
                  "&response-content-disposition=attachment%3Bfilename%3DSECRET_DO_NOT_ECHO")
        with self.assertRaises(case.OfficialPdfRedirectBlocked) as caught:
            case.SameHost().redirect_request(
                Request(case.PUBLIC_FILE), None, 303, "See Other", {}, target)
        safe = caught.exception.safe_projection()
        assert safe["redirect_path_sha256_only"] == hashlib.sha256(
            urlsplit(target).path.encode()).hexdigest()
        assert safe["redirect_host"] == "iae-fbo-attachments.s3.amazonaws.com"
        assert "response-content-disposition" in safe["redirect_query_parameter_names_only"]
        assert "X-Amz-Signature" in safe["redirect_query_parameter_names_only"]
        assert "SECRET_DO_NOT_ECHO" not in json.dumps(safe)

    def test_pinned_sam_s3_presigned_transport_enforces_exact_source_and_expiry(self):
        from datetime import datetime, timezone, timedelta
        from urllib.parse import urlencode
        import hashlib
        now = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)
        path = "/official/attachments/" + case.RESOURCE + "/public.pdf"
        official = "https://sam.gov/api/prod/opps/v3/opportunities/resources/files/" + case.RESOURCE + "/download"
        assert case.PUBLIC_FILE == official
        stamp = now.strftime("%Y%m%dT%H%M%SZ")
        scope = now.strftime("%Y%m%d") + "/us-east-1/s3/aws4_request"
        fields = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": "AKIAY3LPYEEX5FRGIQ4E/" + scope,
            "X-Amz-Date": stamp, "X-Amz-Expires": "3600",
            "X-Amz-SignedHeaders": "host", "X-Amz-Signature": "b"*64,
            "response-content-disposition": "attachment",
        }
        target = "https://iae-fbo-attachments.s3.amazonaws.com" + path + "?" + urlencode(fields)
        expected_path = hashlib.sha256(path.encode()).hexdigest()
        assert case._approved_s3_signed_redirect(
            official, target, now=now, expected_path_sha256=expected_path)
        for changed in (
            target.replace("iae-fbo-attachments.s3.amazonaws.com", "evil.example"),
            target.replace("3600", "999999"),
            target.replace("AKIAY3LPYEEX5FRGIQ4E", "NOT_A_REAL_ACCESS_ID"),
            target.replace(case.RESOURCE, "f"*32),
            target + "&X-Amz-Signature=" + "c"*64,
            target.replace("us-east-1", "US_EAST_NA"),
        ):
            with self.subTest(changed=changed[:150]):
                assert not case._approved_s3_signed_redirect(
                    official, changed, now=now, expected_path_sha256=expected_path)
        assert not case._approved_s3_signed_redirect(
            official, target, now=now+timedelta(hours=2),
            expected_path_sha256=expected_path)
        assert not case._approved_s3_signed_redirect(
            official.replace("sam.gov","sam.gov.evil.example"), target,
            now=now, expected_path_sha256=expected_path)

    def test_official_resource_only_matches_authenticated_current_action(self):
        from copy import deepcopy
        original = {
            "source_url": "https://api.sam.gov/prod/opportunities/v2/search",
            "source_contract": "SAM_GET_OPPORTUNITIES_V2",
            "automation_mode": "APPROVED_API",
            "observed_at": "2026-10-28T17:30:00+00:00",
            "payload_sha256": "a"*64, "response_sha256": "b"*64,
            "pagination": {"complete": True,"total_records":1,
                           "returned_records":1,"limit":100,"offset":0},
            "record": {"noticeId":case.NOTICE, "solicitationNumber":case.SOL,
                       "active":"Yes", "postedDate":"2026-10-26"},
            "resource_links":[case.PUBLIC_FILE]
        }
        assert case._require_exact_original_resource(original) == case.PUBLIC_FILE
        for other in (
            {**original, "resource_links":[case.PUBLIC_FILE+"?fn=untrusted.pdf"]},
            {**original, "record":{**original["record"], "noticeId":"f"*32}},
            {**original, "resource_links":[]},
            {**original, "resource_links":[case.PUBLIC_FILE,case.PUBLIC_FILE]},
        ):
            with self.assertRaises((ValueError,RuntimeError)):
                case._require_exact_original_resource(other)

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
