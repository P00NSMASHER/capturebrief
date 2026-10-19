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

from capturebrief_core.atomic_io import ensure_exact_bytes, exclusive_path_lock
from capturebrief_core.decision_trace import canonical, digest
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


# A daily supervised watch has 14 intended observations, but bounded retries
# may create additional receipts. An unbounded directory scan is unsafe.
MAX_RECEIPT_FILES = 512
MAX_RECEIPT_BYTES = 2 * 1024 * 1024


def _saved_watch_history(root: Path, baseline: dict) -> list[tuple[datetime, dict]]:
    """Verify immutable prior receipts before trusting their lineage.

    A matching SHA filename alone is not proof that the stored bytes or
    intervening historical receipts are untampered. Reject any ambiguous,
    modified, or missing chain rather than skipping a prior warning.
    """
    if not root.is_dir():
        return []
    entries = sorted(root.glob("watch-*.json"))
    if len(entries) > MAX_RECEIPT_FILES:
        raise ValueError("Watch history exceeds bounded receipt count")
    records: list[tuple[datetime, dict]] = []
    for path in entries:
        if (path.is_symlink() or not path.is_file() or
                path.stat().st_size > MAX_RECEIPT_BYTES):
            raise ValueError("Existing watch receipt is not a safe regular file")
        raw = path.read_bytes()
        # A matching logical JSON digest alone is insufficient for immutable
        # retention: modified whitespace or duplicate keys could alter stored
        # bytes while preserving the same parsed object/canonical digest.
        def unique_keys(pairs):
            out = {}
            for key, value in pairs:
                if key in out:
                    raise ValueError("Existing watch receipt has duplicate JSON fields")
                out[key] = value
            return out
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_keys)
        if not isinstance(data, dict):
            raise ValueError("Existing watch receipt is not a JSON object")
        exact = (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)
                 + "\n").encode("utf-8")
        if raw != exact:
            raise ValueError("Existing watch receipt was not retained byte-for-byte")
        sha = data.get("observation_sha256")
        if not isinstance(sha, str) or len(sha) != 64 or path.name != f"watch-{sha}.json":
            raise ValueError("Existing watch receipt filename/digest mismatch")
        body = {k:v for k,v in data.items() if k != "observation_sha256"}
        if digest(canonical(body)) != sha:
            raise ValueError("Existing watch receipt content hash mismatch")
        if (data.get("case_id"), data.get("baseline_sha256")) != (
            baseline.get("case_id"), baseline.get("baseline_sha256")
        ):
            continue
        if data.get("family_id") != baseline.get("family_id"):
            raise ValueError("Watch receipt has inconsistent pursuit family")
        observed = parse_dt(data.get("observed_at"))
        if observed is None:
            raise ValueError("Existing watch receipt has invalid timestamp")
        records.append((observed, data))

    records.sort(key=lambda row: (row[0], row[1]["observation_sha256"]))
    # One observation per clock tick. Identical same-time replays are already
    # content-addressed and share one path, so different digests mean a fork.
    if len({row[0] for row in records}) != len(records):
        raise ValueError("Watch history has conflicting same-time observations")
    # Verify no recorded step skips an intervening observation. A prior
    # unresolved REVIEW_REQUIRED result is preserved by the comparator.
    for i, (_, recorded) in enumerate(records):
        predecessor = (records[i-1][1]["observation_sha256"] if i else None)
        if recorded.get("previous_observation_sha256") != predecessor:
            raise ValueError("Watch history has a broken predecessor chain")
    return records


def evaluate_and_retain(
    baseline: dict,
    refreshed_case: dict,
    *,
    checked_at: datetime,
    receipt_dir: str,
    previous_observation: dict | None = None,
) -> dict:
    if checked_at.utcoffset() is None:
        raise ValueError("watch check time must be timezone aware")
    created = parse_dt(baseline.get("created_at"))
    if created is None or checked_at.astimezone(timezone.utc) <= created:
        raise ValueError("Watch check requires a later independent observation after delivery")
    target_dir = _private_dir(receipt_dir)
    # Serialize read-history -> validate predecessor -> publish. Without this
    # engagement-wide lock, simultaneous scheduled retries can fork a valid
    # on-disk receipt chain between the prior read and new file creation.
    with exclusive_path_lock(target_dir / ".watch-series", suffix=".lock"):
        # Every later check must chain to the actual last immutable receipt on
        # disk, not merely to an arbitrary older (but correctly hashed) receipt.
        # Otherwise an operator could skip a prior review-required event and
        # misrepresent the state of a 14-day engagement.
        history = _saved_watch_history(target_dir, baseline)
        if history:
            last_at, last = history[-1]
            if checked_at < last_at:
                raise ValueError("Watch check cannot precede the latest saved observation")
            if checked_at == last_at:
                # Only an exact same-time replay of the SAME step is allowed.
                expected_previous = last.get("previous_observation_sha256")
                if expected_previous is None:
                    if previous_observation is not None:
                        raise ValueError("Same-time watch replay has mismatched predecessor")
                elif (not isinstance(previous_observation, dict) or
                      previous_observation.get("observation_sha256") != expected_previous):
                    raise ValueError("Same-time watch replay has mismatched predecessor")
            elif (not isinstance(previous_observation, dict) or
                  previous_observation.get("observation_sha256") !=
                  last.get("observation_sha256") or
                  previous_observation != last):
                raise ValueError("Later watch check must include the latest retained receipt")
        elif previous_observation is not None:
            raise ValueError("Previous watch receipt is not retained in this private directory")
        observation = compare_watch_baseline(
            baseline, refreshed_case, now=checked_at,
            previous_observation=previous_observation,
        )
        # A same-time check may replay only the exact original result. Creating
        # another observation at the same timestamp would fork the signed chain.
        if (history and checked_at == history[-1][0] and
                observation["observation_sha256"] !=
                history[-1][1]["observation_sha256"]):
            raise ValueError("Conflicting same-time watch observations")
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
            "previous_observation_sha256": observation["previous_observation_sha256"],
            "source_check_count": len(observation["source_checks"]),
            "external_send_authorized": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", help="Private delivered watch baseline JSON")
    parser.add_argument("refreshed_case", help="Private newly acquired case JSON")
    parser.add_argument("--receipt-dir", required=True, help="Private output directory outside the public repository")
    parser.add_argument("--as-of", help="Timezone-aware ISO timestamp; defaults to current UTC")
    parser.add_argument("--previous-receipt", help="Private original JSON receipt from the prior watch check")
    args = parser.parse_args(argv)
    try:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        case = json.loads(Path(args.refreshed_case).read_text(encoding="utf-8"))
        checked_at = (datetime.fromisoformat(args.as_of.replace("Z","+00:00"))
                      if args.as_of else datetime.now(timezone.utc))
        prev = (json.loads(Path(args.previous_receipt).read_text(encoding="utf-8"))
                if args.previous_receipt else None)
        result = evaluate_and_retain(
            baseline, case, checked_at=checked_at, receipt_dir=args.receipt_dir,
            previous_observation=prev,
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
