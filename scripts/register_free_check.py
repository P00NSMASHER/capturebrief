"""Reserve a free CaptureBrief assumption check from private imported intake.

No network, customer messages, billing or delivery. A separate operator identity
review must supply the canonical business key and retained review fingerprint.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capturebrief_core.free_trial import reserve_free_check, inspect_free_check
from scripts.batch_import_request_drafts import _private_directory
from scripts.review_private_cases import _bounded_json, _load_unverified_pair, MAX_RECEIPT_BYTES

_CASE_NAME = re.compile(r"^request-([0-9a-f]{64})\.case\.json$")


def register_private_free_check(
    case_file: str | Path, *, registry: str | Path,
    reviewed_business_key: str, identity_review_sha256: str,
) -> dict:
    raw = Path(case_file).expanduser().absolute()
    private_root = _private_directory(raw.parent)
    match = _CASE_NAME.fullmatch(raw.name)
    if not match or raw.is_symlink():
        raise ValueError("Expected an original digest-addressed private intake case")
    case_path = private_root / raw.name
    receipt_path = private_root / f"request-{match.group(1)}.receipt.json"
    for path in (case_path, receipt_path):
        lock = path.with_name(path.name + ".intake.lock")
        if lock.exists() or lock.is_symlink():
            raise ValueError("Private request import is in progress")
    case = _load_unverified_pair(case_path, receipt_path, match.group(1))
    receipt, _ = _bounded_json(receipt_path, MAX_RECEIPT_BYTES)
    result = reserve_free_check(
        registry, case=case, receipt=receipt,
        reviewed_business_key=reviewed_business_key,
        identity_review_sha256=identity_review_sha256,
    )
    result["evidence_readiness"] = inspect_free_check(case, database_path=registry)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", help="Original private request-<sha>.case.json")
    parser.add_argument("--registry", required=True, help="Dedicated private .sqlite registry outside source trees")
    parser.add_argument("--reviewed-business-key", required=True,
                        help="Operator-confirmed domain:example.com or registry:authority:identifier")
    parser.add_argument("--identity-review-sha256", required=True,
                        help="SHA-256 of separately retained operator identity review")
    args = parser.parse_args(argv)
    try:
        report = register_private_free_check(
            args.case, registry=args.registry,
            reviewed_business_key=args.reviewed_business_key,
            identity_review_sha256=args.identity_review_sha256,
        )
    except (ValueError, OSError, TypeError, KeyError, RuntimeError, sqlite3.Error) as exc:
        print(json.dumps({
            "status": "FREE_CHECK_RESERVATION_BLOCKED", "error_type": type(exc).__name__,
            "payment_verified": False, "customer_release_authorized": False,
            "external_send_authorized": False,
        }, sort_keys=True))
        return 3
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
