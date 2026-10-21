"""Read-only, evidence-scoped CaptureBrief order + research + delivery + watch dashboard.

This joins PRIVATE registered payments to original case/receipt integrity
and the existing fulfillment planner. No case is auto-promoted from an
unverified buyer draft. Source catalog coverage stays pinned to approved FY.
No case, order DB, source, bundle or watch record is written or sent.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from contextlib import closing, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from capturebrief_core.archive_catalog import (
    ArchiveCatalogStale, ARCHIVE_CATALOG_CURRENT_THROUGH_FY,
    catalog_years_for_fiscal_year, fiscal_year_for_datetime,
)
from capturebrief_core.fulfillment_plan import build_fulfillment_plan
from capturebrief_core.model import canonical_json, sha256_hex
from capturebrief_core.private_order_registry import (
    _private_db, _read_only_connection, _record_is_safe, _tag,
)
from scripts.batch_import_request_drafts import _private_directory
from scripts.review_private_cases import _load_unverified_pair

MAX_ORDERS = 100


def source_catalog_preflight(*, now: datetime | None = None) -> dict[str, Any]:
    """Evaluate frozen approved source *scope*, not actual publisher bytes."""
    at = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(at, datetime) or at.utcoffset() is None:
        raise ValueError("Readiness timestamp must have an offset")
    at = at.astimezone(timezone.utc)
    fiscal_year = fiscal_year_for_datetime(at)
    try:
        years = catalog_years_for_fiscal_year(fiscal_year)
        status = "APPROVED_CATALOG_SCOPE_ONLY_NOT_SOURCE_COVERAGE"
    except ArchiveCatalogStale:
        years = []
        status = "SOURCE_CATALOG_REFRESH_REVIEW_REQUIRED"
    return {
        "schema": "capturebrief-private-source-preflight-v1",
        "checked_at": at.isoformat().replace("+00:00", "Z"),
        "requested_fiscal_year": fiscal_year,
        "approved_catalog_current_through_fy": ARCHIVE_CATALOG_CURRENT_THROUGH_FY,
        "approved_catalog_archive_years": len(years),
        "status": status,
        "verified_source_bytes": False,
        "publisher_originals_authenticated": False,
        "full_history_coverage_approved": False,
        "human_source_review_complete": False,
        "customer_release_authorized": False,
    }


def inspect_fulfillment(
    private_case_dir: str | Path, database_path: str | Path,
    *, now: datetime | None = None, max_orders: int = MAX_ORDERS,
) -> dict[str, Any]:
    if type(max_orders) is not int or not 1 <= max_orders <= MAX_ORDERS:
        raise ValueError("Maximum private orders must be 1-100")
    root = _private_directory(private_case_dir)
    source = source_catalog_preflight(now=now)
    at = datetime.fromisoformat(source["checked_at"].replace("Z", "+00:00"))
    db = _private_db(database_path)
    if db.is_relative_to(root):
        raise ValueError("Private order registry must be separate from customer case folder")
    result: list[dict[str, Any]] = []
    blocked = 0
    connector = _read_only_connection(db)
    with (closing(connector) if connector is not None else nullcontext(None)) as connection:
        if connection is None:
            stored = []
        else:
            try:
                stored = connection.execute("SELECT * FROM orders ORDER BY created_at,session_ref").fetchall()
            except sqlite3.DatabaseError:
                return {
                    "status": "PRIVATE_ORDER_FULFILLMENT_BLOCKED",
                    "blocked": 1, "orders": [], "external_send_authorized": False,
                }
        if len(stored) > max_orders:
            raise ValueError("Too many private orders for bounded review")
        for row in stored:
            order_tag = _tag(row["session_ref"])
            review: dict[str, Any] = {"order_tag": order_tag}
            try:
                if not _record_is_safe(row):
                    raise ValueError("Order row contains unauthorized state")
                digest = row["request_sha256"]
                case_path = root / f"request-{digest}.case.json"
                receipt_path = root / f"request-{digest}.receipt.json"
                for p in (case_path, receipt_path):
                    lock = p.with_name(p.name + ".intake.lock")
                    if lock.exists() or lock.is_symlink():
                        raise ValueError("Intake case is locked")
                case = _load_unverified_pair(case_path, receipt_path, digest)
                if sha256_hex(canonical_json(case)) != row["case_sha256"]:
                    raise ValueError("Order points to a mutated original intake case")
                plan = build_fulfillment_plan(case, now=at)
                if (plan.get("delivery_bundle_eligible") is not False
                        or plan.get("release_state") != "FAIL_CLOSED"
                        or plan["communications"]["external_send_authorized"] is not False):
                    raise ValueError("Unverified intake must never satisfy delivery gates")
                pending = ["SENDER_IDENTITY_REVIEW", "LIVE_PAYMENT_REFRESH_BEFORE_WORK",
                           "FAMILY_AND_PACKET_SOURCE_REVIEW",
                           "ASSUMPTION_AND_RULE_QA",
                           "DELIVERY_RECEIPT_AND_HUMAN_ACCEPTANCE",
                           "14_DAY_WATCH_NOT_STARTED"]
                if source["status"] == "SOURCE_CATALOG_REFRESH_REVIEW_REQUIRED":
                    pending.insert(2, "FY2027_ARCHIVE_CATALOG_RECERTIFICATION")
                next_task = plan.get("next_task") or {}
                review.update({
                    "status": "PENDING_PRIVATE_CUSTOMER_REVIEW",
                    "payment_state": row["payment_state"],
                    "review_task_count": plan["summary"]["open_tasks"],
                    "next_effort_stage": next_task.get("effort_stage") or "OTHER",
                    "current_case_release_state": plan["release_state"],
                    "source_state": source["status"],
                    "delivery_state": "NOT_VERIFIED",
                    "watch_state": "NOT_STARTED",
                    "pending_evidence": pending,
                    "payment_currently_authenticated_for_start": False,
                    "customer_release_authorized": False,
                    "external_send_authorized": False,
                })
            except (OSError, ValueError, TypeError, KeyError, sqlite3.DatabaseError) as exc:
                blocked += 1
                review.update(status="BLOCKED_INTEGRITY", error_type=type(exc).__name__)
            result.append(review)
    return {
        "schema": "capturebrief-private-order-fulfillment-v1",
        "status": ("PRIVATE_ORDER_FULFILLMENT_BLOCKED" if blocked
                   else "PRIVATE_ORDER_FULFILLMENT_REVIEW_PENDING" if result
                   else "PRIVATE_ORDER_FULFILLMENT_EMPTY"),
        "source_catalog": source,
        "orders": result,
        "blocked": blocked,
        "review_only": True,
        "external_send_authorized": False,
        "customer_release_authorized": False,
        "delivery_verified": False,
        "watch_started": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases-dir", required=True)
    p.add_argument("--registry", required=True)
    p.add_argument("--max-orders", type=int, default=MAX_ORDERS)
    args = p.parse_args(argv)
    try:
        result = inspect_fulfillment(args.cases_dir, args.registry, max_orders=args.max_orders)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 3 if result["blocked"] else 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            "status": "PRIVATE_ORDER_FULFILLMENT_BLOCKED",
            "error_type": type(exc).__name__,
            "customer_release_authorized": False,
        }, sort_keys=True))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
