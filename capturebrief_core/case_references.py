from __future__ import annotations

import copy
from typing import Any
from urllib.parse import urlparse

from .model import canonical_json, parse_dt, sha256_hex, valid_sha256
from .packet import validate_reference_closure


class CaseReferenceError(RuntimeError):
    pass


def _inventory_validation_errors(packet: dict[str, Any]) -> list[str]:
    _, findings = validate_reference_closure(packet)
    allowed = {"REFERENCED_ARTIFACT_UNRESOLVED"}
    return sorted({f.code for f in findings if f.code not in allowed})


def apply_reference_review_result(
    case: dict[str, Any],
    review_result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Attach a human-confirmed reference inventory without silently resolving anything."""
    if not isinstance(review_result, dict):
        raise CaseReferenceError("reference review result must be an object")
    scan = review_result.get("reference_scan")
    references = review_result.get("references")
    if not isinstance(scan, dict) or not isinstance(references, list):
        raise CaseReferenceError("reference review result must contain reference_scan and references")
    if scan.get("status") != "COMPLETE" or scan.get("review_mode") != "HUMAN_CONFIRMED":
        raise CaseReferenceError("only a COMPLETE HUMAN_CONFIRMED reference review may be applied")
    if not parse_dt(scan.get("reviewed_at")):
        raise CaseReferenceError("reference review timestamp is invalid")

    for idx, ref in enumerate(references):
        if not isinstance(ref, dict):
            raise CaseReferenceError(f"references[{idx}] is not an object")
        if str(ref.get("resolution") or "UNRESOLVED").upper() != "UNRESOLVED":
            raise CaseReferenceError("reference review application cannot smuggle pre-resolved dependencies")
        if str(ref.get("source_object_state") or "") != "UNRESOLVED_SOURCE_OBJECT":
            raise CaseReferenceError("newly confirmed references must begin with unresolved source identity")
        if str(ref.get("byte_state") or "") != "BYTES_NOT_YET_CHECKED":
            raise CaseReferenceError("newly confirmed references must begin with unchecked bytes")

    result = copy.deepcopy(case)
    packet = result.setdefault("packet", {})
    existing_scan = packet.get("reference_scan") or {}
    existing_refs = packet.get("references") or []

    # Reapplying the exact reviewed inventory is idempotent and must not roll back later closure.
    if (
        existing_scan.get("status") == "COMPLETE"
        and existing_scan.get("scan_sha256") == scan.get("scan_sha256")
    ):
        existing_ids = sorted(str(x.get("reference_id")) for x in existing_refs if x.get("reference_id"))
        new_ids = sorted(str(x.get("reference_id")) for x in references if x.get("reference_id"))
        if existing_ids != new_ids:
            raise CaseReferenceError("same reference review digest has a different reference ID set")
        packet["reference_scan"] = copy.deepcopy(scan)
        return result, {
            "status": "REFERENCE_REVIEW_ALREADY_APPLIED",
            "scan_sha256": scan.get("scan_sha256"),
            "reference_ids": new_ids,
        }

    if existing_scan.get("status") == "COMPLETE":
        if any(str(x.get("resolution") or "UNRESOLVED").upper() != "UNRESOLVED" for x in existing_refs):
            raise CaseReferenceError(
                "cannot replace a reviewed reference inventory after closure work has begun"
            )

    proposed_packet = copy.deepcopy(packet)
    proposed_packet["reference_scan"] = copy.deepcopy(scan)
    proposed_packet["references"] = copy.deepcopy(references)
    errors = _inventory_validation_errors(proposed_packet)
    if errors:
        raise CaseReferenceError(f"reference review failed inventory validation: {errors}")

    packet["reference_scan"] = copy.deepcopy(scan)
    packet["references"] = copy.deepcopy(references)
    return result, {
        "status": "REFERENCE_REVIEW_APPLIED",
        "scan_sha256": scan.get("scan_sha256"),
        "reference_ids": sorted(str(x.get("reference_id")) for x in references),
        "reviewer": scan.get("reviewer"),
        "reviewed_at": scan.get("reviewed_at"),
    }


def _manifest_resource_ids(packet: dict[str, Any]) -> set[str]:
    return {
        str(item.get("resource_id"))
        for receipt in packet.get("manifest_receipts") or []
        for item in receipt.get("items") or []
        if item.get("resource_id")
    }


def _artifact_map(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("artifact_id")): item
        for item in packet.get("artifacts") or []
        if item.get("artifact_id")
    }


def _resolution_review(decision: dict[str, Any], reference_id: str) -> dict[str, Any]:
    reviewer = str(decision.get("reviewer") or "").strip()
    reviewed_at = str(decision.get("reviewed_at") or "").strip()
    reason = str(decision.get("reason") or "").strip()
    if not reviewer:
        raise CaseReferenceError("reference resolution reviewer is required")
    if not parse_dt(reviewed_at):
        raise CaseReferenceError("reference resolution reviewed_at must be timezone-aware ISO-8601")
    if not reason:
        raise CaseReferenceError("reference resolution reason is required")
    payload = {
        "reference_id": reference_id,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "reason": reason,
        "resolution": str(decision.get("resolution") or "").upper(),
        "resource_id": decision.get("resource_id"),
        "successor_resource_id": decision.get("successor_resource_id"),
        "supersession_source_id": decision.get("supersession_source_id"),
        "url": decision.get("url"),
        "byte_state": decision.get("byte_state"),
        "byte_sha256": decision.get("byte_sha256"),
    }
    return {
        "contract": "CAPTUREBRIEF_REFERENCE_RESOLUTION_V1",
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "reason": reason,
        "decision_sha256": sha256_hex(canonical_json(payload)),
        "payload": payload,
    }


def apply_reference_resolution(
    case: dict[str, Any],
    reference_id: str,
    decision: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply one explicit human resolution decision to a confirmed reference inventory."""
    result = copy.deepcopy(case)
    packet = result.get("packet") or {}
    scan = packet.get("reference_scan") or {}
    if scan.get("status") != "COMPLETE" or scan.get("review_mode") != "HUMAN_CONFIRMED":
        raise CaseReferenceError("reference resolution requires a COMPLETE HUMAN_CONFIRMED inventory")

    refs = list(packet.get("references") or [])
    matches = [idx for idx, ref in enumerate(refs) if str(ref.get("reference_id")) == str(reference_id)]
    if len(matches) != 1:
        raise CaseReferenceError("reference_id must identify exactly one confirmed reference")
    idx = matches[0]
    current = copy.deepcopy(refs[idx])
    resolution = str(decision.get("resolution") or "").upper()
    if resolution not in {"RESOLVED_TO_RESOURCE", "SUPERSEDED_BY", "EXTERNAL_DEPENDENCY"}:
        raise CaseReferenceError("resolution must be RESOLVED_TO_RESOURCE, SUPERSEDED_BY, or EXTERNAL_DEPENDENCY")

    review = _resolution_review(decision, str(reference_id))
    resources = _manifest_resource_ids(packet)
    artifacts = _artifact_map(packet)

    # Clear stale closure fields before constructing the new state.
    for key in (
        "resource_id","successor_resource_id","supersession_source_id","url","reason",
        "byte_sha256","resolution_review",
    ):
        current.pop(key, None)

    if resolution == "RESOLVED_TO_RESOURCE":
        rid = str(decision.get("resource_id") or "")
        byte_sha = str(decision.get("byte_sha256") or "")
        if not rid or rid not in resources:
            raise CaseReferenceError("resolved resource is not present in retained manifest evidence")
        artifact = artifacts.get(rid)
        if not artifact:
            raise CaseReferenceError("resolved resource has no retained case artifact/byte receipt")
        if artifact.get("byte_state") != "BYTES_VERIFIED_HASHED":
            raise CaseReferenceError("resolved resource artifact bytes are not verified")
        artifact_sha = str(artifact.get("sha256") or "")
        if not valid_sha256(artifact_sha):
            raise CaseReferenceError("resolved resource artifact lacks a valid SHA-256")
        if not valid_sha256(byte_sha) or byte_sha != artifact_sha:
            raise CaseReferenceError("reference byte SHA-256 does not match retained artifact bytes")
        current.update({
            "resolution": resolution,
            "source_object_state": "VERIFIED_SOURCE_OBJECT",
            "resource_id": rid,
            "byte_state": "BYTES_VERIFIED_HASHED",
            "byte_sha256": byte_sha,
        })

    elif resolution == "SUPERSEDED_BY":
        successor = str(decision.get("successor_resource_id") or "")
        source_id = str(decision.get("supersession_source_id") or "")
        if not successor or successor not in resources:
            raise CaseReferenceError("supersession successor is not present in retained manifest evidence")
        if not source_id or source_id not in {str(x.get("source_id")) for x in result.get("sources") or []}:
            raise CaseReferenceError("supersession source is not retained in case sources")
        current.update({
            "resolution": resolution,
            "successor_resource_id": successor,
            "supersession_source_id": source_id,
            "source_object_state": str(decision.get("source_object_state") or "UNRESOLVED_SOURCE_OBJECT"),
            "byte_state": str(decision.get("byte_state") or "BYTES_UNAVAILABLE_AT_OBSERVATION"),
        })

    else:
        url = str(decision.get("url") or "").strip()
        reason = str(decision.get("reason") or "").strip()
        byte_state = str(decision.get("byte_state") or "").upper()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CaseReferenceError("external dependency requires an absolute HTTP(S) URL")
        if byte_state not in {"BYTES_EXTERNAL_DEPENDENCY", "BYTES_RESTRICTED"}:
            raise CaseReferenceError("external dependency requires an explicit external/restricted byte state")
        current.update({
            "resolution": resolution,
            "source_object_state": str(decision.get("source_object_state") or "VERIFIED_SOURCE_OBJECT"),
            "byte_state": byte_state,
            "url": url,
            "reason": reason,
        })

    current["resolution_review"] = review
    refs[idx] = current
    packet["references"] = refs
    result["packet"] = packet

    _, findings = validate_reference_closure(packet)
    target_path = f"packet.references[{idx}]"
    target_errors = sorted({
        f.code for f in findings
        if f.severity == "BLOCK" and (f.path == target_path or not str(f.path or "").startswith("packet.references["))
    })
    if target_errors:
        raise CaseReferenceError(f"reference resolution failed closure validation: {target_errors}")

    remaining = [
        str(ref.get("reference_id"))
        for ref in refs
        if str(ref.get("resolution") or "UNRESOLVED").upper() == "UNRESOLVED"
    ]
    closure_verdict, _ = validate_reference_closure(packet)
    return result, {
        "status": "REFERENCE_RESOLUTION_APPLIED",
        "reference_id": reference_id,
        "resolution": resolution,
        "decision_sha256": review["decision_sha256"],
        "remaining_unresolved_reference_ids": remaining,
        "reference_closure": closure_verdict,
    }
