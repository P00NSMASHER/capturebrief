from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .archive_catalog import (
    catalog_snapshot,
    catalog_years_for_fiscal_year,
    fiscal_year_for_datetime,
)
from .data_services import (
    ACTIVE_DATA_SERVICES_PAGE,
    ACTIVE_DOWNLOAD,
    ARCHIVE_DOWNLOAD,
    REQUIRED_COLUMNS,
    FamilyAmbiguous,
)
from .model import canonical_json, history_set_digest, parse_dt, sha256_hex
from .source_policy import require_approved_automation

INDEX_SCHEMA_VERSION = 2
DEFAULT_MAX_EXTRACT_BYTES = 2_000_000_000
ACTIVE_MAX_AGE = timedelta(hours=48)
ARCHIVE_MAX_AGE = timedelta(days=9)
APPROVED_FETCH = "APPROVED_FETCH"
OPERATOR_FILE = "OPERATOR_FILE"


class HistoryIndexError(RuntimeError):
    pass


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().upper()


def _file_sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _encoding(path: Path) -> str:
    with path.open("rb") as handle:
        prefix = handle.read(3)
    return "utf-8-sig" if prefix == b"\xef\xbb\xbf" else "cp1252"


def _slot(source_kind: str, fiscal_year: int | None) -> str:
    kind = source_kind.upper()
    if kind == "ACTIVE":
        if fiscal_year is not None:
            raise ValueError("ACTIVE source must not declare fiscal_year")
        return "ACTIVE"
    if kind == "ARCHIVE":
        if fiscal_year is None:
            raise ValueError("ARCHIVE source requires fiscal_year")
        return f"ARCHIVE:{int(fiscal_year)}"
    raise ValueError("source_kind must be ACTIVE or ARCHIVE")


def _connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_index(path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with _connect(p) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                fiscal_year INTEGER,
                source_url TEXT NOT NULL,
                extract_sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                observed_at TEXT NOT NULL,
                local_path TEXT NOT NULL,
                rows_scanned INTEGER NOT NULL DEFAULT 0,
                UNIQUE(slot, extract_sha256)
            );
            CREATE TABLE IF NOT EXISTS current_sources (
                slot TEXT PRIMARY KEY,
                snapshot_id INTEGER NOT NULL REFERENCES source_snapshots(snapshot_id),
                checked_at TEXT,
                collection_mode TEXT,
                source_etag TEXT,
                source_last_modified TEXT
            );
            CREATE TABLE IF NOT EXISTS opportunity_rows (
                snapshot_id INTEGER NOT NULL REFERENCES source_snapshots(snapshot_id),
                row_number INTEGER NOT NULL,
                notice_id TEXT NOT NULL,
                solicitation_norm TEXT NOT NULL,
                solicitation_raw TEXT,
                cgac TEXT,
                fpds_code TEXT,
                aac_code TEXT,
                department TEXT,
                subtier TEXT,
                office TEXT,
                posted_date TEXT,
                notice_type TEXT,
                base_type TEXT,
                active TEXT,
                link TEXT,
                row_sha256 TEXT NOT NULL,
                PRIMARY KEY(snapshot_id, row_number)
            );
            CREATE INDEX IF NOT EXISTS idx_opportunity_sol ON opportunity_rows(solicitation_norm);
            CREATE INDEX IF NOT EXISTS idx_opportunity_notice ON opportunity_rows(notice_id);
            CREATE INDEX IF NOT EXISTS idx_opportunity_aac ON opportunity_rows(solicitation_norm, aac_code);
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(current_sources)").fetchall()}
        for name, ddl in (
            ("checked_at", "TEXT"),
            ("collection_mode", "TEXT"),
            ("source_etag", "TEXT"),
            ("source_last_modified", "TEXT"),
        ):
            if name not in columns:
                conn.execute(f"ALTER TABLE current_sources ADD COLUMN {name} {ddl}")
        conn.execute(
            "INSERT INTO metadata(key,value) VALUES('schema_version',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(INDEX_SCHEMA_VERSION),),
        )


def download_extract_to_file(
    destination: str | Path,
    *,
    source_url: str,
    timeout: float = 120.0,
    max_bytes: int = DEFAULT_MAX_EXTRACT_BYTES,
    opener=urlopen,
) -> dict[str, Any]:
    """Stream one approved Data Services extract to disk with a verified SHA-256."""
    require_approved_automation(source_url, expected="SAM_DATA_SERVICES_EXTRACT")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    digest = hashlib.sha256()
    size = 0
    req = Request(source_url, headers={"User-Agent": "CaptureBrief/0.3"})
    try:
        response = opener(req, timeout=timeout)
        with response, tmp.open("wb") as out:
            declared = response.headers.get("Content-Length") if getattr(response, "headers", None) else None
            if declared and int(declared) > max_bytes:
                raise HistoryIndexError(f"extract exceeds max_bytes before download: {declared}")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HistoryIndexError("extract exceeds max_bytes during download")
                digest.update(chunk)
                out.write(chunk)
        final_url = response.geturl() if hasattr(response, "geturl") else source_url
        source_etag = response.headers.get("ETag") if getattr(response, "headers", None) else None
        source_last_modified = response.headers.get("Last-Modified") if getattr(response, "headers", None) else None
        tmp.replace(dest)
    except HTTPError as exc:
        tmp.unlink(missing_ok=True)
        raise HistoryIndexError(f"Data Services HTTP {exc.code}") from exc
    except URLError as exc:
        tmp.unlink(missing_ok=True)
        raise HistoryIndexError(f"Data Services transport failure: {exc.reason}") from exc
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return {
        "path": str(dest),
        "source_url": source_url,
        "sha256": digest.hexdigest(),
        "size_bytes": size,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "final_url": final_url,
        "source_etag": source_etag,
        "source_last_modified": source_last_modified,
    }


def fetch_and_ingest_slot(
    index_path: str | Path,
    *,
    slot: str,
    destination: str | Path,
    snapshot_dir: str | Path | None = None,
    observed_at: str | None = None,
    max_bytes: int = DEFAULT_MAX_EXTRACT_BYTES,
    opener=urlopen,
) -> dict[str, Any]:
    """Explicitly fetch and ingest one catalog slot. Never syncs other slots implicitly."""
    slot = str(slot).upper()
    if slot == "ACTIVE":
        kind, fy, url = "ACTIVE", None, ACTIVE_DOWNLOAD
    elif slot.startswith("ARCHIVE:"):
        fy = int(slot.split(":", 1)[1])
        if fy not in set(catalog_years_for_fiscal_year(fiscal_year_for_datetime())):
            raise HistoryIndexError(f"archive slot is not in the current pinned catalog: {slot}")
        kind, url = "ARCHIVE", ARCHIVE_DOWNLOAD.format(fy=fy)
    else:
        raise ValueError("slot must be ACTIVE or ARCHIVE:<FY>")
    download = download_extract_to_file(
        destination, source_url=url, max_bytes=max_bytes, opener=opener
    )
    ingested = ingest_extract_file(
        index_path,
        download["path"],
        source_url=url,
        source_kind=kind,
        fiscal_year=fy,
        observed_at=download["observed_at"],
        snapshot_dir=snapshot_dir,
        collection_mode=APPROVED_FETCH,
        source_etag=download.get("source_etag"),
        source_last_modified=download.get("source_last_modified"),
    )
    return {"download": download, "ingest": ingested}


def ingest_extract_file(
    index_path: str | Path,
    csv_path: str | Path,
    *,
    source_url: str,
    source_kind: str,
    fiscal_year: int | None = None,
    observed_at: str | None = None,
    snapshot_dir: str | Path | None = None,
    collection_mode: str = OPERATOR_FILE,
    source_etag: str | None = None,
    source_last_modified: str | None = None,
) -> dict[str, Any]:
    """Stream one approved Data Services CSV into a reusable evidence index.

    The source file is hashed before parsing. When snapshot_dir is supplied, bytes are copied to
    a content-addressed, read-only path so case receipts can point back to the exact file indexed.
    """
    require_approved_automation(source_url, expected="SAM_DATA_SERVICES_EXTRACT")
    kind = source_kind.upper()
    slot = _slot(kind, fiscal_year)
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    if not parse_dt(observed_at):
        raise ValueError("observed_at must be timezone-aware ISO-8601")
    collection_mode = str(collection_mode).upper()
    if collection_mode not in {APPROVED_FETCH, OPERATOR_FILE}:
        raise ValueError("collection_mode must be APPROVED_FETCH or OPERATOR_FILE")

    source_path = Path(csv_path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    digest, size = _file_sha256(source_path)

    retained_path = source_path
    if snapshot_dir is not None:
        root = Path(snapshot_dir)
        root.mkdir(parents=True, exist_ok=True)
        retained_path = root / f"{digest}.csv"
        if not retained_path.exists():
            tmp = retained_path.with_suffix(".csv.part")
            shutil.copyfile(source_path, tmp)
            copied_digest, copied_size = _file_sha256(tmp)
            if copied_digest != digest or copied_size != size:
                tmp.unlink(missing_ok=True)
                raise HistoryIndexError("content-addressed snapshot copy failed hash verification")
            tmp.replace(retained_path)
            try:
                retained_path.chmod(0o444)
            except OSError:
                pass

    init_index(index_path)
    with _connect(index_path) as conn:
        existing = conn.execute(
            "SELECT snapshot_id, rows_scanned FROM source_snapshots WHERE slot=? AND extract_sha256=?",
            (slot, digest),
        ).fetchone()
        if existing is not None:
            conn.execute(
                "INSERT INTO current_sources(slot,snapshot_id,checked_at,collection_mode,source_etag,source_last_modified) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(slot) DO UPDATE SET "
                "snapshot_id=excluded.snapshot_id, checked_at=excluded.checked_at, "
                "collection_mode=excluded.collection_mode, source_etag=excluded.source_etag, "
                "source_last_modified=excluded.source_last_modified",
                (slot, int(existing["snapshot_id"]), observed_at, collection_mode, source_etag, source_last_modified),
            )
            return {
                "snapshot_id": int(existing["snapshot_id"]),
                "slot": slot,
                "extract_sha256": digest,
                "size_bytes": size,
                "rows_scanned": int(existing["rows_scanned"]),
                "reused": True,
                "local_path": str(retained_path),
            }

        cur = conn.execute(
            "INSERT INTO source_snapshots(slot,source_kind,fiscal_year,source_url,extract_sha256,"
            "size_bytes,observed_at,local_path,rows_scanned) VALUES(?,?,?,?,?,?,?,?,0)",
            (slot, kind, fiscal_year, source_url, digest, size, observed_at, str(retained_path)),
        )
        snapshot_id = int(cur.lastrowid)
        rows_scanned = 0
        batch: list[tuple[Any, ...]] = []

        with retained_path.open("r", encoding=_encoding(retained_path), errors="replace", newline="") as handle:
            reader = csv.DictReader(handle, restkey="_extra")
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing:
                raise HistoryIndexError(f"extract missing required columns: {sorted(missing)}")
            for row_number, row in enumerate(reader, start=1):
                rows_scanned += 1
                raw = {k: row.get(k) for k in reader.fieldnames or []}
                batch.append(
                    (
                        snapshot_id,
                        row_number,
                        str(row.get("NoticeId") or "").strip(),
                        _norm(row.get("Sol#")),
                        str(row.get("Sol#") or "").strip() or None,
                        str(row.get("CGAC") or "").strip() or None,
                        str(row.get("FPDS Code") or "").strip() or None,
                        str(row.get("AAC Code") or "").strip() or None,
                        str(row.get("Department/Ind.Agency") or "").strip() or None,
                        str(row.get("Sub-Tier") or "").strip() or None,
                        str(row.get("Office") or "").strip() or None,
                        str(row.get("PostedDate") or "").strip() or None,
                        str(row.get("Type") or "").strip() or None,
                        str(row.get("BaseType") or "").strip() or None,
                        str(row.get("Active") or "").strip() or None,
                        str(row.get("Link") or "").strip() or None,
                        sha256_hex(canonical_json(raw)),
                    )
                )
                if len(batch) >= 2000:
                    conn.executemany(
                        "INSERT INTO opportunity_rows(snapshot_id,row_number,notice_id,solicitation_norm,"
                        "solicitation_raw,cgac,fpds_code,aac_code,department,subtier,office,posted_date,"
                        "notice_type,base_type,active,link,row_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        batch,
                    )
                    batch.clear()
            if batch:
                conn.executemany(
                    "INSERT INTO opportunity_rows(snapshot_id,row_number,notice_id,solicitation_norm,"
                    "solicitation_raw,cgac,fpds_code,aac_code,department,subtier,office,posted_date,"
                    "notice_type,base_type,active,link,row_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    batch,
                )

        conn.execute(
            "UPDATE source_snapshots SET rows_scanned=? WHERE snapshot_id=?",
            (rows_scanned, snapshot_id),
        )
        conn.execute(
            "INSERT INTO current_sources(slot,snapshot_id,checked_at,collection_mode,source_etag,source_last_modified) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(slot) DO UPDATE SET "
            "snapshot_id=excluded.snapshot_id, checked_at=excluded.checked_at, "
            "collection_mode=excluded.collection_mode, source_etag=excluded.source_etag, "
            "source_last_modified=excluded.source_last_modified",
            (slot, snapshot_id, observed_at, collection_mode, source_etag, source_last_modified),
        )
        return {
            "snapshot_id": snapshot_id,
            "slot": slot,
            "extract_sha256": digest,
            "size_bytes": size,
            "rows_scanned": rows_scanned,
            "reused": False,
            "local_path": str(retained_path),
        }


def index_status(
    index_path: str | Path,
    *,
    fiscal_year: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    fiscal_year = fiscal_year or fiscal_year_for_datetime()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    required_years = catalog_years_for_fiscal_year(fiscal_year)
    required_slots = {"ACTIVE", *{f"ARCHIVE:{year}" for year in required_years}}
    init_index(index_path)
    with _connect(index_path) as conn:
        rows = conn.execute(
            "SELECT c.slot,c.checked_at,c.collection_mode,c.source_etag,c.source_last_modified,"
            "s.snapshot_id,s.source_kind,s.fiscal_year,s.source_url,s.extract_sha256,"
            "s.size_bytes,s.observed_at,s.local_path,s.rows_scanned "
            "FROM current_sources c JOIN source_snapshots s ON s.snapshot_id=c.snapshot_id"
        ).fetchall()
    snapshots = [dict(row) for row in rows]
    present = {row["slot"] for row in snapshots}
    missing = sorted(required_slots - present)
    stale: list[str] = []
    unverified: list[str] = []
    fresh: list[str] = []
    for row in snapshots:
        slot = row["slot"]
        if slot not in required_slots:
            continue
        if row.get("collection_mode") != APPROVED_FETCH:
            unverified.append(slot)
            continue
        checked = parse_dt(row.get("checked_at"))
        if not checked:
            unverified.append(slot)
            continue
        max_age = ACTIVE_MAX_AGE if slot == "ACTIVE" else ARCHIVE_MAX_AGE
        if now - checked > max_age or checked > now + timedelta(minutes=5):
            stale.append(slot)
        else:
            fresh.append(slot)
    return {
        "complete": not missing and not stale and not unverified,
        "fiscal_year": fiscal_year,
        "checked_at": now.isoformat(),
        "catalog": catalog_snapshot(),
        "required_archive_years": required_years,
        "required_slots": sorted(required_slots),
        "present_slots": sorted(present),
        "fresh_slots": sorted(fresh),
        "missing_slots": missing,
        "stale_slots": sorted(stale),
        "unverified_slots": sorted(unverified),
        "freshness_policy": {
            "active_max_age_hours": int(ACTIVE_MAX_AGE.total_seconds() // 3600),
            "archive_max_age_hours": int(ARCHIVE_MAX_AGE.total_seconds() // 3600),
            "basis": "GSA publishes active notices daily and archived notices weekly; CaptureBrief uses conservative check windows.",
        },
        "snapshots": snapshots,
    }


def sync_plan(index_path: str | Path, *, fiscal_year: int | None = None, now: datetime | None = None) -> dict[str, Any]:
    status = index_status(index_path, fiscal_year=fiscal_year, now=now)
    items: list[dict[str, Any]] = []
    needed = [
        *(("MISSING", slot) for slot in status["missing_slots"]),
        *(("STALE", slot) for slot in status["stale_slots"]),
        *(("UNVERIFIED", slot) for slot in status["unverified_slots"]),
    ]
    for reason, slot in needed:
        if slot == "ACTIVE":
            items.append({"slot": slot, "reason": reason, "source_kind": "ACTIVE", "fiscal_year": None, "source_url": ACTIVE_DOWNLOAD})
        else:
            fy = int(slot.split(":", 1)[1])
            items.append({"slot": slot, "reason": reason, "source_kind": "ARCHIVE", "fiscal_year": fy, "source_url": ARCHIVE_DOWNLOAD.format(fy=fy)})
    return {**status, "download_plan": items}


def _current_family_rows(conn: sqlite3.Connection, solicitation_number: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT r.*, s.slot, s.source_kind, s.fiscal_year, s.source_url, s.extract_sha256,
               s.observed_at AS extract_observed_at
        FROM opportunity_rows r
        JOIN source_snapshots s ON s.snapshot_id=r.snapshot_id
        JOIN current_sources c ON c.snapshot_id=s.snapshot_id
        WHERE r.solicitation_norm=?
        """,
        (_norm(solicitation_number),),
    ).fetchall()
    return [dict(row) for row in rows]


def issue_history_receipt_from_index(
    index_path: str | Path,
    *,
    solicitation_number: str,
    seed_notice_id: str,
    observed_at: str | None = None,
    fiscal_year: int | None = None,
) -> dict[str, Any]:
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    if not parse_dt(observed_at):
        raise ValueError("observed_at must be timezone-aware ISO-8601")
    fiscal_year = fiscal_year or fiscal_year_for_datetime()
    coverage = index_status(index_path, fiscal_year=fiscal_year, now=parse_dt(observed_at))

    with _connect(index_path) as conn:
        rows = _current_family_rows(conn, solicitation_number)

    seed = next((row for row in rows if row.get("notice_id") == seed_notice_id), None)
    errors: list[str] = []
    if seed is None:
        errors.append("SEED_NOTICE_NOT_IN_CURRENT_INDEX")
        family_rows: list[dict[str, Any]] = []
        family = {
            "solicitation_number": solicitation_number,
            "aac_code": None,
            "office": None,
            "seed_notice_id": seed_notice_id,
        }
    else:
        seed_aac = _norm(seed.get("aac_code"))
        seed_office = _norm(seed.get("office"))
        if seed_aac:
            family_rows = [row for row in rows if _norm(row.get("aac_code")) == seed_aac]
        elif seed_office:
            family_rows = [row for row in rows if _norm(row.get("office")) == seed_office]
        else:
            aacs = {_norm(row.get("aac_code")) for row in rows if _norm(row.get("aac_code"))}
            if len(aacs) > 1:
                raise FamilyAmbiguous(f"solicitation number spans multiple AAC codes: {sorted(aacs)}")
            family_rows = rows
        family = {
            "solicitation_number": seed.get("solicitation_raw") or solicitation_number,
            "aac_code": seed.get("aac_code"),
            "office": seed.get("office"),
            "seed_notice_id": seed_notice_id,
        }

    by_notice: dict[str, list[dict[str, Any]]] = {}
    for row in family_rows:
        notice_id = str(row.get("notice_id") or "")
        if not notice_id:
            continue
        observation = {
            "row_sha256": row.get("row_sha256"),
            "source_kind": row.get("source_kind"),
            "fiscal_year": row.get("fiscal_year"),
            "source_url": row.get("source_url"),
            "extract_sha256": row.get("extract_sha256"),
            "posted_date": row.get("posted_date"),
            "notice_type": row.get("notice_type"),
            "active": row.get("active"),
            "aac_code": row.get("aac_code"),
            "office": row.get("office"),
            "link": row.get("link"),
        }
        by_notice.setdefault(notice_id, []).append(observation)

    action_ids = sorted(by_notice)
    if seed_notice_id and seed_notice_id not in action_ids:
        errors.append("SEED_NOTICE_OUTSIDE_FILTERED_FAMILY")
    if coverage["missing_slots"]:
        errors.append("FULL_ARCHIVE_CATALOG_NOT_INDEXED")
    if coverage["stale_slots"]:
        errors.append("FULL_ARCHIVE_CATALOG_STALE")
    if coverage["unverified_slots"]:
        errors.append("FULL_ARCHIVE_CATALOG_UNVERIFIED")

    cat = coverage["catalog"]
    scope = {
        "mode": "FULL_CATALOG",
        "catalog_version": cat["catalog_version"],
        "catalog_sha256": cat["catalog_sha256"],
        "catalog_source_url": cat["source_url"],
        "catalog_observed_at": cat["observed_at"],
        "catalog_fiscal_year": fiscal_year,
        "scope_confirmed": True,
        "required_archive_fys": coverage["required_archive_years"],
        "supplied_archive_fys": sorted(
            int(row["fiscal_year"])
            for row in coverage["snapshots"]
            if row.get("source_kind") == "ARCHIVE" and row.get("fiscal_year") is not None
        ),
        "missing_archive_fys": [
            int(slot.split(":", 1)[1])
            for slot in coverage["missing_slots"]
            if slot.startswith("ARCHIVE:")
        ],
        "active_extract_present": "ACTIVE" in coverage["present_slots"],
        "catalog_snapshot": cat,
        "coverage_complete": coverage["complete"],
        "stale_slots": coverage["stale_slots"],
        "unverified_slots": coverage["unverified_slots"],
        "freshness_checked_at": coverage["checked_at"],
        "freshness_policy": coverage["freshness_policy"],
    }
    payload = {
        "source_contract": "SAM_DATA_SERVICES_EXTRACT",
        "family": family,
        "scope": scope,
        "actions": [
            {"notice_id": notice_id, "observations": observations}
            for notice_id, observations in sorted(by_notice.items())
        ],
        "source_snapshots": [
            {
                "source_kind": row["source_kind"],
                "fiscal_year": row["fiscal_year"],
                "source_url": row["source_url"],
                "extract_sha256": row["extract_sha256"],
                "rows_scanned": row["rows_scanned"],
                "checked_at": row["checked_at"],
                "collection_mode": row["collection_mode"],
                "source_etag": row["source_etag"],
                "source_last_modified": row["source_last_modified"],
                "freshness_status": (
                    "FRESH" if row["slot"] in coverage["fresh_slots"]
                    else "STALE" if row["slot"] in coverage["stale_slots"]
                    else "UNVERIFIED"
                ),
            }
            for row in coverage["snapshots"]
        ],
        "ordering_authoritative": False,
        "current_action_authoritative": False,
        "index_contract": "CAPTUREBRIEF_DATA_SERVICES_INDEX_V1",
        "index_schema_version": INDEX_SCHEMA_VERSION,
        "coverage_errors": errors,
    }
    status = "COMPLETE" if not errors and action_ids else "OBSERVED_ONLY"
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
