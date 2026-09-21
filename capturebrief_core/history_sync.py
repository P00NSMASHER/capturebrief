from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .history_index import DEFAULT_MAX_EXTRACT_BYTES, fetch_and_ingest_slot, index_status, sync_plan
from .model import parse_dt


def _filename_for_slot(slot: str) -> str:
    if slot == "ACTIVE":
        return "ContractOpportunitiesFullCSV.csv"
    if slot.startswith("ARCHIVE:"):
        fy = int(slot.split(":", 1)[1])
        return f"FY{fy}_archived_opportunities.csv"
    raise ValueError(f"unsupported history slot: {slot}")


def sync_missing_slots(
    index_path: str | Path,
    download_dir: str | Path,
    *,
    snapshot_dir: str | Path | None = None,
    fiscal_year: int | None = None,
    max_slots: int | None = 1,
    observed_at: str | None = None,
    max_bytes: int = DEFAULT_MAX_EXTRACT_BYTES,
    fetcher: Callable[..., dict[str, Any]] = fetch_and_ingest_slot,
) -> dict[str, Any]:
    """Explicitly fetch missing/stale/unverified approved Data Services slots.

    The default advances exactly one remediation slot. Passing max_slots=None is an explicit
    request to process the entire remaining plan. Existing fresh approved slots are skipped.
    """
    if max_slots is not None and max_slots <= 0:
        raise ValueError("max_slots must be positive or None")
    now = parse_dt(observed_at) if observed_at else None
    if observed_at and not now:
        raise ValueError("observed_at must be timezone-aware ISO-8601")

    root = Path(download_dir)
    root.mkdir(parents=True, exist_ok=True)

    plan = sync_plan(index_path, fiscal_year=fiscal_year, now=now)
    items = list(plan.get("download_plan") or [])
    selected = items if max_slots is None else items[:max_slots]
    results: list[dict[str, Any]] = []

    for item in selected:
        slot = str(item["slot"])
        destination = root / _filename_for_slot(slot)
        result = fetcher(
            index_path,
            slot=slot,
            destination=destination,
            snapshot_dir=snapshot_dir,
            observed_at=observed_at,
            max_bytes=max_bytes,
        )
        results.append({
            "slot": slot,
            "reason": item.get("reason"),
            "destination": str(destination),
            "result": result,
        })

    refreshed = index_status(index_path, fiscal_year=fiscal_year, now=now)
    return {
        "complete": refreshed["complete"],
        "requested_slots": [item["slot"] for item in selected],
        "requested_reasons": {item["slot"]: item.get("reason") for item in selected},
        "processed_slots": [item["slot"] for item in results],
        "remaining_slots": [item["slot"] for item in sync_plan(index_path, fiscal_year=fiscal_year, now=now).get("download_plan", [])],
        "processed_count": len(results),
        "remaining_count": len(sync_plan(index_path, fiscal_year=fiscal_year, now=now).get("download_plan", [])),
        "index_status": refreshed,
    }
