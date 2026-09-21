from __future__ import annotations

import hashlib
import io
import json
import unittest

from capturebrief_core.current_api import (
    SEARCH_URL,
    CurrentApiError,
    CurrentApiIncompletePageError,
    download_resource_from_api_observation,
    fetch_latest_active,
)


LINK="https://sam.gov/api/prod/opps/v3/opportunities/resources/files/r1/download"


class FakeResponse:
    def __init__(self,data:bytes,*,final_url:str|None=None,declared:object="auto"):
        self._io=io.BytesIO(data)
        if declared=="auto":
            self.headers={"Content-Length":str(len(data))}
        elif declared is None:
            self.headers={}
        else:
            self.headers={"Content-Length":str(declared)}
        self._final_url=final_url
    def read(self,n=-1):
        return self._io.read(n)
    def geturl(self):
        return self._final_url or SEARCH_URL
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False


def payload(*,total=1,rows=None,limit=100,offset=0):
    if rows is None:
        rows=[{
            "noticeId":"a"*32,
            "solicitationNumber":"SOL-1",
            "postedDate":"2026-09-20",
            "active":"Yes",
            "resourceLinks":[LINK],
        }]
    return {
        "totalRecords":total,
        "limit":limit,
        "offset":offset,
        "opportunitiesData":rows,
    }


def api_observation():
    raw=json.dumps(payload()).encode()
    return fetch_latest_active(
        solicitation_number="SOL-1",
        posted_from="09/01/2026",
        posted_to="09/21/2026",
        api_key="test-key",
        opener=lambda req,timeout=30: FakeResponse(raw),
    )


class CurrentApiIntegrityTests(unittest.TestCase):
    def test_complete_page_records_raw_and_canonical_hashes(self):
        raw=json.dumps(payload()).encode()
        observation=fetch_latest_active(
            solicitation_number="SOL-1",
            posted_from="09/01/2026",
            posted_to="09/21/2026",
            api_key="test-key",
            opener=lambda req,timeout=30: FakeResponse(raw),
        )
        self.assertTrue(observation["pagination"]["complete"])
        self.assertEqual(observation["pagination"]["total_records"],1)
        self.assertEqual(observation["pagination"]["returned_records"],1)
        self.assertEqual(observation["response_sha256"],hashlib.sha256(raw).hexdigest())
        self.assertNotEqual(observation["response_sha256"],"")

    def test_incomplete_first_page_is_rejected(self):
        raw=json.dumps(payload(total=2)).encode()
        with self.assertRaises(CurrentApiIncompletePageError):
            fetch_latest_active(
                solicitation_number="SOL-1",
                posted_from="09/01/2026",
                posted_to="09/21/2026",
                api_key="test-key",
                opener=lambda req,timeout=30: FakeResponse(raw),
            )

    def test_missing_pagination_metadata_is_rejected(self):
        raw=json.dumps({"opportunitiesData":payload()["opportunitiesData"]}).encode()
        with self.assertRaises(CurrentApiError):
            fetch_latest_active(
                solicitation_number="SOL-1",
                posted_from="09/01/2026",
                posted_to="09/21/2026",
                api_key="test-key",
                opener=lambda req,timeout=30: FakeResponse(raw),
            )

    def test_current_api_redirect_to_external_host_is_rejected(self):
        raw=json.dumps(payload()).encode()
        with self.assertRaises(CurrentApiError):
            fetch_latest_active(
                solicitation_number="SOL-1",
                posted_from="09/01/2026",
                posted_to="09/21/2026",
                api_key="test-key",
                opener=lambda req,timeout=30: FakeResponse(
                    raw,final_url="https://example.com/search?api_key=do-not-trust"
                ),
            )

    def test_current_api_truncated_content_length_is_rejected(self):
        raw=json.dumps(payload()).encode()
        with self.assertRaises(CurrentApiError):
            fetch_latest_active(
                solicitation_number="SOL-1",
                posted_from="09/01/2026",
                posted_to="09/21/2026",
                api_key="test-key",
                opener=lambda req,timeout=30: FakeResponse(raw,declared=len(raw)+10),
            )

    def test_unapproved_resource_link_in_api_payload_is_rejected(self):
        p=payload()
        p["opportunitiesData"][0]["resourceLinks"]=["https://sam.gov/opp/a/view"]
        raw=json.dumps(p).encode()
        with self.assertRaises(CurrentApiError):
            fetch_latest_active(
                solicitation_number="SOL-1",
                posted_from="09/01/2026",
                posted_to="09/21/2026",
                api_key="test-key",
                opener=lambda req,timeout=30: FakeResponse(raw),
            )

    def test_resource_capture_refuses_legacy_under_specified_observation(self):
        observation=api_observation()
        observation.pop("pagination")
        with self.assertRaises(CurrentApiError):
            download_resource_from_api_observation(
                observation,LINK,opener=lambda req,timeout=30: FakeResponse(b"abc")
            )

    def test_signed_https_redirect_is_hashed_not_retained(self):
        observation=api_observation()
        signed="https://objects.example/file?X-Amz-Signature=secret-value&X-Amz-Expires=60"
        receipt,data=download_resource_from_api_observation(
            observation,
            LINK,
            opener=lambda req,timeout=30: FakeResponse(b"abc",final_url=signed),
        )
        self.assertEqual(data,b"abc")
        self.assertTrue(receipt["redirect_used"])
        self.assertFalse(receipt["final_url_retained"])
        self.assertEqual(receipt["final_delivery_host"],"objects.example")
        self.assertEqual(receipt["final_url_sha256"],hashlib.sha256(signed.encode()).hexdigest())
        self.assertNotIn("final_url",receipt)
        self.assertNotIn("secret-value",json.dumps(receipt))

    def test_resource_redirect_must_remain_https(self):
        observation=api_observation()
        with self.assertRaises(CurrentApiError):
            download_resource_from_api_observation(
                observation,
                LINK,
                opener=lambda req,timeout=30: FakeResponse(
                    b"abc",final_url="http://objects.example/file"
                ),
            )

    def test_resource_truncation_is_rejected(self):
        observation=api_observation()
        with self.assertRaises(CurrentApiError):
            download_resource_from_api_observation(
                observation,
                LINK,
                opener=lambda req,timeout=30: FakeResponse(b"abc",declared=9),
            )


if __name__=="__main__":
    unittest.main()
