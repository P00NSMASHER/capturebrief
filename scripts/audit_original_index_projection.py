"""Operator-only exact original -> SQLite indexed row projection integrity audit.

Reads an EXISTING private SQLite index in query-only mode and one retained
original CSV inside an explicitly authorized private source root. Verifies
full-byte SHA-256, exact official source identity, every recorded row digest
and every displayed/normalized indexed field. No writes, source downloads,
catalog changes, customer contacts, charges or release certification.

This is a deep on-demand audit, not the hot-path history receipt validator.
Passing local byte integrity is NOT independent publisher provenance.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import quote

from capturebrief_core.archive_catalog import ARCHIVE_CATALOG_CURRENT_THROUGH_FY
from capturebrief_core.data_services import ACTIVE_DOWNLOAD, ARCHIVE_DOWNLOAD, REQUIRED_COLUMNS
from capturebrief_core.history_index import INDEX_SCHEMA_VERSION, _encoding, _norm
from capturebrief_core.model import canonical_json, sha256_hex

REPO = Path(__file__).resolve().parents[1]
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CHUNK_BYTES = 1024 * 1024

class IndexSourceMismatch(ValueError):
    """A retained original and its indexed SQL projection disagree."""


def _private_file(path: str | Path) -> Path:
    value = Path(path).expanduser().absolute()
    if value.is_symlink() or value.is_relative_to(REPO):
        raise IndexSourceMismatch("Private index must be outside source repository")
    resolved = value.resolve(strict=True)
    if resolved.is_relative_to(REPO) or not resolved.is_file():
        raise IndexSourceMismatch("Expected private regular index file")
    return resolved


def _private_root(path: str | Path) -> Path:
    value = Path(path).expanduser().absolute()
    if value.is_symlink() or value.is_relative_to(REPO):
        raise IndexSourceMismatch("Original root must be private")
    resolved = value.resolve(strict=True)
    if resolved.is_relative_to(REPO) or not resolved.is_dir():
        raise IndexSourceMismatch("Original source root is unavailable")
    return resolved


def _exact_slot(slot: str) -> tuple[str, int | None, str]:
    if slot == "ACTIVE":
        return "ACTIVE", None, ACTIVE_DOWNLOAD
    if not isinstance(slot, str) or not re.fullmatch(r"ARCHIVE:(19[0-9]{2}|20[0-2][0-9])", slot):
        raise IndexSourceMismatch("Unrecognized archived fiscal-year slot")
    year = int(slot.partition(":")[2])
    if year > 2027:
        raise IndexSourceMismatch("Future source slot is outside FY2027 candidate review")
    return "ARCHIVE", year, ARCHIVE_DOWNLOAD.format(fy=year)


def _original_sha_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_BYTES), b""):
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


def _source_row_expected(row: dict, field_names: list[str], line: int) -> tuple:
    if "_extra" in row or any(row.get(col) is None for col in field_names):
        raise IndexSourceMismatch("Original CSV row has missing or extra columns")
    raw = {col: row.get(col) for col in field_names}
    notice_id = str(row.get("NoticeId") or "").strip()
    if not notice_id:
        raise IndexSourceMismatch("Original row lacks primary notice identity")
    return (
        line, notice_id,
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


def audit_row_projection(
    index_path: str | Path,
    *,
    slot: str,
    snapshot_root: str | Path,
) -> dict:
    kind, year, expected_url = _exact_slot(slot)
    if ARCHIVE_CATALOG_CURRENT_THROUGH_FY != 2026:
        raise IndexSourceMismatch("Production catalog unexpectedly changed")
    db = _private_file(index_path)
    root = _private_root(snapshot_root)
    uri = "file:" + quote(str(db), safe="/:") + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        schema = conn.execute(
            "SELECT value FROM metadata WHERE key='schema_version'"
        ).fetchone()
        if schema is None or schema["value"] != str(INDEX_SCHEMA_VERSION):
            raise IndexSourceMismatch("Unsupported history index schema")
        current = conn.execute(
            "SELECT s.*,c.slot AS current_slot,c.collection_mode "
            "FROM current_sources c JOIN source_snapshots s "
            "ON s.snapshot_id=c.snapshot_id WHERE c.slot=?",
            (slot,),
        ).fetchone()
        if current is None:
            raise IndexSourceMismatch("Required source slot is not indexed")
        metadata = dict(current)
        if (metadata["slot"] != slot or metadata["current_slot"] != slot
                or metadata["source_kind"] != kind
                or metadata["fiscal_year"] != year
                or metadata["source_url"] != expected_url
                or not isinstance(metadata["extract_sha256"], str)
                or SHA256.fullmatch(metadata["extract_sha256"]) is None
                or type(metadata["size_bytes"]) is not int
                or metadata["size_bytes"] < 1
                or type(metadata["rows_scanned"]) is not int
                or metadata["rows_scanned"] < 0):
            raise IndexSourceMismatch("Source snapshot identity or metadata invalid")

        raw_file = Path(str(metadata["local_path"]))
        if not raw_file.is_absolute() or raw_file.is_symlink() or not raw_file.is_file():
            raise IndexSourceMismatch("Retained source file absent or unsafe")
        source = raw_file.resolve(strict=True)
        if not source.is_relative_to(root):
            raise IndexSourceMismatch("Database attempted to read outside approved root")
        original_sha, nbytes = _original_sha_and_size(source)
        if (original_sha != metadata["extract_sha256"]
                or nbytes != metadata["size_bytes"]):
            raise IndexSourceMismatch("Original bytes differ from database SHA or size")

        recorded_rows = conn.execute(
            "SELECT row_number,notice_id,solicitation_norm,solicitation_raw,"
            "cgac,fpds_code,aac_code,department,subtier,office,posted_date,"
            "notice_type,base_type,active,link,row_sha256 "
            "FROM opportunity_rows WHERE snapshot_id=? ORDER BY row_number",
            (metadata["snapshot_id"],),
        )
        seen = 0
        with source.open("r", encoding=_encoding(source),
                         errors="strict", newline="") as handle:
            reader = csv.DictReader(handle, restkey="_extra", strict=True)
            columns = list(reader.fieldnames or [])
            if (not set(REQUIRED_COLUMNS).issubset(columns)
                    or len(columns) != len(set(columns))):
                raise IndexSourceMismatch("CSV source headers incomplete or duplicated")
            for line, source_row in enumerate(reader, start=1):
                expected = _source_row_expected(source_row, columns, line)
                indexed = recorded_rows.fetchone()
                if indexed is None or tuple(indexed) != expected:
                    raise IndexSourceMismatch("Indexed action differs from retained original")
                seen += 1
        if recorded_rows.fetchone() is not None or seen != metadata["rows_scanned"]:
            raise IndexSourceMismatch("Indexed original row count mismatch")
        conn.execute("ROLLBACK")
    return {
        "status": "EXACT_PRIVATE_SOURCE_ROW_PROJECTION_PASS_UNAPPROVED",
        "slot": slot,
        "source_original_sha256": original_sha,
        "source_original_bytes": nbytes,
        "rows_checked": seen,
        "exact_row_fields_verified": True,
        "source_original_sha256_verified": True,
        "private_sqlite_mutated": False,
        "source_original_bytes_retained_by_audit": False,
        "independent_publisher_review_approved": False,
        "FY2027_catalog_approved": False,
        "encrypted_offdevice_restore_verified": False,
        "customer_release_authorized": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-index", required=True)
    p.add_argument("--snapshot-root", required=True)
    p.add_argument("--slot", required=True)
    args = p.parse_args(argv)
    try:
        report = audit_row_projection(
            args.private_index, slot=args.slot, snapshot_root=args.snapshot_root,
        )
    except Exception as exc:
        # No untrusted SQLite path, URL, source text or notice ID is emitted.
        print(json.dumps({
            "status": "SOURCE_ROW_PROJECTION_AUDIT_BLOCKED",
            "error_type": type(exc).__name__,
            "customer_release_authorized": False,
            "FY2027_catalog_approved": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
