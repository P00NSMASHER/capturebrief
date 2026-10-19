"""Read-only operator audit of CaptureBrief's indexed SAM source coverage.

This does NOT download sources, migrate/create an index, verify that a publisher
actually supplied a file, approve a catalog, or authorize customer work.
The optional full-byte check compares each private retained file with its
locally recorded SHA-256 (an integrity check, not publisher authentication).
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from capturebrief_core.archive_catalog import catalog_years_for_fiscal_year
from capturebrief_core.data_services import ACTIVE_DOWNLOAD, ARCHIVE_DOWNLOAD
from capturebrief_core.history_index import (
    ACTIVE_MAX_AGE, ARCHIVE_MAX_AGE, APPROVED_FETCH, INDEX_SCHEMA_VERSION,
)
from capturebrief_core.model import parse_dt

REPOSITORY = Path(__file__).resolve().parents[1]
SHA = re.compile(r"^[a-f0-9]{64}$")


def _private_regular(path: str | Path) -> Path:
    raw = Path(path).expanduser().absolute()
    if raw.is_relative_to(REPOSITORY) or raw.is_symlink():
        raise ValueError("Index must be a private regular file outside public repository")
    resolved = raw.resolve(strict=True)
    if resolved.is_relative_to(REPOSITORY) or not resolved.is_file():
        raise ValueError("Index must be a private regular file outside public repository")
    return resolved


def _source_file_matches(row: dict, *, check_hash: bool, snapshot_root: Path) -> bool:
    try:
        path = Path(str(row["local_path"]))
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            return False
        # Database fields are untrusted pointers. Never inspect arbitrary
        # operator/system files: only the explicitly approved extract root.
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(snapshot_root):
            return False
        declared = row["size_bytes"]
        if type(declared) is not int or declared < 1:
            return False
        if path.stat().st_size != declared:
            return False
        if not check_hash:
            return True
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest() == row["extract_sha256"]
    except (OSError, ValueError, TypeError, KeyError):
        return False


def inspect_private_index(
    index_path: str | Path,
    *,
    fiscal_year: int,
    now: datetime,
    verify_bytes: bool = False,
    snapshot_root: str | Path | None = None,
) -> dict:
    """Summarize approved SAM slot metadata; never create/mutate the index."""
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("Inspection time must be timezone-aware")
    now = now.astimezone(timezone.utc)
    years = catalog_years_for_fiscal_year(fiscal_year)  # fail-closed catalog check
    required = {"ACTIVE", *(f"ARCHIVE:{fy}" for fy in years)}
    path = _private_regular(index_path)
    raw_root = Path(snapshot_root).expanduser().absolute() if snapshot_root is not None else path.parent
    if raw_root.is_symlink() or raw_root.is_relative_to(REPOSITORY):
        raise ValueError("Snapshot root must be a private directory outside public repository")
    allowed_root = raw_root.resolve(strict=True)
    if allowed_root.is_relative_to(REPOSITORY) or not allowed_root.is_dir():
        raise ValueError("Snapshot root must be a private directory outside public repository")
    uri = "file:" + quote(str(path), safe="/:") + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        schema = conn.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
        if schema is None or schema["value"] != str(INDEX_SCHEMA_VERSION):
            raise ValueError("History index schema version is not supported")
        rows = [dict(row) for row in conn.execute(
            "SELECT c.slot, c.checked_at, c.collection_mode, "
            "s.source_kind, s.fiscal_year, s.source_url, s.extract_sha256, "
            "s.size_bytes, s.observed_at, s.local_path "
            "FROM current_sources c JOIN source_snapshots s "
            "ON s.snapshot_id=c.snapshot_id"
        ).fetchall()]
        conn.execute("ROLLBACK")

    by_slot = {row["slot"]: row for row in rows if row["slot"] in required}
    missing = sorted(required - set(by_slot))
    stale: list[str] = []
    unverified: list[str] = []
    missing_bytes: list[str] = []
    mismatched_hashes: list[str] = []
    fresh: list[str] = []
    for slot, row in sorted(by_slot.items()):
        fy = None if slot == "ACTIVE" else int(slot.removeprefix("ARCHIVE:"))
        expected = ACTIVE_DOWNLOAD if fy is None else ARCHIVE_DOWNLOAD.format(fy=fy)
        checked = parse_dt(row.get("checked_at"))
        observed = parse_dt(row.get("observed_at"))
        if (row.get("collection_mode") != APPROVED_FETCH
                or row.get("source_url") != expected
                or row.get("source_kind") != ("ACTIVE" if fy is None else "ARCHIVE")
                or row.get("fiscal_year") != fy
                or not isinstance(row.get("extract_sha256"), str)
                or SHA.fullmatch(row["extract_sha256"]) is None
                or checked is None or observed is None
                or observed > checked + timedelta(minutes=5)):
            unverified.append(slot)
            continue
        age_limit = ACTIVE_MAX_AGE if fy is None else ARCHIVE_MAX_AGE
        if now - checked > age_limit or checked > now + timedelta(minutes=5):
            stale.append(slot)
            continue
        if not _source_file_matches(row, check_hash=False, snapshot_root=allowed_root):
            missing_bytes.append(slot)
            continue
        if verify_bytes and not _source_file_matches(row, check_hash=True, snapshot_root=allowed_root):
            mismatched_hashes.append(slot)
            continue
        fresh.append(slot)

    metadata_complete = not (missing or stale or unverified or missing_bytes)
    intact_local_bytes = metadata_complete and verify_bytes and not mismatched_hashes
    return {
        "schema": "capturebrief-source-coverage-audit-v1",
        "fiscal_year": fiscal_year,
        "checked_at": now.isoformat().replace("+00:00", "Z"),
        "required_slot_count": len(required),
        "fresh_slot_count": len(fresh),
        "missing_slots": missing,
        "stale_slots": stale,
        "unverified_slots": unverified,
        "missing_or_wrong_size_file_slots": missing_bytes,
        "hash_mismatch_slots": mismatched_hashes,
        "metadata_complete": metadata_complete,
        "file_hashes_checked": verify_bytes,
        "local_file_hashes_match": intact_local_bytes,
        "publisher_authenticity_independently_established": False,
        "human_catalog_approval_supplied": False,
        "external_send_authorized": False,
    }
