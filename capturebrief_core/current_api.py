from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .model import canonical_json, history_set_digest, parse_dt, sha256_hex
from .source_policy import require_approved_automation

SEARCH_URL = "https://api.sam.gov/opportunities/v2/search"


class CurrentApiError(RuntimeError):
    pass


def _date(value: str) -> datetime:
    return datetime.strptime(value, "%m/%d/%Y").replace(tzinfo=timezone.utc)


def fetch_latest_active(
    *,
    solicitation_number: str,
    posted_from: str,
    posted_to: str,
    api_key: str,
    organization_code: str | None = None,
    timeout: float = 30.0,
    opener=urlopen,
) -> dict[str, Any]:
    """Use the documented Opportunities v2 API for its explicit latest-active semantics."""
    if not api_key:
        raise ValueError("api_key is required")
    start, end = _date(posted_from), _date(posted_to)
    if start > end or end - start > timedelta(days=366):
        raise ValueError("posted date window must be ordered and no longer than one year")

    params: dict[str, Any] = {
        "api_key": api_key,
        "solnum": solicitation_number,
        "postedFrom": posted_from,
        "postedTo": posted_to,
        "limit": 100,
        "offset": 0,
    }
    if organization_code:
        params["organizationCode"] = organization_code

    url = SEARCH_URL + "?" + urlencode(params)
    require_approved_automation(SEARCH_URL, expected="SAM_PUBLIC_API")
    # Do not retain or log the request URL because it contains the API key.
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "CaptureBrief/0.3"})
    try:
        with opener(req, timeout=timeout) as response:
            body = response.read()
    except HTTPError as exc:
        raise CurrentApiError(f"SAM Opportunities API HTTP {exc.code}") from exc
    except URLError as exc:
        raise CurrentApiError(f"SAM Opportunities API transport failure: {exc.reason}") from exc

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurrentApiError("SAM Opportunities API returned invalid JSON") from exc

    rows = payload.get("opportunitiesData") or []
    exact = [
        r
        for r in rows
        if str(r.get("solicitationNumber") or "").strip().upper()
        == solicitation_number.strip().upper()
    ]
    if organization_code:
        exact = [
            r
            for r in exact
            if str(r.get("fullParentPathCode") or "").endswith(organization_code)
        ]
    if len(exact) != 1:
        raise CurrentApiError(f"expected exactly one latest-active family row, found {len(exact)}")

    record = exact[0]
    return {
        "record": record,
        "source_url": SEARCH_URL,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "payload_sha256": sha256_hex(canonical_json(payload)),
        "source_contract": "SAM_GET_OPPORTUNITIES_V2",
        "automation_mode": "APPROVED_API",
        "resource_links": list(record.get("resourceLinks") or []),
    }


def make_current_action_receipt(
    api_observation: dict[str, Any],
    *,
    history_action_ids: list[str],
    expires_hours: int = 24,
) -> dict[str, Any]:
    record = api_observation.get("record") or {}
    action_id = str(record.get("noticeId") or "")
    if not action_id:
        raise CurrentApiError("API record has no noticeId")
    if action_id not in {str(x) for x in history_action_ids}:
        raise CurrentApiError("latest-active API noticeId is outside the observed Data Services history set")

    observed = parse_dt(api_observation.get("observed_at"))
    if not observed:
        raise CurrentApiError("API observation timestamp is invalid")

    evidence = {
        "source_contract": api_observation.get("source_contract"),
        "notice_id": action_id,
        "solicitation_number": record.get("solicitationNumber"),
        "posted_date": record.get("postedDate"),
        "active": record.get("active"),
        "resource_links": api_observation.get("resource_links") or [],
        "api_payload_sha256": api_observation.get("payload_sha256"),
    }
    return {
        "asserted_action_id": action_id,
        "semantics": "CURRENT_ACTIVE",
        "observed_family_status": "ACTIVE",
        "source_url": SEARCH_URL,
        "observed_at": observed.isoformat(),
        "expires_at": (observed + timedelta(hours=expires_hours)).isoformat(),
        "evidence_payload": evidence,
        "evidence_payload_sha256": sha256_hex(canonical_json(evidence)),
        "history_set_sha256": history_set_digest(history_action_ids),
        "automation_mode": "APPROVED_API",
    }


def download_resource_from_api_observation(
    api_observation: dict[str, Any],
    resource_url: str,
    *,
    max_bytes: int = 50 * 1024 * 1024,
    timeout: float = 30.0,
    opener=urlopen,
) -> tuple[dict[str, Any], bytes]:
    """Download only a resource URL that was returned by the documented Opportunities API."""
    links = {str(x) for x in api_observation.get("resource_links") or []}
    if resource_url not in links:
        raise CurrentApiError("resource URL is not bound to this approved API observation")
    require_approved_automation(resource_url, expected="SAM_API_RESOURCE_LINK")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")

    req = Request(resource_url, headers={"User-Agent": "CaptureBrief/0.3"})
    try:
        response = opener(req, timeout=timeout)
        with response:
            declared = (
                response.headers.get("Content-Length")
                if getattr(response, "headers", None)
                else None
            )
            if declared and int(declared) > max_bytes:
                raise CurrentApiError(f"resource exceeds max_bytes before download: {declared}")

            import hashlib

            digest = hashlib.sha256()
            size = 0
            chunks: list[bytes] = []
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise CurrentApiError("resource exceeds max_bytes during download")
                digest.update(chunk)
                chunks.append(chunk)
            final_url = response.geturl() if hasattr(response, "geturl") else resource_url
    except HTTPError as exc:
        raise CurrentApiError(f"SAM resource HTTP {exc.code}") from exc
    except URLError as exc:
        raise CurrentApiError(f"SAM resource transport failure: {exc.reason}") from exc

    receipt = {
        "source_contract": "SAM_GET_OPPORTUNITIES_RESOURCE_LINK",
        "automation_mode": "APPROVED_API",
        "source_url": resource_url,
        "final_url": final_url,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "byte_state": "BYTES_VERIFIED_HASHED",
        "sha256": digest.hexdigest(),
        "size": size,
        "api_payload_sha256": api_observation.get("payload_sha256"),
    }
    return receipt, b"".join(chunks)
