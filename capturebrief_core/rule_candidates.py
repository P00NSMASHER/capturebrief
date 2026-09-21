"""Conservative FAR/DFARS citation candidate discovery for CaptureBrief.

This module reduces lookup work. It never selects the controlling rule version,
decides applicability, or turns a citation mention into a finding.
"""
from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .rule_registry import canonical, digest, list_rule_versions

CONTRACT = "capturebrief-rule-candidate-proposal-v1"
_EXPLICIT = re.compile(
    r"\b(?P<ns>FAR|DFARS)\s*(?:§|SECTION|CLAUSE|SUBPART|PART)?\s*"
    r"(?P<citation>\d{1,3}\.\d+(?:-\d+)?)\b",
    re.I,
)
_BARE = re.compile(r"(?<![A-Za-z0-9.])(?P<citation>\d{1,3}\.\d{3}(?:-\d+)?)(?![A-Za-z0-9.-])")
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _context(text: str, start: int, end: int, radius: int = 100) -> str:
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    return " ".join(text[lo:hi].split())


def _namespace_hint(citation: str) -> tuple[str | None, str]:
    """Return conservative namespace hint for a bare citation.

    FAR occupies parts <= 53; DFARS uses 2xx numbering. This is only a search
    hint and is explicitly non-authoritative.
    """
    try:
        major = int(citation.split(".", 1)[0])
    except (ValueError, AttributeError):
        return None, "NONE"
    if 1 <= major <= 53:
        return "FAR", "NUMBER_RANGE_HEURISTIC"
    if 200 <= major <= 299:
        return "DFARS", "NUMBER_RANGE_HEURISTIC"
    return None, "NONE"


def extract_rule_citations(
    sources: list[dict[str, Any]],
    *,
    captured_by: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(captured_by, str) or not captured_by.strip():
        raise ValueError("captured_by is required")
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware")

    occurrences: list[dict[str, Any]] = []
    source_receipts: list[dict[str, Any]] = []
    for item in sources:
        if not isinstance(item, dict):
            raise ValueError("source inputs must be objects")
        source_id = str(item.get("source_id") or "")
        text = item.get("text")
        document_sha = item.get("document_sha256")
        if not source_id or not isinstance(text, str) or not text.strip():
            raise ValueError("source_id and non-empty text are required")
        if not isinstance(document_sha, str) or not _SHA.fullmatch(document_sha):
            raise ValueError("document_sha256 must be supplied from the retained case source")
        text_sha = digest(text)
        source_receipts.append({
            "source_id": source_id,
            "document_sha256": document_sha,
            "text_sha256": text_sha,
            "characters": len(text),
        })

        consumed: list[tuple[int, int]] = []
        for match in _EXPLICIT.finditer(text):
            namespace = match.group("ns").upper()
            citation = match.group("citation")
            consumed.append(match.span())
            occurrences.append({
                "occurrence_id": "RULEMENTION:" + digest(canonical({
                    "source_id": source_id,
                    "text_sha256": text_sha,
                    "start": match.start(),
                    "end": match.end(),
                    "namespace": namespace,
                    "citation": citation,
                })),
                "source_id": source_id,
                "document_sha256": document_sha,
                "text_sha256": text_sha,
                "line": _line_number(text, match.start()),
                "span_start": match.start(),
                "span_end": match.end(),
                "mention": match.group(0),
                "citation": citation,
                "namespace_hint": namespace,
                "namespace_hint_basis": "EXPLICIT_PREFIX",
                "context": _context(text, match.start(), match.end()),
            })

        def overlaps(span: tuple[int, int]) -> bool:
            return any(span[0] < used[1] and span[1] > used[0] for used in consumed)

        for match in _BARE.finditer(text):
            if overlaps(match.span()):
                continue
            citation = match.group("citation")
            namespace, basis = _namespace_hint(citation)
            occurrences.append({
                "occurrence_id": "RULEMENTION:" + digest(canonical({
                    "source_id": source_id,
                    "text_sha256": text_sha,
                    "start": match.start(),
                    "end": match.end(),
                    "namespace": namespace,
                    "citation": citation,
                })),
                "source_id": source_id,
                "document_sha256": document_sha,
                "text_sha256": text_sha,
                "line": _line_number(text, match.start()),
                "span_start": match.start(),
                "span_end": match.end(),
                "mention": match.group(0),
                "citation": citation,
                "namespace_hint": namespace,
                "namespace_hint_basis": basis,
                "context": _context(text, match.start(), match.end()),
            })

    occurrences.sort(key=lambda x: (x["source_id"], x["span_start"], x["occurrence_id"]))
    payload = {
        "contract": CONTRACT,
        "status": "EXTRACTED",
        "captured_by": captured_by,
        "observed_at": observed_at,
        "sources": sorted(source_receipts, key=lambda x: x["source_id"]),
        "occurrences": occurrences,
        "automatic_completeness_claim": False,
        "can_auto_select_version": False,
        "can_auto_apply": False,
    }
    return {**payload, "extraction_sha256": digest(canonical(payload))}


def match_rule_versions(
    registry_path: str | Path,
    extraction: dict[str, Any],
) -> dict[str, Any]:
    if extraction.get("contract") != CONTRACT or extraction.get("status") != "EXTRACTED":
        raise ValueError("citation extraction contract is invalid")
    body = {k: v for k, v in extraction.items() if k != "extraction_sha256"}
    if digest(canonical(body)) != extraction.get("extraction_sha256"):
        raise ValueError("citation extraction digest mismatch")

    matches: list[dict[str, Any]] = []
    for occ in extraction.get("occurrences") or []:
        citation = occ.get("citation")
        namespace = occ.get("namespace_hint")
        candidates = list_rule_versions(
            registry_path,
            citation=citation,
            namespace=namespace if namespace in {"FAR", "DFARS"} else None,
        )
        # If a heuristic namespace yielded zero candidates, fall back to citation-
        # only lookup and expose the ambiguity instead of silently discarding it.
        fallback = False
        if not candidates and occ.get("namespace_hint_basis") == "NUMBER_RANGE_HEURISTIC":
            candidates = list_rule_versions(registry_path, citation=citation)
            fallback = True
        candidate_rows = [
            {
                "rule_source_id": row["rule_source_id"],
                "rule_key": row["rule_key"],
                "namespace": row["namespace"],
                "citation": row["citation"],
                "agency": row["agency"],
                "edition": row["edition"],
                "observed_at": row["observed_at"],
                "effective_from": row.get("effective_from"),
                "effective_until": row.get("effective_until"),
                "source_repository": row["source_repository"],
                "source_revision": row["source_revision"],
                "source_path": row["source_path"],
                "source_sha256": row["source_sha256"],
            }
            for row in candidates
        ]
        namespaces = sorted({row["namespace"] for row in candidate_rows})
        matches.append({
            "occurrence_id": occ["occurrence_id"],
            "source_id": occ["source_id"],
            "line": occ["line"],
            "mention": occ["mention"],
            "citation": citation,
            "namespace_hint": namespace,
            "namespace_hint_basis": occ.get("namespace_hint_basis"),
            "namespace_fallback_used": fallback,
            "context": occ["context"],
            "candidate_count": len(candidate_rows),
            "candidate_namespaces": namespaces,
            "ambiguous_namespace": len(namespaces) > 1,
            "candidate_versions": candidate_rows,
            "can_auto_select_version": False,
            "can_auto_apply": False,
        })

    payload = {
        "contract": CONTRACT,
        "status": "PROPOSED",
        "extraction_sha256": extraction["extraction_sha256"],
        "captured_by": extraction["captured_by"],
        "observed_at": extraction["observed_at"],
        "matches": matches,
        "review_required": bool(matches),
        "can_auto_select_version": False,
        "can_auto_apply": False,
    }
    return {**payload, "proposal_sha256": digest(canonical(payload))}


def attach_rule_candidate_proposal(
    case: dict[str, Any],
    registry_path: str | Path,
    source_texts: list[dict[str, Any]],
    *,
    captured_by: str,
    observed_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Attach a proposal only when source IDs/hashes are bound to the case."""
    case_sources = {
        str(row.get("source_id")): row
        for row in case.get("sources") or []
        if isinstance(row, dict) and row.get("source_id")
    }
    bound: list[dict[str, Any]] = []
    for row in source_texts:
        source_id = str(row.get("source_id") or "")
        source = case_sources.get(source_id)
        if source is None:
            raise ValueError(f"source {source_id} is not retained in the case")
        if source.get("artifact_state") != "PUBLIC":
            raise ValueError(f"source {source_id} is not public")
        doc_sha = source.get("content_sha256")
        if not isinstance(doc_sha, str) or not _SHA.fullmatch(doc_sha):
            raise ValueError(f"source {source_id} lacks a valid retained document SHA-256")
        bound.append({
            "source_id": source_id,
            "document_sha256": doc_sha,
            "text": row.get("text"),
        })

    extraction = extract_rule_citations(bound, captured_by=captured_by, observed_at=observed_at)
    proposal = match_rule_versions(registry_path, extraction)
    result = copy.deepcopy(case)
    result.setdefault("packet", {})["rule_candidate_proposal"] = proposal
    return result, {
        "status": "RULE_CANDIDATE_PROPOSAL_ATTACHED",
        "proposal_sha256": proposal["proposal_sha256"],
        "occurrences": len(proposal["matches"]),
        "can_auto_select_version": False,
        "can_auto_apply": False,
    }


def rule_candidate_proposal_is_current(case: dict[str, Any]) -> bool:
    proposal = (case.get("packet") or {}).get("rule_candidate_proposal")
    if not isinstance(proposal, dict) or proposal.get("contract") != CONTRACT or proposal.get("status") != "PROPOSED":
        return False
    if proposal.get("can_auto_select_version") is not False or proposal.get("can_auto_apply") is not False:
        return False
    body = {k: v for k, v in proposal.items() if k != "proposal_sha256"}
    return digest(canonical(body)) == proposal.get("proposal_sha256")


def rule_candidate_work_item(case: dict[str, Any]) -> dict[str, Any] | None:
    if not rule_candidate_proposal_is_current(case):
        return None
    proposal = case["packet"]["rule_candidate_proposal"]
    unmatched = sum(row.get("candidate_count", 0) == 0 for row in proposal.get("matches") or [])
    ambiguous = sum(
        row.get("ambiguous_namespace") is True or row.get("candidate_count", 0) > 1
        for row in proposal.get("matches") or []
    )
    return {
        "task_key": "rules:review-candidates",
        "priority": "P1",
        "title": "Review FAR/DFARS citation and version candidates",
        "actor": "HUMAN_REVIEW",
        "can_auto_execute": False,
        "reason": "Local extraction found rule citations and candidate pinned versions. Citation presence/version matches do not establish controlling edition or applicability.",
        "evidence_needed": "Reviewer selects the relevant edition or leaves it unresolved, cites the solicitation/incorporation basis, and records applicability separately in Decision Evidence.",
        "metadata": {
            "proposal_sha256": proposal["proposal_sha256"],
            "occurrences": len(proposal.get("matches") or []),
            "unmatched_occurrences": unmatched,
            "ambiguous_occurrences": ambiguous,
            "can_auto_select_version": False,
            "can_auto_apply": False,
        },
        "status": "OPEN",
    }
