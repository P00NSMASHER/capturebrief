"""Immutable, local-only operator receipt for a CaptureBrief 14-day watch check.

No network access, no implicit source refresh, no outgoing alerts or emails.
The operator must supply a separately refreshed *private* case snapshot.
Exit codes: 0 only for independently evidenced no-change; 3 needs review;
2 missing/invalid/expired setup errors. Not a scheduler or a send approval.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capturebrief_core.atomic_io import ensure_exact_bytes
from capturebrief_core.model import parse_dt
from capturebrief_core.watch_baseline import compare_watch_baseline

REPO_ROOT = Path(__file__).resolve().parents[1]


def _private_dir(value: str) -> Path:
    root = Path(value).expanduser().resolve()
    if root.is_relative_to(REPO_ROOT):
        raise ValueError("Watch receipts must be kept outside the public repository")
    # Avoid producing a public document under a GitHub Pages working tree.
    if any(p.name in {"gh-pages", ".git"} for p in (root, *root.parents)):
        raise ValueError("Watch receipts cannot be placed in a website or Git directory")
    return root


def evaluate_and_retain(
    baseline: dict,
    refreshed_case: dict,
    *,
    checked_at: datetime,
    receipt_dir: str,
) -> dict:
    if checked_at.utcoffset() is None:
        raise ValueError("watch check time must be timezone aware")
    created = parse_dt(baseline.get("created_at"))
    if created is None or checked_at.astimezone(timezone.utc) <= created:
        raise ValueError("Watch check requires a later independent observation after delivery")
    target_dir = _private_dir(receipt_dir)
    observation = compare_watch_baseline(baseline, refreshed_case, now=checked_at)
    if observation["watch_status"] == "NO_CHANGE_OBSERVED" and not observation["fresh_observation_evidenced"]:
        raise ValueError("A clean watch result requires fresh retained source observations")
    raw = (json.dumps(observation, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"watch-{observation['observation_sha256']}.json"
    ensure_exact_bytes(path, raw)
    return {
        "watch_status": observation["watch_status"],
        "observation_sha256": observation["observation_sha256"],
        "receipt_path": str(path),
        "fresh_observation_evidenced": observation["fresh_observation_evidenced"],
        "requires_human_review": observation["requires_human_review"],
        "event_count": len(observation["events"]),
        "external_send_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", help="Private delivered watch baseline JSON")
    parser.add_argument("refreshed_case", help="Private newly acquired case JSON")
    parser.add_argument("--receipt-dir", required=True, help="Private output directory outside the public repository")
    parser.add_argument("--as-of", help="Timezone-aware ISO timestamp; defaults to current UTC")
    args = parser.parse_args(argv)
    try:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        case = json.loads(Path(args.refreshed_case).read_text(encoding="utf-8"))
        checked_at = (datetime.fromisoformat(args.as_of.replace("Z","+00:00"))
                      if args.as_of else datetime.now(timezone.utc))
        result = evaluate_and_retain(
            baseline, case, checked_at=checked_at, receipt_dir=args.receipt_dir,
        )
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "WATCH_CHECK_INVALID", "reason": type(exc).__name__,
                          "external_send_authorized": False}))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if (result["watch_status"] == "NO_CHANGE_OBSERVED"
                 and result["fresh_observation_evidenced"]
                 and not result["requires_human_review"]) else 3


if __name__ == "__main__":
    raise SystemExit(main())
