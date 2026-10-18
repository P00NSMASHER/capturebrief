"""Import a locally saved CaptureBrief buyer request into a private case.

No email access, network, payment lookup, customer messaging, or launch approval.
Both outputs MUST be outside the public source repository and its Pages tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capturebrief_core.atomic_io import ensure_exact_bytes
from capturebrief_core.model import canonical_json, sha256_hex
from capturebrief_core.request_draft import MAX_REQUEST_TEXT, create_unverified_case

REPOSITORY = Path(__file__).resolve().parents[1]


def _private_file(path: str) -> Path:
    dest = Path(path).expanduser().resolve()
    if dest.is_relative_to(REPOSITORY) or any(
        parent.name in {"gh-pages", ".git"}
        for parent in (dest, *dest.parents)
    ):
        raise ValueError("Customer intake artifacts must remain outside public source or publishing trees")
    if dest.exists() and not dest.is_file():
        raise ValueError("A private intake path must identify a regular file")
    return dest


def import_request(message_path: str, case_path: str, receipt_path: str, *,
                   imported_at: datetime | None = None) -> dict:
    checked_at = imported_at or datetime.now(timezone.utc)
    if not isinstance(checked_at, datetime) or checked_at.utcoffset() is None:
        raise ValueError("Import time must be timezone aware")
    checked_at = checked_at.astimezone(timezone.utc)
    src = _private_file(message_path)
    case_output, receipt_output = _private_file(case_path), _private_file(receipt_path)
    if len({src, case_output, receipt_output}) != 3:
        raise ValueError("Source, case and receipt paths must be distinct")
    # Bounded read; no user request text, credentials or contact details in logs.
    with src.open("rb") as handle:
        raw = handle.read(MAX_REQUEST_TEXT * 4 + 1)
    if len(raw) > MAX_REQUEST_TEXT * 4:
        raise ValueError("Input draft exceeds byte limit")
    message = raw.decode("utf-8")
    case, claims = create_unverified_case(
        message,
        submitted_at=checked_at.isoformat().replace("+00:00", "Z"),
    )
    # This is an operator import timestamp, NOT authenticated email-delivery time.
    case["intake"]["record_time_basis"] = "LOCAL_IMPORT_TIME_NOT_MAIL_PROVIDER_RECEIPT"
    case_bytes = (json.dumps(case, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    # Case-content identity MUST match Product Core canonical-json SHA-256;
    # the pretty-printed on-disk bytes have a separate file integrity digest.
    case_sha = sha256_hex(canonical_json(case))
    case_file_sha = hashlib.sha256(case_bytes).hexdigest()
    receipt = {
        "schema": "capturebrief-private-intake-receipt-v1",
        "case_id": case["case_id"],
        "case_sha256": case_sha,
        "case_file_sha256": case_file_sha,
        "request_sha256": hashlib.sha256(raw).hexdigest(),
        "imported_at": checked_at.isoformat().replace("+00:00", "Z"),
        "case_submitted_at_is_email_delivery_proof": False,
        **claims,
        "independent_payment_lookup": "NOT_PERFORMED",
        "operator_review_required": True,
        "case_release_authorized": False,
    }
    receipt_bytes = (json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    # Hash-based idempotence; no silent overwrite or symlink traversal.
    ensure_exact_bytes(case_output, case_bytes)
    ensure_exact_bytes(receipt_output, receipt_bytes)
    return {
        "status": "PRIVATE_CASE_CREATED_REVIEW_REQUIRED",
        "case_id": case["case_id"],
        "case_sha256": case_sha,
        "case_file_sha256": case_file_sha,
        "request_sha256": receipt["request_sha256"],
        "case_output": str(case_output),
        "receipt_output": str(receipt_output),
        "operator_review_required": True,
        "payment_verified": False,
        "external_send_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("message", help="Private plain-text request saved from inbox/copy action")
    p.add_argument("--case-output", required=True, help="Private case JSON destination")
    p.add_argument("--receipt-output", required=True, help="Private receipt JSON destination")
    p.add_argument("--imported-at", help="Import time with timezone; default now UTC")
    args = p.parse_args(argv)
    try:
        checked_at = (
            datetime.fromisoformat(args.imported_at.replace("Z", "+00:00"))
            if args.imported_at else None
        )
        result = import_request(
            args.message, args.case_output, args.receipt_output,
            imported_at=checked_at,
        )
    except (OSError, ValueError, UnicodeError, TypeError) as exc:
        print(json.dumps({"status": "IMPORT_BLOCKED", "error": type(exc).__name__,
                          "external_send_authorized": False}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
