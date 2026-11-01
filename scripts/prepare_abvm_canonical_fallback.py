#!/usr/bin/env python3
"""Use independently matching public ABVM repo + Pages bytes after a stale bridge.

This is a bounded, fail-closed fallback, not a substitute for the authoritative
teacher sources. The original capture time is never advanced. Parent/uploaded
notices are intentionally excluded from the public CaptureBrief school app.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from validate_abvm_school_pack import prepare_school_pack, PackValidationError

MAX_BYTES = 1_500_000
MAX_OBSERVATION_AGE = timedelta(hours=20)
EXPECTED_PAGES = {"Home", "Homework", "Reading Work", "Weekly Spelling List", "Tests", "Religion"}
FIELDS = (
    "schemaVersion", "weekLabel", "sourceCapturedAt", "sourceSufficient",
    "summary", "subjects", "homework", "reminders", "questions",
    "importantDates", "lunchMenu", "vocabulary", "gaps"
)


class FallbackError(ValueError):
    pass


def timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise FallbackError("MISSING_TIMESTAMP:" + field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FallbackError("INVALID_TIMESTAMP:" + field) from exc
    if parsed.tzinfo is None:
        raise FallbackError("NAIVE_TIMESTAMP:" + field)
    return parsed.astimezone(timezone.utc)


def sanitized_candidate(repo_bytes: bytes, published_bytes: bytes, now: datetime) -> dict[str, Any]:
    if not isinstance(repo_bytes, bytes) or not isinstance(published_bytes, bytes):
        raise FallbackError("INVALID_SOURCE_BYTES")
    if not repo_bytes or len(repo_bytes) > MAX_BYTES or repo_bytes != published_bytes:
        raise FallbackError("CANONICAL_PUBLICATION_BYTES_MISMATCH")
    try:
        record = json.loads(repo_bytes)
    except (ValueError, UnicodeDecodeError) as exc:
        raise FallbackError("INVALID_CANONICAL_JSON") from exc
    if not isinstance(record, dict) or record.get("delivery") != "verified":
        raise FallbackError("CANONICAL_SCHOOL_SOURCE_UNVERIFIED")
    pack = record.get("pack")
    if not isinstance(pack, dict) or pack.get("schemaVersion") != 2 or pack.get("sourceSufficient") is not True:
        raise FallbackError("CANONICAL_PACK_INSUFFICIENT")
    teacher_hash = pack.get("sourceHash")
    if not isinstance(teacher_hash, str) or not re.fullmatch(r"teacher-pages-[0-9a-f]{16,64}", teacher_hash):
        raise FallbackError("UNRECOGNIZED_TEACHER_PROVENANCE")
    seen = timestamp(record.get("sourceLastSeenAt"), "sourceLastSeenAt")
    checked = timestamp(record.get("sourceLastCheckedAt"), "sourceLastCheckedAt")
    captured = timestamp(record.get("sourceCapturedAt"), "sourceCapturedAt")
    pack_captured = timestamp(pack.get("sourceCapturedAt"), "pack.sourceCapturedAt")
    now = now.astimezone(timezone.utc)
    if captured != pack_captured or seen != checked or not captured <= checked <= now + timedelta(minutes=5):
        raise FallbackError("CANONICAL_SOURCE_TIME_CONFLICT")
    if now - checked > MAX_OBSERVATION_AGE:
        raise FallbackError("CANONICAL_REVIEW_TOO_OLD")
    pages = record.get("sourcePages")
    if not isinstance(pages, list) or len(pages) != len(EXPECTED_PAGES):
        raise FallbackError("TEACHER_SOURCE_COUNT_INVALID")
    observed_titles = set()
    for page in pages:
        if not isinstance(page, dict) or page.get("title") in observed_titles:
            raise FallbackError("TEACHER_SOURCE_DUPLICATE")
        observed_titles.add(page.get("title"))
        if page.get("checkedAt") != record["sourceLastCheckedAt"] or not re.fullmatch(
            r"[0-9a-f]{64}", str(page.get("contentHash") or "")
        ):
            raise FallbackError("TEACHER_SOURCE_PROOF_INVALID")
    if observed_titles != EXPECTED_PAGES:
        raise FallbackError("TEACHER_SOURCE_MISSING")

    selected = {key: pack[key] for key in FIELDS if key in pack}
    # Keep only explicitly teacher-sourced dates, never uploaded parent notices.
    dates = selected.get("importantDates", [])
    if not isinstance(dates, list):
        raise FallbackError("INVALID_TEACHER_DATES")
    selected["importantDates"] = [
        {"date": row["date"], "label": row["label"], "kind": row.get("kind", "school event")}
        for row in dates
        if isinstance(row, dict) and row.get("source") in {"teacher-home", "teacher-tests"}
        and isinstance(row.get("date"), str) and isinstance(row.get("label"), str)
    ]
    if not isinstance(selected.get("questions"), list) or not selected["questions"]:
        raise FallbackError("NO_REVIEWED_QUESTIONS")
    proof = {
        "source": "P00NSMASHER/abvmschoolstarworld/pages/data/study-pack.json",
        "gitHubAndPublishedPagesIdentical": True,
        "artifactSha256": hashlib.sha256(repo_bytes).hexdigest(),
        "upstreamTeacherSourceHash": teacher_hash,
        "teacherPages": sorted(observed_titles),
    }
    selected["sourceHash"] = hashlib.sha256(
        json.dumps({"pack": selected, "sourceProof": proof}, sort_keys=True,
                   separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    payload = {
        "source": "ABVM verified public teacher pages (repo+Pages byte parity)",
        "delivery": "verified",
        "sourceCapturedAt": record["sourceCapturedAt"],
        "sourceLastSeenAt": record["sourceLastSeenAt"],
        "sourceProof": proof,
        "pack": selected,
    }
    try:
        prepare_school_pack(payload, existing=None, now=now)
    except PackValidationError as exc:
        raise FallbackError("EXISTING_PUBLICATION_GATE:" + str(exc)) from exc
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical", required=True, type=Path)
    parser.add_argument("--published", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = sanitized_candidate(
        args.canonical.read_bytes(), args.published.read_bytes(),
        datetime.now(timezone.utc)
    )
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ABVM_CANONICAL_FALLBACK_SOURCE_VERIFIED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FallbackError, OSError) as exc:
        print("ABVM_CANONICAL_FALLBACK_REJECTED:" + str(exc), file=sys.stderr)
        raise SystemExit(1)
