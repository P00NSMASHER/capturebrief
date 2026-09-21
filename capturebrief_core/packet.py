from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from .model import Finding, canonical_json, parse_dt, sha256_hex, valid_sha256
from .references import CANDIDATE_DECISIONS, REFERENCE_REVIEW_VERSION

REFERENCE_RESOLUTIONS = {"RESOLVED_TO_RESOURCE", "SUPERSEDED_BY", "EXTERNAL_DEPENDENCY", "UNRESOLVED"}
SOURCE_OBJECT_STATES = {"VERIFIED_SOURCE_OBJECT", "INFERRED_SOURCE_OBJECT", "UNRESOLVED_SOURCE_OBJECT"}
BYTE_STATES = {
    "BYTES_VERIFIED_HASHED",
    "BYTES_RESTRICTED",
    "BYTES_EXTERNAL_DEPENDENCY",
    "BYTES_UNAVAILABLE_AT_OBSERVATION",
    "BYTES_NOT_YET_CHECKED",
}


def _resources(receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("resource_id")): item
        for item in receipt.get("items", [])
        if item.get("resource_id")
    }


def diff_manifest_receipts(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """Diff two complete observations without treating filename as identity.

    Resource ID is source identity. Filename and content hash are attributes. A later complete
    observation that omits a prior resource produces a disappearance event instead of erasing
    history. Same-name/different-resource replacement is surfaced explicitly.
    """
    events: list[dict[str, Any]] = []
    b = _resources(before)
    a = _resources(after)

    for rid in sorted(set(b) | set(a)):
        old, new = b.get(rid), a.get(rid)
        if old is None:
            events.append({"type": "ADDED", "resource_id": rid, "name": new.get("name")})
            continue
        if new is None:
            events.append({"type": "DISAPPEARED_AFTER_COMPLETE_OBSERVATION", "resource_id": rid, "name": old.get("name")})
            continue
        if old.get("artifact_state") != new.get("artifact_state"):
            if new.get("artifact_state") == "DELETED":
                etype = "EXPLICITLY_DELETED"
            elif old.get("artifact_state") in {"PUBLIC", "EXTERNAL"} and new.get("artifact_state") in {"RESTRICTED", "EXPORT_CONTROLLED", "UNAVAILABLE"}:
                etype = "ACCESS_RESTRICTED"
            else:
                etype = "RESOURCE_STATE_CHANGED"
            events.append({"type": etype, "resource_id": rid, "before": old.get("artifact_state"), "after": new.get("artifact_state")})
        tracked = ("name", "declared_size", "mime_type", "file_exists", "posted_at")
        if any(old.get(k) != new.get(k) for k in tracked):
            events.append({"type": "RESOURCE_METADATA_CHANGED", "resource_id": rid, "before": {k: old.get(k) for k in tracked}, "after": {k: new.get(k) for k in tracked}})

    # Same presentation name, new source identity: do not collapse into overwrite.
    old_by_name: dict[str, set[str]] = defaultdict(set)
    new_by_name: dict[str, set[str]] = defaultdict(set)
    for rid, item in b.items():
        if item.get("name") and item.get("artifact_state") != "DELETED":
            old_by_name[str(item["name"])].add(rid)
    for rid, item in a.items():
        if item.get("name") and item.get("artifact_state") != "DELETED":
            new_by_name[str(item["name"])].add(rid)
    for name in sorted(set(old_by_name) & set(new_by_name)):
        removed = old_by_name[name] - new_by_name[name]
        added = new_by_name[name] - old_by_name[name]
        if removed and added:
            events.append({"type": "REPLACED_SAME_FILENAME", "name": name, "prior_resource_ids": sorted(removed), "new_resource_ids": sorted(added)})

    return events


def build_resource_union(receipts: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build an append-only source-object union across action-bound manifest observations."""
    observations: list[dict[str, Any]] = []
    by_resource: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for receipt in receipts:
        action_id = str(receipt.get("action_id", ""))
        observed_at = receipt.get("observed_at")
        manifest_hash = receipt.get("raw_manifest_sha256")
        for item in receipt.get("items", []):
            rid = str(item.get("resource_id", ""))
            if not rid:
                continue
            observation = {
                "action_id": action_id,
                "observed_at": observed_at,
                "manifest_sha256": manifest_hash,
                "resource_id": rid,
                "name": item.get("name"),
                "artifact_state": item.get("artifact_state"),
                "declared_size": item.get("declared_size"),
                "mime_type": item.get("mime_type"),
                "raw_sha256": item.get("raw_sha256"),
            }
            observations.append(observation)
            by_resource[rid].append(observation)
    return {
        "observations": observations,
        "resource_ids": sorted(by_resource),
        "union_sha256": sha256_hex(canonical_json(observations)),
    }


def validate_reference_closure(packet: dict[str, Any]) -> tuple[str, list[Finding]]:
    """Validate semantic closure of named/incorporated packet dependencies.

    A manifest can be technically complete while the notice tells offerors to use a named
    artifact that is absent. Every extracted reference must resolve to a verified source
    object plus bytes, a source-backed supersession, or an explicit non-public dependency.
    """
    findings: list[Finding] = []
    scan = packet.get("reference_scan") or {}
    if scan.get("status") != "COMPLETE":
        findings.append(Finding("REFERENCE_SCAN_UNRESOLVED", "BLOCK", "Semantic reference extraction/scan is not complete.", "packet.reference_scan"))
        return "REFERENCE_CLOSURE_UNRESOLVED", findings
    scan_digest = scan.get("scan_sha256")
    if not valid_sha256(scan_digest):
        findings.append(Finding("REFERENCE_SCAN_HASH_INVALID", "BLOCK", "Reference scan lacks a valid immutable digest.", "packet.reference_scan.scan_sha256"))
    elif scan.get("payload") is not None and sha256_hex(canonical_json(scan.get("payload"))) != scan_digest:
        findings.append(Finding("REFERENCE_SCAN_PAYLOAD_MISMATCH", "BLOCK", "Reference scan payload does not match its immutable digest.", "packet.reference_scan"))
    elif scan.get("payload") is None and not (scan.get("payload_hash_verified") is True and scan.get("snapshot_ref")):
        findings.append(Finding("REFERENCE_SCAN_PAYLOAD_UNVERIFIED", "BLOCK", "Reference scan digest is not bound to retained payload evidence.", "packet.reference_scan"))
    if not scan.get("parser_version"):
        findings.append(Finding("REFERENCE_SCAN_PARSER_MISSING", "BLOCK", "Reference scan must identify the extraction/parser version.", "packet.reference_scan.parser_version"))
    elif scan.get("parser_version") != REFERENCE_REVIEW_VERSION:
        findings.append(Finding("REFERENCE_SCAN_REVIEW_VERSION_INVALID", "BLOCK", "Complete reference scan must use the pinned human-review contract version.", "packet.reference_scan.parser_version"))
    if scan.get("review_mode") != "HUMAN_CONFIRMED":
        findings.append(Finding("REFERENCE_SCAN_NOT_HUMAN_CONFIRMED", "BLOCK", "Automated reference proposals cannot claim complete semantic coverage.", "packet.reference_scan.review_mode"))
    if scan.get("coverage_attestation") is not True:
        findings.append(Finding("REFERENCE_SCAN_COVERAGE_UNATTESTED", "BLOCK", "Complete reference scan requires explicit human coverage attestation.", "packet.reference_scan.coverage_attestation"))
    if not str(scan.get("reviewer") or "").strip():
        findings.append(Finding("REFERENCE_SCAN_REVIEWER_MISSING", "BLOCK", "Complete reference scan must identify the reviewer.", "packet.reference_scan.reviewer"))
    if not parse_dt(scan.get("reviewed_at")):
        findings.append(Finding("REFERENCE_SCAN_REVIEW_TIME_INVALID", "BLOCK", "Complete reference scan requires a timezone-aware review timestamp.", "packet.reference_scan.reviewed_at"))
    if not valid_sha256(scan.get("proposal_sha256")):
        findings.append(Finding("REFERENCE_SCAN_PROPOSAL_HASH_INVALID", "BLOCK", "Complete reference scan must bind to a verified proposal digest.", "packet.reference_scan.proposal_sha256"))

    scan_payload = scan.get("payload") if isinstance(scan.get("payload"), dict) else {}
    proposal_payload = scan_payload.get("proposal_payload")
    if not isinstance(proposal_payload, dict) or sha256_hex(canonical_json(proposal_payload)) != scan.get("proposal_sha256"):
        findings.append(Finding("REFERENCE_SCAN_PROPOSAL_PAYLOAD_MISMATCH", "BLOCK", "Human review is not bound to the exact automated proposal payload.", "packet.reference_scan.payload"))
    else:
        proposal_sources = {str(x.get("source_id")) for x in proposal_payload.get("sources", []) if isinstance(x, dict) and x.get("source_id")}
        reviewed_sources = {str(x) for x in scan_payload.get("reviewed_source_ids", []) if str(x)}
        if reviewed_sources != proposal_sources:
            findings.append(Finding("REFERENCE_SCAN_SOURCE_COVERAGE_MISMATCH", "BLOCK", "Human-reviewed source IDs do not exactly cover the proposal source set.", "packet.reference_scan.payload.reviewed_source_ids"))
        candidates = {str(x.get("candidate_id")) for x in proposal_payload.get("candidates", []) if isinstance(x, dict) and x.get("candidate_id")}
        decisions = scan_payload.get("candidate_decisions")
        if not isinstance(decisions, list):
            findings.append(Finding("REFERENCE_SCAN_DECISIONS_MISSING", "BLOCK", "Human review must retain a decision for every proposal candidate.", "packet.reference_scan.payload.candidate_decisions"))
        else:
            decision_ids: set[str] = set()
            for j, decision in enumerate(decisions):
                dpath = f"packet.reference_scan.payload.candidate_decisions[{j}]"
                if not isinstance(decision, dict):
                    findings.append(Finding("REFERENCE_SCAN_DECISION_INVALID", "BLOCK", "Reference decision is not an object.", dpath)); continue
                cid = str(decision.get("candidate_id") or "")
                action = str(decision.get("decision") or "").upper()
                if not cid or cid in decision_ids or action not in CANDIDATE_DECISIONS:
                    findings.append(Finding("REFERENCE_SCAN_DECISION_INVALID", "BLOCK", "Reference candidate decision is missing, duplicated, or invalid.", dpath))
                if action == "IGNORE_NOT_DEPENDENCY" and not str(decision.get("reason") or "").strip():
                    findings.append(Finding("REFERENCE_SCAN_IGNORE_REASON_MISSING", "BLOCK", "Ignored proposal candidates require a retained reviewer reason.", dpath))
                decision_ids.add(cid)
            if decision_ids != candidates:
                findings.append(Finding("REFERENCE_SCAN_CANDIDATE_COVERAGE_MISMATCH", "BLOCK", "Human decisions do not exactly cover every automated reference candidate.", "packet.reference_scan.payload.candidate_decisions"))
        if scan_payload.get("attests_complete") is not True:
            findings.append(Finding("REFERENCE_SCAN_PAYLOAD_ATTESTATION_MISSING", "BLOCK", "Retained review payload does not attest complete source review.", "packet.reference_scan.payload"))
        if scan_payload.get("reviewer") != scan.get("reviewer") or scan_payload.get("reviewed_at") != scan.get("reviewed_at"):
            findings.append(Finding("REFERENCE_SCAN_REVIEW_METADATA_MISMATCH", "BLOCK", "Top-level review metadata differs from the retained review payload.", "packet.reference_scan"))

    resource_ids = set()
    for receipt in packet.get("manifest_receipts") or []:
        resource_ids.update(_resources(receipt))
    artifacts = {
        str(item.get("artifact_id")): item
        for item in packet.get("artifacts") or []
        if item.get("artifact_id")
    }

    references = packet.get("references") or []
    reference_ids = sorted(str(ref.get("reference_id")) for ref in references if ref.get("reference_id"))
    reference_set_digest = sha256_hex(canonical_json(reference_ids))
    if not valid_sha256(scan.get("reference_set_sha256")) or scan.get("reference_set_sha256") != reference_set_digest:
        findings.append(Finding("REFERENCE_SET_HASH_MISMATCH", "BLOCK", "Case reference IDs are not exactly bound to the human-confirmed scan.", "packet.reference_scan.reference_set_sha256"))
    tracked_ids = sorted(str(x) for x in scan_payload.get("tracked_reference_ids", []) if str(x))
    if tracked_ids != reference_ids:
        findings.append(Finding("REFERENCE_SET_TRACKED_IDS_MISMATCH", "BLOCK", "Retained review payload tracked-reference IDs differ from the case reference set.", "packet.reference_scan.payload.tracked_reference_ids"))

    seen: set[str] = set()
    for i, ref in enumerate(references):
        path = f"packet.references[{i}]"
        ref_id = str(ref.get("reference_id", ""))
        if not ref_id or ref_id in seen:
            findings.append(Finding("REFERENCE_ID_INVALID", "BLOCK", "Reference ID is missing or duplicated.", path))
        seen.add(ref_id)
        resolution = str(ref.get("resolution", "UNRESOLVED")).upper()
        source_state = str(ref.get("source_object_state", "UNRESOLVED_SOURCE_OBJECT")).upper()
        byte_state = str(ref.get("byte_state", "BYTES_NOT_YET_CHECKED")).upper()
        if resolution not in REFERENCE_RESOLUTIONS:
            findings.append(Finding("REFERENCE_RESOLUTION_INVALID", "BLOCK", "Reference has an invalid resolution state.", path))
            continue
        if source_state not in SOURCE_OBJECT_STATES:
            findings.append(Finding("REFERENCE_SOURCE_STATE_INVALID", "BLOCK", "Reference has an invalid source-object state.", path))
        if byte_state not in BYTE_STATES:
            findings.append(Finding("REFERENCE_BYTE_STATE_INVALID", "BLOCK", "Reference has an invalid artifact-byte state.", path))

        if resolution == "UNRESOLVED":
            findings.append(Finding("REFERENCED_ARTIFACT_UNRESOLVED", "BLOCK", f"Referenced dependency remains unresolved: {ref.get('label') or ref_id}.", path))
            continue
        if resolution == "RESOLVED_TO_RESOURCE":
            rid = str(ref.get("resource_id", ""))
            if source_state != "VERIFIED_SOURCE_OBJECT" or not rid or rid not in resource_ids:
                findings.append(Finding("REFERENCE_RESOURCE_NOT_VERIFIED", "BLOCK", "Resolved reference is not bound to a verified manifest resource.", path))
            if byte_state != "BYTES_VERIFIED_HASHED":
                findings.append(Finding("REFERENCE_BYTES_NOT_VERIFIED", "BLOCK", "Controlling referenced public artifact does not have verified hashed bytes.", path))
            if byte_state == "BYTES_VERIFIED_HASHED" and not valid_sha256(ref.get("byte_sha256")):
                findings.append(Finding("REFERENCE_BYTE_HASH_INVALID", "BLOCK", "Verified byte state requires a valid SHA-256 digest.", path))
            artifact = artifacts.get(rid)
            if artifact is None:
                findings.append(Finding("REFERENCE_ARTIFACT_RECEIPT_MISSING", "BLOCK", "Resolved reference is not bound to a retained case artifact/byte receipt.", path))
            else:
                artifact_sha = artifact.get("sha256")
                if artifact.get("byte_state") != "BYTES_VERIFIED_HASHED" or not valid_sha256(artifact_sha):
                    findings.append(Finding("REFERENCE_ARTIFACT_BYTES_NOT_VERIFIED", "BLOCK", "Resolved reference artifact does not carry verified hashed bytes.", path))
                elif ref.get("byte_sha256") != artifact_sha:
                    findings.append(Finding("REFERENCE_ARTIFACT_HASH_MISMATCH", "BLOCK", "Reference byte hash does not match the retained case artifact hash.", path))
        elif resolution == "SUPERSEDED_BY":
            successor = str(ref.get("successor_resource_id", ""))
            if not successor or successor not in resource_ids:
                findings.append(Finding("REFERENCE_SUCCESSOR_NOT_VERIFIED", "BLOCK", "Supersession successor is not a verified manifest resource.", path))
            if not ref.get("supersession_source_id"):
                findings.append(Finding("REFERENCE_SUPERSESSION_UNSOURCED", "BLOCK", "Supersession requires explicit source evidence.", path))
        elif resolution == "EXTERNAL_DEPENDENCY":
            if byte_state not in {"BYTES_EXTERNAL_DEPENDENCY", "BYTES_RESTRICTED"}:
                findings.append(Finding("REFERENCE_EXTERNAL_BYTE_STATE_INVALID", "BLOCK", "External/restricted dependency must retain an explicit non-public byte state.", path))
            if not ref.get("url") or not ref.get("reason"):
                findings.append(Finding("REFERENCE_EXTERNAL_DEPENDENCY_INCOMPLETE", "BLOCK", "External dependency must include URL and reason.", path))

    verdict = "REFERENCE_CLOSURE_COMPLETE" if not any(x.severity == "BLOCK" for x in findings) else "REFERENCE_CLOSURE_UNRESOLVED"
    return verdict, findings
