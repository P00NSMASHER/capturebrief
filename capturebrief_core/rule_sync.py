"""Pinned public GSA FAR/DFARS source retrieval for CaptureBrief.

Only exact revisions from RULE-SOURCE-CATALOG.json are eligible. The sync path
accepts no caller-supplied URL and follows no redirect as authority.
"""
from __future__ import annotations

import re
import urllib.request
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from .rule_registry import (
    add_rule_version,
    canonical,
    digest,
    load_source_catalog,
    parse_gsa_dita,
)

FETCH_CONTRACT = "capturebrief-pinned-rule-fetch-v1"
MAX_DITA_BYTES = 5 * 1024 * 1024
_CITATION_RE = re.compile(r"^\d{1,3}\.\d+(?:-\d+)?$")
_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
_APPROVED_GSA = {
    "GSA/GSA-Acquisition-FAR": ("FAR", "FAR Council"),
    "GSA/GSA-Acquisition-DFARS": ("DFARS", "DoD"),
}


def _catalog_item(catalog: dict[str, Any], source_id: str) -> dict[str, Any]:
    rows = [
        row for row in catalog.get("sources") or []
        if isinstance(row, dict) and row.get("source_id") == source_id
    ]
    if len(rows) != 1:
        raise ValueError(f"source_id {source_id!r} must identify exactly one catalog source")
    return rows[0]


def build_pinned_dita_request(
    catalog: dict[str, Any],
    *,
    source_id: str,
    citation: str,
) -> dict[str, Any]:
    """Build an immutable GSA DITA request from the approved source catalog."""
    if catalog.get("schema_version") != "1.0":
        raise ValueError("rule source catalog schema is unsupported")
    if not _CITATION_RE.fullmatch(str(citation or "")):
        raise ValueError("citation is not a safe FAR/DFARS citation")
    row = _catalog_item(catalog, source_id)
    repository = str(row.get("repository") or "")
    if repository not in _APPROVED_GSA:
        raise ValueError("source is not an approved GSA DITA repository")
    expected_namespace, default_agency = _APPROVED_GSA[repository]
    if row.get("namespace") != expected_namespace:
        raise ValueError("catalog namespace does not match approved GSA repository")
    revision = str(row.get("revision") or "")
    if not _REVISION_RE.fullmatch(revision):
        raise ValueError("catalog source must use a full immutable Git revision")
    path = f"dita/{citation}.dita"
    raw_url = f"https://raw.githubusercontent.com/{repository}/{revision}/{path}"
    display_url = f"https://github.com/{repository}/blob/{revision}/{path}"
    return {
        "source_id": source_id,
        "namespace": expected_namespace,
        "agency": str(row.get("agency") or default_agency),
        "repository": repository,
        "revision": revision,
        "path": path,
        "raw_url": raw_url,
        "display_url": display_url,
        "source_snapshot_label": row.get("snapshot_label"),
        "catalog_sha256": digest(canonical(catalog)),
        "mutable_ref_used": False,
        "caller_url_used": False,
    }


def _default_fetcher(url: str, max_bytes: int) -> tuple[bytes, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CaptureBrief-PinnedRuleSync/1.0",
            "Accept": "text/plain, application/xml, application/octet-stream",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        final_url = response.geturl()
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                if int(content_length) > max_bytes:
                    raise ValueError("pinned DITA response exceeds byte limit")
            except ValueError as exc:
                if str(exc) == "pinned DITA response exceeds byte limit":
                    raise
        data = response.read(max_bytes + 1)
    return data, final_url


def _validate_final_url(requested: str, final: str) -> None:
    if final != requested:
        raise ValueError("pinned GSA fetch redirected or changed URL")
    parsed = urlsplit(final)
    if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com":
        raise ValueError("pinned GSA fetch ended on an unapproved host")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("pinned GSA URL must not contain credentials/query/fragment")


def fetch_pinned_gsa_rule(
    catalog: dict[str, Any],
    *,
    source_id: str,
    citation: str,
    observed_at: str,
    fetcher: Callable[[str, int], tuple[bytes, str]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fetch one exact-revision GSA DITA topic and normalize it."""
    request = build_pinned_dita_request(
        catalog,
        source_id=source_id,
        citation=citation,
    )
    fetch = fetcher or _default_fetcher
    data, final_url = fetch(request["raw_url"], MAX_DITA_BYTES)
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("pinned source fetcher must return bytes")
    data = bytes(data)
    if len(data) > MAX_DITA_BYTES:
        raise ValueError("pinned DITA response exceeds byte limit")
    _validate_final_url(request["raw_url"], final_url)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("GSA DITA source is not UTF-8") from exc

    record = parse_gsa_dita(
        text,
        namespace=request["namespace"],
        agency=request["agency"],
        edition=request.get("source_snapshot_label"),
        source_repository=request["repository"],
        source_revision=request["revision"],
        source_path=request["path"],
        source_url=request["display_url"],
        observed_at=observed_at,
    )
    if record["citation"] != citation:
        raise ValueError("fetched DITA citation does not match requested citation")

    receipt_payload = {
        "contract": FETCH_CONTRACT,
        "source_id": source_id,
        "citation": citation,
        "namespace": request["namespace"],
        "repository": request["repository"],
        "revision": request["revision"],
        "path": request["path"],
        "requested_raw_url": request["raw_url"],
        "final_raw_url": final_url,
        "display_url": request["display_url"],
        "catalog_sha256": request["catalog_sha256"],
        "observed_at": observed_at,
        "byte_length": len(data),
        "source_sha256": digest(data),
        "rule_source_id": record["rule_source_id"],
        "mutable_ref_used": False,
        "caller_url_used": False,
        "credentials_used": False,
    }
    receipt = {
        **receipt_payload,
        "fetch_receipt_id": "RULEFETCH:" + digest(canonical(receipt_payload)),
    }
    if receipt["source_sha256"] != record["source_sha256"]:
        raise ValueError("fetch receipt/source record byte hash mismatch")
    return record, receipt


def sync_pinned_gsa_rule(
    registry_path: str | Path,
    catalog_path: str | Path,
    *,
    source_id: str,
    citation: str,
    observed_at: str,
    fetcher: Callable[[str, int], tuple[bytes, str]] | None = None,
) -> dict[str, Any]:
    catalog = load_source_catalog(catalog_path)
    record, receipt = fetch_pinned_gsa_rule(
        catalog,
        source_id=source_id,
        citation=citation,
        observed_at=observed_at,
        fetcher=fetcher,
    )
    registry_result = add_rule_version(registry_path, record)
    return {
        "status": "PINNED_RULE_SYNCED",
        "registry_result": registry_result,
        "rule_source_id": record["rule_source_id"],
        "citation": record["citation"],
        "edition": record["edition"],
        "edition_basis": record.get("edition_basis"),
        "source_revision": record["source_revision"],
        "source_sha256": record["source_sha256"],
        "fetch_receipt": receipt,
        "record": record,
        "applicability_authoritative": False,
        "can_auto_apply": False,
    }
