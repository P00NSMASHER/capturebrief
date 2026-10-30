"""Read-only operator audit of CaptureBrief's indexed SAM source coverage.

This does NOT download sources, migrate/create an index, verify that a publisher
actually supplied a file, approve a catalog, or authorize customer work.
The optional full-byte check compares each private retained file with its
locally recorded SHA-256 (an integrity check, not publisher authentication).
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from capturebrief_core.accepted_case_release import _reject_private_path_links
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
    # Reject every symlink/junction ancestor before resolving or reading the
    # index. A final regular file can still be reached via an unsafe alias.
    try:
        _reject_private_path_links(raw)
    except ValueError:
        # Preserve the existing read-only index error contract while
        # refusing a symlink/junction anywhere in the ancestry.
        raise ValueError("Index must be a private regular file outside public repository") from None
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
        # The index is not authority to traverse an attacker-controlled alias
        # even if it resolves back inside the approved extract directory.
        # Shared guard also catches Windows junction/reparse ancestors.
        _reject_private_path_links(path)
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


def _inspect_index_for_explicit_years(
    index_path: str | Path,
    *,
    fiscal_year: int,
    years: list[int],
    now: datetime,
    verify_bytes: bool = False,
    snapshot_root: str | Path | None = None,
) -> dict:
    """Summarize approved SAM slot metadata; never create/mutate the index."""
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("Inspection time must be timezone-aware")
    now = now.astimezone(timezone.utc)
    if (type(years) is not list or len(years) == 0
            or any(type(fy) is not int or fy < 1900 or fy > fiscal_year for fy in years)
            or len(set(years)) != len(years)):
        raise ValueError("Invalid explicit archive-year inventory for read-only audit")
    required = {"ACTIVE", *(f"ARCHIVE:{fy}" for fy in years)}
    path = _private_regular(index_path)
    raw_root = Path(snapshot_root).expanduser().absolute() if snapshot_root is not None else path.parent
    _reject_private_path_links(raw_root)
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


def inspect_private_index(
    index_path: str | Path,
    *,
    fiscal_year: int,
    now: datetime,
    verify_bytes: bool = False,
    snapshot_root: str | Path | None = None,
) -> dict:
    """Production-catalog-bound read-only coverage check; FY2027 still fails closed."""
    years = catalog_years_for_fiscal_year(fiscal_year)
    return _inspect_index_for_explicit_years(
        index_path, fiscal_year=fiscal_year, years=years, now=now,
        verify_bytes=verify_bytes, snapshot_root=snapshot_root,
    )


def inspect_unapproved_fy2027_candidate_index(
    index_path: str | Path,
    *,
    now: datetime,
    verify_bytes: bool = False,
    snapshot_root: str | Path | None = None,
) -> dict:
    """Compare an existing private index with the frozen, UNAPPROVED 36-file listing.

    Read-only diagnostic; NEVER certifies the FY2027 catalog even if all fake
    or genuine local file hashes happen to match. Source candidates not yet
    imported in the approved private index remain explicitly MISSING.
    """
    from scripts.reconcile_sam_catalog_candidate import reconcile_observation

    observation_path = REPOSITORY / "research" / "sam_archives_observation_20261019.json"
    if not observation_path.is_file() or observation_path.stat().st_size > 128 * 1024:
        raise ValueError("Frozen FY2027 source observation is unavailable or oversized")

    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate key in frozen source observation")
            result[key] = value
        return result

    observation = json.loads(
        observation_path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicate_keys,
    )
    candidate = reconcile_observation(observation)
    if (candidate["approved_to_update_catalog"] is not False
            or candidate["approved_for_full_catalog_claims"] is not False
            or candidate["production_current_through_fy"] != 2026):
        raise ValueError("FY2027 candidate must be unapproved and production still pinned")
    years = candidate["proposed_required_through_fy2027"]
    # Require all 34 years plus active; exclude merely future-listed FY2029/30.
    if len(years) != 34 or 2027 not in years or 2028 in years:
        raise ValueError("FY2027 candidate year inventory is incomplete or unexpected")
    audit = _inspect_index_for_explicit_years(
        index_path, fiscal_year=2027, years=years, now=now,
        verify_bytes=verify_bytes, snapshot_root=snapshot_root,
    )
    # Keep candidate completeness in separate names: no caller can mistake
    # this result for approved production FULL_CATALOG coverage.
    metadata_complete = audit.pop("metadata_complete")
    local_file_hashes_match = audit.pop("local_file_hashes_match")
    audit.update({
        "schema": "capturebrief-fy2027-unapproved-candidate-coverage-v1",
        "status": "FY2027_CATALOG_REVIEW_REQUIRED",
        "candidate_observation_sha256": candidate["observation_sha256"],
        "candidate_catalog_approved": False,
        "candidate_metadata_complete": metadata_complete,
        "candidate_local_file_hashes_match": local_file_hashes_match,
        "production_catalog_current_through_fy": 2026,
        "approved_full_catalog_coverage": False,
        "customer_release_authorized": False,
        "source_files_downloaded_by_this_tool": False,
    })
    return audit
