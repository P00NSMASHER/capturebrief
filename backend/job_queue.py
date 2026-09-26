"""Durable, tenant-scoped CaptureBrief job queue with leases and review gate."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sqlite3

class QueueConflict(ValueError): pass
class LeaseLost(RuntimeError): pass
class JobNotFound(KeyError): pass

_ID=re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}\Z")
_ERROR=re.compile(r"[a-z][a-z0-9_]{0,63}\Z")

def _id(v,name='identifier'):
    if not isinstance(v,str) or not _ID.fullmatch(v): raise ValueError(f"invalid {name}")
    return v

def _dt(v):
    v=datetime.now(timezone.utc) if v is None else v
    if not isinstance(v,datetime) or v.tzinfo is None or v.utcoffset() is None: raise ValueError("timezone-aware datetime required")
    return v.astimezone(timezone.utc)

def _iso(v): return _dt(v).isoformat()

@dataclass(frozen=True)
class Job:
    job_id:str; idempotency_key:str; organization_id:str; source_version:str; profile_version:str; product:str; analysis_version:str
    budget_cents:int; max_attempts:int; attempt_count:int; status:str; worker_id:str|None; lease_expires_at:str|None
    next_attempt_at:str; last_error_code:str|None; created_at:str; updated_at:str; delivered_at:str|None

@dataclass(frozen=True)
class EnqueueResult:
    job:Job; created:bool

class Queue:
    def __init__(self,db_path:str|Path,max_budget_cents:int=800):
        if str(db_path)==':memory:' or str(db_path).startswith('file:'): raise ValueError('persistent file required')
        if type(max_budget_cents) is not int or max_budget_cents<=0: raise ValueError('max_budget_cents must be positive int')
        self.db_path=str(db_path); self.max_budget_cents=max_budget_cents
        with self._conn() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS jobs(
              job_id TEXT PRIMARY KEY,
              idempotency_key TEXT NOT NULL UNIQUE,
              organization_id TEXT NOT NULL,
              source_version TEXT NOT NULL,
              profile_version TEXT NOT NULL,
              product TEXT NOT NULL,
              analysis_version TEXT NOT NULL,
              budget_cents INTEGER NOT NULL,
              max_attempts INTEGER NOT NULL,
              attempt_count INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL,
              worker_id TEXT,
              lease_expires_at TEXT,
              next_attempt_at TEXT NOT NULL,
              last_error_code TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              delivered_at TEXT
            );
            CREATE INDEX IF NOT EXISTS jobs_claim ON jobs(status,next_attempt_at,created_at,job_id);
            CREATE TABLE IF NOT EXISTS job_events(
              event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              job_id TEXT NOT NULL REFERENCES jobs(job_id),
              organization_id TEXT NOT NULL,
              from_status TEXT,
              to_status TEXT NOT NULL,
              reason_code TEXT NOT NULL,
              actor_id TEXT,
              created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS job_events_job ON job_events(job_id,event_id);
            ''')
    @contextmanager
    def _conn(self):
        c=sqlite3.connect(self.db_path,timeout=30,isolation_level=None); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON')
        try: yield c
        finally: c.close()
    @contextmanager
    def _tx(self):
        with self._conn() as c:
            c.execute('BEGIN IMMEDIATE')
            try: yield c; c.commit()
            except BaseException: c.rollback(); raise
    def _job(self,row):
        return Job(**{k:row[k] for k in Job.__dataclass_fields__})
    def _event(self,c,job,from_status,to_status,reason,actor,instant):
        c.execute('INSERT INTO job_events(job_id,organization_id,from_status,to_status,reason_code,actor_id,created_at) VALUES(?,?,?,?,?,?,?)',
                  (job['job_id'],job['organization_id'],from_status,to_status,reason,actor,instant))
    def enqueue(self,*,job_id,idempotency_key,organization_id,source_version,profile_version,product,analysis_version,budget_cents,max_attempts=3,now=None):
        vals=[(job_id,'job_id'),(idempotency_key,'idempotency_key'),(organization_id,'organization_id'),(source_version,'source_version'),(profile_version,'profile_version'),(product,'product'),(analysis_version,'analysis_version')]
        for v,n in vals: _id(v,n)
        if type(budget_cents) is not int or not 0<budget_cents<=self.max_budget_cents: raise ValueError('budget exceeds queue cap')
        if type(max_attempts) is not int or not 1<=max_attempts<=8: raise ValueError('max_attempts out of range')
        instant=_iso(now)
        with self._tx() as c:
            row=c.execute('SELECT * FROM jobs WHERE idempotency_key=?',(idempotency_key,)).fetchone()
            if row:
                expected=(job_id,organization_id,source_version,profile_version,product,analysis_version,budget_cents,max_attempts)
                actual=(row['job_id'],row['organization_id'],row['source_version'],row['profile_version'],row['product'],row['analysis_version'],row['budget_cents'],row['max_attempts'])
                if actual!=expected: raise QueueConflict('idempotency replay conflict')
                return EnqueueResult(self._job(row),False)
            if c.execute('SELECT 1 FROM jobs WHERE job_id=?',(job_id,)).fetchone(): raise QueueConflict('job_id already exists')
            c.execute('''INSERT INTO jobs(job_id,idempotency_key,organization_id,source_version,profile_version,product,analysis_version,budget_cents,max_attempts,status,next_attempt_at,created_at,updated_at)
                         VALUES(?,?,?,?,?,?,?,?,?,'queued',?,?,?)''',(job_id,idempotency_key,organization_id,source_version,profile_version,product,analysis_version,budget_cents,max_attempts,instant,instant,instant))
            row=c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone(); self._event(c,row,None,'queued','enqueued',None,instant)
            return EnqueueResult(self._job(row),True)
    def claim_next(self,worker_id,*,now=None,lease_seconds=300):
        worker_id=_id(worker_id,'worker_id'); instant=_dt(now)
        if type(lease_seconds) is not int or not 1<=lease_seconds<=3600: raise ValueError('invalid lease_seconds')
        with self._tx() as c:
            row=c.execute("SELECT * FROM jobs WHERE status IN ('queued','ready') AND next_attempt_at<=? ORDER BY created_at,job_id LIMIT 1",(instant.isoformat(),)).fetchone()
            if not row: return None
            new_status='fetching' if row['status']=='queued' else 'delivering'
            attempts=row['attempt_count']+1
            expiry=(instant+timedelta(seconds=lease_seconds)).isoformat()
            c.execute('UPDATE jobs SET status=?,worker_id=?,lease_expires_at=?,attempt_count=?,updated_at=? WHERE job_id=?',(new_status,worker_id,expiry,attempts,instant.isoformat(),row['job_id']))
            new=c.execute('SELECT * FROM jobs WHERE job_id=?',(row['job_id'],)).fetchone(); self._event(c,new,row['status'],new_status,'claimed',worker_id,instant.isoformat())
            return self._job(new)
    def _leased(self,c,job_id,worker_id,now):
        row=c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone()
        if not row: raise JobNotFound(job_id)
        if row['worker_id']!=worker_id or not row['lease_expires_at'] or row['lease_expires_at']<=now.isoformat(): raise LeaseLost(job_id)
        return row
    def transition(self,job_id,worker_id,next_status,*,now=None):
        job_id=_id(job_id,'job_id'); worker_id=_id(worker_id,'worker_id'); instant=_dt(now)
        allowed={'fetching':'parsing','parsing':'analyzing','analyzing':'validating','validating':'review_required','delivering':'delivered'}
        with self._tx() as c:
            row=self._leased(c,job_id,worker_id,instant)
            if allowed.get(row['status'])!=next_status: raise QueueConflict('invalid transition')
            delivered=instant.isoformat() if next_status=='delivered' else row['delivered_at']
            release=next_status in {'review_required','delivered'}
            c.execute('UPDATE jobs SET status=?,worker_id=?,lease_expires_at=?,delivered_at=?,updated_at=? WHERE job_id=?',
                      (next_status,None if release else worker_id,None if release else row['lease_expires_at'],delivered,instant.isoformat(),job_id))
            new=c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone(); self._event(c,new,row['status'],next_status,'transition',worker_id,instant.isoformat())
            return self._job(new)
    def review_decide(self,job_id,reviewer_id,*,approved,now=None):
        job_id=_id(job_id,'job_id'); reviewer_id=_id(reviewer_id,'reviewer_id'); instant=_iso(now)
        if type(approved) is not bool: raise ValueError('approved must be bool')
        with self._tx() as c:
            row=c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone()
            if not row: raise JobNotFound(job_id)
            if row['status']!='review_required': raise QueueConflict('job not awaiting review')
            status='ready' if approved else 'blocked_source'; error=None if approved else 'stale_source'
            c.execute('UPDATE jobs SET status=?,last_error_code=?,next_attempt_at=?,updated_at=? WHERE job_id=?',(status,error,instant,instant,job_id))
            new=c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone(); self._event(c,new,row['status'],status,'review_approved' if approved else 'review_rejected',reviewer_id,instant)
            return self._job(new)
    def sweep_expired(self,now=None):
        instant=_dt(now); count=0
        with self._tx() as c:
            rows=c.execute("SELECT * FROM jobs WHERE worker_id IS NOT NULL AND lease_expires_at IS NOT NULL AND lease_expires_at<? AND status IN ('fetching','parsing','analyzing','validating','delivering') ORDER BY job_id",(instant.isoformat(),)).fetchall()
            for row in rows:
                if row['attempt_count']>=row['max_attempts']:
                    status='failed'; error='retry_exhausted'; next_at=instant.isoformat()
                else:
                    status='ready' if row['status']=='delivering' else 'queued'; error='lease_expired'; next_at=instant.isoformat()
                c.execute('UPDATE jobs SET status=?,worker_id=NULL,lease_expires_at=NULL,last_error_code=?,next_attempt_at=?,updated_at=? WHERE job_id=?',(status,error,next_at,instant.isoformat(),row['job_id']))
                new=c.execute('SELECT * FROM jobs WHERE job_id=?',(row['job_id'],)).fetchone(); self._event(c,new,row['status'],status,'lease_expired',row['worker_id'],instant.isoformat()); count+=1
        return count
    def fail(self,job_id,worker_id,error_code,*,retryable=True,now=None):
        job_id=_id(job_id,'job_id'); worker_id=_id(worker_id,'worker_id')
        if not isinstance(error_code,str) or not _ERROR.fullmatch(error_code): raise ValueError('invalid error code')
        if type(retryable) is not bool: raise ValueError('retryable must be bool')
        instant=_dt(now)
        with self._tx() as c:
            row=self._leased(c,job_id,worker_id,instant)
            if retryable and row['attempt_count']<row['max_attempts']:
                delay=5*(2**max(0,row['attempt_count']-1)); status='queued'; stored=error_code; next_at=(instant+timedelta(seconds=delay)).isoformat(); reason='retry_scheduled'
            elif retryable:
                status='failed'; stored='retry_exhausted'; next_at=instant.isoformat(); reason='retry_exhausted'
            else:
                status='failed'; stored=error_code; next_at=instant.isoformat(); reason=error_code
            c.execute('UPDATE jobs SET status=?,worker_id=NULL,lease_expires_at=NULL,last_error_code=?,next_attempt_at=?,updated_at=? WHERE job_id=?',(status,stored,next_at,instant.isoformat(),job_id))
            new=c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone(); self._event(c,new,row['status'],status,reason,worker_id,instant.isoformat())
            return self._job(new)
    def get(self,job_id,organization_id):
        job_id=_id(job_id,'job_id'); organization_id=_id(organization_id,'organization_id')
        with self._conn() as c:
            row=c.execute('SELECT * FROM jobs WHERE job_id=? AND organization_id=?',(job_id,organization_id)).fetchone()
            if not row: raise JobNotFound(job_id)
            return self._job(row)
    def events(self,job_id,organization_id):
        self.get(job_id,organization_id)
        with self._conn() as c:
            return [dict(r) for r in c.execute('SELECT * FROM job_events WHERE job_id=? AND organization_id=? ORDER BY event_id',(job_id,organization_id)).fetchall()]
    def cancel(self,job_id,actor_id,*,now=None):
        job_id=_id(job_id,'job_id'); actor_id=_id(actor_id,'actor_id'); instant=_iso(now)
        with self._tx() as c:
            row=c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone()
            if not row: raise JobNotFound(job_id)
            if row['status']=='cancelled': return self._job(row)
            if row['status'] not in {'queued','ready'}: raise QueueConflict('job cannot be cancelled now')
            c.execute("UPDATE jobs SET status='cancelled',last_error_code='cancelled',worker_id=NULL,lease_expires_at=NULL,updated_at=? WHERE job_id=?",(instant,job_id))
            new=c.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone(); self._event(c,new,row['status'],'cancelled','cancelled',actor_id,instant); return self._job(new)
    def last_success_at(self):
        with self._conn() as c:
            row=c.execute("SELECT MAX(delivered_at) AS t FROM jobs WHERE status='delivered'").fetchone(); return row['t']
