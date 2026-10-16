#!/usr/bin/env python3
"""Fail-closed validation and stable publication for the ABVM school pack."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


MAX_SOURCE_AGE = timedelta(days=7)
MAX_CLOCK_SKEW = timedelta(minutes=5)
WEEK_LABEL_TOLERANCE = timedelta(days=7)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
WEEK_DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(\d{1,2}),\s+(\d{4})"
)


class PackValidationError(ValueError):
    """Raised when a candidate pack cannot cross the publication boundary."""


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise PackValidationError(f"MISSING_TIMESTAMP:{field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PackValidationError(f"INVALID_TIMESTAMP:{field}") from exc
    if parsed.tzinfo is None:
        raise PackValidationError(f"NAIVE_TIMESTAMP:{field}")
    return parsed.astimezone(timezone.utc)


def _week_date(label: Any) -> datetime:
    if not isinstance(label, str):
        raise PackValidationError("INVALID_WEEK_LABEL")
    match = WEEK_DATE_RE.search(label)
    if not match:
        raise PackValidationError("INVALID_WEEK_LABEL")
    try:
        return datetime.strptime(
            " ".join(match.groups()), "%B %d %Y"
        ).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise PackValidationError("INVALID_WEEK_LABEL") from exc


def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(payload)
    normalized.pop("freshnessHours", None)
    normalized.pop("sourceLastSeenAt", None)
    pack = normalized.get("pack")
    if isinstance(pack, dict):
        pack.pop("generatedAt", None)
    return normalized


def prepare_school_pack(
    payload: dict[str, Any],
    *,
    existing: dict[str, Any] | None,
    now: datetime,
) -> tuple[dict[str, Any], bool]:
    if not isinstance(payload, dict):
        raise PackValidationError("INVALID_DOCUMENT")
    if now.tzinfo is None:
        raise PackValidationError("NAIVE_NOW")
    now = now.astimezone(timezone.utc)

    pack = payload.get("pack")
    if not isinstance(pack, dict):
        raise PackValidationError("MISSING_PACK")
    if pack.get("sourceSufficient") is not True:
        raise PackValidationError("SOURCE_INSUFFICIENT")

    questions = pack.get("questions")
    if not isinstance(questions, list) or not any(
        isinstance(question, dict)
        and isinstance(question.get("prompt"), str)
        and question["prompt"].strip()
        and isinstance(question.get("answer"), str)
        and question["answer"].strip()
        for question in questions
    ):
        raise PackValidationError("NO_USABLE_QUESTIONS")

    root_captured = _parse_timestamp(payload.get("sourceCapturedAt"), "sourceCapturedAt")
    pack_captured = _parse_timestamp(
        pack.get("sourceCapturedAt"), "pack.sourceCapturedAt"
    )
    if root_captured != pack_captured:
        raise PackValidationError("CAPTURE_TIMESTAMP_MISMATCH")
    if root_captured > now + MAX_CLOCK_SKEW:
        raise PackValidationError("SOURCE_FROM_FUTURE")
    age = now - root_captured
    if age > MAX_SOURCE_AGE:
        raise PackValidationError(
            f"STALE_SOURCE:age_hours={age.total_seconds() / 3600:.3f}"
        )

    last_seen = payload.get("sourceLastSeenAt")
    if last_seen is not None:
        observed = _parse_timestamp(last_seen, "sourceLastSeenAt")
        if observed + MAX_CLOCK_SKEW < root_captured:
            raise PackValidationError("OBSERVATION_PRECEDES_CAPTURE")
        if observed > now + MAX_CLOCK_SKEW:
            raise PackValidationError("OBSERVATION_FROM_FUTURE")

    freshness = payload.get("freshnessHours")
    if freshness is not None:
        if not isinstance(freshness, (int, float)) or freshness < 0:
            raise PackValidationError("INVALID_FRESHNESS_HOURS")
        computed = age.total_seconds() / 3600
        if abs(float(freshness) - computed) > 1.0:
            raise PackValidationError("FRESHNESS_TIMESTAMP_MISMATCH")

    week_date = _week_date(pack.get("weekLabel"))
    if abs(week_date - root_captured) > WEEK_LABEL_TOLERANCE:
        raise PackValidationError("WEEK_LABEL_CAPTURE_MISMATCH")

    source_hash = pack.get("sourceHash")
    if not isinstance(source_hash, str) or not SHA256_RE.fullmatch(source_hash):
        raise PackValidationError("INVALID_SOURCE_HASH")

    normalized = _normalize(payload)
    if existing is None:
        return normalized, True
    if not isinstance(existing, dict):
        raise PackValidationError("INVALID_EXISTING_DOCUMENT")

    old_normalized = _normalize(existing)
    old_pack = old_normalized.get("pack")
    old_hash = old_pack.get("sourceHash") if isinstance(old_pack, dict) else None
    if old_hash == source_hash and old_normalized != normalized:
        raise PackValidationError("SOURCE_HASH_REUSE_WITH_CHANGED_CONTENT")
    return normalized, old_normalized != normalized


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PackValidationError(f"INVALID_DOCUMENT:{path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--existing", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--now", help="UTC ISO-8601 test override")
    args = parser.parse_args()

    now = (
        _parse_timestamp(args.now, "now")
        if args.now
        else datetime.now(timezone.utc)
    )
    existing = (
        _read_json(args.existing)
        if args.existing is not None and args.existing.exists()
        else None
    )
    normalized, changed = prepare_school_pack(
        _read_json(args.input), existing=existing, now=now
    )
    if not changed:
        print("ABVM_PACK_UNCHANGED")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print("ABVM_PACK_UPDATED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PackValidationError as exc:
        print(f"ABVM_PACK_REJECTED:{exc}", file=sys.stderr)
        raise SystemExit(1)
