from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .archive_catalog import ARCHIVE_CATALOG_CURRENT_THROUGH_FY
from .model import canonical_json, history_set_digest, parse_dt, sha256_hex
from .source_policy import (
    open_approved_extract, require_approved_automation,
    require_approved_extract_delivery,
)

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


def _require_exact_original_source_slot(source_kind: str, fiscal_year: int | None,
                                        source_url: str) -> str:
    """Bind source type to exact GSA active/archive original endpoint.

    A URL being in the approved Data Services class does not prove it
    describes the specific ARCHIVE FY or ACTIVE type supplied by a caller.
    """
    if source_kind not in {"ACTIVE", "ARCHIVE"}:
        raise ValueError("source_kind must be ACTIVE or ARCHIVE")
    if source_kind == "ACTIVE":
        if fiscal_year is not None or source_url != ACTIVE_DOWNLOAD:
            raise ValueError("ACTIVE original source and fiscal-year label do not match")
        return "ACTIVE"
    if (type(fiscal_year) is not int or not 1900 <= fiscal_year <= 2099
            or source_url != ARCHIVE_DOWNLOAD.format(fy=fiscal_year)):
        raise ValueError("ARCHIVE original fiscal year and official source URL do not match")
    return f"ARCHIVE:{fiscal_year}"


def fiscal_year_for_date(value: str) -> int:
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return d.year + 1 if d.month >= 10 else d.year


def download_extract(
    url: str, *, timeout: float = 60.0,
    max_bytes: int = 500 * 1024 * 1024, opener=None,
) -> bytes:
    """Read an approved SAM extract without following arbitrary URL redirects."""
    require_approved_extract_delivery(url, url)
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    req = Request(url, headers={
        "User-Agent": "CaptureBrief/0.3",
        "Accept-Encoding": "identity",
    })
    try:
        with open_approved_extract(req, timeout=timeout, source_url=url, opener=opener) as response:
            # Revalidate even when using an injected opener (test cases) and
            # before accepting ANY bytes as first-party Data Services evidence.
            final_url = response.geturl() if hasattr(response, "geturl") else url
            require_approved_extract_delivery(url, final_url)
            status = getattr(response, "status", None)
            if status is None and hasattr(response, "getcode"):
                status = response.getcode()
            if status != 200:
                raise DataServicesError("Data Services full original requires HTTP 200")
            headers = getattr(response, "headers", None)
            if headers is None:
                raise DataServicesError("Data Services source response lacks headers")
            if str(headers.get("Content-Encoding", "identity")).strip().lower() != "identity":
                raise DataServicesError("Data Services original must use identity transfer encoding")
            if headers.get("Content-Range"):
                raise DataServicesError("Data Services full original cannot be a byte range")
            declared = headers.get("Content-Length")
            expected = None
            if declared not in (None, ""):
                try:
                    expected = int(declared)
                except (ValueError, TypeError) as exc:
                    raise DataServicesError("Data Services extract Content-Length is invalid") from exc
                if expected < 0 or expected > max_bytes:
                    raise DataServicesError("Data Services extract Content-Length exceeds accepted bounds")
            data = response.read(max_bytes + 1)
    except HTTPError as exc:
        # HTTPError may include a temporary X-Amz-signed URL as its cause.
        raise DataServicesError(f"Data Services extract HTTP {exc.code}") from None
    except URLError:
        # Suppress urllib's cause to avoid exposing query signatures even
        # when a caller prints the complete Python traceback.
        raise DataServicesError("Data Services extract transport failure") from None
    if len(data) > max_bytes:
        raise DataServicesError("extract exceeds max_bytes during download")
    if expected is not None and len(data) != expected:
        raise DataServicesError("Data Services extract did not match Content-Length")
    return data


def _decode_csv(data: bytes) -> str:
    # A UTF-8 BOM declares encoding. Never reinterpret invalid UTF-8
    # with a permissive fallback that changes a publisher NoticeId.
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="strict")
    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="strict")


def scan_extract_bytes(
    data: bytes,
    *,
    source_url: str,
    source_kind: str,
    solicitation_number: str,
    fiscal_year: int | None = None,
) -> dict[str, Any]:
    _require_exact_original_source_slot(source_kind, fiscal_year, source_url)
    require_approved_automation(source_url, expected="SAM_DATA_SERVICES_EXTRACT")
    target = _norm(solicitation_number)
    if not target:
        raise ValueError("Solicitation number must be nonempty for extract matching")
    reader = csv.DictReader(
        io.StringIO(_decode_csv(data), newline=""), restkey="_extra", strict=True,
    )
    columns = list(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - set(columns)
    if missing:
        raise DataServicesError(f"extract missing columns: {sorted(missing)}")
    if (len(columns) != len(set(columns))
            or any(not isinstance(field, str) or not field.strip() for field in columns)
            or "_extra" in columns):
        raise DataServicesError("extract contains duplicate, blank or reserved CSV headers")

    rows_scanned = 0
    seen_original_notice_ids: set[str] = set()
    matches: list[dict[str, Any]] = []
    for row in reader:
        if "_extra" in row or any(row.get(field) is None for field in columns):
            raise DataServicesError("extract original has an invalid CSV column count")
        notice_id = str(row.get("NoticeId") or "").strip()
        if not notice_id:
            raise DataServicesError("extract original row lacks primary NoticeId")
        # Reject duplicate action identities within ONE original, including
        # rows outside the requested Sol#, before a receipt can look complete.
        # The same NoticeId may legitimately appear in different snapshots.
        normalized_notice = _norm(notice_id)
        if normalized_notice in seen_original_notice_ids:
            raise DataServicesError("extract original contains duplicate NoticeId")
        seen_original_notice_ids.add(normalized_notice)
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

    if seed is not None:
        seed_aac = _norm(seed.get("aac_code"))
        seed_office = _norm(seed.get("office"))
        if not seed_aac or not seed_office:
            raise FamilyAmbiguous("seed has no independently anchored agency and office")
        anchored = [
            row for row in rows
            if _norm(row.get("aac_code")) == seed_aac
            and _norm(row.get("office")) == seed_office
        ]
        anchor_notice_ids = {str(row.get("notice_id") or "") for row in anchored}
        for row in rows:
            row_aac = _norm(row.get("aac_code"))
            row_office = _norm(row.get("office"))
            if ((row_aac == seed_aac and row_office != seed_office)
                    or (not row_aac and row_office in ("", seed_office))
                    or (str(row.get("notice_id") or "") in anchor_notice_ids
                        and (row_aac, row_office) != (seed_aac, seed_office))):
                raise FamilyAmbiguous("solicitation family has conflicting agency or office identity")
        rows = anchored
    else:
        # Without an anchored seed, neither an unknown AAC nor differing
        # offices can be silently resolved by solicitation number alone.
        known_aacs = {_norm(row.get("aac_code")) for row in rows}
        known_offices = {_norm(row.get("office")) for row in rows}
        if (len(known_aacs) != 1 or "" in known_aacs
                or len(known_offices) != 1 or "" in known_offices):
            raise FamilyAmbiguous("solicitation family needs a unique agency and office")
        seed_aac = next(iter(known_aacs))
        seed_office = next(iter(known_offices))

    family = {
        "solicitation_number": rows[0].get("solicitation_number"),
        "aac_code": seed_aac,
        "office": seed_office,
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
    target_solicitation = _norm(solicitation_number)
    if not target_solicitation:
        raise ValueError("Solicitation number must be nonempty for history receipt")
    if not isinstance(snapshots, list) or not snapshots:
        raise DataServicesError("No original source snapshots supplied")
    source_slots: set[str] = set()
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            raise DataServicesError("Malformed original source snapshot")
        try:
            slot = _require_exact_original_source_slot(
                snapshot.get("source_kind"), snapshot.get("fiscal_year"),
                snapshot.get("source_url"),
            )
            require_approved_automation(
                snapshot["source_url"], expected="SAM_DATA_SERVICES_EXTRACT",
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise DataServicesError("Original snapshot source slot is invalid") from None
        if slot in source_slots:
            raise DataServicesError("Duplicate original source slot in history receipt")
        source_slots.add(slot)
        count = snapshot.get("rows_scanned")
        digest = snapshot.get("extract_sha256")
        matches = snapshot.get("matches")
        if (type(count) is not int or count < 0
                or not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                or not isinstance(matches, list) or len(matches) > count):
            raise DataServicesError("Invalid original snapshot count or source digest")
        seen_notice: set[str] = set()
        for match in matches:
            if not isinstance(match, dict):
                raise DataServicesError("Malformed source-matched action")
            notice_id = match.get("notice_id")
            row_digest = match.get("row_sha256")
            if (not isinstance(notice_id, str) or not notice_id.strip()
                    or _norm(match.get("solicitation_number")) != target_solicitation
                    or not isinstance(row_digest, str)
                    or re.fullmatch(r"[0-9a-f]{64}", row_digest) is None):
                raise DataServicesError("Original snapshot contains invalid matched action")
            normalized = _norm(notice_id)
            if normalized in seen_notice:
                raise DataServicesError("Duplicate NoticeId within source snapshot matches")
            seen_notice.add(normalized)
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

    # A caller-supplied scope flag is NOT human approval of a later
    # publisher catalog. The production catalog still ends at FY2026.
    production_catalog_approved = (
        type(scope_start_fy) is int and type(scope_end_fy) is int
        and 1900 <= scope_start_fy <= scope_end_fy
        and scope_end_fy <= ARCHIVE_CATALOG_CURRENT_THROUGH_FY
    )
    if scope_confirmed is True and required_archive_fys:
        out_of_scope = supplied_archive_fys - required_archive_fys
        if out_of_scope:
            raise DataServicesError("Out-of-scope archived originals cannot certify history")
    complete = bool(
        scope_confirmed is True and production_catalog_approved
        and active_present and required_archive_fys and not missing_fys
    )
    status = "COMPLETE" if complete else "OBSERVED_ONLY"

    payload = {
        "source_contract": "SAM_DATA_SERVICES_EXTRACT",
        "data_services_pages": [ACTIVE_DATA_SERVICES_PAGE, ARCHIVE_DATA_SERVICES_PAGE],
        "family": family,
        "scope": {
            "start_fy": scope_start_fy,
            "end_fy": scope_end_fy,
            "scope_confirmed": scope_confirmed,
            "production_archive_catalog_approved": production_catalog_approved,
            "production_catalog_current_through_fy": ARCHIVE_CATALOG_CURRENT_THROUGH_FY,
            "original_snapshot_slots_validated": True,
            "independent_publisher_authenticity_approved": False,
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
