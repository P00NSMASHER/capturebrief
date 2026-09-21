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
_BARE = re.compile(r"(?<![A-Za-z0-9.])(?P<citation>\d{1,3}\.\d{3}(?:-\d+)?)(?![A-Za-z0-9-]|\.\d)")
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
    if rule_candidate_review_is_current(case):
        return None
    proposal = case["packet"]["rule_candidate_proposal"]
    if not (proposal.get("matches") or []):
        return None
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


REVIEW_CONTRACT = "capturebrief-rule-candidate-review-v1"
_REVIEW_DECISIONS = {"TRACK_VERSION", "UNRESOLVED", "IGNORE"}


def confirm_rule_candidate_review(
    proposal: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    """Human-confirm a citation proposal without deciding rule applicability."""
    if proposal.get("contract") != CONTRACT or proposal.get("status") != "PROPOSED":
        raise ValueError("rule candidate proposal contract is invalid")
    proposal_body = {k: v for k, v in proposal.items() if k != "proposal_sha256"}
    if digest(canonical(proposal_body)) != proposal.get("proposal_sha256"):
        raise ValueError("rule candidate proposal digest mismatch")

    reviewer = review.get("reviewer")
    reviewed_at = review.get("reviewed_at")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("reviewer is required")
    if not isinstance(reviewed_at, str):
        raise ValueError("reviewed_at is required")
    try:
        dt = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("reviewed_at must be ISO-8601") from exc
    if dt.tzinfo is None:
        raise ValueError("reviewed_at must be timezone-aware")

    matches = {
        row["occurrence_id"]: row
        for row in proposal.get("matches") or []
        if isinstance(row, dict) and row.get("occurrence_id")
    }
    decisions = review.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("decisions must be a list")

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for row in decisions:
        if not isinstance(row, dict):
            raise ValueError("review decision must be an object")
        occurrence_id = str(row.get("occurrence_id") or "")
        if occurrence_id not in matches:
            raise ValueError(f"unknown occurrence_id {occurrence_id}")
        if occurrence_id in seen:
            raise ValueError(f"duplicate decision for {occurrence_id}")
        seen.add(occurrence_id)

        decision = str(row.get("decision") or "").upper()
        if decision not in _REVIEW_DECISIONS:
            raise ValueError(f"invalid decision for {occurrence_id}")
        reason = row.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"review reason required for {occurrence_id}")

        match = matches[occurrence_id]
        candidate_map = {
            str(candidate.get("rule_source_id")): candidate
            for candidate in match.get("candidate_versions") or []
            if candidate.get("rule_source_id")
        }
        selected = None
        if decision == "TRACK_VERSION":
            selected_id = str(row.get("selected_rule_source_id") or "")
            if selected_id not in candidate_map:
                raise ValueError(
                    f"selected rule version for {occurrence_id} must come from the proposal"
                )
            selected = copy.deepcopy(candidate_map[selected_id])
        elif row.get("selected_rule_source_id") not in (None, ""):
            raise ValueError(
                f"{decision} decision for {occurrence_id} cannot select a rule version"
            )

        normalized.append({
            "occurrence_id": occurrence_id,
            "source_id": match.get("source_id"),
            "line": match.get("line"),
            "mention": match.get("mention"),
            "citation": match.get("citation"),
            "decision": decision,
            "reason": reason.strip(),
            "selected_rule": selected,
            "applicability": "UNRESOLVED",
            "applicability_authoritative": False,
            "can_auto_apply": False,
        })

    missing = sorted(set(matches) - seen)
    if missing:
        raise ValueError(
            "every rule citation occurrence requires a human decision: "
            + ",".join(missing)
        )

    normalized.sort(key=lambda x: x["occurrence_id"])
    payload = {
        "contract": REVIEW_CONTRACT,
        "status": "COMPLETE",
        "review_mode": "HUMAN_CONFIRMED",
        "proposal_sha256": proposal["proposal_sha256"],
        "reviewer": reviewer.strip(),
        "reviewed_at": reviewed_at,
        "decisions": normalized,
        "tracked_rule_source_ids": sorted({
            row["selected_rule"]["rule_source_id"]
            for row in normalized
            if row.get("selected_rule")
        }),
        "applicability_authoritative": False,
        "can_auto_apply": False,
    }
    return {**payload, "review_sha256": digest(canonical(payload))}


def attach_rule_candidate_review(
    case: dict[str, Any],
    review: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not rule_candidate_proposal_is_current(case):
        raise ValueError("case does not contain a current rule candidate proposal")
    proposal = case["packet"]["rule_candidate_proposal"]
    result_review = confirm_rule_candidate_review(proposal, review)
    result = copy.deepcopy(case)
    result.setdefault("packet", {})["rule_candidate_review"] = result_review
    return result, {
        "status": "RULE_CANDIDATE_REVIEW_ATTACHED",
        "review_sha256": result_review["review_sha256"],
        "tracked_rule_source_ids": result_review["tracked_rule_source_ids"],
        "applicability_authoritative": False,
        "can_auto_apply": False,
    }


def rule_candidate_review_is_current(case: dict[str, Any]) -> bool:
    if not rule_candidate_proposal_is_current(case):
        return False
    packet = case.get("packet") or {}
    proposal = packet.get("rule_candidate_proposal") or {}
    review = packet.get("rule_candidate_review")
    if not isinstance(review, dict):
        return False
    if (
        review.get("contract") != REVIEW_CONTRACT
        or review.get("status") != "COMPLETE"
        or review.get("review_mode") != "HUMAN_CONFIRMED"
        or review.get("proposal_sha256") != proposal.get("proposal_sha256")
        or review.get("applicability_authoritative") is not False
        or review.get("can_auto_apply") is not False
    ):
        return False
    review_body = {k: v for k, v in review.items() if k != "review_sha256"}
    if digest(canonical(review_body)) != review.get("review_sha256"):
        return False
    expected = {
        row.get("occurrence_id")
        for row in proposal.get("matches") or []
        if row.get("occurrence_id")
    }
    actual = {
        row.get("occurrence_id")
        for row in review.get("decisions") or []
        if isinstance(row, dict) and row.get("occurrence_id")
    }
    if expected != actual:
        return False
    return all(
        row.get("applicability") == "UNRESOLVED"
        and row.get("applicability_authoritative") is False
        and row.get("can_auto_apply") is False
        for row in review.get("decisions") or []
        if isinstance(row, dict)
    )


def tracked_rule_versions(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Return human-selected source versions as context, never applicability."""
    if not rule_candidate_review_is_current(case):
        return []
    out = []
    for row in case["packet"]["rule_candidate_review"]["decisions"]:
        if row.get("decision") != "TRACK_VERSION" or not row.get("selected_rule"):
            continue
        out.append({
            "occurrence_id": row["occurrence_id"],
            "citation": row["citation"],
            "reason": row["reason"],
            "selected_rule": copy.deepcopy(row["selected_rule"]),
            "applicability": "UNRESOLVED",
            "can_auto_apply": False,
        })
    return out


_AUTO_SYNC_SOURCE = {
    "FAR": "gsa-far-dita",
    "DFARS": "gsa-dfars-dita",
}


def _lookup_candidate_versions(
    registry_path: str | Path,
    *,
    citation: str,
    namespace_hint: str | None,
    namespace_hint_basis: str | None,
) -> tuple[list[dict[str, Any]], bool]:
    candidates = list_rule_versions(
        registry_path,
        citation=citation,
        namespace=namespace_hint if namespace_hint in {"FAR", "DFARS"} else None,
    )
    fallback = False
    if not candidates and namespace_hint_basis == "NUMBER_RANGE_HEURISTIC":
        candidates = list_rule_versions(registry_path, citation=citation)
        fallback = True
    rows = [
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
    return rows, fallback


def refresh_rule_candidate_proposal(
    registry_path: str | Path,
    proposal: dict[str, Any],
) -> dict[str, Any]:
    """Re-run only registry matching while preserving the original text extraction."""
    if proposal.get("contract") != CONTRACT or proposal.get("status") != "PROPOSED":
        raise ValueError("rule candidate proposal contract is invalid")
    body = {k: v for k, v in proposal.items() if k != "proposal_sha256"}
    if digest(canonical(body)) != proposal.get("proposal_sha256"):
        raise ValueError("rule candidate proposal digest mismatch")

    refreshed: list[dict[str, Any]] = []
    for old in proposal.get("matches") or []:
        candidates, fallback = _lookup_candidate_versions(
            registry_path,
            citation=str(old.get("citation") or ""),
            namespace_hint=old.get("namespace_hint"),
            namespace_hint_basis=old.get("namespace_hint_basis"),
        )
        namespaces = sorted({row["namespace"] for row in candidates})
        row = {
            key: copy.deepcopy(value)
            for key, value in old.items()
            if key not in {
                "candidate_count",
                "candidate_namespaces",
                "ambiguous_namespace",
                "candidate_versions",
                "namespace_fallback_used",
            }
        }
        row.update({
            "namespace_fallback_used": fallback,
            "candidate_count": len(candidates),
            "candidate_namespaces": namespaces,
            "ambiguous_namespace": len(namespaces) > 1,
            "candidate_versions": candidates,
            "can_auto_select_version": False,
            "can_auto_apply": False,
        })
        refreshed.append(row)

    payload = {
        "contract": CONTRACT,
        "status": "PROPOSED",
        "extraction_sha256": proposal["extraction_sha256"],
        "captured_by": proposal["captured_by"],
        "observed_at": proposal["observed_at"],
        "matches": refreshed,
        "review_required": bool(refreshed),
        "can_auto_select_version": False,
        "can_auto_apply": False,
        "refreshed_from_proposal_sha256": proposal["proposal_sha256"],
    }
    return {**payload, "proposal_sha256": digest(canonical(payload))}


def rule_sync_work_items(case: dict[str, Any]) -> list[dict[str, Any]]:
    if not rule_candidate_proposal_is_current(case):
        return []
    proposal = case["packet"]["rule_candidate_proposal"]
    needed = {}
    for row in proposal.get("matches") or []:
        namespace = row.get("namespace_hint")
        citation = row.get("citation")
        if row.get("candidate_count") != 0:
            continue
        source_id = _AUTO_SYNC_SOURCE.get(namespace)
        if source_id and isinstance(citation, str):
            needed[(namespace, citation)] = source_id
    if not needed:
        return []
    entries = [
        {"namespace": ns, "citation": citation, "source_id": source_id}
        for (ns, citation), source_id in sorted(needed.items())
    ]
    return [{
        "task_key": "rules:sync-missing-pinned-sources",
        "priority": "P0",
        "title": "Sync missing FAR/DFARS rules from pinned GSA sources",
        "actor": "AUTOMATED_APPROVED_SOURCE",
        "can_auto_execute": True,
        "status": "OPEN",
        "reason": "The citation proposal contains FAR/DFARS references with no local pinned rule version. Exact-revision GSA sync can fill this lookup gap without deciding applicability.",
        "evidence_needed": "Fetch only the catalog-pinned GSA DITA revision, refresh the candidate proposal, then require human version/applicability review.",
        "metadata": {
            "proposal_sha256": proposal["proposal_sha256"],
            "rules": entries,
            "can_auto_apply": False,
            "refresh_required_after_sync": True,
        },
    }]


def sync_missing_rule_candidates_for_case(
    case: dict[str, Any],
    registry_path: str | Path,
    catalog_path: str | Path,
    *,
    observed_at: str,
    fetcher=None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Sync only missing FAR/DFARS candidates and refresh the bound proposal.

    Registry writes may be partially complete if a later network fetch fails,
    but the case itself is not updated until all requested syncs finish. Re-run
    is safe because registry insertion is content-addressed/idempotent.
    """
    if not rule_candidate_proposal_is_current(case):
        raise ValueError("case does not contain a current rule candidate proposal")
    proposal = case["packet"]["rule_candidate_proposal"]
    needed = {}
    for row in proposal.get("matches") or []:
        namespace = row.get("namespace_hint")
        citation = row.get("citation")
        if row.get("candidate_count") != 0:
            continue
        source_id = _AUTO_SYNC_SOURCE.get(namespace)
        if source_id and isinstance(citation, str):
            needed[(namespace, citation)] = source_id

    if not needed:
        return copy.deepcopy(case), {
            "status": "NO_MISSING_PINNED_RULES",
            "proposal_sha256": proposal["proposal_sha256"],
            "synced": [],
            "case_changed": False,
            "can_auto_apply": False,
        }

    from .rule_sync import sync_pinned_gsa_rule

    synced = []
    for (namespace, citation), source_id in sorted(needed.items()):
        result = sync_pinned_gsa_rule(
            registry_path,
            catalog_path,
            source_id=source_id,
            citation=citation,
            observed_at=observed_at,
            fetcher=fetcher,
        )
        synced.append({
            "namespace": namespace,
            "citation": citation,
            "source_id": source_id,
            "registry_result": result["registry_result"],
            "rule_source_id": result["rule_source_id"],
            "edition": result["edition"],
            "source_revision": result["source_revision"],
            "fetch_receipt": copy.deepcopy(result["fetch_receipt"]),
        })

    refreshed = refresh_rule_candidate_proposal(registry_path, proposal)
    result_case = copy.deepcopy(case)
    packet = result_case.setdefault("packet", {})
    packet.setdefault("rule_candidate_proposal_history", []).append(copy.deepcopy(proposal))
    packet["rule_candidate_proposal"] = refreshed

    stale_review = packet.pop("rule_candidate_review", None)
    review_invalidated = stale_review is not None
    if stale_review is not None:
        packet.setdefault("rule_candidate_review_history", []).append(stale_review)

    return result_case, {
        "status": "MISSING_PINNED_RULES_SYNCED",
        "previous_proposal_sha256": proposal["proposal_sha256"],
        "proposal_sha256": refreshed["proposal_sha256"],
        "synced": synced,
        "review_invalidated": review_invalidated,
        "case_changed": True,
        "can_auto_apply": False,
    }
