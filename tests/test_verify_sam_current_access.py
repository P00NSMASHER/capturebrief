import json
import unittest
from datetime import datetime, timedelta, timezone
from urllib.request import Request

from capturebrief_core.current_api import (
    CurrentApiCardinalityError, CurrentApiIncompletePageError, SEARCH_URL,
)
from scripts.verify_sam_current_access import ApprovedApiRedirects, SOLICITATION, run_probe


NOW = datetime(2026, 10, 27, 14, 30, tzinfo=timezone.utc)
SECRET = "TEST_SECRET_MUST_NEVER_APPEAR"


def observation():
    return {
        "source_url": SEARCH_URL, "source_contract": "SAM_GET_OPPORTUNITIES_V2",
        "automation_mode": "APPROVED_API", "observed_at": NOW.isoformat(),
        "payload_sha256": "a" * 64, "response_sha256": "b" * 64,
        "record": {"noticeId": "SYNTHETIC-NOTICE", "solicitationNumber": SOLICITATION,
                   "active": "Yes", "private_contact": SECRET},
        "resource_links": [],
        "pagination": {"complete": True, "total_records": 1,
                       "returned_records": 1, "limit": 100, "offset": 0},
        "untrusted_extra": SECRET,
    }


class SamCurrentAccessTests(unittest.TestCase):
    def probe(self, data):
        return run_probe(SECRET, fetcher=lambda **kw: data, now=lambda: NOW)

    def test_missing_runtime_key_makes_no_request(self):
        def forbidden(**kw):
            self.fail("Missing credentials must not initiate a request")
        result, code = run_probe("", fetcher=forbidden, now=lambda: NOW)
        self.assertEqual(code, 3)
        self.assertEqual(result["status"], "BLOCKED_SAM_API_KEY_UNAVAILABLE")

    def test_safe_projection_does_not_promote_customer_or_catalog_authority(self):
        calls = []
        def fetcher(**kw):
            calls.append(kw)
            return observation()
        result, code = run_probe(SECRET, fetcher=fetcher, now=lambda: NOW)
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["api_key"], SECRET)
        self.assertEqual(calls[0]["timeout"], 30.0)
        self.assertEqual(calls[0]["max_response_bytes"], 2 * 1024 * 1024)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn("record", result)
        self.assertTrue(result["api_access_verified"])
        self.assertTrue(result["latest_active_observation_verified"])
        for field in ("source_catalog_approved", "full_history_verified", "customer_review_verified",
                      "customer_delivery_verified", "external_send_authorized", "raw_record_published"):
            self.assertIs(result[field], False)

    def test_errors_do_not_publish_secret_or_credential_url(self):
        def fails(**kw):
            raise RuntimeError("https://api.sam.gov/?api_key=" + SECRET)
        result, code = run_probe(SECRET, fetcher=fails, now=lambda: NOW)
        self.assertEqual(code, 3)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertEqual(result["status"], "BLOCKED_API_OBSERVATION_FAILED")

    def test_distinguishes_empty_family_and_incomplete_response(self):
        for error, status in [(CurrentApiCardinalityError(0), "BLOCKED_API_FAMILY_CARDINALITY"),
                              (CurrentApiIncompletePageError(2, 1), "BLOCKED_API_INCOMPLETE_RESPONSE")]:
            with self.subTest(status=status):
                def fails(**kw):
                    raise error
                result, code = run_probe(SECRET, fetcher=fails, now=lambda: NOW)
                self.assertEqual((code, result["status"]), (3, status))
                self.assertFalse(result["latest_active_observation_verified"])

    def test_inactive_stale_future_and_mismatched_records_do_not_pass(self):
        for field, value in [("active", "No"), ("solicitationNumber", "WRONG")]:
            data = observation()
            data["record"][field] = value
            result, code = self.probe(data)
            self.assertEqual(code, 3)
            self.assertFalse(result["latest_active_observation_verified"])
        for delta in (-301, 1):
            data = observation()
            data["observed_at"] = (NOW + timedelta(seconds=delta)).isoformat()
            result, code = self.probe(data)
            self.assertEqual(code, 3)
            self.assertFalse(result["latest_active_observation_verified"])

    def test_rejects_unapproved_redirect_before_following(self):
        handler = ApprovedApiRedirects()
        req = Request(SEARCH_URL + "?api_key=" + SECRET)
        for target in ("https://other.example/search?api_key=" + SECRET,
                       "http://api.sam.gov/opportunities/v2/search",
                       "https://api.sam.gov/unapproved"):
            with self.subTest(target=target):
                with self.assertRaisesRegex(Exception, "rejected before connection"):
                    handler.redirect_request(req, None, 302, "Found", {}, target)
        approved = "https://api.sam.gov/opportunities/v2/search?api_key=" + SECRET
        self.assertEqual(handler.redirect_request(req, None, 302, "Found", {}, approved).full_url, approved)


if __name__ == "__main__":
    unittest.main()
