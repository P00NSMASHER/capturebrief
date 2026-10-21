"""Private, idempotent CaptureBrief payment-to-case registration.

This local SQLite register stores minimal provider/case references, not customer
contact information, card details or credentials. It does not accept webhooks,
customer-supplied paid flags, mailto URLs or unauthenticated Stripe JSON as proof.
Registration never authorizes work, source interpretation, delivery or messaging.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model import canonical_json, sha256_hex

REPO = Path(__file__).resolve().parents[1]
_ID = re.compile(r"^[A-Za-z0-9_]{6,100}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    session_ref TEXT PRIMARY KEY,
    intent_ref TEXT NOT NULL UNIQUE,
    case_sha256 TEXT NOT NULL UNIQUE,
    request_sha256 TEXT NOT NULL UNIQUE,
    case_tag TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    observation_sha256 TEXT NOT NULL,
    payment_state TEXT NOT NULL,
    intake_state TEXT NOT NULL,
    source_state TEXT NOT NULL,
    research_state TEXT NOT NULL,
    delivery_state TEXT NOT NULL,
    watch_state TEXT NOT NULL,
    work_authorized INTEGER NOT NULL CHECK(work_authorized = 0),
    external_send_authorized INTEGER NOT NULL CHECK(external_send_authorized = 0),
    customer_release_authorized INTEGER NOT NULL CHECK(customer_release_authorized = 0)
)
"""

class OrderConflict(ValueError):
    """A provider payment or private intake was already bound elsewhere."""


def _private_db(file: str | Path) -> Path:
    raw = Path(file).expanduser().absolute()
    for path in (raw, *raw.parents):
        junction = getattr(path, "is_junction", None)
        if path.is_symlink() or (junction is not None and junction()):
            raise ValueError("Private order registry path must not follow links")
    path = raw.resolve(strict=False)
    if (path.is_relative_to(REPO)
            or any(p.name.casefold() in {".git", "gh-pages"} for p in (path, *path.parents))
            or not path.parent.is_dir()
            or (path.exists() and not path.is_file())
            or path.suffix != ".sqlite"):
        raise ValueError("Order registry must be a private SQLite file outside the repo")
    return path


def _at(value: datetime | None) -> str:
    now = value if value is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("Order observation timestamp requires timezone")
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _tag(value: str) -> str:
    return hashlib.sha256(("capturebrief-private-order:" + value).encode()).hexdigest()[:16]


def _read_only_connection(file: Path) -> sqlite3.Connection | None:
    if not file.exists():
        return None
    conn = sqlite3.connect(file.as_uri() + "?mode=ro", uri=True, timeout=3)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def _record_is_safe(row: sqlite3.Row) -> bool:
    return (
        row["work_authorized"] == 0
        and row["external_send_authorized"] == 0
        and row["customer_release_authorized"] == 0
        and row["payment_state"] in {
            "LIVE_STRIPE_OBSERVED_REVIEW_REQUIRED",
            "SYNTHETIC_CONSISTENT_NOT_LIVE_PROOF",
        }
        and row["intake_state"] == "CUSTOMER_IDENTITY_NOT_AUTHENTICATED"
        and row["source_state"] == "SOURCE_CATALOG_NOT_ATTESTED"
        and row["research_state"] == "NOT_STARTED"
        and row["delivery_state"] == "NOT_VERIFIED"
        and row["watch_state"] == "NOT_STARTED"
    )


def register_order(
    database_path: str | Path,
    *,
    case: dict[str, Any],
    source_request_sha256: str,
    session_id: str,
    payment_intent_id: str,
    payment_report: dict[str, Any],
    synthetic_provider: bool,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Attach exactly ONE provider Session+Intent to ONE original private case.

    A verified local intake pair must be checked by the caller before invoking
    this API. A synthetic provider can exercise everything except the live
    payment claim. Database UNIQUE constraints make retries idempotent.
    """
    if (not isinstance(case, dict) or not isinstance(payment_report, dict)
            or type(synthetic_provider) is not bool):
        raise ValueError("Expected a local case, Stripe check and explicit provider mode")
    if (not isinstance(session_id, str) or not session_id.startswith("cs_live_")
            or not _ID.fullmatch(session_id)
            or not isinstance(payment_intent_id, str)
            or not payment_intent_id.startswith("pi_")
            or not _ID.fullmatch(payment_intent_id)
            or not isinstance(source_request_sha256, str)
            or not _SHA.fullmatch(source_request_sha256)):
        raise ValueError("Invalid pinned payment or request identity")
    case_sha256 = sha256_hex(canonical_json(case))
    if (
        payment_report.get("status") != "PROCESSOR_RECORDS_CONSISTENT_REVIEW_REQUIRED"
        or payment_report.get("payment_verified_by_matching_records") is not True
        or payment_report.get("source") != "STRIPE_DIRECT_LIVE_READ_ONLY_API"
        or payment_report.get("case_sha256") != case_sha256
        or payment_report.get("case_id") != case.get("case_id")
        or payment_report.get("payment_reference") != session_id
        or payment_report.get("work_authorized") is not False
        or payment_report.get("external_send_authorized") is not False
        or payment_report.get("scope_approved") is not False
        or payment_report.get("sender_verified") is not False
        or payment_report.get("case_release_authorized") is not False
        or not _SHA.fullmatch(str(payment_report.get("reconciliation_sha256") or ""))
    ):
        raise ValueError("Payment data is not an acceptable direct-read review receipt")
    if (case.get("sources") != [] or case.get("current_action_receipts") != []
            or case.get("decision_trace_required") is not True
            or not isinstance(case.get("intake"), dict)
            or case["intake"].get("record_time_basis") != "LOCAL_IMPORT_TIME_NOT_MAIL_PROVIDER_RECEIPT"
            or not isinstance(case.get("assumptions"), list)
            or not case["assumptions"]
            or any(not isinstance(item, dict) or item.get("evidence_state") != "UNPROVEN"
                   for item in case["assumptions"])):
        raise ValueError("Only an original unverified private intake case can register")
    state = ("SYNTHETIC_CONSISTENT_NOT_LIVE_PROOF" if synthetic_provider
             else "LIVE_STRIPE_OBSERVED_REVIEW_REQUIRED")
    created_at = _at(observed_at)
    db_file = _private_db(database_path)
    # sqlite automatically serializes committed writes and enforces UNIQUE
    # across sessions, intents, source drafts and canonical case fingerprints.
    new_file = not db_file.exists()
    if new_file:
        fd = os.open(db_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    with closing(sqlite3.connect(db_file, timeout=5, isolation_level=None)) as conn:
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(_SCHEMA)
            existing = conn.execute(
                "SELECT * FROM orders WHERE session_ref = ?", (session_id,)
            ).fetchone()
            if existing:
                if (existing["intent_ref"] != payment_intent_id
                        or existing["case_sha256"] != case_sha256
                        or existing["request_sha256"] != source_request_sha256
                        or not _record_is_safe(existing)):
                    raise OrderConflict("Checkout Session is already bound or unsafe")
                # A synthetic check can never upgrade an existing LIVE record,
                # and a real recheck never silently promotes a synthetic row.
                if existing["payment_state"] != state:
                    raise OrderConflict("Cannot silently change payment provenance")
                status = "ALREADY_REGISTERED_UNVERIFIED"
            else:
                conn.execute(
                    """INSERT INTO orders (
                        session_ref, intent_ref, case_sha256, request_sha256,
                        case_tag, created_at, last_observed_at, observation_sha256,
                        payment_state, intake_state, source_state, research_state,
                        delivery_state, watch_state, work_authorized,
                        external_send_authorized, customer_release_authorized)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,0)""",
                    (session_id, payment_intent_id, case_sha256,
                     source_request_sha256, _tag(case_sha256), created_at,
                     created_at, payment_report["reconciliation_sha256"], state,
                     "CUSTOMER_IDENTITY_NOT_AUTHENTICATED",
                     "SOURCE_CATALOG_NOT_ATTESTED", "NOT_STARTED",
                     "NOT_VERIFIED", "NOT_STARTED"),
                )
                status = "PRIVATE_ORDER_REGISTERED_REVIEW_REQUIRED"
            conn.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            conn.execute("ROLLBACK")
            raise OrderConflict("Duplicate payment intent or intake case") from None
        except BaseException:
            conn.execute("ROLLBACK")
            raise
    return {
        "schema": "capturebrief-private-order-registration-v1",
        "status": status,
        "order_tag": _tag(session_id),
        "payment_state": state,
        "case_tag": _tag(case_sha256),
        "payment_session_reference_stored_privately": True,
        "source_review_required": True,
        "intake_review_required": True,
        "work_authorized": False,
        "delivery_verified": False,
        "watch_started": False,
        "external_send_authorized": False,
        "customer_release_authorized": False,
    }


def order_summary(database_path: str | Path) -> dict[str, Any]:
    """Read private registry without creating files or revealing provider IDs."""
    file = _private_db(database_path)
    conn = _read_only_connection(file)
    rows: list[dict[str, Any]] = []
    invalid = 0
    if conn:
        with closing(conn):
            try:
                data = conn.execute("SELECT * FROM orders ORDER BY created_at,session_ref").fetchall()
            except sqlite3.DatabaseError:
                return {"status": "PRIVATE_ORDER_REGISTRY_INVALID", "orders": [],
                        "all_customer_release_authorized": False}
            for row in data:
                if not _record_is_safe(row):
                    invalid += 1
                    continue
                rows.append({
                    "order_tag": _tag(row["session_ref"]),
                    "case_tag": row["case_tag"],
                    "payment_state": row["payment_state"],
                    "intake_state": row["intake_state"],
                    "source_state": row["source_state"],
                    "research_state": row["research_state"],
                    "delivery_state": row["delivery_state"],
                    "watch_state": row["watch_state"],
                    "last_payment_observed_at": row["last_observed_at"],
                    "customer_release_authorized": False,
                })
    return {
        "status": "PRIVATE_ORDER_REGISTRY_BLOCKED" if invalid
                  else "PRIVATE_ORDER_REVIEW_PENDING" if rows
                  else "PRIVATE_ORDER_REGISTRY_EMPTY",
        "orders": rows,
        "review_only": True,
        "rejected_registry_rows": invalid,
        "all_customer_release_authorized": False,
        "any_external_send_authorized": False,
        "actual_delivery_verified": False,
    }
