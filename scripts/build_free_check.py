"""Build one private free-check report after reservation and full evidence review.

This has no network, payment, watch scheduling or customer-send capability.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capturebrief_core.free_trial import build_free_check_report
from scripts.batch_import_request_drafts import _private_directory
from scripts.review_private_cases import _bounded_json, MAX_CASE_BYTES


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path, help="Reviewed private case retaining original trial scope")
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Private .md result outside public source")
    args = parser.parse_args(argv)
    try:
        private = _private_directory(args.case.expanduser().absolute().parent)
        case, _ = _bounded_json(private / args.case.name, MAX_CASE_BYTES)
        report = build_free_check_report(case, args.output, database_path=args.registry)
    except (ValueError, OSError, TypeError, KeyError, RuntimeError, sqlite3.Error) as error:
        print(json.dumps({
            "status": "FREE_CHECK_BUILD_BLOCKED", "error_type": type(error).__name__,
            "customer_release_authorized": False, "external_send_authorized": False,
        }, sort_keys=True))
        return 3
    print(json.dumps({"status": "PRIVATE_FREE_CHECK_BUILT_REVIEW_REQUIRED", **report},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
