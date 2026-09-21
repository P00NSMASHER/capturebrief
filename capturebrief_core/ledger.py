from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .model import canonical_json, sha256_hex

LEDGER_VERSION = "capturebrief-evidence-ledger-v1"
GENESIS = "0" * 64
DEFAULT_LOCK_TIMEOUT_SECONDS = 5.0
_LOCK_POLL_SECONDS = 0.05


class LedgerLockedError(TimeoutError):
    pass


def _record_hash(record: dict[str, Any]) -> str:
    body = {k: v for k, v in record.items() if k != "record_sha256"}
    return sha256_hex(canonical_json(body))


def _lock_path(path: Path) -> Path:
    return path.with_name(path.name + ".lock")


@contextmanager
def _ledger_lock(path: Path, *, timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS) -> Iterator[None]:
    if timeout_seconds < 0:
        raise ValueError("lock timeout must be non-negative")
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = _lock_path(path)
    deadline = time.monotonic() + timeout_seconds

    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise LedgerLockedError(
                    f"ledger is locked; verify no writer is active before removing: {lock}"
                ) from None
            time.sleep(_LOCK_POLL_SECONDS)
            continue
        try:
            payload = (
                f"pid={os.getpid()} created_at={datetime.now(timezone.utc).isoformat()}\n"
            ).encode("utf-8")
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        break

    try:
        yield
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _verify_unlocked(path: Path) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    previous = GENESIS
    count = 0
    if not path.exists():
        return {"valid": True, "records": 0, "head_sha256": GENESIS, "errors": []}

    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        count += 1
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            errors.append({"line": idx, "code": "INVALID_JSON"})
            continue

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

    return {
        "valid": not errors,
        "records": count,
        "head_sha256": previous if count else GENESIS,
        "errors": errors,
    }


def _append_bytes(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        view = memoryview(data)
        written = 0
        while written < len(view):
            n = os.write(fd, view[written:])
            if n <= 0:
                raise OSError("ledger append made no forward progress")
            written += n
        os.fsync(fd)
    finally:
        os.close(fd)


def append_record(
    path: str | Path,
    *,
    record_type: str,
    payload: Any,
    recorded_at: str | None = None,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Append one verified hash-chained JSONL record.

    Writers are serialized by a sidecar lock. The existing chain is re-verified
    while that lock is held, closing the prior verify-then-append race. A stuck
    lock times out and requires operator review rather than being guessed stale.
    """
    p = Path(path)
    with _ledger_lock(p, timeout_seconds=lock_timeout_seconds):
        status = _verify_unlocked(p)
        if not status["valid"]:
            raise ValueError("refusing to append to invalid evidence ledger")

        record = {
            "ledger_version": LEDGER_VERSION,
            "record_type": str(record_type),
            "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
            "previous_record_sha256": status["head_sha256"],
            "payload_sha256": sha256_hex(canonical_json(payload)),
            "payload": payload,
        }
        record["record_sha256"] = _record_hash(record)
        raw = (
            json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        _append_bytes(p, raw)
        return record


def verify_ledger(
    path: str | Path,
    *,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    p = Path(path)
    with _ledger_lock(p, timeout_seconds=lock_timeout_seconds):
        return _verify_unlocked(p)
