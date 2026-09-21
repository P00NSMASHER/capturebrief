from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .model import Finding, canonical_json, first_party_sam, parse_dt, sha256_hex, valid_sha256
from .source_policy import SourcePolicyError

MANIFEST_PARSER_VERSION = "capturebrief-sam-manifest-v1"
MANIFEST_URL = "https://sam.gov/api/prod/opps/v3/opportunities/{action_id}/resources?excludeDeleted=false&withScanResult=false"
DOWNLOAD_URL = "https://sam.gov/api/prod/opps/v3/opportunities/resources/files/{resource_id}/download"
MANIFEST_ACCEPT = "application/hal+json"
MANIFEST_GOOD_STATUSES = {"CHECKED", "CHECKED_EMPTY"}


class ManifestError(RuntimeError):
    pass


class ManifestShapeError(ManifestError):
    pass


class ManifestUnavailable(ManifestError):
    pass


class NoticeUnknown(ManifestError):
    pass


def _flag(value: Any) -> bool:
    return str(value or "0").strip().lower() not in {"0", "false", "", "none"}


def _absolute_http(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def _artifact_state(raw: dict[str, Any], *, kind: str, uri: str | None) -> str:
    if _flag(raw.get("deletedFlag")):
        return "DELETED"
    if kind == "link" and _absolute_http(uri):
        return "EXTERNAL"
    if _flag(raw.get("exportControlled")):
        return "EXPORT_CONTROLLED"
    access = str(raw.get("accessStatus") or "").strip().lower()
    if access and access != "public":
        return "RESTRICTED"
    file_exists = raw.get("fileExists")
    if file_exists is not None and str(file_exists).strip().lower() in {"0", "false", "no"}:
        return "UNAVAILABLE"
    return "PUBLIC"


def normalize_manifest_item(raw: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ManifestShapeError(f"{path}: attachment entry is not an object")
    resource_id = raw.get("resourceId")
    if not isinstance(resource_id, str) or not resource_id:
        raise ManifestShapeError(f"{path}: attachment entry has no resourceId")
    kind = raw.get("type") or "file"
    if not isinstance(kind, str):
        raise ManifestShapeError(f"{path}: attachment type is not a string")
    uri = raw.get("uri") if isinstance(raw.get("uri"), str) and raw.get("uri") else None
    name = raw.get("name") if isinstance(raw.get("name"), str) and raw.get("name") else None
    if not name and kind == "link":
        desc = raw.get("description")
        if isinstance(desc, str) and desc:
            name = desc
    size = raw.get("size")
    if size is not None and not isinstance(size, int):
        raise ManifestShapeError(f"{path}: attachment size is not an integer")
    return {
        "resource_id": resource_id,
        "name": name or "attachment",
        "kind": kind,
        "uri": uri,
        "mime_type": raw.get("mimeType") if isinstance(raw.get("mimeType"), str) else None,
        "declared_size": size,
        "posted_at": raw.get("postedDate") if isinstance(raw.get("postedDate"), str) else None,
        "access_status": raw.get("accessStatus") if isinstance(raw.get("accessStatus"), str) else None,
        "export_controlled": _flag(raw.get("exportControlled")),
        "deleted": _flag(raw.get("deletedFlag")),
        "deleted_at": raw.get("deletedDate") if isinstance(raw.get("deletedDate"), str) else None,
        "attachment_id": raw.get("attachmentId") if isinstance(raw.get("attachmentId"), str) else raw.get("attachmentId"),
        "attachment_order": raw.get("attachmentOrder"),
        "file_exists": raw.get("fileExists"),
        "artifact_state": _artifact_state(raw, kind=kind, uri=uri),
        "raw_sha256": sha256_hex(canonical_json(raw)),
    }


def normalize_manifest_payload(
    action_id: str,
    payload: Any,
    *,
    observed_at: str | None = None,
    source_url: str | None = None,
    observation_mode: str = "HUMAN_SUPERVISED",
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ManifestShapeError("manifest response is not an object")
    action_id = str(action_id or "")
    if not action_id:
        raise ValueError("action_id is required")
    source_url = source_url or MANIFEST_URL.format(action_id=action_id)
    if not first_party_sam(source_url):
        raise ValueError("manifest source URL must be first-party sam.gov HTTPS")
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    if not parse_dt(observed_at):
        raise ValueError("observed_at must be timezone-aware ISO-8601")

    embedded = payload.get("_embedded")
    if embedded is None:
        groups: list[Any] = []
    else:
        if not isinstance(embedded, dict):
            raise ManifestShapeError("_embedded is not an object")
        groups = embedded.get("opportunityAttachmentList") or []
        if not isinstance(groups, list):
            raise ManifestShapeError("opportunityAttachmentList is not a list")

    items: list[dict[str, Any]] = []
    for gi, group in enumerate(groups):
        if not isinstance(group, dict):
            raise ManifestShapeError(f"group[{gi}] is not an object")
        attachments = group.get("attachments") or []
        if not isinstance(attachments, list):
            raise ManifestShapeError(f"group[{gi}].attachments is not a list")
        for ai, raw in enumerate(attachments):
            items.append(normalize_manifest_item(raw, path=f"group[{gi}].attachments[{ai}]"))

    raw_digest = sha256_hex(canonical_json(payload))
    normalized_digest = sha256_hex(canonical_json(items))
    return {
        "action_id": action_id,
        "source_url": source_url,
        "observed_at": observed_at,
        "status": "CHECKED_EMPTY" if not items else "CHECKED",
        "deletion_inclusive": True,
        "with_scan_result": False,
        "parser_version": MANIFEST_PARSER_VERSION,
        "source_contract": "UNDOCUMENTED_SAM_WEB_UI",
        "observation_mode": observation_mode,
        "endpoint_version": "v3",
        "shape_validated": True,
        "raw_manifest_sha256": raw_digest,
        "raw_manifest": payload,
        "normalized_manifest_sha256": normalized_digest,
        "items": items,
    }


def fetch_manifest(action_id: str, *, timeout: float = 30.0) -> dict[str, Any]:
    """Automation is disabled for the undocumented SAM web-UI manifest surface."""
    raise SourcePolicyError(
        "automated SAM web-UI manifest collection is disabled by source policy; "
        "capture a first-party snapshot manually and use normalize_manifest_payload"
    )


def _verified_raw_hash(receipt: dict[str, Any]) -> bool:
    digest = receipt.get("raw_manifest_sha256")
    if not valid_sha256(digest):
        return False
    raw = receipt.get("raw_manifest")
    if raw is not None:
        return sha256_hex(canonical_json(raw)) == digest
    return receipt.get("payload_hash_verified") is True and bool(receipt.get("snapshot_ref"))


def validate_manifest_receipts(
    history_action_ids: Iterable[str],
    receipts: Iterable[dict[str, Any]],
) -> tuple[str, dict[str, Any], list[Finding]]:
    """Derive attachment-manifest completeness from per-action receipts.

    A producer cannot make a packet green with ``manifest_complete: true``. Every observed
    history action must have a deletion-inclusive, shape-validated, first-party receipt.
    Conflicting complete receipts for the same action fail closed.
    """
    findings: list[Finding] = []
    history = {str(x) for x in history_action_ids if str(x)}
    by_action: dict[str, list[dict[str, Any]]] = {}

    for i, receipt in enumerate(receipts):
        path = f"packet.manifest_receipts[{i}]"
        action_id = str(receipt.get("action_id", ""))
        if not action_id or action_id not in history:
            findings.append(Finding("MANIFEST_RECEIPT_ACTION_OUTSIDE_HISTORY", "BLOCK", "Manifest receipt action is not in the observed history set.", path))
            continue
        if not first_party_sam(receipt.get("source_url")):
            findings.append(Finding("MANIFEST_RECEIPT_NOT_FIRST_PARTY", "BLOCK", "Manifest receipt source is not first-party sam.gov HTTPS.", path))
            continue
        if not parse_dt(receipt.get("observed_at")):
            findings.append(Finding("MANIFEST_RECEIPT_TIME_INVALID", "BLOCK", "Manifest receipt lacks a timezone-aware observation timestamp.", path))
            continue
        if receipt.get("status") not in MANIFEST_GOOD_STATUSES:
            findings.append(Finding("MANIFEST_RECEIPT_NOT_COMPLETE", "BLOCK", "Manifest receipt did not complete successfully.", path))
            continue
        if receipt.get("deletion_inclusive") is not True:
            findings.append(Finding("MANIFEST_RECEIPT_NOT_DELETION_INCLUSIVE", "BLOCK", "Manifest receipt did not explicitly include deleted resources.", path))
            continue
        if receipt.get("shape_validated") is not True:
            findings.append(Finding("MANIFEST_RECEIPT_SHAPE_UNVERIFIED", "BLOCK", "Manifest receipt was not validated against the pinned parser shape.", path))
            continue
        if not _verified_raw_hash(receipt):
            findings.append(Finding("MANIFEST_RECEIPT_HASH_UNVERIFIED", "BLOCK", "Manifest receipt raw payload hash is missing or unverified.", path))
            continue
        if receipt.get("parser_version") != MANIFEST_PARSER_VERSION:
            findings.append(Finding("MANIFEST_RECEIPT_PARSER_VERSION_MISMATCH", "BLOCK", "Manifest receipt parser version is not the current pinned version.", path))
            continue
        by_action.setdefault(action_id, []).append(receipt)

    missing = sorted(history - set(by_action))
    for action_id in missing:
        findings.append(Finding("MANIFEST_ACTION_UNOBSERVED", "BLOCK", f"No successful deletion-inclusive manifest receipt exists for history action {action_id}."))

    conflicts: list[str] = []
    for action_id, action_receipts in by_action.items():
        digests = {r.get("raw_manifest_sha256") for r in action_receipts}
        if len(digests) > 1:
            conflicts.append(action_id)
            findings.append(Finding("MANIFEST_SOURCE_DISAGREEMENT", "BLOCK", f"Multiple successful manifest receipts disagree for action {action_id}."))

    covered = sorted(set(by_action) - set(conflicts))
    verdict = "MANIFEST_COMPLETE" if history and not missing and not conflicts and set(covered) == history else "MANIFEST_UNRESOLVED"
    summary = {
        "history_actions": sorted(history),
        "covered_actions": covered,
        "missing_actions": missing,
        "conflicting_actions": conflicts,
        "coverage_sha256": sha256_hex(canonical_json(covered)),
    }
    return verdict, summary, findings


def resource_download_url(resource_id: str) -> str:
    return DOWNLOAD_URL.format(resource_id=resource_id)


def download_public_resource(
    resource: dict[str, Any],
    *,
    max_bytes: int = 50 * 1024 * 1024,
    timeout: float = 30.0,
    opener=urlopen,
) -> tuple[dict[str, Any], bytes]:
    """Capture and hash a public SAM-hosted file before historical delivery disappears.

    The function never dereferences manifest ``type=link`` entries and never sends credentials.
    It starts only from SAM's first-party resource download endpoint; redirects may terminate on
    SAM's short-lived object-storage delivery URL.
    """
    if opener is urlopen:
        raise SourcePolicyError("automated downloads from web-UI manifest receipts are disabled; use a documented API resourceLinks observation")
    if resource.get("kind") != "file" or resource.get("artifact_state") != "PUBLIC":
        raise ValueError("only public SAM file resources may be downloaded")
    resource_id = str(resource.get("resource_id", ""))
    if not resource_id:
        raise ValueError("resource_id is required")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    url = resource_download_url(resource_id)
    req = Request(url, headers={"User-Agent": "CaptureBrief/0.2"})
    try:
        response = opener(req, timeout=timeout)
        with response:
            declared = response.headers.get("Content-Length") if getattr(response, "headers", None) else None
            if declared and int(declared) > max_bytes:
                raise ManifestUnavailable(f"resource exceeds max_bytes before download: {declared}")
            import hashlib
            digest = hashlib.sha256(); size = 0
            chunks: list[bytes] = []
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise ManifestUnavailable("resource exceeds max_bytes during download")
                digest.update(chunk); chunks.append(chunk)
            final_url = response.geturl() if hasattr(response, "geturl") else url
    except HTTPError as exc:
        raise ManifestUnavailable(f"SAM resource HTTP {exc.code}") from exc
    except URLError as exc:
        raise ManifestUnavailable(f"SAM resource transport failure: {exc.reason}") from exc
    receipt = {
        "resource_id": resource_id,
        "source_url": url,
        "final_url": final_url,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "byte_state": "BYTES_VERIFIED_HASHED",
        "sha256": digest.hexdigest(),
        "size": size,
    }
    return receipt, b"".join(chunks)
