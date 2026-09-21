"""Bind prepared rule evidence to a specific bid assumption by human review.

This is the only stage in the rule pipeline that writes a rule applicability
link into Decision Evidence. It requires a separate solicitation/amendment
basis passage for positive/negative applicability decisions and never changes
the buyer-facing assumption state by itself.
"""
from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from .decision_trace import canonical, digest
from .rule_evidence import (
    prepared_rule_evidence,
    rule_evidence_preparation_is_current,
)

CONTRACT = "capturebrief-rule-applicability-review-v1"
_APPLICABILITY = {"APPLIES", "DOES_NOT_APPLY", "UNRESOLVED"}
_BASES = {
    "INCORPORATED_EDITION",
    "SOLICITATION_TEXT",
    "AMENDMENT_TEXT",
    "EFFECTIVE_DATE_REVIEW",
    "DEVIATION_REVIEW",
    "UNRESOLVED",
}
_ALLOWED_BASIS_KINDS = {"SOLICITATION", "AMENDMENT", "CONTEXT"}


def _aware_time(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _trace_maps(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    trace = case.get("decision_trace")
    if not isinstance(trace, dict):
        raise ValueError("Decision Evidence trace must exist before rule applicability review")
    if trace.get("schema_version") != "1.0" or trace.get("family_id") != case.get("family_id"):
        raise ValueError("Decision Evidence trace schema/family is invalid")
    assumptions = {
        str(row.get("assumption_id")): row
        for row in case.get("assumptions") or []
        if isinstance(row, dict) and row.get("assumption_id")
    }
    reviews: dict[str, Any] = {}
    for row in trace.get("reviews") or []:
        if not isinstance(row, dict) or not row.get("assumption_id"):
            continue
        aid = str(row["assumption_id"])
        if aid in reviews:
            raise ValueError(f"duplicate Decision Evidence review for assumption {aid}")
        reviews[aid] = row
    snapshots = {
        str(row.get("snapshot_id")): row
        for row in trace.get("snapshots") or []
        if isinstance(row, dict) and row.get("snapshot_id")
    }
    return assumptions, reviews, snapshots


def _validate_basis_passage(
    passage: dict[str, Any] | None,
    snapshots: dict[str, Any],
    *,
    forbidden_snapshot_id: str,
    required: bool,
) -> dict[str, Any] | None:
    if passage is None:
        if required:
            raise ValueError("resolved applicability requires a solicitation/amendment basis passage")
        return None
    if not isinstance(passage, dict):
        raise ValueError("basis_passage must be an exact Decision Evidence passage")
    snapshot_id = str(passage.get("snapshot_id") or "")
    if snapshot_id == forbidden_snapshot_id:
        raise ValueError("rule text cannot be its own solicitation-specific applicability basis")
    snapshot = snapshots.get(snapshot_id)
    if snapshot is None:
        raise ValueError("basis_passage references an unknown Decision Evidence snapshot")
    if required and snapshot.get("kind") not in _ALLOWED_BASIS_KINDS:
        raise ValueError("resolved applicability basis must come from solicitation/amendment/context evidence")
    lines = str(snapshot.get("text") or "").splitlines()
    start, end = passage.get("line_start"), passage.get("line_end")
    if (
        type(start) is not int
        or type(end) is not int
        or start < 1
        or end < start
        or end > len(lines)
    ):
        raise ValueError("basis_passage line range is invalid")
    if not isinstance(passage.get("locator"), str) or not passage["locator"].strip():
        raise ValueError("basis_passage requires a human-readable locator")
    expected = "\n".join(lines[start - 1 : end])
    if passage.get("quote") != expected:
        raise ValueError("basis_passage quote does not exactly match retained source text")
    return copy.deepcopy(passage)


def review_rule_applicability(
    case: dict[str, Any],
    review: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Human-bind every prepared rule occurrence to an assumption/applicability."""
    if not rule_evidence_preparation_is_current(case):
        raise ValueError("case does not contain current prepared rule evidence")
    prepared = {
        str(row["occurrence_id"]): row
        for row in prepared_rule_evidence(case)
        if row.get("occurrence_id")
    }
    assumptions, trace_reviews, snapshots = _trace_maps(case)

    reviewed_by = review.get("reviewed_by")
    reviewed_at = review.get("reviewed_at")
    if not isinstance(reviewed_by, str) or not reviewed_by.strip():
        raise ValueError("reviewed_by is required")
    if not _aware_time(reviewed_at):
        raise ValueError("reviewed_at must be timezone-aware ISO-8601")
    decisions = review.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("decisions must be a list")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row in decisions:
        if not isinstance(row, dict):
            raise ValueError("rule applicability decision must be an object")
        occurrence_id = str(row.get("occurrence_id") or "")
        if occurrence_id not in prepared:
            raise ValueError(f"unknown prepared rule occurrence {occurrence_id}")
        if occurrence_id in seen:
            raise ValueError(f"duplicate applicability decision for {occurrence_id}")
        seen.add(occurrence_id)

        assumption_id = str(row.get("assumption_id") or "")
        if assumption_id not in assumptions:
            raise ValueError(f"unknown assumption {assumption_id}")
        if assumption_id not in trace_reviews:
            raise ValueError(
                f"Decision Evidence review must exist for assumption {assumption_id}"
            )

        applicability = str(row.get("applicability") or "").upper()
        if applicability not in _APPLICABILITY:
            raise ValueError(f"invalid applicability for {occurrence_id}")
        basis = str(row.get("basis") or "").upper()
        if basis not in _BASES:
            raise ValueError(f"invalid applicability basis for {occurrence_id}")
        if applicability != "UNRESOLVED" and basis == "UNRESOLVED":
            raise ValueError("resolved applicability cannot use UNRESOLVED basis")
        if applicability == "UNRESOLVED" and basis != "UNRESOLVED":
            # A reviewer may have partial evidence, but an unresolved decision must
            # not be made to look resolved through a named deterministic basis.
            raise ValueError("UNRESOLVED applicability must use UNRESOLVED basis")

        rationale = row.get("rationale")
        scope_rationale = row.get("scope_rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(f"applicability rationale required for {occurrence_id}")
        if not isinstance(scope_rationale, str) or not scope_rationale.strip():
            raise ValueError(f"rule scope rationale required for {occurrence_id}")

        item = prepared[occurrence_id]
        rule_version = item["rule_version"]
        rule_snapshot = item["snapshot"]
        incorporated_edition = row.get("incorporated_edition")
        if basis == "INCORPORATED_EDITION":
            if incorporated_edition != rule_version.get("edition"):
                raise ValueError(
                    "INCORPORATED_EDITION basis must name the exact prepared rule edition"
                )
        elif incorporated_edition not in (None, ""):
            raise ValueError(
                "incorporated_edition is only valid with INCORPORATED_EDITION basis"
            )

        basis_passage = _validate_basis_passage(
            row.get("basis_passage"),
            snapshots,
            forbidden_snapshot_id=rule_snapshot["snapshot_id"],
            required=applicability != "UNRESOLVED",
        )

        normalized.append({
            "occurrence_id": occurrence_id,
            "assumption_id": assumption_id,
            "rule_version_id": rule_version["rule_version_id"],
            "selected_rule_source_id": item["selected_rule_source_id"],
            "applicability": applicability,
            "basis": basis,
            "incorporated_edition": incorporated_edition or None,
            "rationale": rationale.strip(),
            "scope_rationale": scope_rationale.strip(),
            "basis_passage": basis_passage,
            "applicability_authoritative": False,
            "human_reviewed": True,
            "can_auto_apply": False,
        })

    missing = sorted(set(prepared) - seen)
    if missing:
        raise ValueError(
            "every prepared rule occurrence requires one applicability decision: "
            + ",".join(missing)
        )

    result = copy.deepcopy(case)
    trace = result["decision_trace"]
    trace_snapshots = {
        str(row.get("snapshot_id")): row
        for row in trace.setdefault("snapshots", [])
        if isinstance(row, dict) and row.get("snapshot_id")
    }
    trace_rules = {
        str(row.get("rule_version_id")): row
        for row in trace.setdefault("rule_versions", [])
        if isinstance(row, dict) and row.get("rule_version_id")
    }
    review_map = {
        str(row.get("assumption_id")): row
        for row in trace.setdefault("reviews", [])
        if isinstance(row, dict) and row.get("assumption_id")
    }

    for decision in normalized:
        item = prepared[decision["occurrence_id"]]
        snapshot = item["snapshot"]
        rule_version = item["rule_version"]

        existing_snapshot = trace_snapshots.get(snapshot["snapshot_id"])
        if existing_snapshot is None:
            trace["snapshots"].append(copy.deepcopy(snapshot))
            trace_snapshots[snapshot["snapshot_id"]] = snapshot
        elif canonical(existing_snapshot) != canonical(snapshot):
            raise ValueError("Decision Evidence snapshot ID collision")

        existing_rule = trace_rules.get(rule_version["rule_version_id"])
        if existing_rule is None:
            trace["rule_versions"].append(copy.deepcopy(rule_version))
            trace_rules[rule_version["rule_version_id"]] = rule_version
        elif canonical(existing_rule) != canonical(rule_version):
            raise ValueError("Decision Evidence rule-version ID collision")

        target = review_map[decision["assumption_id"]]
        existing_links = target.setdefault("rule_links", [])
        link = {
            "rule_version_id": decision["rule_version_id"],
            "family_id": result["family_id"],
            "applicability": decision["applicability"],
            "basis": decision["basis"],
            "incorporated_edition": decision["incorporated_edition"],
            "rationale": decision["rationale"],
            "basis_passage": copy.deepcopy(decision["basis_passage"]),
        }
        same_rule = [
            x for x in existing_links
            if isinstance(x, dict)
            and x.get("rule_version_id") == decision["rule_version_id"]
        ]
        if same_rule:
            if len(same_rule) != 1 or canonical(same_rule[0]) != canonical(link):
                raise ValueError(
                    "existing Decision Evidence rule link differs; preserve prior "
                    "decision history instead of rewriting it in place"
                )
        else:
            existing_links.append(link)

        scope = target.get("rule_scope")
        desired_scope = {
            "status": "REQUIRED",
            "rationale": decision["scope_rationale"],
        }
        if (
            isinstance(scope, dict)
            and scope.get("status") == "REQUIRED"
            and target.get("rule_links")
            and scope != desired_scope
            and len(target["rule_links"]) > 1
        ):
            raise ValueError("existing multi-rule scope rationale cannot be silently rewritten")
        target["rule_scope"] = desired_scope

    normalized.sort(key=lambda x: x["occurrence_id"])
    prep = result["packet"]["rule_evidence_preparation"]
    payload = {
        "contract": CONTRACT,
        "status": "COMPLETE",
        "preparation_sha256": prep["preparation_sha256"],
        "reviewed_by": reviewed_by.strip(),
        "reviewed_at": reviewed_at,
        "decisions": normalized,
        "human_reviewed": True,
        "can_auto_apply": False,
        "assumption_state_changed": False,
    }
    application = {
        **payload,
        "applicability_review_sha256": digest(canonical(payload)),
    }
    packet = result.setdefault("packet", {})
    old = packet.get("rule_applicability_review")
    if old is not None:
        packet.setdefault("rule_applicability_review_history", []).append(old)
    packet["rule_applicability_review"] = application

    return result, {
        "status": "RULE_APPLICABILITY_REVIEW_ATTACHED",
        "preparation_sha256": prep["preparation_sha256"],
        "applicability_review_sha256": application["applicability_review_sha256"],
        "bound_occurrences": [row["occurrence_id"] for row in normalized],
        "assumption_ids": sorted({row["assumption_id"] for row in normalized}),
        "human_reviewed": True,
        "can_auto_apply": False,
        "assumption_state_changed": False,
    }


def rule_applicability_review_is_current(case: dict[str, Any]) -> bool:
    if not rule_evidence_preparation_is_current(case):
        return False
    packet = case.get("packet") or {}
    prep = packet.get("rule_evidence_preparation") or {}
    application = packet.get("rule_applicability_review")
    if not isinstance(application, dict):
        return False
    if (
        application.get("contract") != CONTRACT
        or application.get("status") != "COMPLETE"
        or application.get("preparation_sha256") != prep.get("preparation_sha256")
        or application.get("human_reviewed") is not True
        or application.get("can_auto_apply") is not False
        or application.get("assumption_state_changed") is not False
    ):
        return False
    body = {
        k: v for k, v in application.items()
        if k != "applicability_review_sha256"
    }
    if digest(canonical(body)) != application.get("applicability_review_sha256"):
        return False

    try:
        _, reviews, snapshots = _trace_maps(case)
    except ValueError:
        return False
    prepared = {
        str(row["occurrence_id"]): row
        for row in prepared_rule_evidence(case)
        if row.get("occurrence_id")
    }
    decisions = {
        str(row.get("occurrence_id")): row
        for row in application.get("decisions") or []
        if isinstance(row, dict) and row.get("occurrence_id")
    }
    if set(decisions) != set(prepared):
        return False

    trace = case["decision_trace"]
    trace_snaps = {
        str(row.get("snapshot_id")): row
        for row in trace.get("snapshots") or []
        if isinstance(row, dict) and row.get("snapshot_id")
    }
    trace_rules = {
        str(row.get("rule_version_id")): row
        for row in trace.get("rule_versions") or []
        if isinstance(row, dict) and row.get("rule_version_id")
    }

    for occurrence_id, decision in decisions.items():
        if (
            decision.get("human_reviewed") is not True
            or decision.get("applicability_authoritative") is not False
            or decision.get("can_auto_apply") is not False
            or decision.get("applicability") not in _APPLICABILITY
        ):
            return False
        item = prepared[occurrence_id]
        if trace_snaps.get(item["snapshot"]["snapshot_id"]) != item["snapshot"]:
            return False
        if trace_rules.get(item["rule_version"]["rule_version_id"]) != item["rule_version"]:
            return False
        target = reviews.get(str(decision.get("assumption_id")))
        if target is None:
            return False
        expected_link = {
            "rule_version_id": decision["rule_version_id"],
            "family_id": case.get("family_id"),
            "applicability": decision["applicability"],
            "basis": decision["basis"],
            "incorporated_edition": decision.get("incorporated_edition"),
            "rationale": decision["rationale"],
            "basis_passage": decision.get("basis_passage"),
        }
        links = [
            row for row in target.get("rule_links") or []
            if isinstance(row, dict)
            and row.get("rule_version_id") == decision["rule_version_id"]
        ]
        if len(links) != 1 or links[0] != expected_link:
            return False
        if target.get("rule_scope") != {
            "status": "REQUIRED",
            "rationale": decision["scope_rationale"],
        }:
            return False
        if decision["applicability"] != "UNRESOLVED":
            try:
                _validate_basis_passage(
                    decision.get("basis_passage"),
                    snapshots,
                    forbidden_snapshot_id=item["snapshot"]["snapshot_id"],
                    required=True,
                )
            except ValueError:
                return False
    return True


def rule_applicability_work_item(case: dict[str, Any]) -> dict[str, Any] | None:
    if not rule_evidence_preparation_is_current(case):
        return None
    if rule_applicability_review_is_current(case):
        return None
    try:
        _, reviews, _ = _trace_maps(case)
    except ValueError:
        return None
    if not reviews:
        return None
    items = prepared_rule_evidence(case)
    return {
        "task_key": "rules:review-applicability",
        "priority": "P0",
        "title": "Bind exact rule evidence to bid assumptions",
        "actor": "HUMAN_REVIEW",
        "can_auto_execute": False,
        "status": "OPEN",
        "reason": (
            "Exact pinned rule passages are prepared, but applicability has not "
            "been human-bound to the affected assumption with a separate "
            "solicitation/amendment basis."
        ),
        "evidence_needed": (
            "For every prepared occurrence choose the affected assumption, "
            "APPLIES / DOES_NOT_APPLY / UNRESOLVED, a rationale, and—when "
            "resolved—an exact solicitation/amendment/context passage that "
            "establishes the pursuit-specific basis."
        ),
        "metadata": {
            "preparation_sha256": (
                case["packet"]["rule_evidence_preparation"]["preparation_sha256"]
            ),
            "prepared": [
                {
                    "occurrence_id": row["occurrence_id"],
                    "citation": row["citation"],
                    "edition": row["rule_version"]["edition"],
                    "rule_version_id": row["rule_version"]["rule_version_id"],
                }
                for row in items
            ],
            "assumption_ids": [
                row.get("assumption_id")
                for row in case.get("assumptions") or []
                if isinstance(row, dict) and row.get("assumption_id")
            ],
            "can_auto_apply": False,
        },
    }
