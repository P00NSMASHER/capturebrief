"""Bounded local case-to-checkout inbox processor for CaptureBrief.

The operator places minimal correlation files in a PRIVATE directory after
receiving a buyer request and its Checkout Session reference through authorized
channels. This is not an unauthenticated webhook. Preview performs NO NETWORK
and NO WRITES. Execute does direct read-only Stripe verification and immutable
SQLite registration; it never approves paid fulfillment or sends messages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from capturebrief_core.private_order_registry import _private_db, order_summary
from scripts.batch_import_request_drafts import _private_directory
from scripts.review_private_cases import _load_unverified_pair
from scripts.register_private_order import register_checkout

MAX_ASSOCIATIONS = 100
MAX_MANIFEST_BYTES = 16 * 1024
_MATCH = re.compile(r"^request-([0-9a-f]{64})\.order\.json$")
_SESSION = re.compile(r"^cs_live_[A-Za-z0-9]+$")
_REQUIRED = {"schema", "request_sha256", "checkout_session_id"}


def _private_association(path: Path, target_sha: str) -> dict[str, str]:
    junction = getattr(path, "is_junction", None)
    if (path.is_symlink() or (junction is not None and junction())
            or not path.is_file() or not 0 < path.stat().st_size <= MAX_MANIFEST_BYTES):
        raise ValueError("Invalid private order association file")
    with path.open("rb") as stream:
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("Private order association exceeds size limit")
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError("Duplicate order association key")
            result[k] = v
        return result
    info = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    if (not isinstance(info, dict) or set(info) != _REQUIRED
            or info.get("schema") != "capturebrief-private-checkout-association-v1"
            or info.get("request_sha256") != target_sha
            or not isinstance(info.get("checkout_session_id"), str)
            or not _SESSION.fullmatch(info["checkout_session_id"])):
        raise ValueError("Private order association is malformed or contradictory")
    return info


def process_private_order_queue(
    cases_directory: str | Path,
    associations_directory: str | Path,
    database_path: str | Path,
    *,
    preview_only: bool = True,
    max_associations: int = MAX_ASSOCIATIONS,
    api_key: str = "",
    synthetic_provider: Callable | None = None,
    synthetic_test_mode: bool = False,
) -> dict[str, Any]:
    if type(preview_only) is not bool or type(synthetic_test_mode) is not bool:
        raise ValueError("Preview and test mode must be booleans")
    if (not synthetic_test_mode and synthetic_provider is not None
            or synthetic_test_mode and synthetic_provider is None):
        raise ValueError("Synthetic fetcher must be used only in explicit synthetic tests")
    if type(max_associations) is not int or not 1 <= max_associations <= MAX_ASSOCIATIONS:
        raise ValueError("Private Checkout associations must be bounded to 1-100")
    cases = _private_directory(cases_directory)
    mappings = _private_directory(associations_directory)
    db = _private_db(database_path)
    if (cases == mappings or cases.is_relative_to(mappings)
            or mappings.is_relative_to(cases)
            or db.is_relative_to(cases)
            or db.is_relative_to(mappings)):
        raise ValueError("Case, Checkout association and registry roots must be distinct")
    entries = sorted(mappings.iterdir(), key=lambda p:(p.name.casefold(),p.name))
    candidates: list[Path] = []
    ignored_non_association_entries = 0
    for entry in entries:
        lower = entry.name.casefold()
        if (lower.startswith("request-")
                or lower.endswith((".order.json", ".order.json.tmp",
                                   ".order.json.lock", ".order.jsn"))):
            # Invalid and interrupted association-looking files are blockers.
            # Otherwise a mistyped file or partial save could make the queue
            # misleadingly report EMPTY while the operator expects an order.
            candidates.append(entry)
        else:
            ignored_non_association_entries += 1
    if len(candidates) > max_associations:
        raise ValueError("Too many private association files")
    statuses = {"preview_ready":0, "registered":0, "reused":0, "blocked":0}
    unexpected_association_entries = 0
    rows: list[dict[str, str]] = []
    for file in candidates:
        tag = hashlib.sha256(file.name.encode()).hexdigest()[:12]
        try:
            match = _MATCH.fullmatch(file.name)
            if not match:
                unexpected_association_entries += 1
                raise ValueError("Invalid case-association file name")
            digest = match.group(1)
            assoc = _private_association(file, digest)
            case_file = cases / f"request-{digest}.case.json"
            receipt = cases / f"request-{digest}.receipt.json"
            _load_unverified_pair(case_file, receipt, digest)
            for target in (case_file, receipt):
                lock = target.with_name(target.name + ".intake.lock")
                if lock.exists() or lock.is_symlink():
                    raise ValueError("Private buyer intake is locked")
            if preview_only:
                statuses["preview_ready"] += 1
                state = "CANDIDATE_ONLY_NOT_PAYMENT_VERIFIED"
            else:
                result = register_checkout(
                    case_file, checkout_session_id=assoc["checkout_session_id"],
                    database_path=db, api_key=api_key,
                    synthetic_test_mode=synthetic_test_mode,
                    fetcher=synthetic_provider,
                )
                if result["status"] == "PRIVATE_ORDER_REGISTERED_REVIEW_REQUIRED":
                    statuses["registered"] += 1
                    state = "REGISTERED_REVIEW_REQUIRED"
                elif result["status"] == "ALREADY_REGISTERED_UNVERIFIED":
                    statuses["reused"] += 1
                    state = "REUSED_UNVERIFIED"
                else:
                    statuses["blocked"] += 1
                    state = "BLOCKED"
            rows.append({"item_tag": tag, "state": state})
        except (OSError, ValueError, UnicodeError, TypeError, KeyError) as exc:
            statuses["blocked"] += 1
            rows.append({"item_tag": tag, "state": "BLOCKED", "error_type": type(exc).__name__})
    return {
        "schema": "capturebrief-private-order-queue-v1",
        "status": ("PRIVATE_ORDER_QUEUE_BLOCKED" if statuses["blocked"]
                   else "PRIVATE_ORDER_QUEUE_EMPTY" if not candidates
                   else "PRIVATE_ORDER_QUEUE_PREVIEW" if preview_only
                   else "PRIVATE_ORDER_QUEUE_REVIEW_REQUIRED"),
        "preview_only": preview_only,
        "input_associations": len(candidates),
        "unexpected_association_entries": unexpected_association_entries,
        "ignored_non_association_entries": ignored_non_association_entries,
        **statuses,
        "items": rows,
        "private_registry_read_only_state": order_summary(db)["status"],
        "provider_mode": "SYNTHETIC_TEST_ONLY" if synthetic_test_mode else "DIRECT_STRIPE_WHEN_EXECUTED",
        "all_work_authorized": False,
        "any_external_send_authorized": False,
        "any_customer_release_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases-dir", required=True)
    parser.add_argument("--associations-dir", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--execute", action="store_true",
                        help="Fetch direct LIVE Stripe and register only matching unique cases")
    parser.add_argument("--max-associations", type=int, default=MAX_ASSOCIATIONS)
    parser.add_argument("--key-env", default="STRIPE_CAPTUREBRIEF_SECRET_KEY")
    args = parser.parse_args(argv)
    try:
        report = process_private_order_queue(
            args.cases_dir, args.associations_dir, args.registry,
            preview_only=not args.execute,
            max_associations=args.max_associations,
            api_key=os.environ.get(args.key_env, ""),
        )
        print(json.dumps(report, sort_keys=True, indent=2))
        return 3 if report["blocked"] else 0
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({
            "status": "PRIVATE_ORDER_QUEUE_BLOCKED",
            "error_type": type(exc).__name__,
            "any_customer_release_authorized": False,
        }, sort_keys=True))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
