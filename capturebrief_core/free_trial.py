"""Private, bounded free-check reservation without payment or release authority.

The operator supplies a canonical business identity after an identity review;
customer email/domain assertions do not grant a trial. Only hashes are stored.
One dedicated registry must be retained across the pilot cohort. Reservations
are irreversible in this first version so aliases, retries, and withdrawals
cannot silently reset the one-per-business limit.
"""
from __future__ import annotations

import hashlib
import copy
import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .delivery_readiness import evaluate_delivery_readiness
from .atomic_io import ensure_exact_bytes, exclusive_path_lock
from .render import render_markdown
from .intake import build_case_from_intake
from .model import canonical_json, sha256_hex
from .private_order_registry import _private_db
from .request_draft import FREE_CLAIM, FREE_OFFER

MAX_COHORT_SIZE = 10
_SHA = re.compile(r"^[0-9a-f]{64}$")
_BUSINESS = re.compile(r"^(?:domain:[a-z0-9](?:[a-z0-9.-]{1,251})[a-z0-9]|registry:[a-z0-9][a-z0-9:._/-]{2,199})$")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS free_check_reservations (
    business_sha256 TEXT PRIMARY KEY,
    request_sha256 TEXT NOT NULL UNIQUE,
    original_case_sha256 TEXT NOT NULL UNIQUE,
    scope_sha256 TEXT NOT NULL UNIQUE,
    identity_review_sha256 TEXT NOT NULL,
    reserved_at TEXT NOT NULL,
    trial_state TEXT NOT NULL CHECK(trial_state = 'RESERVED_REVIEW_REQUIRED'),
    amount_due_cents INTEGER NOT NULL CHECK(amount_due_cents = 0),
    automatic_upgrade_authorized INTEGER NOT NULL CHECK(automatic_upgrade_authorized = 0),
    customer_release_authorized INTEGER NOT NULL CHECK(customer_release_authorized = 0),
    external_send_authorized INTEGER NOT NULL CHECK(external_send_authorized = 0)
)
"""


class TrialConflict(ValueError):
    """A business/request was already reserved or the first cohort is full."""


def _utc(value: datetime | None) -> str:
    value = value or datetime.now(timezone.utc)
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Trial observation time requires a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _business_digest(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Operator-reviewed canonical business key is required")
    key = value.strip().casefold().rstrip(".")
    if not _BUSINESS.fullmatch(key) or ".." in key:
        raise ValueError("Use a canonical domain: or registry: business identity")
    if key.startswith("domain:"):
        domain = key.removeprefix("domain:")
        if "." not in domain or any(not p or p.startswith("-") or p.endswith("-") for p in domain.split(".")):
            raise ValueError("Business domain must be a canonical public domain")
    return sha256_hex("capturebrief-free-check-business:" + key)


def _trial_identity(case: dict[str, Any], receipt: dict[str, Any]) -> tuple[str, str]:
    """Verify the intact imported free-request pair, never only a free flag."""
    intake = case.get("intake") if isinstance(case, dict) else None
    if not isinstance(intake, dict) or not isinstance(receipt, dict):
        raise ValueError("Original free-check intake and receipt are required")
    if (intake.get("requested_offer") != FREE_OFFER
            or receipt.get("requested_offer") != FREE_OFFER
            or receipt.get("purchase_claim") != FREE_CLAIM
            or receipt.get("schema") != "capturebrief-private-intake-receipt-v1"
            or receipt.get("source_kind") != "BUYER_SUPPLIED_EMAIL_DRAFT"
            or receipt.get("independent_payment_lookup") != "NOT_PERFORMED"
            or intake.get("record_time_basis") != "LOCAL_IMPORT_TIME_NOT_MAIL_PROVIDER_RECEIPT"
            or receipt.get("imported_at") != intake.get("submitted_at")
            or receipt.get("case_id") != case.get("case_id")
            or receipt.get("operator_review_required") is not True
            or any(receipt.get(field) is not False for field in (
                "purchase_claim_verified", "sender_authenticated", "message_delivery_verified",
                "source_evidence_verified", "external_send_authorized", "ready_to_start_work",
                "case_release_authorized", "case_submitted_at_is_email_delivery_proof",
                "trial_eligibility_verified", "trial_admission_authorized",
                "automatic_upgrade_authorized",
            ))):
        raise ValueError("Free-check request evidence is inconsistent or claims authority")
    assumptions = case.get("assumptions")
    if not isinstance(assumptions, list) or len(assumptions) != 1:
        raise ValueError("One free check must contain exactly one assumption")
    source_sha = receipt.get("request_sha256")
    if not isinstance(source_sha, str) or not _SHA.fullmatch(source_sha):
        raise ValueError("Original request fingerprint is required")
    rebuilt = build_case_from_intake({
        **intake,
        "current_posture": case.get("current_posture"),
        "question": intake.get("note"),
        "assumption_1": assumptions[0].get("text") if isinstance(assumptions[0], dict) else None,
    }, submitted_at=intake.get("submitted_at"))
    rebuilt["intake"]["requested_offer"] = FREE_OFFER
    rebuilt["intake"]["record_time_basis"] = "LOCAL_IMPORT_TIME_NOT_MAIL_PROVIDER_RECEIPT"
    if case != rebuilt:
        raise ValueError("Trial reservation requires the original unreviewed intake")
    case_sha = sha256_hex(canonical_json(case))
    if receipt.get("case_sha256") != case_sha:
        raise ValueError("Trial intake fingerprint mismatch")
    return source_sha, case_sha


def _scope_digest(case: dict[str, Any]) -> str:
    assumptions = case.get("assumptions")
    if (not isinstance(case.get("intake"), dict)
            or case["intake"].get("requested_offer") != FREE_OFFER
            or not isinstance(assumptions, list) or len(assumptions) != 1
            or not isinstance(assumptions[0], dict)):
        raise ValueError("Expected one original free-check scope")
    return sha256_hex(canonical_json({
        "case_id": case.get("case_id"), "intake": case["intake"],
        "assumption_id": assumptions[0].get("assumption_id"),
        "assumption_text": assumptions[0].get("text"),
    }))


def _reservation_timestamp_valid(
    reserved_at: Any, case: dict[str, Any], checked_at: datetime | None
) -> bool:
    """Reject unusable reservation chronology from a stale or mutated registry.

    This does not authenticate the identity-review evidence or grant delivery.
    """
    intake = case.get("intake")
    imported_at = intake.get("submitted_at") if isinstance(intake, dict) else None
    if not isinstance(reserved_at, str) or not isinstance(imported_at, str):
        return False
    try:
        reserved = datetime.fromisoformat(reserved_at.replace("Z", "+00:00"))
        imported = datetime.fromisoformat(imported_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    observed = checked_at if checked_at is not None else datetime.now(timezone.utc)
    if (not isinstance(observed, datetime) or observed.utcoffset() is None
            or reserved.utcoffset() is None or imported.utcoffset() is None):
        return False
    return imported <= reserved <= observed.astimezone(timezone.utc)


def reserve_free_check(
    database_path: str | Path, *, case: dict[str, Any], receipt: dict[str, Any],
    reviewed_business_key: str, identity_review_sha256: str,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Reserve one supervised slot after a separately retained identity review.

    The review hash pins operator evidence; this local registry cannot certify
    that evidence's authenticity. It never replaces source or delivery gates.
    """
    request_sha, case_sha = _trial_identity(case, receipt)
    business_sha = _business_digest(reviewed_business_key)
    scope_sha = _scope_digest(case)
    if not isinstance(identity_review_sha256, str) or not _SHA.fullmatch(identity_review_sha256):
        raise ValueError("Retained operator identity review SHA-256 is required")
    at = _utc(observed_at)
    imported = datetime.fromisoformat(case["intake"]["submitted_at"].replace("Z", "+00:00"))
    if imported.utcoffset() is None or imported > datetime.fromisoformat(at.replace("Z", "+00:00")):
        raise ValueError("Trial reservation cannot predate request import")
    path = _private_db(database_path)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        _private_db(path)
    else:
        os.close(fd)
    with closing(sqlite3.connect(path, timeout=5, isolation_level=None)) as db:
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute(_SCHEMA)
            existing = db.execute(
                "SELECT * FROM free_check_reservations WHERE business_sha256 = ?",
                (business_sha,),
            ).fetchone()
            if existing:
                if (existing["request_sha256"] != request_sha
                        or existing["original_case_sha256"] != case_sha
                        or existing["scope_sha256"] != scope_sha
                        or existing["identity_review_sha256"] != identity_review_sha256
                        or existing["trial_state"] != "RESERVED_REVIEW_REQUIRED"
                        or any(existing[k] != 0 for k in (
                            "amount_due_cents", "automatic_upgrade_authorized",
                            "customer_release_authorized", "external_send_authorized",
                        ))):
                    raise TrialConflict("Business has an existing free-check reservation")
                status = "ALREADY_RESERVED_REVIEW_REQUIRED"
            else:
                count = db.execute("SELECT COUNT(*) FROM free_check_reservations").fetchone()[0]
                if count >= MAX_COHORT_SIZE:
                    raise TrialConflict("The ten-business supervised cohort is full")
                db.execute(
                    "INSERT INTO free_check_reservations VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0)",
                    (business_sha, request_sha, case_sha, scope_sha, identity_review_sha256,
                     at, "RESERVED_REVIEW_REQUIRED"),
                )
                status = "FREE_CHECK_RESERVED_REVIEW_REQUIRED"
            count = db.execute("SELECT COUNT(*) FROM free_check_reservations").fetchone()[0]
            db.execute("COMMIT")
        except sqlite3.IntegrityError:
            db.execute("ROLLBACK")
            raise TrialConflict("Request or case is already bound to a business") from None
        except Exception:
            db.execute("ROLLBACK")
            raise
    if os.name != "nt":
        path.chmod(0o600)
    return {
        "status": status,
        "trial_tag": hashlib.sha256(("free-check:" + request_sha).encode()).hexdigest()[:16],
        "cohort_reserved": count,
        "cohort_limit": MAX_COHORT_SIZE,
        "amount_due_cents": 0,
        "payment_verified": False,
        "watch_included": False,
        "automatic_upgrade_authorized": False,
        "source_readiness_verified": False,
        "customer_release_authorized": False,
        "external_send_authorized": False,
    }


def inspect_free_check(
    case: dict[str, Any], *, database_path: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Require reserved scope and the existing evidence gates without a bypass.

    Enrichment may add reviewed evidence, but cannot change the original intake,
    case identity or selected assumption to spend a reservation on another job.
    """
    scope_sha = _scope_digest(case)
    reserved = False
    if database_path is not None:
        path = _private_db(database_path)
        if path.is_file():
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA query_only = ON")
                row = db.execute(
                    "SELECT * FROM free_check_reservations WHERE scope_sha256 = ?", (scope_sha,),
                ).fetchone()
                reserved = bool(row and row["trial_state"] == "RESERVED_REVIEW_REQUIRED"
                    and _reservation_timestamp_valid(row["reserved_at"], case, now)
                    and all(row[key] == 0 for key in (
                        "amount_due_cents", "automatic_upgrade_authorized",
                        "customer_release_authorized", "external_send_authorized",
                    )))
    readiness = evaluate_delivery_readiness(case, now=now)
    blockers = list(readiness.blocker_codes)
    if not reserved:
        blockers.insert(0, "FREE_CHECK_RESERVATION_REQUIRED")
    return {
        "offer": FREE_OFFER,
        "state": ("BLOCKED_NO_RESERVATION" if not reserved else
                  "EVIDENCE_ELIGIBLE_REVIEW_REQUIRED" if readiness.eligible else "BLOCKED_BY_CORE_EVIDENCE"),
        "reservation_scope_matches": reserved,
        "blocker_codes": blockers,
        "amount_due_cents": 0,
        "watch_included": False,
        "automatic_upgrade_authorized": False,
        "customer_release_authorized": False,
        "external_send_authorized": False,
    }


def build_free_check_report(
    case: dict[str, Any], output: str | Path, *, database_path: str | Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build one private, complete Markdown result with a separate byte receipt.

    A single-result report deliberately has no watch baseline or enrollment.
    Existing render/source gates and per-message release approval remain intact.
    """
    # Use the same strict private-path checks as the intake pipeline. A public
    # source checkout is never an acceptable destination for a customer result.
    from scripts.import_request_draft import _private_file
    from contextlib import ExitStack
    case = copy.deepcopy(case)
    checked_at = datetime.fromisoformat(_utc(now).replace("Z", "+00:00"))
    check = inspect_free_check(case, database_path=database_path, now=checked_at)
    if check["state"] != "EVIDENCE_ELIGIBLE_REVIEW_REQUIRED":
        raise ValueError("Free result is blocked by reservation or source evidence")
    raw = Path(output).expanduser().absolute()
    if any(p.is_symlink() for p in (raw, *raw.parents)):
        raise ValueError("Free result path must not follow links")
    path = _private_file(str(raw))
    if path.suffix != ".md" or not path.parent.is_dir():
        raise ValueError("Free result must be a Markdown file in existing private storage")
    receipt_path = path.with_name(path.name + ".receipt.json")
    if receipt_path.is_symlink():
        raise ValueError("Free result receipt must not follow links")
    # render_markdown includes the full exact Decision Evidence trace and
    # source-version appendix. No paid bundle/watch is generated incidentally.
    content = ("# Your free CaptureBrief assumption check\n\n"
               "One selected assumption. No charge, automatic upgrade or included change watch.\n\n"
               + render_markdown(case, now=checked_at) + "\n")
    data = content.encode("utf-8")
    receipt = {
        "schema": "capturebrief-free-check-report-receipt-v1",
        "requested_offer": FREE_OFFER,
        "case_sha256": sha256_hex(canonical_json(case)),
        "scope_sha256": _scope_digest(case),
        "report_sha256": hashlib.sha256(data).hexdigest(),
        "report_bytes": len(data),
        "evaluated_at": checked_at.isoformat().replace("+00:00", "Z"),
        "reservation_scope_matches": True,
        "core_evidence_eligible": True,
        "assumption_count": 1,
        "amount_due_cents": 0,
        "watch_included": False,
        "payment_verified": False,
        "automatic_upgrade_authorized": False,
        "customer_delivery_verified": False,
        "customer_release_authorized": False,
        "external_send_authorized": False,
    }
    encoded = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with ExitStack() as stack:
        for target in sorted((path, receipt_path), key=str):
            stack.enter_context(exclusive_path_lock(target, suffix=".free-check.lock"))
        for target, expected in ((path, data), (receipt_path, encoded)):
            if target.exists() and (not target.is_file() or target.read_bytes() != expected):
                raise ValueError("Existing free-check report or receipt conflicts")
        ensure_exact_bytes(path, data)
        ensure_exact_bytes(receipt_path, encoded)
    return receipt
