"""Prepare exact official rule passages for CaptureBrief Decision Evidence.

This stage converts a human-selected pinned rule version plus a human-selected
paragraph into content-addressed source/snapshot/rule-version objects. It does
not decide applicability or bind the rule to a buyer assumption.
"""
from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
from typing import Any

from .decision_trace import canonical, digest, freeze_rule_version, passage
from .rule_candidates import (
    rule_candidate_review_is_current,
    tracked_rule_versions,
)
from .rule_registry import get_rule_version, to_trace_source_snapshot

CONTRACT = "capturebrief-rule-evidence-prep-v1"


def _time(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _source_id(rule_source_id: str) -> str:
    if not rule_source_id.startswith("RULESRC:"):
        raise ValueError("selected rule source is not content-addressed")
    return "rule-source:" + rule_source_id.split(":", 1)[1]


def _selected_map(case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["occurrence_id"]): row
        for row in tracked_rule_versions(case)
        if row.get("occurrence_id")
    }


def _validate_selected_record(
    selected: dict[str, Any],
    record: dict[str, Any],
) -> None:
    expected = selected.get("selected_rule") or {}
    fields = (
        "rule_source_id",
        "rule_key",
        "namespace",
        "citation",
        "agency",
        "edition",
        "source_repository",
        "source_revision",
        "source_path",
        "source_sha256",
    )
    for field in fields:
        if expected.get(field) != record.get(field):
            raise ValueError(
                f"selected rule metadata changed for {selected.get('occurrence_id')}: {field}"
            )


def prepare_rule_evidence(
    case: dict[str, Any],
    registry_path: str | Path,
    preparation: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Prepare exact official rule evidence for all TRACK_VERSION decisions."""
    if not rule_candidate_review_is_current(case):
        raise ValueError("case does not contain a current human rule-version review")

    selected = _selected_map(case)
    if not selected:
        raise ValueError("current review has no TRACK_VERSION decisions to prepare")

    prepared_by = preparation.get("prepared_by")
    prepared_at = preparation.get("prepared_at")
    if not isinstance(prepared_by, str) or not prepared_by.strip():
        raise ValueError("prepared_by is required")
    if not _time(prepared_at):
        raise ValueError("prepared_at must be timezone-aware ISO-8601")

    selections = preparation.get("selections")
    if not isinstance(selections, list):
        raise ValueError("selections must be a list")

    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []

    for selection in selections:
        if not isinstance(selection, dict):
            raise ValueError("preparation selection must be an object")
        occurrence_id = str(selection.get("occurrence_id") or "")
        if occurrence_id not in selected:
            raise ValueError(f"unknown tracked occurrence {occurrence_id}")
        if occurrence_id in seen:
            raise ValueError(f"duplicate preparation for {occurrence_id}")
        seen.add(occurrence_id)

        locator = selection.get("paragraph_locator")
        if not isinstance(locator, str) or not locator.strip():
            raise ValueError(f"paragraph_locator required for {occurrence_id}")

        selected_row = selected[occurrence_id]
        selected_rule = selected_row["selected_rule"]
        record = get_rule_version(
            registry_path,
            selected_rule["rule_source_id"],
        )
        if record is None:
            raise ValueError(
                f"selected pinned rule source is missing from registry: "
                f"{selected_rule['rule_source_id']}"
            )
        _validate_selected_record(selected_row, record)

        matches = [
            p for p in record.get("paragraphs") or []
            if p.get("locator") == locator
        ]
        if len(matches) != 1:
            raise ValueError(
                f"paragraph locator {locator!r} must identify exactly one "
                f"paragraph in {record['rule_source_id']}"
            )
        paragraph = matches[0]
        line = paragraph.get("line")
        if type(line) is not int or line < 2:
            raise ValueError("stored rule paragraph line is invalid")

        source_id = _source_id(record["rule_source_id"])
        source, snapshot = to_trace_source_snapshot(
            record,
            source_id=source_id,
            reviewer=prepared_by.strip(),
        )
        exact_passage = passage(
            snapshot,
            line,
            line,
            locator=locator,
        )
        if exact_passage["quote"] != f"[{locator}] {paragraph['text']}":
            raise ValueError("normalized paragraph/trace passage mismatch")

        rule_version = freeze_rule_version(
            namespace=record["namespace"],
            citation=record["citation"],
            edition=record["edition"],
            agency=record["agency"],
            text_passage=exact_passage,
            effective_from=record.get("effective_from"),
            effective_until=record.get("effective_until"),
            effective_date_passage=None,
            revision_ref=record["rule_source_id"],
        )

        source_rows.append(source)
        items.append({
            "occurrence_id": occurrence_id,
            "citation": selected_row["citation"],
            "review_reason": selected_row["reason"],
            "selected_rule_source_id": record["rule_source_id"],
            "paragraph_locator": locator,
            "paragraph_text_sha256": paragraph["text_sha256"],
            "source": source,
            "snapshot": snapshot,
            "text_passage": exact_passage,
            "rule_version": rule_version,
            "applicability": "UNRESOLVED",
            "applicability_authoritative": False,
            "bound_assumption_id": None,
            "can_auto_bind_assumption": False,
            "can_auto_apply": False,
        })

    missing = sorted(set(selected) - seen)
    if missing:
        raise ValueError(
            "every TRACK_VERSION occurrence requires one exact paragraph selection: "
            + ",".join(missing)
        )

    items.sort(key=lambda x: x["occurrence_id"])
    packet = case.get("packet") or {}
    review = packet["rule_candidate_review"]

    payload = {
        "contract": CONTRACT,
        "status": "COMPLETE",
        "review_sha256": review["review_sha256"],
        "prepared_by": prepared_by.strip(),
        "prepared_at": prepared_at,
        "items": items,
        "applicability_authoritative": False,
        "can_auto_bind_assumption": False,
        "can_auto_apply": False,
    }
    prepared = {
        **payload,
        "preparation_sha256": digest(canonical(payload)),
    }

    result = copy.deepcopy(case)
    result_packet = result.setdefault("packet", {})
    old = result_packet.get("rule_evidence_preparation")
    if old is not None:
        result_packet.setdefault("rule_evidence_preparation_history", []).append(old)
    result_packet["rule_evidence_preparation"] = prepared

    existing_sources = {
        str(row.get("source_id")): row
        for row in result.get("sources") or []
        if isinstance(row, dict) and row.get("source_id")
    }
    result.setdefault("sources", [])
    for source in source_rows:
        current = existing_sources.get(source["source_id"])
        if current is None:
            result["sources"].append(copy.deepcopy(source))
            existing_sources[source["source_id"]] = source
        elif canonical(current) != canonical(source):
            raise ValueError(
                f"case source ID collision for prepared rule source {source['source_id']}"
            )

    return result, {
        "status": "RULE_EVIDENCE_PREPARED",
        "review_sha256": review["review_sha256"],
        "preparation_sha256": prepared["preparation_sha256"],
        "prepared_occurrences": [row["occurrence_id"] for row in items],
        "rule_version_ids": [
            row["rule_version"]["rule_version_id"] for row in items
        ],
        "applicability_authoritative": False,
        "can_auto_bind_assumption": False,
        "can_auto_apply": False,
    }


def rule_evidence_preparation_is_current(case: dict[str, Any]) -> bool:
    if not rule_candidate_review_is_current(case):
        return False
    packet = case.get("packet") or {}
    review = packet.get("rule_candidate_review") or {}
    prepared = packet.get("rule_evidence_preparation")
    if not isinstance(prepared, dict):
        return False
    if (
        prepared.get("contract") != CONTRACT
        or prepared.get("status") != "COMPLETE"
        or prepared.get("review_sha256") != review.get("review_sha256")
        or prepared.get("applicability_authoritative") is not False
        or prepared.get("can_auto_bind_assumption") is not False
        or prepared.get("can_auto_apply") is not False
    ):
        return False
    body = {
        k: v for k, v in prepared.items()
        if k != "preparation_sha256"
    }
    if digest(canonical(body)) != prepared.get("preparation_sha256"):
        return False

    selected = _selected_map(case)
    prepared_ids = {
        str(item.get("occurrence_id"))
        for item in prepared.get("items") or []
        if isinstance(item, dict) and item.get("occurrence_id")
    }
    if prepared_ids != set(selected):
        return False

    sources = {
        str(row.get("source_id")): row
        for row in case.get("sources") or []
        if isinstance(row, dict) and row.get("source_id")
    }
    for item in prepared.get("items") or []:
        if not isinstance(item, dict):
            return False
        if (
            item.get("applicability") != "UNRESOLVED"
            or item.get("applicability_authoritative") is not False
            or item.get("bound_assumption_id") is not None
            or item.get("can_auto_bind_assumption") is not False
            or item.get("can_auto_apply") is not False
        ):
            return False
        source = item.get("source")
        snapshot = item.get("snapshot")
        rule_version = item.get("rule_version")
        if not all(isinstance(x, dict) for x in (source, snapshot, rule_version)):
            return False
        if sources.get(str(source.get("source_id"))) != source:
            return False
        if snapshot.get("source_id") != source.get("source_id"):
            return False
        if snapshot.get("document_sha256") != source.get("content_sha256"):
            return False
        if rule_version.get("revision_ref") != item.get("selected_rule_source_id"):
            return False
        if rule_version.get("text_passage") != item.get("text_passage"):
            return False
    return True


def prepared_rule_evidence(case: dict[str, Any]) -> list[dict[str, Any]]:
    if not rule_evidence_preparation_is_current(case):
        return []
    return copy.deepcopy(
        case["packet"]["rule_evidence_preparation"]["items"]
    )


def rule_evidence_work_item(case: dict[str, Any]) -> dict[str, Any] | None:
    if not rule_candidate_review_is_current(case):
        return None
    tracked = tracked_rule_versions(case)
    if not tracked or rule_evidence_preparation_is_current(case):
        return None
    return {
        "task_key": "rules:prepare-evidence",
        "priority": "P0",
        "title": "Select exact official rule passages for Decision Evidence",
        "actor": "HUMAN_REVIEW",
        "can_auto_execute": False,
        "status": "OPEN",
        "reason": (
            "One or more FAR/DFARS versions were human-selected, but no current "
            "exact rule passage has been prepared for the assumption trace."
        ),
        "evidence_needed": (
            "Choose one exact paragraph locator from each selected pinned rule "
            "source. CaptureBrief will prepare the content-addressed source, "
            "snapshot, and rule-version objects; applicability remains unresolved."
        ),
        "metadata": {
            "review_sha256": (
                case["packet"]["rule_candidate_review"]["review_sha256"]
            ),
            "tracked": [
                {
                    "occurrence_id": row["occurrence_id"],
                    "citation": row["citation"],
                    "rule_source_id": row["selected_rule"]["rule_source_id"],
                    "edition": row["selected_rule"]["edition"],
                }
                for row in tracked
            ],
            "can_auto_bind_assumption": False,
            "can_auto_apply": False,
        },
    }
