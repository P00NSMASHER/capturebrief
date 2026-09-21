from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model import canonical_json, sha256_hex

LEDGER_VERSION = "capturebrief-evidence-ledger-v1"
GENESIS = "0" * 64


def _record_hash(record: dict[str, Any]) -> str:
    body = {k: v for k, v in record.items() if k != "record_sha256"}
    return sha256_hex(canonical_json(body))


def append_record(path: str | Path, *, record_type: str, payload: Any, recorded_at: str | None = None) -> dict[str, Any]:
    """Append a hash-chained JSONL evidence record.

    This is deliberately append-only. It makes accidental or silent mutation of the 14-day
    evidence history detectable without requiring a database or external service.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    previous = GENESIS
    if p.exists() and p.stat().st_size:
        lines = [line for line in p.read_text().splitlines() if line.strip()]
        if lines:
            last = json.loads(lines[-1])
            previous = str(last.get("record_sha256", ""))
    record = {
        "ledger_version": LEDGER_VERSION,
        "record_type": str(record_type),
        "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
        "previous_record_sha256": previous,
        "payload_sha256": sha256_hex(canonical_json(payload)),
        "payload": payload,
    }
    record["record_sha256"] = _record_hash(record)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
    return record


def verify_ledger(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    errors: list[dict[str, Any]] = []
    previous = GENESIS; count = 0
    if not p.exists():
        return {"valid": True, "records": 0, "head_sha256": GENESIS, "errors": []}
    for idx, line in enumerate(p.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        count += 1
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            errors.append({"line": idx, "code": "INVALID_JSON"}); continue
        if record.get("ledger_version") != LEDGER_VERSION:
            errors.append({"line": idx, "code": "LEDGER_VERSION_MISMATCH"})
        if record.get("previous_record_sha256") != previous:
            errors.append({"line": idx, "code": "CHAIN_BREAK"})
        if record.get("payload_sha256") != sha256_hex(canonical_json(record.get("payload"))):
            errors.append({"line": idx, "code": "PAYLOAD_HASH_MISMATCH"})
        expected = _record_hash(record)
        if record.get("record_sha256") != expected:
            errors.append({"line": idx, "code": "RECORD_HASH_MISMATCH"})
        previous = str(record.get("record_sha256", ""))
    return {"valid": not errors, "records": count, "head_sha256": previous if count else GENESIS, "errors": errors}
