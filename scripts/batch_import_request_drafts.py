"""Import a bounded folder of PRIVATE CaptureBrief buyer drafts for human review.

This is an operator-invoked local batch utility, not a mailbox listener,
customer upload service, payment confirmation, or outbound communication.
Reports contain only counts, request digests and failure type names.
All source requests and generated cases remain outside the public repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from capturebrief_core.request_draft import MAX_REQUEST_TEXT
from scripts.import_request_draft import REPOSITORY, import_request

MAX_FILES = 100
MAX_BYTES = MAX_REQUEST_TEXT * 4


def _private_directory(value: str | Path) -> Path:
    """Accept an existing private, regular directory, never a junction."""
    raw = Path(value).expanduser().absolute()
    for part in (raw, *raw.parents):
        junction = getattr(part, "is_junction", None)
        if part.is_symlink() or (junction is not None and junction()):
            raise ValueError("Private import directory cannot traverse links")
    try:
        root = raw.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ValueError("Private import folder is unavailable") from None
    if (not root.is_dir() or root.is_relative_to(REPOSITORY)
            or any(part.name.casefold() in {".git", "gh-pages"}
                   for part in (root, *root.parents))):
        raise ValueError("Private request directories must be outside publishing trees")
    return root


def _valid_request_entry(entry: Path) -> bytes:
    """Bound untrusted source bytes and refuse links without following them."""
    junction = getattr(entry, "is_junction", None)
    if (entry.is_symlink() or (junction is not None and junction())
            or not entry.is_file() or not 0 < entry.stat().st_size <= MAX_BYTES):
        raise ValueError("Expected a bounded regular customer draft file")
    with entry.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Buyer draft changed or exceeds byte budget")
    return raw


def batch_import(
    input_directory: str | Path,
    output_directory: str | Path,
    *,
    max_files: int = MAX_FILES,
) -> dict[str, Any]:
    """Import only immediate .txt drafts, deduplicated by exact input bytes.

    The validated single-request importer owns timestamp reuse, concurrent
    file locking, and fail-closed publication. No case is release-ready.
    """
    if type(max_files) is not int or not 1 <= max_files <= MAX_FILES:
        raise ValueError("Batch must be limited to 1-100 buyer drafts")
    incoming = _private_directory(input_directory)
    destination = _private_directory(output_directory)
    if (incoming == destination or incoming.is_relative_to(destination)
            or destination.is_relative_to(incoming)):
        raise ValueError("Private source and case directories must be separate")

    all_entries = sorted(incoming.iterdir(), key=lambda item: (item.name.casefold(), item.name))
    eligible = [item for item in all_entries if item.name.lower().endswith(".txt")]
    if len(eligible) > max_files:
        raise ValueError("Too many request files; no cases have been imported")

    counters = dict(created=0, reused=0, recovered=0, duplicates=0, blocked=0)
    records: list[dict[str, str]] = []
    observed: set[str] = set()
    for entry in eligible:
        # The item tag is a one-way digest of its local name. Never print a
        # buyer's filename, email address, path or draft text in a result.
        tag = hashlib.sha256(entry.name.encode("utf-8")).hexdigest()[:12]
        try:
            raw = _valid_request_entry(entry)
            source_sha = hashlib.sha256(raw).hexdigest()
            if source_sha in observed:
                counters["duplicates"] += 1
                records.append({"item_tag": tag, "state": "DUPLICATE"})
                continue

            case = destination / f"request-{source_sha}.case.json"
            receipt = destination / f"request-{source_sha}.receipt.json"
            # A destination symlink, including a dangling symlink, must
            # never point an operator's case outside the chosen private root.
            if case.is_symlink() or receipt.is_symlink():
                raise ValueError("Private output artifact cannot be a link")
            was_case, was_receipt = case.exists(), receipt.exists()

            imported = import_request(
                str(entry), str(case), str(receipt),
                expected_request_sha256=source_sha,
            )
            if imported["request_sha256"] != source_sha:
                raise ValueError("Import source fingerprint changed")
            state = ("REUSED" if was_case and was_receipt
                     else "RECOVERED" if was_case or was_receipt
                     else "CREATED")
            counters[state.lower()] += 1
            observed.add(source_sha)
            records.append({"item_tag": tag, "state": state})
        except (OSError, ValueError, UnicodeError, TimeoutError) as exc:
            counters["blocked"] += 1
            records.append({
                "item_tag": tag, "state": "BLOCKED",
                "error_type": type(exc).__name__,
            })

    return {
        "schema": "capturebrief-private-batch-intake-v1",
        "status": ("BATCH_NO_REQUESTS" if not eligible
                   else "BATCH_PARTIAL_REVIEW_REQUIRED" if counters["blocked"]
                   else "BATCH_ACCEPTED_REVIEW_REQUIRED"),
        "processed_txt": len(eligible),
        "ignored_non_txt": len(all_entries) - len(eligible),
        **counters,
        "items": records,
        "payment_verified": False,
        "message_delivery_verified": False,
        "external_send_authorized": False,
        "customer_release_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, help="Existing private folder of saved .txt drafts")
    parser.add_argument("--output-dir", required=True, help="Separate existing private folder for cases")
    parser.add_argument("--max-files", type=int, default=MAX_FILES)
    args = parser.parse_args(argv)
    try:
        result = batch_import(args.input_dir, args.output_dir, max_files=args.max_files)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            "status": "BATCH_IMPORT_BLOCKED",
            "error_type": type(exc).__name__,
            "customer_release_authorized": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 3 if result["blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
