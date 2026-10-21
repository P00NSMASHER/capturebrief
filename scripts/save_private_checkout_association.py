"""Create one privately saved Checkout-to-intake association, without network.

The local operator enters a Checkout Session reference found independently in
Stripe. This command checks the original UNVERIFIED private intake pair and
prevents accidentally using the same Session ID for two cases. It does NOT
query Stripe, prove payment, authenticate a buyer, or approve fulfillment.

Run without --session-id to enter the ID interactively (avoids process args).
"""
from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from capturebrief_core.atomic_io import ensure_exact_bytes, exclusive_path_lock
from capturebrief_core.private_order_registry import _tag
from scripts.batch_import_request_drafts import _private_directory
from scripts.review_private_cases import _load_unverified_pair
from scripts.process_private_order_queue import _MATCH, _SESSION, _private_association

_CASE_NAME = re.compile(r"^request-([0-9a-f]{64})\.case\.json$")


def save_private_checkout_association(
    case_file: str | Path,
    associations_directory: str | Path,
    session_id: str,
) -> dict[str, Any]:
    """Create or exactly reuse a private association, never silently reassign."""
    if not isinstance(session_id, str) or not _SESSION.fullmatch(session_id):
        raise ValueError("An independently observed live Checkout Session reference is required")
    supplied = Path(case_file).expanduser().absolute()
    cases = _private_directory(supplied.parent)
    associations = _private_directory(associations_directory)
    if (cases == associations or cases.is_relative_to(associations)
            or associations.is_relative_to(cases)):
        raise ValueError("Checkout associations must have a separate private directory")
    name = supplied.name
    match = _CASE_NAME.fullmatch(name)
    if not match or supplied.is_symlink():
        raise ValueError("Expected digest-addressed private customer intake")
    digest = match.group(1)
    receipt = cases / f"request-{digest}.receipt.json"
    if receipt.is_symlink():
        raise ValueError("Private receipt must not be a link")
    for artifact in (supplied, receipt):
        lock = artifact.with_name(artifact.name + ".intake.lock")
        if lock.exists() or lock.is_symlink():
            raise ValueError("Private intake is still in progress")
    _load_unverified_pair(supplied, receipt, digest)
    candidate = associations / f"request-{digest}.order.json"
    payload = {
        "schema": "capturebrief-private-checkout-association-v1",
        "request_sha256": digest,
        "checkout_session_id": session_id,
    }
    encoded = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    # Serialize mappings with a single very short private directory lock to
    # prevent competing operators assigning one Session to different cases.
    with exclusive_path_lock(
        associations / ".capturebrief-associations", timeout_seconds=5,
        suffix=".lock",
    ):
        for entry in sorted(associations.iterdir(), key=lambda p: (p.name.casefold(),p.name)):
            lower = entry.name.casefold()
            if entry.name == ".capturebrief-associations.lock":
                continue
            if not (lower.startswith("request-")
                    or lower.endswith((".order.json", ".order.json.tmp",
                                       ".order.json.lock", ".order.jsn"))):
                continue
            valid = _MATCH.fullmatch(entry.name)
            if not valid:
                raise ValueError("A malformed private Checkout association requires review")
            existing = _private_association(entry, valid.group(1))
            if existing["checkout_session_id"] == session_id and valid.group(1) != digest:
                raise ValueError("Checkout session is already correlated to another request")
        result = ensure_exact_bytes(candidate, encoded)
    return {
        "schema": "capturebrief-private-checkout-association-receipt-v1",
        "status": ("PRIVATE_ASSOCIATION_SAVED_UNVERIFIED" if result["created"]
                   else "PRIVATE_ASSOCIATION_ALREADY_SAVED_UNVERIFIED"),
        "opaque_item_tag": _tag(digest),
        "operator_supplied_reference_not_authenticated": True,
        "stripe_payment_verified": False,
        "sender_authenticated": False,
        "registered_order_created": False,
        "work_authorized": False,
        "external_send_authorized": False,
        "customer_release_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", help="Private request-<SHA256>.case.json path")
    parser.add_argument("--associations-dir", required=True)
    parser.add_argument(
        "--session-id",
        help="Session ID (not recommended: exposed in process arguments). Prefer interactive input.",
    )
    args = parser.parse_args(argv)
    try:
        if args.session_id is None:
            if not sys.stdin.isatty():
                raise ValueError("Interactive terminal required for private Checkout Session input")
            session_id = getpass.getpass("Paste independently verified Checkout Session ID: ")
        else:
            session_id = args.session_id
        result = save_private_checkout_association(
            args.case, args.associations_dir, session_id,
        )
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(json.dumps({
            "status": "PRIVATE_ASSOCIATION_BLOCKED",
            "error_type": type(exc).__name__,
            "stripe_payment_verified": False,
            "customer_release_authorized": False,
        }, sort_keys=True))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
