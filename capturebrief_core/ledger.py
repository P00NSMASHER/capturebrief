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


def _verify_unlocked(
    path: Path, *, captured_bytes: bytes | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    previous = GENESIS
    count = 0
    if captured_bytes is None:
        if not path.exists():
            return {"valid": True, "records": 0, "head_sha256": GENESIS, "errors": []}
        captured_bytes = path.read_bytes()

    # The producer uses LF framing. splitlines() incorrectly treats U+0085,
    # U+2028 and U+2029 *inside valid JSON strings* as record boundaries.
    text = captured_bytes.decode("utf-8", "strict")
    for idx, line in enumerate(text.split("\n"), start=1):
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

def read_verified_outcome_snapshot(
    path: str | Path,
    *,
    max_bytes: int = 16 * 1024 * 1024,
    lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Capture one verified byte snapshot for an approved private observer.

    The owner/runtime MUST independently authorize the exact source location
    and protect its transport. This function neither locates/authenticates a
    commercial ledger, publishes customer records, nor validates Stripe or
    business identities. The lock sidecar is temporary; source bytes are not
    modified. A missing file is NOT treated as an empty observed ledger.
    """
    if type(max_bytes) is not int or not 0 < max_bytes <= 16 * 1024 * 1024:
        raise ValueError("invalid bounded outcome snapshot limit")
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise FileNotFoundError("approved outcome ledger is missing or not a regular file")
    try:
        with _ledger_lock(p, timeout_seconds=lock_timeout_seconds):
            if p.is_symlink() or not p.is_file():
                raise ValueError("approved outcome ledger changed during snapshot")
            with p.open("rb") as stream:
                captured = stream.read(max_bytes + 1)
            if len(captured) > max_bytes:
                raise ValueError("outcome snapshot exceeds bounded allowance")
            # Do not pass an incomplete append or an ignored blank frame into
            # an otherwise valid-looking downstream snapshot.
            if captured and (not captured.endswith(b"\n") or
                             any(not frame for frame in captured[:-1].split(b"\n"))):
                raise ValueError("outcome snapshot is not complete LF-framed JSONL")
            try:
                status = _verify_unlocked(p, captured_bytes=captured)
            except (ValueError, TypeError, AttributeError, UnicodeError, KeyError):
                raise ValueError("outcome snapshot chain validation failed") from None
            if not status["valid"]:
                raise ValueError("outcome snapshot chain validation failed")
            # Observed-at means time captured, NOT time last customer worked,
            # settled, paid or authorized. The result is private raw bytes.
            return {
                "present": True,
                "content": captured,
                "snapshot_sha256": sha256_hex(captured),
                "observed_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            }
    except LedgerLockedError:
        raise ValueError("approved outcome ledger is locked") from None
