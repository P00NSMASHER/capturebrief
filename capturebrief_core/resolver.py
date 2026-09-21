from __future__ import annotations

import copy
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .archive_catalog import fiscal_year_for_datetime
from .history_index import index_status, init_index, issue_history_receipt_from_index
from .model import parse_dt
from .opportunity_ref import parse_opportunity_reference


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().upper()


def _connect(path: str | Path) -> sqlite3.Connection:
    init_index(path)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _rows_for_notice(index_path: str | Path, notice_id: str) -> list[dict[str, Any]]:
    with _connect(index_path) as conn:
        rows = conn.execute(
            """
            SELECT r.notice_id,r.solicitation_norm,r.solicitation_raw,r.aac_code,r.office,
                   r.posted_date,r.notice_type,r.active,r.link,
                   s.slot,s.source_kind,s.fiscal_year,s.source_url,s.extract_sha256,
                   c.checked_at,c.collection_mode
            FROM opportunity_rows r
            JOIN source_snapshots s ON s.snapshot_id=r.snapshot_id
            JOIN current_sources c ON c.snapshot_id=s.snapshot_id
            WHERE LOWER(r.notice_id)=LOWER(?)
            """,
            (notice_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def _rows_for_solicitation(index_path: str | Path, solicitation_number: str) -> list[dict[str, Any]]:
    with _connect(index_path) as conn:
        rows = conn.execute(
            """
            SELECT r.notice_id,r.solicitation_norm,r.solicitation_raw,r.aac_code,r.office,
                   r.posted_date,r.notice_type,r.active,r.link,
                   s.slot,s.source_kind,s.fiscal_year,s.source_url,s.extract_sha256,
                   c.checked_at,c.collection_mode
            FROM opportunity_rows r
            JOIN source_snapshots s ON s.snapshot_id=r.snapshot_id
            JOIN current_sources c ON c.snapshot_id=s.snapshot_id
            WHERE r.solicitation_norm=?
            """,
            (_norm(solicitation_number),),
        ).fetchall()
    return [dict(row) for row in rows]


def _candidate_families(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        aac = _norm(row.get("aac_code"))
        office = _norm(row.get("office"))
        key = (aac, "") if aac else ("", office)
        groups.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for (aac, office), members in groups.items():
        raw_sol = next((str(r.get("solicitation_raw") or "").strip() for r in members if r.get("solicitation_raw")), "")
        out.append({
            "solicitation_number": raw_sol or None,
            "aac_code": aac or None,
            "office": office or next((r.get("office") for r in members if r.get("office")), None),
            "notice_ids": sorted({str(r.get("notice_id")) for r in members if r.get("notice_id")}),
            "observations": len(members),
        })
    return sorted(out, key=lambda x: ((x.get("aac_code") or ""), (x.get("office") or "")))


def resolve_reference_from_index(
    index_path: str | Path,
    reference: Any,
    *,
    fiscal_year: int | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Resolve a buyer reference against the reusable Data Services index.

    A SAM action URL/UUID supplies an independent seed identity. A bare solicitation number
    never authorizes CaptureBrief to choose a seed from bulk rows; it only returns candidates.
    Index completeness includes approved-fetch provenance and freshness.
    """
    parsed = parse_opportunity_reference(reference)
    fiscal_year = fiscal_year or fiscal_year_for_datetime()
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    observed_dt = parse_dt(observed_at)
    if not observed_dt:
        raise ValueError("observed_at must be timezone-aware ISO-8601")
    coverage = index_status(index_path, fiscal_year=fiscal_year, now=observed_dt)

    if parsed["reference_type"] in {"UNSUPPORTED_URL", "SAM_URL_UNRESOLVED"}:
        return {
            "status": "UNSUPPORTED_REFERENCE",
            "reference": parsed,
            "coverage": coverage,
            "currentness_inferred": False,
        }

    if parsed["reference_type"] == "SOLICITATION_NUMBER":
        rows = _rows_for_solicitation(index_path, parsed["solicitation_number"])
        if not rows:
            return {
                "status": "NOT_FOUND",
                "reference": parsed,
                "coverage": coverage,
                "currentness_inferred": False,
            }
        return {
            "status": "NEEDS_SEED_NOTICE_ID",
            "reference": parsed,
            "coverage": coverage,
            "candidate_families": _candidate_families(rows),
            "currentness_inferred": False,
            "reason": "Data Services membership cannot independently choose the seed/current action.",
        }

    action_id = str(parsed.get("action_id") or "").lower()
    rows = _rows_for_notice(index_path, action_id)
    if not rows:
        return {
            "status": "NOT_FOUND",
            "reference": parsed,
            "coverage": coverage,
            "currentness_inferred": False,
        }

    solicitation_norms = {_norm(row.get("solicitation_raw") or row.get("solicitation_norm")) for row in rows}
    solicitation_norms.discard("")
    if len(solicitation_norms) != 1:
        return {
            "status": "AMBIGUOUS_INDEX_IDENTITY",
            "reference": parsed,
            "coverage": coverage,
            "rows": rows,
            "currentness_inferred": False,
        }

    solicitation_number = next(
        (
            str(row.get("solicitation_raw") or "").strip()
            for row in rows
            if str(row.get("solicitation_raw") or "").strip()
        ),
        next(iter(solicitation_norms)),
    )

    receipt = issue_history_receipt_from_index(
        index_path,
        solicitation_number=solicitation_number,
        seed_notice_id=action_id,
        observed_at=observed_at,
        fiscal_year=fiscal_year,
    )
    family = receipt.get("evidence_payload", {}).get("family") or {}
    resolved_status = "RESOLVED" if receipt.get("status") == "COMPLETE" else "RESOLVED_PARTIAL_COVERAGE"
    return {
        "status": resolved_status,
        "reference": parsed,
        "coverage": coverage,
        "solicitation_number": family.get("solicitation_number") or solicitation_number,
        "seed_notice_id": action_id,
        "aac_code": family.get("aac_code"),
        "office": family.get("office"),
        "history_receipt": receipt,
        "currentness_inferred": False,
    }


def attach_history_resolution(
    case: dict[str, Any],
    index_path: str | Path,
    *,
    fiscal_year: int | None = None,
    observed_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Attach a Data Services history receipt to an intake-derived case when safely resolvable."""
    result = copy.deepcopy(case)
    intake = result.get("intake") or {}
    resolution = resolve_reference_from_index(
        index_path,
        intake.get("public_opportunity"),
        fiscal_year=fiscal_year,
        observed_at=observed_at,
    )

    packet = result.setdefault("packet", {})
    packet["family_resolution"] = {
        "status": resolution["status"],
        "reference_type": (resolution.get("reference") or {}).get("reference_type"),
        "currentness_inferred": False,
    }

    if resolution["status"] not in {"RESOLVED", "RESOLVED_PARTIAL_COVERAGE"}:
        return result, resolution

    receipt = resolution["history_receipt"]
    packet["history_action_ids"] = list(receipt.get("action_ids") or [])

    receipts = list(packet.get("history_receipts") or [])
    digest = receipt.get("evidence_payload_sha256")
    if not any(r.get("evidence_payload_sha256") == digest for r in receipts):
        receipts.append(receipt)
    packet["history_receipts"] = receipts

    family_bits = [
        str(resolution.get("solicitation_number") or "").strip(),
        str(resolution.get("aac_code") or resolution.get("office") or resolution.get("seed_notice_id") or "").strip(),
    ]
    result["family_id"] = "SAM:" + ":".join(bit for bit in family_bits if bit)

    source_id = "sam-data-services-history"
    sources = list(result.get("sources") or [])
    source = {
        "source_id": source_id,
        "url": receipt.get("source_url"),
        "authority": "SUPPORTING",
        "artifact_state": "PUBLIC",
        "observed_at": receipt.get("observed_at"),
        "content_sha256": receipt.get("evidence_payload_sha256"),
        "source_contract": "SAM_DATA_SERVICES_EXTRACT",
    }
    replaced = False
    for idx, existing in enumerate(sources):
        if existing.get("source_id") == source_id:
            sources[idx] = source
            replaced = True
            break
    if not replaced:
        sources.append(source)
    result["sources"] = sources
    return result, resolution
