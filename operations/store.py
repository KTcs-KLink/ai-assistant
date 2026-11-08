from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("KLINK_OPERATIONS_DATA", ROOT / "server/.data/operations"))
DB = DATA / "operations.sqlite3"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


DEFAULTS = dict(monthly_budget_usd="20.00", daily_request_limit=100,
                budget_action="observe", maintenance=False, revision=1,
                updated_at=None, scope="LOCAL_DEMO", currency="USD")
DEFAULT_RATE = dict(model="gpt-6-luna", input="0.10", cached="0.01", write="0.125", output="0.50",
                    reference="https://developers.openai.com/api/docs/models/gpt-6-luna",
                    checked_at="2026-11-08", tier="Standard assumption", revision=1)


def init():
    with connect() as c:
        c.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,role TEXT NOT NULL,actor TEXT NOT NULL,
          created REAL NOT NULL,expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(id TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,owner TEXT NOT NULL,title TEXT NOT NULL,
          category TEXT NOT NULL,body TEXT NOT NULL,state TEXT NOT NULL,reply TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,updated_at TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at TEXT NOT NULL,actor TEXT NOT NULL,
          action TEXT NOT NULL,target TEXT NOT NULL,detail TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,kind TEXT NOT NULL,state TEXT NOT NULL,
          documents TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
          progress INTEGER NOT NULL DEFAULT 0,message TEXT NOT NULL,report TEXT, retry_of TEXT);
        CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY,state TEXT NOT NULL,note TEXT NOT NULL,
          reviewer TEXT NOT NULL,updated_at TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,started_at TEXT NOT NULL,day TEXT NOT NULL,
          completed_at TEXT,status INTEGER,latency_ms INTEGER,answer_state TEXT,call_count INTEGER,
          usage_complete INTEGER NOT NULL DEFAULT 0, input_tokens INTEGER,output_tokens INTEGER,
          cached_tokens INTEGER,cost_usd TEXT,model TEXT,validation TEXT);
        CREATE TABLE IF NOT EXISTS generations(id INTEGER PRIMARY KEY,request_id TEXT NOT NULL REFERENCES requests(id),
          phase TEXT NOT NULL,model TEXT NOT NULL,input_tokens INTEGER,output_tokens INTEGER,
          cached_tokens INTEGER,write_tokens INTEGER,cost_usd TEXT,rate_snapshot TEXT);
        CREATE INDEX IF NOT EXISTS request_day ON requests(day);
        """)
        c.execute("INSERT OR IGNORE INTO settings VALUES('policy',?)", (json.dumps(DEFAULTS),))
        c.execute("INSERT OR IGNORE INTO settings VALUES('rates',?)", (json.dumps([DEFAULT_RATE]),))
        c.execute("UPDATE jobs SET state='interrupted',message='서비스 재시작으로 중단됨 · 재시도 가능',updated_at=? WHERE state IN ('queued','running')", (now(),))


def setting(name):
    with connect() as c:
        return json.loads(c.execute("SELECT value FROM settings WHERE id=?", (name,)).fetchone()[0])


def audit(c, actor, action, target="", detail=None):
    c.execute("INSERT INTO audit(at,actor,action,target,detail) VALUES(?,?,?,?,?)",
              (now(), actor, action, target, json.dumps(detail or {}, ensure_ascii=False)))


def uid(prefix):
    return prefix + "-" + secrets.token_hex(6)


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def rows(query, args=()):
    with connect() as c:
        return [dict(row) for row in c.execute(query, args)]
