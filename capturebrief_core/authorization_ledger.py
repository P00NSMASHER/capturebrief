"""Append-only, cross-case one-message authorization nonce reservation.

This ledger does NOT send, draft, email, or claim provider delivery. The
only valid caller first verifies the six signed release gates against the
full private source/report bytes, then reserves its single-use nonce in one
shared private authorization ledger across all accepted cases. Do not make
a different ledger per customer or reset the ledger after recovery.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .accepted_case_release import AcceptedCaseBlocked, _root, canonical, sha256

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


def reserve_once(
    manifest: dict[str, Any], *,
    verification: dict[str, Any], ledger_path: str | Path,
    at: datetime | None = None,
) -> dict[str, Any]:
    """Reserve a unique per-message approval; no transport side effect."""
    if verification.get("status") != "EVIDENCE_AND_PER_MESSAGE_APPROVAL_VERIFIED_MANUAL_SEND_ONLY":
        raise AcceptedCaseBlocked("Full signed release verification must run before reserving")
    at = at or datetime.now(timezone.utc)
    if at.utcoffset() is None:
        raise AcceptedCaseBlocked("Authorization reservation timestamp lacks timezone")
    delivery = manifest.get("delivery")
    if not isinstance(delivery, dict):
        raise AcceptedCaseBlocked("No reviewed delivery envelope")
    # Recheck the one-message window, as it can expire while a UI is waiting.
    from .accepted_case_release import timestamp
    if timestamp(delivery.get("expires_at")) <= at.astimezone(timezone.utc):
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
