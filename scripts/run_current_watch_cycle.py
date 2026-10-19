"""One bounded CaptureBrief current-source watch cycle. No automatic messaging.

The operator supplies a previously delivered, independently reviewed baseline
and a private case with a complete history receipt. This command queries ONLY
the documented official SAM.gov Opportunities API with an operator-supplied key,
applies a validated latest-active observation, and writes private immutable
outputs. It cannot certify archive completeness, rule changes or buyer posture.

This is ON-DEMAND infrastructure, not a scheduler, continuous watch, notification
service, customer delivery, or proof that 14 scheduled days were completed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))

from capturebrief_core.atomic_io import ensure_exact_bytes
from capturebrief_core.current_search import fetch_and_apply_current
from capturebrief_core.model import canonical_json, sha256_hex
from capturebrief_core.watch_baseline import _validate_baseline, compare_watch_baseline
from scripts.run_watch_receipt import _private_dir, evaluate_and_retain

def _private_path(path: str) -> Path:
    dest = Path(path).expanduser().resolve()
    _private_dir(str(dest.parent))
    if dest.exists() and not dest.is_file():
        raise ValueError("Watch output must be a regular file")
    return dest


def execute(
    case: dict[str, Any],
    baseline: dict[str, Any],
    *,
    api_key: str,
    updated_case_path: str,
    receipt_dir: str,
    checked_at: datetime | None = None,
    opener: Callable[..., Any] | None = None,
    previous_observation: dict | None = None,
) -> dict[str, Any]:
    """Fetch and store one real API currentness observation; fail closed otherwise."""
    if not api_key:
        raise ValueError("An operator-provided SAM_API_KEY is required")
    if checked_at is not None and (
        not isinstance(checked_at, datetime) or checked_at.utcoffset() is None
    ):
        raise ValueError("Watch cycle requires timezone-aware checked_at")
    # Observe the check completion clock AFTER the network fetch below. The
    # provider's genuine observed_at would otherwise be later than a time
    # captured just before the request, causing every live run to fail.
    now = checked_at.astimezone(timezone.utc) if checked_at else None
    target = _private_path(updated_case_path)
    receipt_root = _private_dir(receipt_dir)
    if target.is_relative_to(receipt_root) and target.name.startswith("watch-"):
        raise ValueError("Updated case cannot collide with a watch receipt")
    # Validate provenance and pursuit identity BEFORE using an API key or
    # accepting an ambiguous no-active-match as an operator review event.
    _validate_baseline(baseline)
    if (baseline.get("case_id"), baseline.get("family_id")) != (
        case.get("case_id"), case.get("family_id")
    ):
        raise ValueError("Delivered baseline belongs to a different pursuit")
    updated, details = fetch_and_apply_current(
        case,
        api_key=api_key,
        **({"opener": opener} if opener is not None else {}),
    )
    observed_completion_at = datetime.now(timezone.utc)
    if now is None:
        now = observed_completion_at
    status = details.get("fetch", {}).get("status")
    if status != "CURRENT_OBSERVATION_FOUND":
        # Crucial: no current API result is NOT proof of an inactive notice.
        # Do not publish old content as a freshly checked source.
        review_event = {
            "schema": "capturebrief-current-watch-cycle-v1",
            "case_id": case.get("case_id"),
            "checked_at": now.isoformat().replace("+00:00", "Z"),
            "status": "CURRENT_SOURCE_REVIEW_REQUIRED",
            "reason": "NO_VERIFIED_CURRENT_ACTION",
            "currentness_inferred": False,
            "case_published_as_refreshed": False,
            "automatic_decision_change": False,
            "external_send_authorized": False,
        }
        raw = (json.dumps(review_event, indent=2, sort_keys=True) + "\n").encode()
        receipt_root.mkdir(parents=True, exist_ok=True)
        stored = receipt_root / f"watch-no-active-{sha256_hex(canonical_json(review_event))}.json"
        ensure_exact_bytes(stored, raw)
        return {
            "status": "CURRENT_SOURCE_REVIEW_REQUIRED",
            "event_receipt_path": str(stored),
            "case_published_as_refreshed": False,
            "external_send_authorized": False,
        }

    # The new API observation is never allowed to be after this check time.
    # Tests inject an opener, but not a forged source timestamp.
    current = (updated.get("packet") or {}).get("current_api_observation") or {}
    observed_at = datetime.fromisoformat(str(current.get("observed_at")).replace("Z", "+00:00"))
    if observed_at.utcoffset() is None or observed_at.astimezone(timezone.utc) > now:
        raise ValueError("Current API response was observed after the declared check time")

    # Validate the baseline before publishing ANY refreshed case file.
    # A tampered or mismatched baseline must not leave behind a case that
    # appears newly sourced without its corresponding review.
    compare_watch_baseline(
        baseline, updated, now=now,
        previous_observation=previous_observation,
    )

    # This is an additional source of case evidence, not consent to update
    # any buyer assertion. It must never overwrite differing bytes.
    encoded = (json.dumps(updated, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
    ensure_exact_bytes(target, encoded)
    check = evaluate_and_retain(
        baseline, updated,
        checked_at=now,
        receipt_dir=str(receipt_root),
        previous_observation=previous_observation,
    )
    return {
        "status": "CURRENT_API_CHECK_REVIEW_REQUIRED"
                  if check["requires_human_review"] else "CURRENT_API_CHECK_RECORDED",
        "case_id": updated.get("case_id"),
        "updated_case_path": str(target),
        "updated_case_sha256": sha256_hex(canonical_json(updated)),
        "watch_status": check["watch_status"],
        "source_observation_recorded": True,
        # One official current API fetch is NOT coverage of history, rule
        # editions, manifests or every other agreed monitored source.
        "all_watch_sources_refreshed": False,
        "watch_receipt_path": check["receipt_path"],
        "human_review_required": check["requires_human_review"],
        "automatic_decision_change": False,
        "external_send_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("case", help="Previously reviewed private case JSON")
    p.add_argument("baseline", help="Private delivered watch baseline JSON")
    p.add_argument("--updated-case", required=True, help="Private new case output file")
    p.add_argument("--receipt-dir", required=True, help="Private receipt directory")
    p.add_argument("--api-key-env", default="SAM_API_KEY", help="Environment variable containing SAM API key")
    p.add_argument("--previous-receipt", help="Original private JSON receipt from the immediately prior scheduled watch check")
    args = p.parse_args(argv)
    try:
        api_key = os.getenv(args.api_key_env, "")
        if not api_key:
            raise ValueError("SAM API key unavailable")
        path_case = _private_path(args.case)
        path_baseline = _private_path(args.baseline)
        if path_case == path_baseline or _private_path(args.updated_case) in (path_case, path_baseline):
            raise ValueError("Source, baseline and updated case must be distinct")
        case = json.loads(path_case.read_text(encoding="utf-8"))
        baseline = json.loads(path_baseline.read_text(encoding="utf-8"))
        previous = (json.loads(_private_path(args.previous_receipt).read_text(encoding="utf-8"))
                    if args.previous_receipt else None)
        result = execute(
            case, baseline, api_key=api_key,
            updated_case_path=args.updated_case, receipt_dir=args.receipt_dir,
            previous_observation=previous,
        )
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
        # Do not print raw provider errors (which may include API-key-bearing
        # URLs, signed links or customer fields).
        print(json.dumps({
            "status": "WATCH_CYCLE_BLOCKED",
            "error_type": type(exc).__name__,
            "human_review_required": True,
            "external_send_authorized": False,
        }))
        return 3
    print(json.dumps(result, indent=2, sort_keys=True))
    return 3 if (result["status"] == "CURRENT_SOURCE_REVIEW_REQUIRED"
                 or result.get("human_review_required")) else 0


if __name__ == "__main__":
    raise SystemExit(main())
