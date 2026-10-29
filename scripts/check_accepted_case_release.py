"""Read-only accepted-case release check; deliberately never sends anything.

Exit 0 means source, private recovery and independently signed per-message
approvals verified against the supplied exact private bytes. It does NOT
perform customer delivery, charge, or independent real-world identity checks.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from capturebrief_core.accepted_case_release import (
    AcceptedCaseBlocked, _json_file, _root, inspect_accepted_case,
)
from capturebrief_core.authorization_ledger import reserve_once


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="capturebrief-accepted-case-release")
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--release-manifest", type=Path, required=True)
    parser.add_argument("--trusted-signers", type=Path, required=True,
                        help="Externally provisioned owner-only roster, NOT in the case root")
    parser.add_argument("--reserve-once", action="store_true",
                        help="Atomically reserve this approved one-message nonce, without sending")
    parser.add_argument("--authorization-ledger", type=Path,
                        help="One durable shared private SQLite ledger for ALL accepted cases")
    args = parser.parse_args(argv)
    try:
        root = _root(args.private_root)
        case = args.case.expanduser().absolute()
        manifest = args.release_manifest.expanduser().absolute()
        roster = args.trusted_signers.expanduser().absolute()
        if (not case.is_relative_to(root) or not manifest.is_relative_to(root)
                or roster.is_relative_to(root)
                or roster == case or roster == manifest):
            raise AcceptedCaseBlocked("Keep case/manifest in approved root and signer trust separate")
        _root(roster.parent)
        trusted = _json_file(roster)
        release = _json_file(manifest)
        result = inspect_accepted_case(
            _json_file(case), release,
            private_root=root, trusted_keys=trusted,
        )
        if args.reserve_once:
            if args.authorization_ledger is None:
                raise AcceptedCaseBlocked("Shared append-only authorization ledger required")
            ledger = args.authorization_ledger.expanduser().absolute()
            if ledger.is_relative_to(root):
                raise AcceptedCaseBlocked("Shared authorization ledger must reside outside the case-specific root")
            result = reserve_once(release, verification=result, ledger_path=ledger)
        elif args.authorization_ledger is not None:
            raise AcceptedCaseBlocked("Ledger path is meaningful only with --reserve-once")
    except (AcceptedCaseBlocked, ValueError, OSError, TypeError, KeyError, AttributeError):
        # Errors can reveal private customer details in exception strings.
        # This operator entrypoint reports a safe fixed-class denial only.
        print(json.dumps({"status": "CUSTOMER_DELIVERY_BLOCKED",
                          "customer_release_authorized": False,
                          "external_send_performed": False}), file=sys.stdout)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
