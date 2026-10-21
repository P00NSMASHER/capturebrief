"""Offline, read-only FY2027 candidate source-coverage inspector.

It NEVER updates the production-approved catalog/index, retains public
sources, promotes private candidate bytes, sends email, or releases cases.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.source_coverage_audit import inspect_unapproved_fy2027_candidate_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-index", required=True)
    parser.add_argument("--snapshot-root", default=None)
    parser.add_argument("--verify-bytes", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = inspect_unapproved_fy2027_candidate_index(
            args.private_index, now=datetime.now(timezone.utc),
            verify_bytes=args.verify_bytes, snapshot_root=args.snapshot_root,
        )
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "FY2027_CANDIDATE_AUDIT_BLOCKED",
            "error_type": type(exc).__name__,
            "approved_full_catalog_coverage": False,
            "customer_release_authorized": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
