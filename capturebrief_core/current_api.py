from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .model import canonical_json, history_set_digest, parse_dt, sha256_hex, valid_sha256
from .source_policy import require_approved_automation

SEARCH_URL = "https://api.sam.gov/prod/opportunities/v2/search"
MAX_API_RESPONSE_BYTES = 10 * 1024 * 1024


class CurrentApiError(RuntimeError):
    pass


class CurrentApiCardinalityError(CurrentApiError):
    def __init__(self, count: int):
        self.count = int(count)
        super().__init__(f"expected exactly one latest-active family row, found {self.count}")


class CurrentApiIncompletePageError(CurrentApiError):
    def __init__(self, total_records: int, returned_records: int):
        self.total_records = int(total_records)
        self.returned_records = int(returned_records)
        super().__init__(
            f"SAM Opportunities API response is paginated/incomplete: "
            f"totalRecords={self.total_records}, returned={self.returned_records}"
        )


def _date(value: str) -> datetime:
    return datetime.strptime(value, "%m/%d/%Y").replace(tzinfo=timezone.utc)


def _nonnegative_int(value: Any, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise CurrentApiError(f"SAM Opportunities API {field} is invalid") from exc
    if parsed < 0:
        raise CurrentApiError(f"SAM Opportunities API {field} is negative")
    return parsed


def _approved_search_final_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() == "api.sam.gov"
        and parsed.path in {"/opportunities/v2/search", "/prod/opportunities/v2/search"}
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    )


def _safe_https_delivery_url(value: str) -> tuple[str, str]:
    try:
        parsed = urlsplit(value)
    except (TypeError, ValueError) as exc:
        raise CurrentApiError("SAM resource final delivery URL is invalid") from exc
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise CurrentApiError("SAM resource redirect must terminate on a safe HTTPS delivery URL")
    return host, sha256_hex(value)


def _response_bytes(response: Any, *, max_bytes: int, label: str) -> bytes:
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    declared = response.headers.get("Content-Length") if getattr(response, "headers", None) else None
    declared_size = None
    if declared not in (None, ""):
        try:
            declared_size = int(declared)
        except (TypeError, ValueError) as exc:
            raise CurrentApiError(f"{label} Content-Length is invalid") from exc
        if declared_size < 0:
            raise CurrentApiError(f"{label} Content-Length is negative")
        if declared_size > max_bytes:
            raise CurrentApiError(f"{label} exceeds max_bytes before download: {declared_size}")

    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = response.read(64 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > max_bytes:
            raise CurrentApiError(f"{label} exceeds max_bytes during download")
        chunks.append(chunk)
    if declared_size is not None and size != declared_size:
        raise CurrentApiError(
            f"{label} byte count {size} does not match Content-Length {declared_size}"
        )
    return b"".join(chunks)


def validate_api_observation(api_observation: dict[str, Any]) -> None:
    if not isinstance(api_observation, dict):
        raise CurrentApiError("API observation must be an object")
    if api_observation.get("source_contract") != "SAM_GET_OPPORTUNITIES_V2":
        raise CurrentApiError("API observation source contract is invalid")
    if api_observation.get("automation_mode") != "APPROVED_API":
        raise CurrentApiError("API observation is not marked APPROVED_API")
    if api_observation.get("source_url") != SEARCH_URL:
        raise CurrentApiError("API observation source endpoint is not the documented production endpoint")
    if parse_dt(api_observation.get("observed_at")) is None:
        raise CurrentApiError("API observation timestamp is invalid")
    if not valid_sha256(api_observation.get("payload_sha256")):
        raise CurrentApiError("API observation payload SHA-256 is invalid")
    if not valid_sha256(api_observation.get("response_sha256")):
        raise CurrentApiError("API observation raw-response SHA-256 is invalid")

    pagination = api_observation.get("pagination")
    if not isinstance(pagination, dict) or pagination.get("complete") is not True:
        raise CurrentApiError("API observation does not prove pagination completeness")
    total = _nonnegative_int(pagination.get("total_records"), "pagination.total_records")
    returned = _nonnegative_int(pagination.get("returned_records"), "pagination.returned_records")
    limit = _nonnegative_int(pagination.get("limit"), "pagination.limit")
    offset = _nonnegative_int(pagination.get("offset"), "pagination.offset")
    if offset != 0 or total != returned or returned > limit:
        raise CurrentApiError("API observation pagination contract is inconsistent")

    record = api_observation.get("record")
    if not isinstance(record, dict) or not str(record.get("noticeId") or "").strip():
        raise CurrentApiError("API observation lacks a noticeId")
    if not str(record.get("solicitationNumber") or "").strip():
        raise CurrentApiError("API observation lacks solicitationNumber")

    links = api_observation.get("resource_links")
    if not isinstance(links, list):
        raise CurrentApiError("API observation resource_links must be a list")
    for link in links:
        try:
            require_approved_automation(str(link), expected="SAM_API_RESOURCE_LINK")
        except Exception as exc:
            raise CurrentApiError("API observation contains a non-approved resource link") from exc


def fetch_latest_active(
    *,
    solicitation_number: str,
    posted_from: str,
    posted_to: str,
    api_key: str,
    organization_code: str | None = None,
    timeout: float = 30.0,
    max_response_bytes: int = MAX_API_RESPONSE_BYTES,
    opener=urlopen,
) -> dict[str, Any]:
    """Use the documented Opportunities v2 API for explicit latest-active semantics."""
    if not api_key:
        raise ValueError("api_key is required")
    start, end = _date(posted_from), _date(posted_to)
    if start > end or end - start > timedelta(days=366):
        raise ValueError("posted date window must be ordered and no longer than one year")
    if max_response_bytes <= 0:
        raise ValueError("max_response_bytes must be positive")

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
    # Never retain or log the request URL because it contains the API key.
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "CaptureBrief/0.3"})
    try:
        with opener(req, timeout=timeout) as response:
            final_url = response.geturl() if hasattr(response, "geturl") else url
            if not _approved_search_final_url(final_url):
                raise CurrentApiError("SAM Opportunities API redirected to a non-approved endpoint")
            body = _response_bytes(
                response, max_bytes=max_response_bytes, label="SAM Opportunities API response"
            )
    except HTTPError as exc:
        raise CurrentApiError(f"SAM Opportunities API HTTP {exc.code}") from exc
    except URLError as exc:
        raise CurrentApiError(f"SAM Opportunities API transport failure: {exc.reason}") from exc

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurrentApiError("SAM Opportunities API returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise CurrentApiError("SAM Opportunities API returned a non-object JSON payload")

    rows = payload.get("opportunitiesData")
    if not isinstance(rows, list):
        raise CurrentApiError("SAM Opportunities API opportunitiesData is not a list")
    total_records = _nonnegative_int(payload.get("totalRecords"), "totalRecords")
    response_limit = _nonnegative_int(payload.get("limit"), "limit")
    response_offset = _nonnegative_int(payload.get("offset"), "offset")
    if response_offset != 0:
        raise CurrentApiError("SAM Opportunities API response offset is not zero")
    if len(rows) > response_limit:
        raise CurrentApiError("SAM Opportunities API returned more rows than its response limit")
    if total_records != len(rows):
        raise CurrentApiIncompletePageError(total_records, len(rows))

    exact = [
        r
        for r in rows
        if isinstance(r, dict)
        and str(r.get("solicitationNumber") or "").strip().upper()
        == solicitation_number.strip().upper()
    ]
    if organization_code:
        exact = [
            r
            for r in exact
            if str(r.get("fullParentPathCode") or "").endswith(organization_code)
        ]
    if len(exact) != 1:
        raise CurrentApiCardinalityError(len(exact))

    record = exact[0]
    links = list(record.get("resourceLinks") or [])
    for link in links:
        try:
            require_approved_automation(str(link), expected="SAM_API_RESOURCE_LINK")
        except Exception as exc:
            raise CurrentApiError("SAM Opportunities API returned a non-approved resource link") from exc

    observation = {
        "record": record,
        "source_url": SEARCH_URL,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "payload_sha256": sha256_hex(canonical_json(payload)),
        "response_sha256": sha256_hex(body),
        "source_contract": "SAM_GET_OPPORTUNITIES_V2",
        "automation_mode": "APPROVED_API",
        "resource_links": links,
        "pagination": {
            "total_records": total_records,
            "returned_records": len(rows),
            "limit": response_limit,
            "offset": response_offset,
            "complete": True,
        },
    }
    validate_api_observation(observation)
    return observation


def make_current_action_receipt(
    api_observation: dict[str, Any],
    *,
    history_action_ids: list[str],
    expires_hours: int = 24,
) -> dict[str, Any]:
    validate_api_observation(api_observation)
    record = api_observation["record"]
    action_id = str(record.get("noticeId") or "")
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
        "api_response_sha256": api_observation.get("response_sha256"),
        "pagination": api_observation.get("pagination"),
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
    """Download only a resource URL descended from a complete documented API observation."""
    validate_api_observation(api_observation)
    links = {str(x) for x in api_observation.get("resource_links") or []}
    if resource_url not in links:
        raise CurrentApiError("resource URL is not bound to this approved API observation")
    require_approved_automation(resource_url, expected="SAM_API_RESOURCE_LINK")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")

    req = Request(resource_url, headers={"User-Agent": "CaptureBrief/0.3"})
    try:
        with opener(req, timeout=timeout) as response:
            content = _response_bytes(response, max_bytes=max_bytes, label="SAM resource")
            final_url = response.geturl() if hasattr(response, "geturl") else resource_url
    except HTTPError as exc:
        raise CurrentApiError(f"SAM resource HTTP {exc.code}") from exc
    except URLError as exc:
        raise CurrentApiError(f"SAM resource transport failure: {exc.reason}") from exc

    final_host, final_url_hash = _safe_https_delivery_url(final_url)
    redirect_used = final_url != resource_url
    receipt = {
        "source_contract": "SAM_GET_OPPORTUNITIES_RESOURCE_LINK",
        "automation_mode": "APPROVED_API",
        "source_url": resource_url,
        "final_url_retained": False,
        "final_delivery_host": final_host,
        "final_url_sha256": final_url_hash,
        "redirect_used": redirect_used,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "byte_state": "BYTES_VERIFIED_HASHED",
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
        "api_payload_sha256": api_observation.get("payload_sha256"),
        "api_response_sha256": api_observation.get("response_sha256"),
    }
    return receipt, content
