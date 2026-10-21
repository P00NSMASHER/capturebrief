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
from contextlib import ExitStack
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capturebrief_core.atomic_io import ensure_exact_bytes, exclusive_path_lock
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



def _bounded_record(path: Path, maximum: int) -> dict:
    """Parse an existing private case/receipt only to recover its import time."""
    if not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("Existing private intake artifact is missing or oversized")
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError) as exc:
        raise ValueError("Existing private intake artifact is malformed") from None
    if not isinstance(result, dict):
        raise ValueError("Existing private intake artifact must be an object")
    return result


def _existing_intake_time(case_output: Path, receipt_output: Path,
                          request_sha256: str) -> datetime | None:
    """Recover the original imported_at for a byte-identical retry.

    Both outputs use one stable timestamp; otherwise a second run with an
    implicit current time would generate a different case identity. Existing
    artifacts are UNTRUSTED until the caller recreates and compares their
    complete expected bytes. Never use prior payment or approval claims.
    """
    if receipt_output.exists():
        record = _bounded_record(receipt_output, 16 * 1024)
        if (record.get("schema") != "capturebrief-private-intake-receipt-v1"
                or record.get("request_sha256") != request_sha256):
            raise ValueError("Existing intake receipt belongs to a different request")
        observed = record.get("imported_at")
    elif case_output.exists():
        record = _bounded_record(case_output, 128 * 1024)
        try:
            observed = record["intake"]["submitted_at"]
        except (KeyError, TypeError):
            raise ValueError("Existing intake case has no recorded import timestamp") from None
    else:
        return None
    if not isinstance(observed, str) or not observed.endswith("Z"):
        raise ValueError("Existing import timestamp is invalid")
    try:
        timestamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Existing import timestamp is invalid") from None
    if (timestamp.utcoffset() is None
            or timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") != observed):
        raise ValueError("Existing import timestamp is not canonical UTC")
    return timestamp



def import_request(message_path: str, case_path: str, receipt_path: str, *,
                   imported_at: datetime | None = None,
                   lock_timeout_seconds: float = 5.0,
                   expected_request_sha256: str | None = None) -> dict:
    checked_at = imported_at or datetime.now(timezone.utc)
    if not isinstance(checked_at, datetime) or checked_at.utcoffset() is None:
        raise ValueError("Import time must be timezone aware")
    checked_at = checked_at.astimezone(timezone.utc)
    src = _private_file(message_path)
    case_output, receipt_output = _private_file(case_path), _private_file(receipt_path)
    if len({src, case_output, receipt_output}) != 3:
        raise ValueError("Source, case and receipt paths must be distinct")
    # Pair-wide publication is not atomic. Lock BOTH paths in a stable
    # order before reading old timestamp/artifacts, so parallel inbox imports
    # cannot invent incompatible case identities or partial output pairs.
    # The same check works when two jobs share just ONE output destination.
    if type(lock_timeout_seconds) not in {int, float} or not 0 <= lock_timeout_seconds <= 60:
        raise ValueError("Invalid bounded private intake lock timeout")
    with ExitStack() as held:
        for output in sorted((case_output, receipt_output),
                             key=lambda value: str(value).casefold()):
            held.enter_context(exclusive_path_lock(
                output, timeout_seconds=lock_timeout_seconds,
                suffix=".intake.lock",
            ))
        return _import_request_locked(
            src, case_output, receipt_output, checked_at, imported_at,
            expected_request_sha256,
        )


def _import_request_locked(
    src: Path, case_output: Path, receipt_output: Path,
    checked_at: datetime, imported_at: datetime | None,
    expected_request_sha256: str | None,
) -> dict:
    """Build and publish one customer request while both output locks are held."""
    # Bounded read; no user request text, credentials or contact details in logs.
    with src.open("rb") as handle:
        raw = handle.read(MAX_REQUEST_TEXT * 4 + 1)
    if len(raw) > MAX_REQUEST_TEXT * 4:
        raise ValueError("Input draft exceeds byte limit")
    message = raw.decode("utf-8")
    request_sha = hashlib.sha256(raw).hexdigest()
    # Batch file names are based on an earlier bounded read of the same
    # local request. Bind the second read to that exact source fingerprint
    # before any case or receipt can be published under its digest path.
    if expected_request_sha256 is not None:
        if (not isinstance(expected_request_sha256, str)
                or len(expected_request_sha256) != 64
                or any(ch not in "0123456789abcdef" for ch in expected_request_sha256)
                or request_sha != expected_request_sha256):
            raise ValueError("Buyer request changed before private import")
    if imported_at is None:
        # Reuse the timestamp of a previously imported byte-identical
        # request, including after interruption between the two file writes.
        # Explicit --imported-at retains its original exact-time semantics.
        checked_at = _existing_intake_time(case_output, receipt_output, request_sha) or checked_at
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
        "request_sha256": request_sha,
        "imported_at": checked_at.isoformat().replace("+00:00", "Z"),
        "case_submitted_at_is_email_delivery_proof": False,
        **claims,
        "independent_payment_lookup": "NOT_PERFORMED",
        "operator_review_required": True,
        "case_release_authorized": False,
    }
    receipt_bytes = (json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    # Preflight BOTH existing artifacts before any write. A corrupt receipt
    # must not cause us to create a new case when only its partner is missing.
    # ensure_exact_bytes then provides the existing atomic, no-overwrite
    # publication and identical-content retry contract.
    for output, expected in ((case_output, case_bytes), (receipt_output, receipt_bytes)):
        if output.exists() and (not output.is_file() or output.read_bytes() != expected):
            raise ValueError("Existing private intake artifact conflicts with request")
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
