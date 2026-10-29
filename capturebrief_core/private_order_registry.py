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

_HOLD_SCHEMA = """
CREATE TABLE IF NOT EXISTS payment_holds (
    session_ref TEXT PRIMARY KEY,
    case_sha256 TEXT NOT NULL,
    request_sha256 TEXT NOT NULL,
    first_blocked_at TEXT NOT NULL,
    blocked_reconciliation_sha256 TEXT NOT NULL,
    synthetic_provider INTEGER NOT NULL CHECK(synthetic_provider IN (0,1)),
    FOREIGN KEY(session_ref) REFERENCES orders(session_ref)
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
        try:
            fd = os.open(db_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            # A simultaneous operator registered first. Re-check that the
            # destination remains private and regular; the transaction and
            # UNIQUE constraints below will decide which payment wins.
            _private_db(db_file)
            if not db_file.is_file():
                raise ValueError("Private order registry race produced an invalid file") from None
        else:
            os.close(fd)
    with closing(sqlite3.connect(db_file, timeout=5, isolation_level=None)) as conn:
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(_SCHEMA)
            conn.execute(_HOLD_SCHEMA)
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
                if conn.execute(
                    "SELECT 1 FROM payment_holds WHERE session_ref = ?",
                    (session_id,),
                ).fetchone() is not None:
                    raise OrderConflict("Prior payment recheck is blocked for review")
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


def mark_payment_recheck_blocked(
    database_path: str | Path, *, case: dict[str, Any],
    source_request_sha256: str, session_id: str,
    payment_report: dict[str, Any], synthetic_provider: bool,
    observed_at: datetime | None = None,
) -> bool:
    """Persist a one-way block for a formerly registered order.

    Only a complete separately retrieved provider reconciliation for the
    previously bound Session and original case may create the hold. The
    successful original observation stays immutable in the orders table.
    This cannot create a new order, authorize work, or clear a hold.
    """
    if (type(synthetic_provider) is not bool
            or not isinstance(case, dict)
            or not isinstance(payment_report, dict)
            or not isinstance(session_id, str)
            or not _ID.fullmatch(session_id)
            or not isinstance(source_request_sha256, str)
            or not _SHA.fullmatch(source_request_sha256)):
        raise ValueError("Invalid payment recheck context")
    original_sha = sha256_hex(canonical_json(case))
    if (payment_report.get("status") != "PAYMENT_RECONCILIATION_BLOCKED"
            or payment_report.get("payment_verified_by_matching_records") is not False
            or payment_report.get("source") != "STRIPE_DIRECT_LIVE_READ_ONLY_API"
            or payment_report.get("payment_reference") != session_id
            or payment_report.get("case_sha256") != original_sha
            or payment_report.get("case_id") != case.get("case_id")
            or payment_report.get("work_authorized") is not False
            or payment_report.get("external_send_authorized") is not False
            or not _SHA.fullmatch(str(payment_report.get("reconciliation_sha256") or ""))):
        raise ValueError("Payment recheck has no traceable account/case binding")
    path = _private_db(database_path)
    if not path.exists():
        return False
    with closing(sqlite3.connect(path, timeout=5, isolation_level=None)) as conn:
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM orders WHERE session_ref = ?", (session_id,),
            ).fetchone()
            expected = ("SYNTHETIC_CONSISTENT_NOT_LIVE_PROOF" if synthetic_provider
                        else "LIVE_STRIPE_OBSERVED_REVIEW_REQUIRED")
            if (row is None or not _record_is_safe(row)
                    or row["case_sha256"] != original_sha
                    or row["request_sha256"] != source_request_sha256
                    or row["payment_state"] != expected):
                conn.execute("ROLLBACK")
                return False
            conn.execute(_HOLD_SCHEMA)
            conn.execute(
                """INSERT OR IGNORE INTO payment_holds (
                   session_ref,case_sha256,request_sha256,first_blocked_at,
                   blocked_reconciliation_sha256,synthetic_provider)
                   VALUES(?,?,?,?,?,?)""",
                (session_id, original_sha, source_request_sha256,
                 _at(observed_at), payment_report["reconciliation_sha256"],
                 int(synthetic_provider)),
            )
            conn.execute("COMMIT")
            return True
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise


def _validated_hold_sessions(
    connection: sqlite3.Connection, orders: list[sqlite3.Row],
) -> set[str]:
    """Reject detached or contradictory payment holds using the SAME read snapshot.

    SQLite foreign keys are optional at connection level; a damaged/restored
    registry can contain orphan hold rows. Never quietly omit those rows from
    a read-only operator view or trust a hold bound to a different original
    case, request, or provider provenance. Does not authenticate Stripe.
    """
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='payment_holds'"
    ).fetchone()
    if exists is None:
        return set()  # Legacy registry without a hold table.
    originals = {row["session_ref"]: row for row in orders}
    # There can be at most one hold per original order. A bounded N+1
    # read detects unexpected extras without loading an unbounded table.
    holds = connection.execute(
        """SELECT session_ref, case_sha256, request_sha256,
                  first_blocked_at, blocked_reconciliation_sha256,
                  synthetic_provider FROM payment_holds LIMIT ?""",
        (len(orders) + 1,),
    ).fetchall()
    if len(holds) > len(orders):
        raise ValueError("Private payment hold has no original order")
    held: set[str] = set()
    for hold in holds:
        reference = originals.get(hold["session_ref"])
        if reference is None:
            raise ValueError("Private payment hold has no original order")
        expected_synthetic = (
            1 if reference["payment_state"] == "SYNTHETIC_CONSISTENT_NOT_LIVE_PROOF"
            else 0
        )
        if (
            hold["case_sha256"] != reference["case_sha256"]
            or hold["request_sha256"] != reference["request_sha256"]
            or type(hold["synthetic_provider"]) is not int
            or hold["synthetic_provider"] != expected_synthetic
            or not isinstance(hold["blocked_reconciliation_sha256"], str)
            or _SHA.fullmatch(hold["blocked_reconciliation_sha256"]) is None
        ):
            raise ValueError("Private payment hold contradicts original order")
        raw_date = hold["first_blocked_at"]
        if not isinstance(raw_date, str):
            raise ValueError("Private payment hold has invalid original timestamp")
        try:
            recorded = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Private payment hold has invalid original timestamp") from exc
        if recorded.utcoffset() is None:
            raise ValueError("Private payment hold timestamp has no timezone")
        held.add(hold["session_ref"])
    return held


def order_summary(database_path: str | Path) -> dict[str, Any]:
    """Read private registry without creating files or revealing provider IDs."""
    file = _private_db(database_path)
    conn = _read_only_connection(file)
    rows: list[dict[str, Any]] = []
    invalid = 0
    held = 0
    if conn:
        with closing(conn):
            try:
                conn.execute("BEGIN")
                # A read transaction pins orders and holds to one SQLite
                # snapshot, even if another worker appends a hold meanwhile.
                # BEGIN must precede the first SELECT.
                data = conn.execute("SELECT * FROM orders ORDER BY created_at,session_ref").fetchall()
                blocked_ids = _validated_hold_sessions(conn, data)
                conn.execute("ROLLBACK")
            except (ValueError, TypeError, KeyError):
                return {"status": "PRIVATE_ORDER_REGISTRY_BLOCKED", "orders": [],
                        "rejected_registry_rows": 1, "payment_rechecks_blocked": 0,
                        "review_only": True, "all_customer_release_authorized": False,
                        "any_external_send_authorized": False,
                        "actual_delivery_verified": False}
            except sqlite3.DatabaseError:
                return {"status": "PRIVATE_ORDER_REGISTRY_INVALID", "orders": [],
                        "all_customer_release_authorized": False}
            for row in data:
                if not _record_is_safe(row):
                    invalid += 1
                    continue
                blocked_recheck = row["session_ref"] in blocked_ids
                held += int(blocked_recheck)
                rows.append({
                    "order_tag": _tag(row["session_ref"]),
                    "case_tag": row["case_tag"],
                    "payment_state": ("PAYMENT_RECHECK_BLOCKED_REVIEW_REQUIRED"
                                      if blocked_recheck else row["payment_state"]),
                    "payment_recheck_blocked": blocked_recheck,
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
                  else "PRIVATE_ORDER_PAYMENT_RECHECK_BLOCKED" if held
                  else "PRIVATE_ORDER_REVIEW_PENDING" if rows
                  else "PRIVATE_ORDER_REGISTRY_EMPTY",
        "orders": rows,
        "review_only": True,
        "rejected_registry_rows": invalid,
        "payment_rechecks_blocked": held,
        "all_customer_release_authorized": False,
        "any_external_send_authorized": False,
        "actual_delivery_verified": False,
    }
