from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from .model import canonical_json, parse_dt, sha256_hex, valid_sha256

REFERENCE_PROPOSAL_VERSION = "capturebrief-reference-proposal-v1"
REFERENCE_REVIEW_VERSION = "capturebrief-reference-review-v1"
CANDIDATE_DECISIONS = {"TRACK", "IGNORE_NOT_DEPENDENCY"}

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AMENDMENT", re.compile(r"\b(?:amendment|amend\.?)\s*(?:no\.?|number|#)?\s*0*\d{1,4}\b", re.I)),
    ("ATTACHMENT", re.compile(r"\battachment\s*(?:no\.?|number|#)?\s*\(?[A-Z0-9][A-Z0-9._-]*\)?", re.I)),
    ("EXHIBIT", re.compile(r"\bexhibit\s*(?:no\.?|number|#)?\s*[A-Z0-9][A-Z0-9._-]*\b", re.I)),
    ("APPENDIX", re.compile(r"\bappendix\s+[A-Z0-9][A-Z0-9._-]*\b", re.I)),
    ("ANNEX", re.compile(r"\bannex\s+[A-Z0-9][A-Z0-9._-]*\b", re.I)),
    ("ENCLOSURE", re.compile(r"\benclosure\s*(?:no\.?|number|#)?\s*\(?[A-Z0-9][A-Z0-9._-]*\)?", re.I)),
    ("SCHEDULE", re.compile(r"\bschedule\s+[A-Z](?:\b|[-\d])", re.I)),
    ("DRAWING", re.compile(r"\bdrawings?\s*(?:no\.?|number|#)?\s*[A-Z0-9][A-Z0-9._/-]*\b", re.I)),
    ("EXTERNAL_SYSTEM", re.compile(r"\b(?:PIEE|FedConnect|GSA\s+eBuy|eBuy|DIBBS)\b", re.I)),
    ("EXTERNAL_URL", re.compile(r"https?://[^\s<>\]\)\"']+", re.I)),
)


class ReferenceReviewError(ValueError):
    pass


def _label(text: str) -> str:
    return " ".join(text.split()).strip(" ,.;:")


def _candidate_id(source_id: str, kind: str, label: str) -> str:
    token = sha256_hex(f"{source_id}|{kind}|{label.upper()}")
    return f"cand-{token[:16]}"


def _excerpt(text: str, start: int, end: int, *, radius: int = 90) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return " ".join(text[left:right].split())


def propose_reference_scan(
    sources: Iterable[dict[str, Any]],
    *,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Propose named dependencies from already-retrieved public text.

    This function can never claim completeness. Regex findings are candidate prompts for a
    human reviewer, not source authority and not evidence that an artifact is required.
    """
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    if not parse_dt(observed_at):
        raise ValueError("observed_at must be timezone-aware ISO-8601")

    source_rows: list[dict[str, Any]] = []
    candidates: dict[str, dict[str, Any]] = {}
    seen_sources: set[str] = set()

    for i, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError(f"sources[{i}] is not an object")
        source_id = str(source.get("source_id") or "").strip()
        text = source.get("text")
        if not source_id or source_id in seen_sources:
            raise ValueError(f"sources[{i}] has a missing or duplicate source_id")
        if not isinstance(text, str):
            raise ValueError(f"sources[{i}] text must be a string")
        seen_sources.add(source_id)
        text_sha = sha256_hex(text)
        declared = source.get("content_sha256")
        if declared is not None and declared != text_sha:
            raise ValueError(f"sources[{i}] content_sha256 does not match text")
        source_rows.append({
            "source_id": source_id,
            "content_sha256": text_sha,
            "characters": len(text),
        })

        for kind, pattern in _PATTERNS:
            for match in pattern.finditer(text):
                label = _label(match.group(0))
                if kind == "EXTERNAL_URL" and "sam.gov/" in label.lower():
                    continue
                cid = _candidate_id(source_id, kind, label)
                occurrence = {
                    "start": match.start(),
                    "end": match.end(),
                    "excerpt": _excerpt(text, match.start(), match.end()),
                }
                if cid not in candidates:
                    candidates[cid] = {
                        "candidate_id": cid,
                        "source_id": source_id,
                        "kind": kind,
                        "label": label,
                        "occurrences": [],
                    }
                candidates[cid]["occurrences"].append(occurrence)

    payload = {
        "parser_version": REFERENCE_PROPOSAL_VERSION,
        "sources": source_rows,
        "candidates": sorted(candidates.values(), key=lambda x: (x["source_id"], x["kind"], x["label"].upper())),
        "automatic_completeness_claim": False,
    }
    return {
        "status": "PROPOSED",
        "observed_at": observed_at,
        "parser_version": REFERENCE_PROPOSAL_VERSION,
        "automation_mode": "LOCAL_PROPOSAL_ONLY",
        "can_claim_completeness": False,
        "proposal_sha256": sha256_hex(canonical_json(payload)),
        "payload": payload,
    }


def _proposal_verified(proposal: dict[str, Any]) -> bool:
    if proposal.get("status") != "PROPOSED":
        return False
    if proposal.get("parser_version") != REFERENCE_PROPOSAL_VERSION:
        return False
    if proposal.get("can_claim_completeness") is not False:
        return False
    digest = proposal.get("proposal_sha256")
    return bool(valid_sha256(digest) and isinstance(proposal.get("payload"), dict)
                and sha256_hex(canonical_json(proposal["payload"])) == digest)


def _reference_id(seed: str) -> str:
    return f"ref-{sha256_hex(seed)[:16]}"


def confirm_reference_scan(
    proposal: dict[str, Any],
    review: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Convert a proposal into a COMPLETE human-confirmed scan plus unresolved references."""
    if not _proposal_verified(proposal):
        raise ReferenceReviewError("reference proposal is not internally verified")
    if not isinstance(review, dict):
        raise ReferenceReviewError("review must be an object")

    reviewer = str(review.get("reviewer") or "").strip()
    reviewed_at = str(review.get("reviewed_at") or "").strip()
    if not reviewer:
        raise ReferenceReviewError("reviewer is required")
    if not parse_dt(reviewed_at):
        raise ReferenceReviewError("reviewed_at must be timezone-aware ISO-8601")
    if review.get("attests_complete") is not True:
        raise ReferenceReviewError("human reviewer must explicitly attest complete source review")

    proposal_payload = proposal["payload"]
    source_ids = {str(x["source_id"]) for x in proposal_payload.get("sources", [])}
    reviewed_source_ids = {str(x) for x in review.get("reviewed_source_ids", []) if str(x)}
    if reviewed_source_ids != source_ids:
        raise ReferenceReviewError("reviewed_source_ids must exactly cover proposal sources")

    candidates = {
        str(x.get("candidate_id")): x
        for x in proposal_payload.get("candidates", [])
        if x.get("candidate_id")
    }
    decisions: dict[str, dict[str, Any]] = {}
    for i, decision in enumerate(review.get("candidate_decisions") or []):
        cid = str(decision.get("candidate_id") or "")
        action = str(decision.get("decision") or "").upper()
        if cid not in candidates or cid in decisions:
            raise ReferenceReviewError(f"candidate_decisions[{i}] references an unknown or duplicate candidate")
        if action not in CANDIDATE_DECISIONS:
            raise ReferenceReviewError(f"candidate_decisions[{i}] has invalid decision")
        if action == "IGNORE_NOT_DEPENDENCY" and not str(decision.get("reason") or "").strip():
            raise ReferenceReviewError(f"candidate_decisions[{i}] ignore decision requires reason")
        decisions[cid] = {
            "candidate_id": cid,
            "decision": action,
            "reason": str(decision.get("reason") or "").strip() or None,
        }
    if set(decisions) != set(candidates):
        missing = sorted(set(candidates) - set(decisions))
        raise ReferenceReviewError(f"every proposed candidate must be decided; missing {missing}")

    references: list[dict[str, Any]] = []
    for cid in sorted(candidates):
        if decisions[cid]["decision"] != "TRACK":
            continue
        candidate = candidates[cid]
        rid = _reference_id(f"candidate|{cid}")
        references.append({
            "reference_id": rid,
            "label": candidate.get("label"),
            "reference_kind": candidate.get("kind"),
            "origin_source_ids": [candidate.get("source_id")],
            "proposal_candidate_id": cid,
            "resolution": "UNRESOLVED",
            "source_object_state": "UNRESOLVED_SOURCE_OBJECT",
            "byte_state": "BYTES_NOT_YET_CHECKED",
        })

    manual_rows: list[dict[str, Any]] = []
    for i, addition in enumerate(review.get("manual_additions") or []):
        label = _label(str(addition.get("label") or ""))
        kind = str(addition.get("kind") or "MANUAL").upper()
        source_id = str(addition.get("source_id") or "")
        reason = str(addition.get("reason") or "").strip()
        if not label or source_id not in source_ids or not reason:
            raise ReferenceReviewError(f"manual_additions[{i}] requires label, reviewed source_id, and reason")
        rid = _reference_id(f"manual|{source_id}|{kind}|{label.upper()}")
        manual = {
            "reference_id": rid,
            "label": label,
            "reference_kind": kind,
            "origin_source_ids": [source_id],
            "manual_addition": True,
            "manual_reason": reason,
            "resolution": "UNRESOLVED",
            "source_object_state": "UNRESOLVED_SOURCE_OBJECT",
            "byte_state": "BYTES_NOT_YET_CHECKED",
        }
        if any(x["reference_id"] == rid for x in references):
            raise ReferenceReviewError(f"manual_additions[{i}] duplicates an existing reference")
        references.append(manual)
        manual_rows.append({
            "reference_id": rid,
            "label": label,
            "kind": kind,
            "source_id": source_id,
            "reason": reason,
        })

    references.sort(key=lambda x: x["reference_id"])
    reference_ids = [x["reference_id"] for x in references]
    scan_payload = {
        "proposal_sha256": proposal["proposal_sha256"],
        "proposal_payload": proposal_payload,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "attests_complete": True,
        "reviewed_source_ids": sorted(reviewed_source_ids),
        "candidate_decisions": [decisions[cid] for cid in sorted(decisions)],
        "manual_additions": manual_rows,
        "tracked_reference_ids": reference_ids,
    }
    scan = {
        "status": "COMPLETE",
        "scan_sha256": sha256_hex(canonical_json(scan_payload)),
        "parser_version": REFERENCE_REVIEW_VERSION,
        "review_mode": "HUMAN_CONFIRMED",
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "coverage_attestation": True,
        "proposal_sha256": proposal["proposal_sha256"],
        "reference_set_sha256": sha256_hex(canonical_json(reference_ids)),
        "payload": scan_payload,
    }
    return scan, references
