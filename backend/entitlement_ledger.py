"""Persistent, idempotent CaptureBrief payment + entitlement ledger.

This is a compact source-controlled reimplementation of the Sept. 15 release
contract. It stores opaque identifiers, fixed event/product names, amounts,
hashes and state transitions; never raw provider payloads or secrets.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
from typing import Mapping

class LedgerConflict(ValueError): pass
class InsufficientEntitlement(RuntimeError): pass
class OrderNotFound(KeyError): pass

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_CURRENCY = re.compile(r"[A-Z]{3}\Z")

PRODUCTS: Mapping[str, tuple[int, Mapping[str,int]]] = {
    "pilot_149": (14_900, {"reviewed_pursuit":1, "monitoring_window_14d":1}),
}
_EVENTS = {"payment_succeeded", "payment_failed", "payment_refunded"}

def _id(v:str, name="identifier") -> str:
    if not isinstance(v,str) or not _ID.fullmatch(v):
        raise ValueError(f"invalid {name}")
    return v

def _hash(v:str) -> str:
    if not isinstance(v,str) or not _HASH.fullmatch(v):
        raise ValueError("invalid payload hash")
    return v

def _now(v:datetime|None)->str:
    v=datetime.now(timezone.utc) if v is None else v
    if not isinstance(v,datetime) or v.tzinfo is None or v.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return v.astimezone(timezone.utc).isoformat()

@dataclass(frozen=True)
class Order:
    order_id:str
    organization_id:str
    product:str
    amount_minor:int
    currency:str
    provider_payment_id:str|None
    status:str

@dataclass(frozen=True)
class PaymentResult:
    event_id:str
    order_id:str
    outcome:str
    order_status:str
    granted:tuple[tuple[str,int],...]=()
    revoked:tuple[tuple[str,int],...]=()

@dataclass(frozen=True)
class CreditReservation:
    organization_id:str
    reservation_key:str
    reference_id:str
    credit_kind:str
    order_id:str
    state:str
    should_execute:bool

@dataclass(frozen=True)
class CreditCompletion:
    reservation_key:str
    state:str
    changed:bool

class Ledger:
    def __init__(self, db_path:str|Path):
        if str(db_path)==":memory:" or str(db_path).startswith("file:"):
            raise ValueError("persistent file required")
        self.db_path=str(db_path)
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS orders(
                  order_id TEXT PRIMARY KEY,
                  organization_id TEXT NOT NULL,
                  product TEXT NOT NULL,
                  amount_minor INTEGER NOT NULL CHECK(amount_minor>0),
                  currency TEXT NOT NULL,
                  provider_payment_id TEXT UNIQUE,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS orders_org_status
                  ON orders(organization_id,status,created_at,order_id);

                CREATE TABLE IF NOT EXISTS payment_events(
                  event_id TEXT PRIMARY KEY,
                  provider_payment_id TEXT NOT NULL,
                  event_type TEXT NOT NULL,
                  order_id TEXT NOT NULL REFERENCES orders(order_id),
                  payload_sha256 TEXT NOT NULL,
                  received_at TEXT NOT NULL,
                  outcome TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS entitlement_ledger(
                  entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  organization_id TEXT NOT NULL,
                  credit_kind TEXT NOT NULL,
                  delta INTEGER NOT NULL,
                  operation TEXT NOT NULL,
                  order_id TEXT NOT NULL REFERENCES orders(order_id),
                  reference_id TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL UNIQUE,
                  created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS entitlement_org_kind
                  ON entitlement_ledger(organization_id,credit_kind,created_at,entry_id);
                CREATE INDEX IF NOT EXISTS entitlement_order_kind
                  ON entitlement_ledger(order_id,credit_kind,created_at,entry_id);

                CREATE TABLE IF NOT EXISTS credit_reservations(
                  reservation_key TEXT PRIMARY KEY,
                  organization_id TEXT NOT NULL,
                  reference_id TEXT NOT NULL,
                  credit_kind TEXT NOT NULL,
                  order_id TEXT NOT NULL REFERENCES orders(order_id),
                  state TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                """
            )

    @contextmanager
    def _conn(self):
        c=sqlite3.connect(self.db_path,timeout=30,isolation_level=None)
        c.row_factory=sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c
        finally:
            c.close()

    @contextmanager
    def _tx(self):
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                yield c
                c.commit()
            except BaseException:
                c.rollback()
                raise

    def _order(self,row):
        return Order(
            row["order_id"],row["organization_id"],row["product"],
            row["amount_minor"],row["currency"],row["provider_payment_id"],
            row["status"]
        )

    def create_order(self, order_id, organization_id, product, amount_minor, *,
                     currency="USD", provider_payment_id=None, now=None):
        order_id=_id(order_id,"order_id")
        organization_id=_id(organization_id,"organization_id")
        product=_id(product,"product")
        if product not in PRODUCTS:
            raise ValueError("unknown product")
        expected,_=PRODUCTS[product]
        if type(amount_minor) is not int or amount_minor!=expected:
            raise ValueError("server-controlled price mismatch")
        if not isinstance(currency,str) or not _CURRENCY.fullmatch(currency):
            raise ValueError("invalid currency")
        if provider_payment_id is not None:
            provider_payment_id=_id(provider_payment_id,"provider_payment_id")
        instant=_now(now)
        with self._tx() as c:
            row=c.execute("SELECT * FROM orders WHERE order_id=?",(order_id,)).fetchone()
            if row:
                actual=(row["organization_id"],row["product"],row["amount_minor"],row["currency"],row["provider_payment_id"])
                wanted=(organization_id,product,amount_minor,currency,provider_payment_id)
                if actual!=wanted:
                    raise LedgerConflict("order replay conflict")
                return self._order(row)
            if provider_payment_id is not None:
                other=c.execute(
                    "SELECT order_id FROM orders WHERE provider_payment_id=?",
                    (provider_payment_id,)
                ).fetchone()
                if other:
                    raise LedgerConflict("provider payment already used")
            c.execute(
                "INSERT INTO orders VALUES(?,?,?,?,?,?,'pending',?,?)",
                (order_id,organization_id,product,amount_minor,currency,
                 provider_payment_id,instant,instant)
            )
            return self._order(
                c.execute("SELECT * FROM orders WHERE order_id=?",(order_id,)).fetchone()
            )

    def get_order(self, order_id, organization_id):
        order_id=_id(order_id,"order_id")
        organization_id=_id(organization_id,"organization_id")
        with self._conn() as c:
            row=c.execute(
                "SELECT * FROM orders WHERE order_id=? AND organization_id=?",
                (order_id,organization_id)
            ).fetchone()
            if not row:
                raise OrderNotFound(order_id)
            return self._order(row)

    def _insert_ledger(self,c,*,organization_id,credit_kind,delta,operation,
                       order_id,reference_id,idempotency_key,created_at):
        try:
            c.execute(
                "INSERT INTO entitlement_ledger("
                "organization_id,credit_kind,delta,operation,order_id,"
                "reference_id,idempotency_key,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (organization_id,credit_kind,delta,operation,order_id,
                 reference_id,idempotency_key,created_at)
            )
        except sqlite3.IntegrityError as e:
            raise LedgerConflict("entitlement idempotency conflict") from e

    def _order_available(self,c,order_id,kind):
        row=c.execute(
            "SELECT COALESCE(SUM(delta),0) AS n FROM entitlement_ledger "
            "WHERE order_id=? AND credit_kind=?",(order_id,kind)
        ).fetchone()
        return max(0,int(row["n"]))

    def apply_payment_event(self,event_id,provider_payment_id,event_type,order_id,
                            payload_sha256,now=None):
        event_id=_id(event_id,"event_id")
        provider_payment_id=_id(provider_payment_id,"provider_payment_id")
        order_id=_id(order_id,"order_id")
        payload_sha256=_hash(payload_sha256)
        if event_type not in _EVENTS:
            raise ValueError("unsupported event type")
        instant=_now(now)
        with self._tx() as c:
            existing=c.execute(
                "SELECT * FROM payment_events WHERE event_id=?",(event_id,)
            ).fetchone()
            if existing:
                if (
                    existing["provider_payment_id"],existing["event_type"],
                    existing["order_id"],existing["payload_sha256"]
                ) != (provider_payment_id,event_type,order_id,payload_sha256):
                    raise LedgerConflict("event replay conflict")
                order=c.execute(
                    "SELECT status FROM orders WHERE order_id=?",(order_id,)
                ).fetchone()
                return PaymentResult(event_id,order_id,"duplicate",order["status"])

            order=c.execute("SELECT * FROM orders WHERE order_id=?",(order_id,)).fetchone()
            if not order:
                raise OrderNotFound(order_id)
            if order["provider_payment_id"] != provider_payment_id:
                raise LedgerConflict("provider payment mismatch")

            status=order["status"]
            outcome="applied"
            granted=[]
            revoked=[]

            if event_type=="payment_succeeded":
                if status=="pending":
                    status="paid"
                    for kind,count in PRODUCTS[order["product"]][1].items():
                        self._insert_ledger(
                            c,organization_id=order["organization_id"],
                            credit_kind=kind,delta=count,operation="grant",
                            order_id=order_id,reference_id=event_id,
                            idempotency_key=f"grant:{event_id}:{kind}",
                            created_at=instant
                        )
                        granted.append((kind,count))
                else:
                    outcome="ignored"
            elif event_type=="payment_failed":
                if status=="pending":
                    status="failed"
                else:
                    outcome="ignored"
            else:
                if status=="pending":
                    status="refunded"
                elif status=="paid":
                    status="refunded"
                    for kind in PRODUCTS[order["product"]][1]:
                        avail=self._order_available(c,order_id,kind)
                        if avail>0:
                            self._insert_ledger(
                                c,organization_id=order["organization_id"],
                                credit_kind=kind,delta=-avail,operation="revoke",
                                order_id=order_id,reference_id=event_id,
                                idempotency_key=f"revoke:{event_id}:{kind}",
                                created_at=instant
                            )
                            revoked.append((kind,avail))
                else:
                    outcome="ignored"

            c.execute(
                "UPDATE orders SET status=?,updated_at=? WHERE order_id=?",
                (status,instant,order_id)
            )
            c.execute(
                "INSERT INTO payment_events("
                "event_id,provider_payment_id,event_type,order_id,payload_sha256,"
                "received_at,outcome) VALUES(?,?,?,?,?,?,?)",
                (event_id,provider_payment_id,event_type,order_id,
                 payload_sha256,instant,outcome)
            )
            return PaymentResult(
                event_id,order_id,outcome,status,tuple(granted),tuple(revoked)
            )

    def reserve_credit(self,organization_id,credit_kind,reservation_key,
                       reference_id,now=None):
        organization_id=_id(organization_id,"organization_id")
        credit_kind=_id(credit_kind,"credit_kind")
        reservation_key=_id(reservation_key,"reservation_key")
        reference_id=_id(reference_id,"reference_id")
        instant=_now(now)
        with self._tx() as c:
            row=c.execute(
                "SELECT * FROM credit_reservations WHERE reservation_key=?",
                (reservation_key,)
            ).fetchone()
            if row:
                if (
                    row["organization_id"],row["credit_kind"],row["reference_id"]
                ) != (organization_id,credit_kind,reference_id):
                    raise LedgerConflict("reservation replay conflict")
                return CreditReservation(
                    organization_id,reservation_key,reference_id,credit_kind,
                    row["order_id"],row["state"],False
                )

            orders=c.execute(
                "SELECT order_id FROM orders WHERE organization_id=? "
                "AND status='paid' ORDER BY created_at,order_id",
                (organization_id,)
            ).fetchall()
            chosen=None
            for item in orders:
                if self._order_available(c,item["order_id"],credit_kind)>0:
                    chosen=item["order_id"]
                    break
            if chosen is None:
                raise InsufficientEntitlement("no available credit")

            self._insert_ledger(
                c,organization_id=organization_id,credit_kind=credit_kind,
                delta=-1,operation="reserve",order_id=chosen,
                reference_id=reference_id,
                idempotency_key=f"reserve:{reservation_key}",created_at=instant
            )
            c.execute(
                "INSERT INTO credit_reservations VALUES(?,?,?,?,?,'reserved',?,?)",
                (reservation_key,organization_id,reference_id,credit_kind,
                 chosen,instant,instant)
            )
            return CreditReservation(
                organization_id,reservation_key,reference_id,credit_kind,
                chosen,"reserved",True
            )

    def complete_credit(self,reservation_key,outcome,now=None):
        reservation_key=_id(reservation_key,"reservation_key")
        if outcome not in {"succeeded","failed"}:
            raise ValueError("outcome must be succeeded or failed")
        instant=_now(now)
        with self._tx() as c:
            row=c.execute(
                "SELECT r.*,o.status AS order_status FROM credit_reservations r "
                "JOIN orders o ON o.order_id=r.order_id WHERE reservation_key=?",
                (reservation_key,)
            ).fetchone()
            if not row:
                raise KeyError("unknown reservation")
            state=row["state"]
            if state!="reserved":
                expected=(
                    "consumed" if outcome=="succeeded"
                    else ("forfeited" if row["order_status"]=="refunded" else "restored")
                )
                if state!=expected:
                    raise LedgerConflict("reservation already completed differently")
                return CreditCompletion(reservation_key,state,False)

            if outcome=="succeeded":
                self._insert_ledger(
                    c,organization_id=row["organization_id"],
                    credit_kind=row["credit_kind"],delta=0,operation="consume",
                    order_id=row["order_id"],reference_id=row["reference_id"],
                    idempotency_key=f"consume:{reservation_key}",
                    created_at=instant
                )
                state="consumed"
            elif row["order_status"]=="refunded":
                state="forfeited"
            else:
                self._insert_ledger(
                    c,organization_id=row["organization_id"],
                    credit_kind=row["credit_kind"],delta=1,operation="restore",
                    order_id=row["order_id"],reference_id=row["reference_id"],
                    idempotency_key=f"restore:{reservation_key}",
                    created_at=instant
                )
                state="restored"

            c.execute(
                "UPDATE credit_reservations SET state=?,updated_at=? "
                "WHERE reservation_key=?",(state,instant,reservation_key)
            )
            return CreditCompletion(reservation_key,state,True)

    def balance(self,organization_id,credit_kind):
        organization_id=_id(organization_id,"organization_id")
        credit_kind=_id(credit_kind,"credit_kind")
        with self._conn() as c:
            row=c.execute(
                "SELECT COALESCE(SUM(delta),0) AS n FROM entitlement_ledger "
                "WHERE organization_id=? AND credit_kind=?",
                (organization_id,credit_kind)
            ).fetchone()
            return max(0,int(row["n"]))

    def balances(self,organization_id):
        organization_id=_id(organization_id,"organization_id")
        with self._conn() as c:
            rows=c.execute(
                "SELECT credit_kind,SUM(delta) AS n FROM entitlement_ledger "
                "WHERE organization_id=? GROUP BY credit_kind "
                "HAVING SUM(delta)>0 ORDER BY credit_kind",
                (organization_id,)
            ).fetchall()
            return {r["credit_kind"]:int(r["n"]) for r in rows}
