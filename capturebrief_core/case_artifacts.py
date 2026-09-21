from __future__ import annotations

import copy
from typing import Any
from urllib.parse import urlparse

from .model import canonical_json, parse_dt, sha256_hex, valid_sha256
from .source_policy import classify_sam_url


class CaseArtifactError(RuntimeError):
    pass


def _resource_id(resource_url: str) -> str:
    if classify_sam_url(resource_url) != "SAM_API_RESOURCE_LINK":
        raise CaseArtifactError("byte receipt source is not an approved SAM API resource link")
    parts = [part for part in urlparse(resource_url).path.split("/") if part]
    try:
        idx = parts.index("files")
        rid = parts[idx + 1]
    except (ValueError, IndexError) as exc:
        raise CaseArtifactError("byte receipt source URL does not expose a resource ID") from exc
    if not rid:
        raise CaseArtifactError("byte receipt resource ID is empty")
    return rid


def apply_api_byte_receipt(
    case: dict[str, Any],
    receipt: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind a documented-API byte receipt to the corresponding case artifact.

    The receipt must descend from the same retained Get Opportunities API observation that
    discovered the resource link. A valid hash alone is not enough.
    """
    if not isinstance(receipt, dict):
        raise CaseArtifactError("byte receipt must be an object")
    if receipt.get("source_contract") != "SAM_GET_OPPORTUNITIES_RESOURCE_LINK":
        raise CaseArtifactError("byte receipt source contract is invalid")
    if receipt.get("automation_mode") != "APPROVED_API":
        raise CaseArtifactError("byte receipt is not marked APPROVED_API")
    if receipt.get("byte_state") != "BYTES_VERIFIED_HASHED":
        raise CaseArtifactError("byte receipt is not BYTES_VERIFIED_HASHED")
    if not valid_sha256(receipt.get("sha256")):
        raise CaseArtifactError("byte receipt lacks a valid SHA-256")
    if not parse_dt(receipt.get("observed_at")):
        raise CaseArtifactError("byte receipt observed_at is invalid")
    size = receipt.get("size")
    if not isinstance(size, int) or size < 0:
        raise CaseArtifactError("byte receipt size is invalid")

    source_url = str(receipt.get("source_url") or "")
    resource_id = _resource_id(source_url)

    result = copy.deepcopy(case)
    packet = result.setdefault("packet", {})
    current = packet.get("current_api_observation") or {}
    if current.get("source_contract") != "SAM_GET_OPPORTUNITIES_V2":
        raise CaseArtifactError("case does not retain the documented current API observation")
    api_digest = str(current.get("api_payload_sha256") or "")
    if not valid_sha256(api_digest):
        raise CaseArtifactError("case current API observation lacks a valid payload digest")
    if receipt.get("api_payload_sha256") != api_digest:
        raise CaseArtifactError("byte receipt is not bound to the case current API payload")

    current_links = {str(x) for x in packet.get("current_resource_links") or []}
    if source_url not in current_links:
        raise CaseArtifactError("byte receipt source URL was not retained in current API resource links")

    artifacts = list(packet.get("artifacts") or [])
    matches = [idx for idx, item in enumerate(artifacts) if str(item.get("artifact_id")) == resource_id]
    if len(matches) != 1:
        raise CaseArtifactError("byte receipt resource must identify exactly one case artifact")
    idx = matches[0]
    artifact = copy.deepcopy(artifacts[idx])
    if artifact.get("resource_url") != source_url:
        raise CaseArtifactError("artifact resource URL disagrees with byte receipt source URL")
    if artifact.get("source_object_state") != "VERIFIED_SOURCE_OBJECT":
        raise CaseArtifactError("artifact source object is not verified")

    existing_sha = artifact.get("sha256")
    existing_state = artifact.get("byte_state")
    if existing_state == "BYTES_VERIFIED_HASHED" and existing_sha:
        if existing_sha != receipt["sha256"]:
            raise CaseArtifactError("new byte receipt conflicts with already verified artifact bytes")
        receipt_digest = sha256_hex(canonical_json(receipt))
        return result, {
            "status": "BYTE_RECEIPT_ALREADY_APPLIED",
            "artifact_id": resource_id,
            "sha256": existing_sha,
            "receipt_sha256": receipt_digest,
        }

    receipt_digest = sha256_hex(canonical_json(receipt))
    artifact.update({
        "sha256": receipt["sha256"],
        "byte_state": "BYTES_VERIFIED_HASHED",
        "byte_size": size,
        "byte_observed_at": receipt["observed_at"],
        "byte_receipt_sha256": receipt_digest,
        "byte_source_contract": receipt["source_contract"],
    })
    artifacts[idx] = artifact
    packet["artifacts"] = artifacts

    receipts = list(packet.get("byte_receipts") or [])
    if not any(x.get("receipt_sha256") == receipt_digest for x in receipts):
        receipts.append({
            "artifact_id": resource_id,
            "receipt_sha256": receipt_digest,
            "receipt": copy.deepcopy(receipt),
        })
    packet["byte_receipts"] = receipts

    return result, {
        "status": "BYTE_RECEIPT_APPLIED",
        "artifact_id": resource_id,
        "sha256": receipt["sha256"],
        "size": size,
        "receipt_sha256": receipt_digest,
    }
