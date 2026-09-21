from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .model import canonical_json, history_set_digest, parse_dt, sha256_hex
from .source_policy import require_approved_automation

ACTIVE_DATA_SERVICES_PAGE = "https://sam.gov/data-services/Contract%20Opportunities/datagov?privacy=Public"
ARCHIVE_DATA_SERVICES_PAGE = "https://sam.gov/data-services/Contract%20Opportunities/Archived%20Data?privacy=Public"
ACTIVE_DOWNLOAD = "https://sam.gov/api/prod/fileextractservices/v1/api/download/Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv?privacy=Public"
ARCHIVE_DOWNLOAD = "https://sam.gov/api/prod/fileextractservices/v1/api/download/Contract%20Opportunities/Archived%20Data/FY{fy}_archived_opportunities.csv?privacy=Public"
REQUIRED_COLUMNS = {"NoticeId", "Sol#", "PostedDate", "Type", "Active", "AAC Code", "Office", "Link"}


class DataServicesError(RuntimeError):
    pass


class FamilyAmbiguous(DataServicesError):
    pass


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().upper()


def fiscal_year_for_date(value: str) -> int:
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return d.year + 1 if d.month >= 10 else d.year


def download_extract(url: str, *, timeout: float = 60.0, max_bytes: int = 500 * 1024 * 1024) -> bytes:
    require_approved_automation(url, expected="SAM_DATA_SERVICES_EXTRACT")
    req = Request(url, headers={"User-Agent": "CaptureBrief/0.3"})
    try:
        with urlopen(req, timeout=timeout) as response:
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > max_bytes:
                raise DataServicesError(f"extract exceeds max_bytes before download: {declared}")
            data = response.read(max_bytes + 1)
    except HTTPError as exc:
        raise DataServicesError(f"Data Services extract HTTP {exc.code}") from exc
    except URLError as exc:
        raise DataServicesError(f"Data Services extract transport failure: {exc.reason}") from exc
    if len(data) > max_bytes:
        raise DataServicesError("extract exceeds max_bytes during download")
    return data


def _decode_csv(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def scan_extract_bytes(
    data: bytes,
    *,
    source_url: str,
    source_kind: str,
    solicitation_number: str,
    fiscal_year: int | None = None,
) -> dict[str, Any]:
    if source_kind not in {"ACTIVE", "ARCHIVE"}:
        raise ValueError("source_kind must be ACTIVE or ARCHIVE")
    require_approved_automation(source_url, expected="SAM_DATA_SERVICES_EXTRACT")
    target = _norm(solicitation_number)
    reader = csv.DictReader(io.StringIO(_decode_csv(data)), restkey="_extra")
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        raise DataServicesError(f"extract missing columns: {sorted(missing)}")

    rows_scanned = 0
    matches: list[dict[str, Any]] = []
    for row in reader:
        rows_scanned += 1
        if _norm(row.get("Sol#")) != target:
            continue
        raw = {k: row.get(k) for k in reader.fieldnames or []}
        matches.append({
            "notice_id": str(row.get("NoticeId") or "").strip(),
            "solicitation_number": str(row.get("Sol#") or "").strip(),
            "posted_date": str(row.get("PostedDate") or "").strip() or None,
            "notice_type": str(row.get("Type") or "").strip() or None,
            "active": str(row.get("Active") or "").strip() or None,
            "aac_code": str(row.get("AAC Code") or "").strip() or None,
            "office": str(row.get("Office") or "").strip() or None,
            "link": str(row.get("Link") or "").strip() or None,
            "row_sha256": sha256_hex(canonical_json(raw)),
        })

    return {
        "source_kind": source_kind,
        "fiscal_year": fiscal_year,
        "source_url": source_url,
        "extract_sha256": hashlib.sha256(data).hexdigest(),
        "rows_scanned": rows_scanned,
        "matches": matches,
    }


def _family_filter(
    snapshots: Iterable[dict[str, Any]],
    *,
    seed_notice_id: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [row for snap in snapshots for row in snap.get("matches", []) if row.get("notice_id")]
    if not rows:
        raise DataServicesError("no Data Services rows matched the solicitation number")

    seed = None
    if seed_notice_id:
        seed = next((r for r in rows if r.get("notice_id") == seed_notice_id), None)
        if seed is None:
            raise DataServicesError("seed notice ID was not present in the supplied extract set")

    seed_aac = (seed or {}).get("aac_code")
    if seed_aac:
        rows = [r for r in rows if r.get("aac_code") == seed_aac]
    elif not seed_notice_id:
        aacs = {r.get("aac_code") for r in rows if r.get("aac_code")}
        if len(aacs) > 1:
            raise FamilyAmbiguous(f"solicitation number spans multiple AAC codes: {sorted(aacs)}")
        if len(aacs) == 1:
            seed_aac = next(iter(aacs))

    family = {
        "solicitation_number": rows[0].get("solicitation_number"),
        "aac_code": seed_aac,
        "office": (seed or rows[0]).get("office"),
        "seed_notice_id": seed_notice_id,
    }
    return rows, family


def issue_history_receipt_from_snapshots(
    snapshots: list[dict[str, Any]],
    *,
    solicitation_number: str,
    observed_at: str | None = None,
    seed_notice_id: str | None = None,
    scope_start_fy: int | None = None,
    scope_end_fy: int | None = None,
    scope_confirmed: bool = False,
) -> dict[str, Any]:
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    if not parse_dt(observed_at):
        raise ValueError("observed_at must be timezone-aware ISO-8601")
    rows, family = _family_filter(snapshots, seed_notice_id=seed_notice_id)

    action_ids = sorted({r["notice_id"] for r in rows})
    by_notice: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_notice.setdefault(row["notice_id"], []).append(row)

    active_present = any(s.get("source_kind") == "ACTIVE" for s in snapshots)
    supplied_archive_fys = {
        int(s["fiscal_year"])
        for s in snapshots
        if s.get("source_kind") == "ARCHIVE" and s.get("fiscal_year") is not None
    }
    required_archive_fys: set[int] = set()
    if scope_start_fy is not None and scope_end_fy is not None:
        if scope_start_fy > scope_end_fy:
            raise ValueError("scope_start_fy cannot exceed scope_end_fy")
        required_archive_fys = set(range(scope_start_fy, scope_end_fy + 1))
    missing_fys = sorted(required_archive_fys - supplied_archive_fys)

    complete = bool(scope_confirmed and active_present and required_archive_fys and not missing_fys)
    status = "COMPLETE" if complete else "OBSERVED_ONLY"

    payload = {
        "source_contract": "SAM_DATA_SERVICES_EXTRACT",
        "data_services_pages": [ACTIVE_DATA_SERVICES_PAGE, ARCHIVE_DATA_SERVICES_PAGE],
        "family": family,
        "scope": {
            "start_fy": scope_start_fy,
            "end_fy": scope_end_fy,
            "scope_confirmed": scope_confirmed,
            "required_archive_fys": sorted(required_archive_fys),
            "supplied_archive_fys": sorted(supplied_archive_fys),
            "missing_archive_fys": missing_fys,
            "active_extract_present": active_present,
        },
        "actions": [
            {
                "notice_id": notice_id,
                "observations": observations,
            }
            for notice_id, observations in sorted(by_notice.items())
        ],
        "source_snapshots": [
            {
                k: snap.get(k)
                for k in ("source_kind", "fiscal_year", "source_url", "extract_sha256", "rows_scanned")
            }
            for snap in snapshots
        ],
        "ordering_authoritative": False,
        "current_action_authoritative": False,
    }
    return {
        "source_surface": "SAM_DATA_SERVICES",
        "source_url": ACTIVE_DATA_SERVICES_PAGE,
        "observed_at": observed_at,
        "status": status,
        "action_ids": action_ids,
        "history_set_sha256": history_set_digest(action_ids),
        "evidence_payload_sha256": sha256_hex(canonical_json(payload)),
        "evidence_payload": payload,
        "automation_mode": "APPROVED_EXTRACT",
    }


def collect_history_from_files(
    *,
    solicitation_number: str,
    active_csv: str | Path,
    archive_csvs: Iterable[tuple[int, str | Path]] = (),
    seed_notice_id: str | None = None,
    scope_start_fy: int | None = None,
    scope_end_fy: int | None = None,
    scope_confirmed: bool = False,
    observed_at: str | None = None,
) -> dict[str, Any]:
    snapshots = [
        scan_extract_bytes(
            Path(active_csv).read_bytes(),
            source_url=ACTIVE_DOWNLOAD,
            source_kind="ACTIVE",
            solicitation_number=solicitation_number,
        )
    ]
    for fy, path in archive_csvs:
        snapshots.append(
            scan_extract_bytes(
                Path(path).read_bytes(),
                source_url=ARCHIVE_DOWNLOAD.format(fy=fy),
                source_kind="ARCHIVE",
                solicitation_number=solicitation_number,
                fiscal_year=fy,
            )
        )
    return issue_history_receipt_from_snapshots(
        snapshots,
        solicitation_number=solicitation_number,
        observed_at=observed_at,
        seed_notice_id=seed_notice_id,
        scope_start_fy=scope_start_fy,
        scope_end_fy=scope_end_fy,
        scope_confirmed=scope_confirmed,
    )
