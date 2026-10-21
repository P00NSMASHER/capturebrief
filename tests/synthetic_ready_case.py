"""Test-only renewal of CaptureBrief's explicitly fictitious delivery fixture.

This is NOT a provider observation, real source attestation or production option.
Only the hardcoded CB-DEMO-READY / sam.gov/opp/example fixture may be renewed.
The production readiness engine remains unchanged and rejects expired receipts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

_SOURCE = Path(__file__).resolve().parents[1] / "fixtures" / "ready_trace_case.json"
_DEMO_CASE = "CB-DEMO-READY"
_DEMO_URL = "https://sam.gov/opp/example/view"


def current_synthetic_case(*, now: datetime | None = None) -> dict:
    """Create a short-lived synthetic in-memory case; never mutate the source fixture."""
    when = datetime.now(timezone.utc) if now is None else now
    if not isinstance(when, datetime) or when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("synthetic fixture clock must be timezone-aware")
    when = when.astimezone(timezone.utc)
    case = json.loads(_SOURCE.read_text(encoding="utf-8"))
    receipts = case.get("current_action_receipts")
    if (case.get("case_id") != _DEMO_CASE or case.get("family_id") != "DEMO-FAMILY-001"
            or not isinstance(receipts, list) or len(receipts) != 1):
        raise ValueError("only the frozen demonstration fixture can be refreshed")
    receipt = receipts[0]
    if (receipt.get("source_url") != _DEMO_URL
            or receipt.get("asserted_action_id") != "action-002"
            or receipt.get("semantics") != "CURRENT_ACTIVE"
            or receipt.get("observed_family_status") != "ACTIVE"):
        raise ValueError("demonstration source identity changed")
    receipt["observed_at"] = (when - timedelta(seconds=30)).isoformat(timespec="seconds")
    receipt["expires_at"] = (when + timedelta(minutes=10)).isoformat(timespec="seconds")
    return case


def write_current_synthetic_case(path: str | Path, *, now: datetime | None = None) -> Path:
    """Write only one new ephemeral test file with exclusive create semantics."""
    destination = Path(path)
    if destination.resolve() == _SOURCE.resolve() or not destination.parent.is_dir():
        raise ValueError("test output must be a distinct pre-existing private temp folder")
    case = current_synthetic_case(now=now)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(case, stream, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        stream.write("\n")
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a short-lived DEMO-ONLY CLI test input.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    write_current_synthetic_case(args.output)
    print("DEMO-ONLY ready fixture created; no actual provider observations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
