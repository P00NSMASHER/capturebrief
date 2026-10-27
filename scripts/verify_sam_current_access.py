"""Bounded, no-send observation of an actual public SAM opportunity.

The key is read only from SAM_API_KEY and sent only to the approved API host.
Only an explicit aggregate projection is printed. This is source-access
evidence, never catalog approval, complete history or customer acceptance.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import HTTPRedirectHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capturebrief_core.current_api import (
    CurrentApiCardinalityError,
    CurrentApiIncompletePageError,
    CurrentApiError,
    SEARCH_URL,
    _approved_search_final_url,
    fetch_latest_active,
    validate_api_observation,
)
from capturebrief_core.model import parse_dt

# Observed in the genuine official ACTIVE extract on October 27, 2026.
# Original digest: 9cc53cb26df3bf0c60d4621c872ff861254c80b223fd89e0d9f6c5c9b90d4d80
# This public source probe is not a customer request or a manufactured notice.
SOLICITATION = "2031JW27Q00011"
POSTED_FROM = "10/25/2026"
POSTED_TO = "10/27/2026"


class ApprovedApiRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Validate before the redirect connection, not just its final response.
        if not _approved_search_final_url(newurl):
            raise CurrentApiError("API redirect rejected before connection")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def run_probe(api_key: str, *, fetcher=fetch_latest_active, now=None):
    clock = now or (lambda: datetime.now(timezone.utc))
    result = {
        "schema": "capturebrief.sam_current_access.v1",
        "generated_at": clock().isoformat(),
        "source_endpoint": SEARCH_URL,
        "public_probe_solicitation": SOLICITATION,
        "posted_from": POSTED_FROM,
        "posted_to": POSTED_TO,
        "api_key_present_in_runtime": bool(api_key),
        "api_access_verified": False,
        "latest_active_observation_verified": False,
        "source_catalog_approved": False,
        "full_history_verified": False,
        "customer_review_verified": False,
        "customer_delivery_verified": False,
        "external_send_authorized": False,
        "raw_record_published": False,
    }
    if not api_key:
        return {**result, "status": "BLOCKED_SAM_API_KEY_UNAVAILABLE"}, 3
    try:
        observation = fetcher(
            solicitation_number=SOLICITATION,
            posted_from=POSTED_FROM,
            posted_to=POSTED_TO,
            api_key=api_key,
            timeout=30.0,
            max_response_bytes=2 * 1024 * 1024,
            opener=build_opener(ApprovedApiRedirects()).open,
        )
        validate_api_observation(observation)
        observed_at = parse_dt(observation["observed_at"])
        age = (clock() - observed_at).total_seconds()
        if age < 0 or age > 300:
            raise CurrentApiError("Source observation is not fresh")
        record = observation["record"]
        if str(record["solicitationNumber"]).strip().upper() != SOLICITATION:
            raise CurrentApiError("Source observation is for a different family")
        result["api_access_verified"] = True
        if str(record.get("active", "")).strip().lower() != "yes":
            return {**result, "status": "BLOCKED_PROBE_NOTICE_NOT_ACTIVE"}, 3
        # Never project unknown fields, resource URLs, contacts, response bodies,
        # exception text, credential-bearing URLs or a raw record into stdout.
        safe = {
            "observed_at": observation["observed_at"],
            "source_contract": observation["source_contract"],
            "payload_sha256": observation["payload_sha256"],
            "response_sha256": observation["response_sha256"],
            "notice_id_sha256": hashlib.sha256(str(record["noticeId"]).encode()).hexdigest(),
            "pagination": {
                k: observation["pagination"][k]
                for k in ("complete", "total_records", "returned_records", "limit", "offset")
            },
            "resource_link_count": len(observation["resource_links"]),
        }
        return {**result, **safe, "latest_active_observation_verified": True,
                "status": "PUBLIC_API_OBSERVATION_VERIFIED"}, 0
    except CurrentApiCardinalityError:
        status = "BLOCKED_API_FAMILY_CARDINALITY"
    except CurrentApiIncompletePageError:
        status = "BLOCKED_API_INCOMPLETE_RESPONSE"
    except Exception:
        # Even a chained transport exception may contain the API key in a URL.
        # Deliberately omit exception text, traceback and raw response details.
        status = "BLOCKED_API_OBSERVATION_FAILED"
    return {**result, "status": status}, 3


def main():
    result, code = run_probe(os.environ.get("SAM_API_KEY", ""))
    print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
