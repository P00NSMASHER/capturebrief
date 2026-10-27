"""Even default tracebacks must not expose a SAM key from transport causes."""
import traceback
import unittest
from urllib.error import HTTPError, URLError

from capturebrief_core.current_api import CurrentApiError, fetch_latest_active, download_resource_from_api_observation
from tests.test_current_api_integrity import api_observation, LINK


class CurrentApiErrorPrivacyTests(unittest.TestCase):
    def test_http_error_keeps_status_without_keyed_url_or_cause(self):
        def denied(request, timeout):
            raise HTTPError(request.full_url, 403, "denied do-not-print-key", {}, None)
        with self.assertRaises(CurrentApiError) as caught:
            fetch_latest_active(solicitation_number="SIMULATED", posted_from="10/25/2026",
                                posted_to="10/27/2026", api_key="do-not-print-key", opener=denied)
        rendered = "".join(traceback.format_exception(caught.exception))
        self.assertEqual(str(caught.exception), "SAM Opportunities API HTTP 403")
        self.assertNotIn("do-not-print-key", rendered)
        self.assertNotIn("api_key=", rendered)
        self.assertTrue(caught.exception.__suppress_context__)

    def test_url_error_reason_cannot_leak_request_url(self):
        def failed(request, timeout):
            raise URLError("failed transport " + request.full_url)
        with self.assertRaises(CurrentApiError) as caught:
            fetch_latest_active(solicitation_number="SIMULATED", posted_from="10/25/2026",
                                posted_to="10/27/2026", api_key="do-not-print-key", opener=failed)
        rendered = "".join(traceback.format_exception(caught.exception))
        self.assertEqual(str(caught.exception), "SAM Opportunities API transport failure")
        self.assertNotIn("do-not-print-key", rendered)
        self.assertNotIn("api_key=", rendered)
        self.assertTrue(caught.exception.__suppress_context__)

    def test_resource_transport_does_not_leak_signed_delivery_url(self):
        observation = api_observation()
        for error in (HTTPError("https://files.example/resource?X-Amz-Signature=do-not-print-signature", 403, "denied", {}, None),
                      URLError("https://files.example/resource?X-Amz-Signature=do-not-print-signature")):
            def failed(*args, **kwargs):
                raise error
            with self.subTest(error=type(error).__name__), self.assertRaises(CurrentApiError) as caught:
                download_resource_from_api_observation(observation, LINK, opener=failed)
            self.assertNotIn("do-not-print-signature", "".join(traceback.format_exception(caught.exception)))


if __name__ == "__main__":
    unittest.main()
