from __future__ import annotations

import copy
import re
from collections import defaultdict
from typing import Any

from .model import canonical_json, sha256_hex
from .packet import build_resource_union

REFERENCE_MATCH_VERSION = "capturebrief-reference-match-v1"
_TOKEN = re.compile(r"[A-Z0-9]+")
_NUMBER = re.compile(r"\d+")

_SYNONYMS = {
    "AMEND": "AMENDMENT",
    "AMD": "AMENDMENT",
    "ATTACH": "ATTACHMENT",
    "ATT": "ATTACHMENT",
    "APP": "APPENDIX",
}


class ReferenceMatchError(RuntimeError):
    pass


def _tokenize(value: Any) -> list[str]:
    raw = str(value or "").upper()
    tokens: list[str] = []
    for token in _TOKEN.findall(raw):
        token = _SYNONYMS.get(token, token)
        if token.isdigit():
            token = str(int(token))
        tokens.append(token)
    return tokens


def _numbers(value: Any) -> set[str]:
    return {str(int(x)) for x in _NUMBER.findall(str(value or ""))}


def _resource_catalog(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    packet = case.get("packet") or {}
    union = build_resource_union(packet.get("manifest_receipts") or [])
    observations = union.get("observations") or []
    by_id: dict[str, dict[str, Any]] = {}
    for obs in observations:
        rid = str(obs.get("resource_id") or "")
        if not rid:
            continue
        row = by_id.setdefault(rid, {
            "resource_id": rid,
            "names": set(),
            "action_ids": set(),
            "artifact_states": set(),
            "declared_sizes": set(),
            "mime_types": set(),
            "observations": 0,
        })
        if obs.get("name"):
            row["names"].add(str(obs["name"]))
        if obs.get("action_id"):
            row["action_ids"].add(str(obs["action_id"]))
        if obs.get("artifact_state"):
            row["artifact_states"].add(str(obs["artifact_state"]))
        if obs.get("declared_size") is not None:
            row["declared_sizes"].add(obs.get("declared_size"))
        if obs.get("mime_type"):
            row["mime_types"].add(str(obs.get("mime_type")))
        row["observations"] += 1

    artifacts = {
        str(a.get("artifact_id")): a
        for a in packet.get("artifacts") or []
        if a.get("artifact_id")
    }
    for rid, row in by_id.items():
        artifact = artifacts.get(rid) or {}
        row["byte_state"] = artifact.get("byte_state")
        row["sha256"] = artifact.get("sha256")
        row["required_for_analysis"] = artifact.get("required_for_analysis") is True
        row["resource_url"] = artifact.get("resource_url")
    return by_id


def _score(reference: dict[str, Any], resource: dict[str, Any]) -> tuple[int, list[str]]:
    label = str(reference.get("label") or "")
    ref_tokens = _tokenize(label)
    ref_set = set(ref_tokens)
    ref_numbers = _numbers(label)
    if not ref_tokens:
        return 0, []

    best = 0
    reasons: list[str] = []
    for name in sorted(resource.get("names") or []):
        name_tokens = _tokenize(name)
        name_set = set(name_tokens)
        name_numbers = _numbers(name)
        score = 0
        local: list[str] = []

        if ref_tokens == name_tokens:
            score = 100
            local.append("EXACT_NORMALIZED_NAME")
        elif len(ref_tokens) >= 2 and all(token in name_set for token in ref_set):
            score = max(score, 82)
            local.append("REFERENCE_TOKENS_CONTAINED")
        else:
            overlap = len(ref_set & name_set)
            union = len(ref_set | name_set)
            if union:
                jaccard = overlap / union
                if jaccard >= 0.75:
                    score = max(score, 70)
                    local.append("HIGH_TOKEN_OVERLAP")
                elif jaccard >= 0.5:
                    score = max(score, 55)
                    local.append("MEDIUM_TOKEN_OVERLAP")
                elif overlap:
                    score = max(score, 25)
                    local.append("PARTIAL_TOKEN_OVERLAP")

        if ref_numbers:
            if ref_numbers == name_numbers:
                score += 12
                local.append("NUMBER_ANCHOR_MATCH")
            elif name_numbers and ref_numbers.isdisjoint(name_numbers):
                score -= 45
                local.append("NUMBER_ANCHOR_CONFLICT")

        if score > best:
            best = score
            reasons = local

    # Exact retained external URL is a strong retrieval cue, still not an auto-resolution.
    label_url = label.strip()
    if label_url.startswith(("http://", "https://")) and resource.get("resource_url") == label_url:
        best = max(best, 100)
        reasons = ["EXACT_RESOURCE_URL"]

    return max(best, 0), reasons


def propose_reference_matches(case: dict[str, Any]) -> dict[str, Any]:
    """Rank retained resource candidates for human review without changing closure state."""
    packet = case.get("packet") or {}
    scan = packet.get("reference_scan") or {}
    if scan.get("status") != "COMPLETE" or scan.get("review_mode") != "HUMAN_CONFIRMED":
        raise ReferenceMatchError("reference matching requires a COMPLETE HUMAN_CONFIRMED inventory")

    resources = _resource_catalog(case)
    matches: list[dict[str, Any]] = []
    for ref in packet.get("references") or []:
        if str(ref.get("resolution") or "UNRESOLVED").upper() != "UNRESOLVED":
            continue
        scored: list[dict[str, Any]] = []
        for rid, resource in resources.items():
            score, reasons = _score(ref, resource)
            if score < 25:
                continue
            states = sorted(resource.get("artifact_states") or [])
            risk_flags: list[str] = []
            if "DELETED" in states:
                risk_flags.append("DELETED_OR_TOMBSTONED")
            if any(state in {"RESTRICTED","EXPORT_CONTROLLED","UNAVAILABLE"} for state in states):
                risk_flags.append("NONPUBLIC_OR_UNAVAILABLE")
            scored.append({
                "resource_id": rid,
                "score": score,
                "match_reasons": reasons,
                "names": sorted(resource.get("names") or []),
                "action_ids": sorted(resource.get("action_ids") or []),
                "artifact_states": states,
                "declared_sizes": sorted(resource.get("declared_sizes") or []),
                "mime_types": sorted(resource.get("mime_types") or []),
                "byte_state": resource.get("byte_state"),
                "sha256": resource.get("sha256"),
                "risk_flags": risk_flags,
            })
        scored.sort(key=lambda x: (-x["score"], x["resource_id"]))
        top = scored[0]["score"] if scored else None
        top_count = sum(item["score"] == top for item in scored) if top is not None else 0

        # Same presentation name across multiple resource IDs is explicitly ambiguous.
        same_name_groups: dict[str, list[str]] = defaultdict(list)
        for item in scored:
            for name in item["names"]:
                same_name_groups[" ".join(_tokenize(name))].append(item["resource_id"])
        same_name_ambiguity = sorted({
            rid
            for ids in same_name_groups.values() if len(set(ids)) > 1
            for rid in ids
        })

        matches.append({
            "reference_id": ref.get("reference_id"),
            "label": ref.get("label"),
            "reference_kind": ref.get("reference_kind"),
            "candidate_count": len(scored),
            "top_score": top,
            "ambiguous_top_score": top_count > 1,
            "same_name_ambiguity_resource_ids": same_name_ambiguity,
            "candidates": scored[:12],
            "can_auto_resolve": False,
        })

    payload = {
        "contract": REFERENCE_MATCH_VERSION,
        "reference_scan_sha256": scan.get("scan_sha256"),
        "reference_set_sha256": scan.get("reference_set_sha256"),
        "resource_union_sha256": build_resource_union(packet.get("manifest_receipts") or []).get("union_sha256"),
        "matches": matches,
        "can_auto_resolve": False,
    }
    return {
        **payload,
        "proposal_sha256": sha256_hex(canonical_json(payload)),
    }


def reference_match_proposal_is_current(case: dict[str, Any], proposal: dict[str, Any] | None = None) -> bool:
    packet = case.get("packet") or {}
    scan = packet.get("reference_scan") or {}
    proposal = proposal if proposal is not None else packet.get("reference_match_proposal")
    if not isinstance(proposal, dict):
        return False
    if proposal.get("contract") != REFERENCE_MATCH_VERSION or proposal.get("can_auto_resolve") is not False:
        return False
    digest = proposal.get("proposal_sha256")
    if not isinstance(digest, str):
        return False
    body = {k: v for k, v in proposal.items() if k != "proposal_sha256"}
    if sha256_hex(canonical_json(body)) != digest:
        return False
    if proposal.get("reference_scan_sha256") != scan.get("scan_sha256"):
        return False
    if proposal.get("reference_set_sha256") != scan.get("reference_set_sha256"):
        return False
    union_sha = build_resource_union(packet.get("manifest_receipts") or []).get("union_sha256")
    return proposal.get("resource_union_sha256") == union_sha


def attach_reference_match_proposal(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    result = copy.deepcopy(case)
    proposal = propose_reference_matches(result)
    result.setdefault("packet", {})["reference_match_proposal"] = proposal
    return result, {
        "status": "REFERENCE_MATCH_PROPOSAL_ATTACHED",
        "proposal_sha256": proposal["proposal_sha256"],
        "references_proposed": len(proposal["matches"]),
        "can_auto_resolve": False,
    }
