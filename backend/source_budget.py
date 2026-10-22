"""Persistent, account-scoped UTC-day request budgets (stdlib only).

Configure the intended account's verified request limit before enabling calls.
This is an operator-enforced request budget, NOT a claim about SAM's quota.
All processes using an account must share this database. Other applications or
hosts outside this database are not coordinated; allocate headroom for them.

Before EACH physical HTTP attempt (including retries), generate a fresh opaque
attempt_id and call reserve(). Send the request ONLY if should_attempt is true.
A replay has should_attempt=False: it must not send a second network request.
Reservations are never refunded, even on timeout, failure, or process crash.
This conservatively overcounts a crash between reservation and sending.

Store only opaque account/attempt identifiers, timestamps, and fixed statuses.
Never pass API keys, query URLs, response bodies, or exception text to this API.
Keep the database server-side. This is not a payment or entitlement ledger.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
import re
import sqlite3


class BudgetNotConfigured(ValueError):
    """The account has no explicitly configured request budget."""


class BudgetExceeded(RuntimeError):
    """No request can be reserved under the current UTC-day budget."""


class AttemptConflict(ValueError):
    """An attempt identifier was reused for a different account or result."""


@dataclass(frozen=True)
class Reservation:
    account_id: str
    attempt_id: str
    day: str
    should_attempt: bool
    status: str


@dataclass(frozen=True)
class Summary:
    account_id: str
    day: str
    daily_limit: int
    used: int
    remaining: int
    pending: int


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_TERMINAL_STATUSES = frozenset(
    {"success", "timeout", "http_error", "network_error", "invalid_response"}
)


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("Use an opaque identifier of 1-128 safe characters")
    return value


def _instant(value: datetime | None) -> datetime:
    value = datetime.now(timezone.utc) if value is None else value
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("A timezone-aware datetime is required")
    return value.astimezone(timezone.utc)


def _day(value: str | date | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).date().isoformat()
    if isinstance(value, datetime):
        raise ValueError("day must be a date or YYYY-MM-DD string")
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("day must be a date or YYYY-MM-DD string")
    return date.fromisoformat(value).isoformat()


class Ledger:
    """One file-backed SQLite ledger shared by all local request workers.

    A new connection is used per operation; BEGIN IMMEDIATE serializes budget
    checks and insertion across processes. SQLITE_BUSY propagates without a
    reservation, and callers must fail closed rather than send an HTTP request.
    at_utc is a trusted server/test clock, never customer-controlled input.
    """

    def __init__(self, db_path: str | Path):
        if str(db_path) == ":memory:" or str(db_path).startswith("file:"):
            raise ValueError("A persistent database file path is required")
        self.db_path = str(db_path)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS source_budgets (
                    account_id TEXT PRIMARY KEY,
                    daily_limit INTEGER NOT NULL CHECK(daily_limit >= 0)
                );
                CREATE TABLE IF NOT EXISTS source_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES source_budgets(account_id),
                    utc_day TEXT NOT NULL,
                    reserved_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'reserved'
                        CHECK(status IN ('reserved', 'success', 'timeout',
                            'http_error', 'network_error', 'invalid_response')),
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS source_attempts_account_day
                    ON source_attempts(account_id, utc_day);
                """
            )

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _transaction(self):
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def configure_budget(self, account_id: str, daily_limit: int) -> None:
        """Explicit operator configuration; zero disables new reservations.

        Changing a limit never clears usage. Lowering below current usage leaves
        remaining=0 and blocks further attempts until capacity is available.
        """
        account_id = _identifier(account_id)
        if type(daily_limit) is not int or not 0 <= daily_limit <= 2**63 - 1:
            raise ValueError("daily_limit must be a nonnegative SQLite integer")
        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO source_budgets(account_id, daily_limit) VALUES (?, ?) "
                "ON CONFLICT(account_id) DO UPDATE SET daily_limit=excluded.daily_limit",
                (account_id, daily_limit),
            )

    def reserve(
        self, account_id: str, attempt_id: str, at_utc: datetime | None = None
    ) -> Reservation:
        """Count an attempt atomically before I/O; replays never authorize I/O."""
        account_id, attempt_id = _identifier(account_id), _identifier(attempt_id)
        instant = _instant(at_utc)
        day = instant.date().isoformat()
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT account_id, utc_day, status FROM source_attempts WHERE attempt_id=?",
                (attempt_id,),
            ).fetchone()
            if existing is not None:
                if existing["account_id"] != account_id:
                    raise AttemptConflict("Attempt identifier belongs to another account")
                return Reservation(account_id, attempt_id, existing["utc_day"], False, existing["status"])
            budget = connection.execute(
                "SELECT daily_limit FROM source_budgets WHERE account_id=?", (account_id,)
            ).fetchone()
            if budget is None:
                raise BudgetNotConfigured("Account request budget is not configured")
            used = connection.execute(
                "SELECT COUNT(*) FROM source_attempts WHERE account_id=? AND utc_day=?",
                (account_id, day),
            ).fetchone()[0]
            if used >= budget["daily_limit"]:
                raise BudgetExceeded("UTC-day request budget exhausted")
            connection.execute(
                "INSERT INTO source_attempts(attempt_id, account_id, utc_day, reserved_at) "
                "VALUES (?, ?, ?, ?)",
                (attempt_id, account_id, day, instant.isoformat()),
            )
            return Reservation(account_id, attempt_id, day, True, "reserved")

    def complete(self, attempt_id: str, status: str) -> bool:
        """Record a fixed terminal result. Return False for an identical replay.

        Completion does not alter usage. Conflicting final results are rejected.
        A crashed attempt may remain reserved forever; it still counts.
        """
        attempt_id = _identifier(attempt_id)
        if not isinstance(status, str) or status not in _TERMINAL_STATUSES:
            raise ValueError("Unsupported completion status")
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT status FROM source_attempts WHERE attempt_id=?", (attempt_id,)
            ).fetchone()
            if existing is None:
                raise KeyError("Unknown attempt identifier")
            if existing["status"] == status:
                return False
            if existing["status"] != "reserved":
                raise AttemptConflict("Attempt already has a different terminal result")
            connection.execute(
                "UPDATE source_attempts SET status=?, completed_at=? WHERE attempt_id=?",
                (status, datetime.now(timezone.utc).isoformat(), attempt_id),
            )
            return True

    def summary(self, account_id: str, day: str | date | None = None) -> Summary:
        """Return counted usage, pending attempts, and CURRENT configured limit.

        Historical usage is immutable; this reports the current limit rather
        than claiming to retain a history of operator budget changes.
        """
        account_id, day = _identifier(account_id), _day(day)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT b.daily_limit, COUNT(a.attempt_id) AS used, "
                "COALESCE(SUM(CASE WHEN a.status='reserved' THEN 1 ELSE 0 END), 0) AS pending "
                "FROM source_budgets b LEFT JOIN source_attempts a "
                "ON a.account_id=b.account_id AND a.utc_day=? "
                "WHERE b.account_id=? GROUP BY b.account_id, b.daily_limit",
                (day, account_id),
            ).fetchone()
            if row is None:
                raise BudgetNotConfigured("Account request budget is not configured")
            return Summary(account_id, day, row["daily_limit"], row["used"],
                           max(0, row["daily_limit"] - row["used"]), row["pending"])
