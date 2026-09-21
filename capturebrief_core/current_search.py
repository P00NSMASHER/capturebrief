from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from .case_current import apply_current_api_observation
from .current_api import (
    CurrentApiCardinalityError,
    CurrentApiError,
    fetch_latest_active,
    make_current_action_receipt,
)
from .history import validate_history_receipts
from .model import parse_dt


class CurrentSearchError(RuntimeError):
    pass


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().upper()


def _posted_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.date()
    except ValueError:
        return None


def _select_complete_history_receipt(case: dict[str, Any]) -> dict[str, Any]:
    packet = case.get("packet") or {}
    history_ids = [str(x) for x in packet.get("history_action_ids") or []]
    valid: list[dict[str, Any]] = []
    for receipt in packet.get("history_receipts") or []:
        verdict, _ = validate_history_receipts(history_ids, [receipt])
        if verdict == "HISTORY_COMPLETE":
            valid.append(receipt)
    if not valid:
        raise CurrentSearchError("current API search planning requires a complete history receipt")
    valid.sort(key=lambda r: parse_dt(r.get("observed_at")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return valid[0]


def build_current_search_plan(case: dict[str, Any]) -> dict[str, Any]:
    """Build non-authoritative API retrieval windows from retained history observations.

    Posted dates are used only to make documented API requests bounded and reproducible.
    They never choose the current action; the returned API Notice ID must still validate
    against the independent history set.
    """
    packet = case.get("packet") or {}
    history_ids = [str(x) for x in packet.get("history_action_ids") or []]
    receipt = _select_complete_history_receipt(case)
    payload = receipt.get("evidence_payload") or {}
    family = payload.get("family") or {}
    solicitation_number = str(family.get("solicitation_number") or "").strip()
    if not solicitation_number:
        raise CurrentSearchError("complete history receipt lacks solicitation_number")

    by_date: dict[date, set[str]] = {}
    missing: set[str] = set()
    seen: set[str] = set()
    for action in payload.get("actions") or []:
        notice_id = str(action.get("notice_id") or "")
        if not notice_id:
            continue
        seen.add(notice_id)
        parsed_dates = {
            d
            for observation in action.get("observations") or []
            if (d := _posted_date(observation.get("posted_date"))) is not None
        }
        if not parsed_dates:
            missing.add(notice_id)
            continue
        for d in parsed_dates:
            by_date.setdefault(d, set()).add(notice_id)

    missing.update(set(history_ids) - seen)
    remaining = sorted(by_date, reverse=True)
    windows: list[dict[str, Any]] = []
    while remaining:
        end = remaining[0]
        earliest_allowed = end - timedelta(days=365)
        grouped = [d for d in remaining if d >= earliest_allowed]
        start = min(grouped)
        covered = sorted({notice for d in grouped for notice in by_date[d]})
        windows.append({
            "posted_from": start.strftime("%m/%d/%Y"),
            "posted_to": end.strftime("%m/%d/%Y"),
            "covers_notice_ids": covered,
            "date_basis_authoritative": False,
        })
        grouped_set = set(grouped)
        remaining = [d for d in remaining if d not in grouped_set]

    return {
        "source_contract": "CAPTUREBRIEF_CURRENT_API_SEARCH_PLAN_V1",
        "solicitation_number": solicitation_number,
        "history_action_ids": history_ids,
        "history_set_sha256": receipt.get("history_set_sha256"),
        "history_receipt_sha256": receipt.get("evidence_payload_sha256"),
        "windows": windows,
        "missing_posted_date_notice_ids": sorted(missing),
        "date_coverage_complete": bool(windows) and not missing,
        "currentness_authoritative": False,
        "ordering_authoritative": False,
    }


def fetch_current_from_plan(
    plan: dict[str, Any],
    *,
    api_key: str,
    organization_code: str | None = None,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if plan.get("source_contract") != "CAPTUREBRIEF_CURRENT_API_SEARCH_PLAN_V1":
        raise CurrentSearchError("current search plan contract is invalid")
    if plan.get("currentness_authoritative") is not False or plan.get("ordering_authoritative") is not False:
        raise CurrentSearchError("search plan must not claim currentness or ordering authority")
    if plan.get("date_coverage_complete") is not True:
        raise CurrentSearchError("history posted-date coverage is incomplete; automated current search is not safe")

    solicitation_number = str(plan.get("solicitation_number") or "").strip()
    history_ids = [str(x) for x in plan.get("history_action_ids") or []]
    if not solicitation_number or not history_ids:
        raise CurrentSearchError("search plan lacks family/history identity")

    observations: dict[str, dict[str, Any]] = {}
    attempts: list[dict[str, Any]] = []
    for window in plan.get("windows") or []:
        kwargs = {
            "solicitation_number": solicitation_number,
            "posted_from": window["posted_from"],
            "posted_to": window["posted_to"],
            "api_key": api_key,
            "organization_code": organization_code,
        }
        if opener is not None:
            kwargs["opener"] = opener
        try:
            observation = fetch_latest_active(**kwargs)
        except CurrentApiCardinalityError as exc:
            attempts.append({
                "posted_from": window["posted_from"],
                "posted_to": window["posted_to"],
                "result_count": exc.count,
            })
            if exc.count == 0:
                continue
            raise CurrentSearchError(str(exc)) from exc
        except CurrentApiError as exc:
            raise CurrentSearchError(str(exc)) from exc

        notice_id = str((observation.get("record") or {}).get("noticeId") or "")
        if not notice_id:
            raise CurrentSearchError("documented API observation lacks noticeId")
        observations[notice_id] = observation
        attempts.append({
            "posted_from": window["posted_from"],
            "posted_to": window["posted_to"],
            "result_count": 1,
            "notice_id": notice_id,
        })

    if not observations:
        return {
            "status": "NO_ACTIVE_MATCH",
            "attempts": attempts,
            "currentness_authoritative": False,
            "meaning": "No active API match was found. This does not prove cancellation, archival, or inactivity.",
        }
    if len(observations) != 1:
        raise CurrentSearchError(
            f"documented API search windows returned conflicting current candidates: {sorted(observations)}"
        )

    observation = next(iter(observations.values()))
    receipt = make_current_action_receipt(observation, history_action_ids=history_ids)
    return {
        "status": "CURRENT_OBSERVATION_FOUND",
        "attempts": attempts,
        "observation": observation,
        "receipt": receipt,
    }


def fetch_and_apply_current(
    case: dict[str, Any],
    *,
    api_key: str,
    organization_code: str | None = None,
    opener: Callable[..., Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = build_current_search_plan(case)
    fetched = fetch_current_from_plan(
        plan,
        api_key=api_key,
        organization_code=organization_code,
        opener=opener,
    )
    if fetched["status"] != "CURRENT_OBSERVATION_FOUND":
        return case, {"plan": plan, "fetch": fetched, "transition": None}
    updated, transition = apply_current_api_observation(case, fetched["observation"])
    return updated, {"plan": plan, "fetch": fetched, "transition": transition}
