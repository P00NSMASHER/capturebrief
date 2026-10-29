"""Append-only, cross-case one-message authorization nonce reservation.

This ledger does NOT send, draft, email, or claim provider delivery. The
only valid caller first verifies the six signed release gates against the
full private source/report bytes, then reserves its single-use nonce in one
shared private authorization ledger across all accepted cases. Do not make
a different ledger per customer or reset the ledger after recovery.
"""
from __future__ import annotations

import re
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .accepted_case_release import (
    AcceptedCaseBlocked, _root, canonical, sha256,
    inspect_accepted_case, timestamp,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS single_message_authorizations (
  nonce_sha256 TEXT PRIMARY KEY,
  case_sha256 TEXT NOT NULL,
  manifest_sha256 TEXT NOT NULL UNIQUE,
  recipient_sha256 TEXT NOT NULL,
  reserved_at TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state = 'MANUAL_SEND_PENDING_NO_PROVIDER_EVIDENCE')
)
"""


def _validate_ledger(db: sqlite3.Connection, checked_at: datetime) -> None:
    """Reject unexpected objects, noncanonical schema or corrupted reservations."""
    if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
        raise AcceptedCaseBlocked("Authorization ledger SQLite integrity failed")
    objects = db.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall()
    tables = [row for row in objects if row[0] == "table"]
    expected_sql = re.sub(r"\s+", " ", _SCHEMA.strip().replace(
        "CREATE TABLE IF NOT EXISTS", "CREATE TABLE", 1)).strip().casefold()
    if (len(tables) != 1 or tables[0][1] != "single_message_authorizations"
            or re.sub(r"\s+", " ", tables[0][2]).strip().casefold() != expected_sql):
        raise AcceptedCaseBlocked("Authorization ledger schema differs from approved one-time contract")
    if any(not (kind == "table" and name == "single_message_authorizations"
                    or kind == "index" and
                       name.startswith("sqlite_autoindex_single_message_authorizations_")
                       and sql is None)
           for kind, name, sql in objects):
        raise AcceptedCaseBlocked("Authorization ledger contains unexpected triggers or tables")
    columns = tuple(row[1] for row in db.execute(
        "PRAGMA table_info(single_message_authorizations)"))
    if columns != (
        "nonce_sha256", "case_sha256", "manifest_sha256",
        "recipient_sha256", "reserved_at", "state",
    ):
        raise AcceptedCaseBlocked("Authorization ledger columns are not approved")
    for nonce, case, manifest, recipient, reserved, state in db.execute(
        "SELECT nonce_sha256, case_sha256, manifest_sha256, "
        "recipient_sha256, reserved_at, state FROM single_message_authorizations"
    ):
        if (state != "MANUAL_SEND_PENDING_NO_PROVIDER_EVIDENCE"
                or any(not isinstance(d, str) or not re.fullmatch(r"[0-9a-f]{64}", d)
                       for d in (nonce, case, manifest, recipient))
                or not isinstance(reserved, str)
                or timestamp(reserved) > checked_at):
            raise AcceptedCaseBlocked("Existing authorization contains invalid or future reservation")


def reserve_once(
    manifest: dict[str, Any], *,
    case: dict[str, Any], private_root: str | Path,
    trusted_keys: dict[str, Any], ledger_path: str | Path,
    at: datetime | None = None,
) -> dict[str, Any]:
    """Reverify original signed source, report and human approval BEFORE reserving.

    Deliberately no 'verification' status parameter: a string or copied success
    JSON must never stand in for independently inspecting immutable originals.
    """
    at = at if at is not None else datetime.now(timezone.utc)
    if not isinstance(at, datetime) or at.utcoffset() is None:
        raise AcceptedCaseBlocked("Authorization reservation timestamp lacks timezone")
    at = at.astimezone(timezone.utc)
    verified = inspect_accepted_case(
        case, manifest, private_root=private_root, trusted_keys=trusted_keys,
        now=at,
    )
    if verified.get("status") != "EVIDENCE_AND_PER_MESSAGE_APPROVAL_VERIFIED_MANUAL_SEND_ONLY":
        raise AcceptedCaseBlocked("Full signed release verification is required for nonce reservation")
    delivery = manifest["delivery"]
    if timestamp(delivery.get("expires_at")) <= at:
        raise AcceptedCaseBlocked("Signed single-message release expired before reservation")
    path = Path(ledger_path).expanduser().absolute()
    if (path.suffix != ".sqlite" or path.is_symlink()
            or not path.parent.is_dir() or path.name.startswith(".")):
        raise AcceptedCaseBlocked("Approved shared authorization ledger must be a .sqlite file")
    _root(path.parent)
    if path.exists() and (not path.is_file() or (os.name != "nt" and path.stat().st_mode & 0o077)):
        raise AcceptedCaseBlocked("Existing authorization ledger is not private")
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        pass
    else:
        os.close(fd)
    nonce_hash = sha256(delivery["authorization_nonce"].encode("ascii"))
    recipient_hash = sha256(delivery["recipient"].casefold().encode("utf-8"))
    manifest_hash = sha256(canonical(manifest))
    try:
        with closing(sqlite3.connect(path, timeout=10, isolation_level=None)) as db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(_SCHEMA)
                _validate_ledger(db, at)
                db.execute(
                    "INSERT INTO single_message_authorizations "
                    "(nonce_sha256, case_sha256, manifest_sha256, recipient_sha256, reserved_at, state) "
                    "VALUES (?, ?, ?, ?, ?, 'MANUAL_SEND_PENDING_NO_PROVIDER_EVIDENCE')",
                    (nonce_hash, manifest["case_sha256"], manifest_hash,
                     recipient_hash, at.astimezone(timezone.utc).isoformat()),
                )
                db.execute("COMMIT")
            except sqlite3.IntegrityError:
                db.execute("ROLLBACK")
                raise AcceptedCaseBlocked("The signed one-message authorization has already been reserved") from None
            except Exception:
                db.execute("ROLLBACK")
                raise
    except sqlite3.DatabaseError:
        raise AcceptedCaseBlocked("Private authorization ledger cannot guarantee unique reservation") from None
    return {
        "status": "SINGLE_MESSAGE_AUTHORIZATION_RESERVED_MANUAL_SEND_PENDING",
        "nonce_tag": nonce_hash[:12], "manifest_tag": manifest_hash[:12],
        "external_send_performed": False, "provider_delivery_verified": False,
    }
