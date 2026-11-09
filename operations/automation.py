"""Local, durable operations workflows. Never promotes an HR source into generation."""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException

from . import corpus, store

TEAMS = ["인사 운영", "양식 지원", "AI 품질", "서비스 지원"]
CATEGORIES = ["규정 문의", "양식 문의", "AI 답변 확인", "서비스 이용"]
DEFAULTS = dict(revision=1, watch_enabled=False, watch_documents=[], watch_interval_minutes=1440,
                cost_warning_percent=80, slow_seconds=60,
                routing=[dict(category=category, team=team, sla_hours=24)
                         for category, team in zip(CATEGORIES, TEAMS)])


def init():
    with store.connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,owner TEXT NOT NULL,requester TEXT NOT NULL,
          kind TEXT NOT NULL,title TEXT NOT NULL,document_id TEXT NOT NULL,job_kind TEXT,
          version_id TEXT,reason TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending',note TEXT NOT NULL DEFAULT '',
          reviewer TEXT,job_id TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS approval_events(id INTEGER PRIMARY KEY,approval_id TEXT NOT NULL,
          at TEXT NOT NULL,actor TEXT NOT NULL,state TEXT NOT NULL,note TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS source_versions(id TEXT PRIMARY KEY,document_id TEXT NOT NULL,title TEXT NOT NULL,
          baseline_sha TEXT NOT NULL,sha256 TEXT NOT NULL,job_id TEXT NOT NULL,state TEXT NOT NULL,
          checked_at TEXT NOT NULL,UNIQUE(document_id,sha256));
        CREATE TABLE IF NOT EXISTS source_checks(document_id TEXT PRIMARY KEY,title TEXT NOT NULL,baseline_sha TEXT NOT NULL,
          last_sha TEXT NOT NULL,checked_at TEXT NOT NULL,job_id TEXT NOT NULL,changed INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS watch_runtime(id INTEGER PRIMARY KEY CHECK(id=1),next_due REAL NOT NULL DEFAULT 0,
          last_job TEXT,last_error TEXT NOT NULL DEFAULT '');
        INSERT OR IGNORE INTO watch_runtime(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS agents(id TEXT PRIMARY KEY,name TEXT NOT NULL,team TEXT NOT NULL,
          active INTEGER NOT NULL,capacity INTEGER NOT NULL,revision INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY,fingerprint TEXT NOT NULL UNIQUE,category TEXT NOT NULL,
          severity TEXT NOT NULL,title TEXT NOT NULL,detail TEXT NOT NULL,target TEXT NOT NULL,
          state TEXT NOT NULL,occurrences INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,owner TEXT NOT NULL,fingerprint TEXT NOT NULL,
          title TEXT NOT NULL,detail TEXT NOT NULL,target TEXT NOT NULL,created_at TEXT NOT NULL,read_at TEXT,
          UNIQUE(owner,fingerprint));
        CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY,request_id TEXT NOT NULL UNIQUE REFERENCES requests(id),
          owner TEXT NOT NULL,reason TEXT NOT NULL,note TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'open',
          resolution TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1);
        CREATE INDEX IF NOT EXISTS approval_owner ON approvals(owner,created_at);
        CREATE INDEX IF NOT EXISTS notification_owner ON notifications(owner,read_at);
        """)
        columns = {r[1] for r in c.execute("PRAGMA table_info(cases)")}
        for key, declaration in [("team", "TEXT NOT NULL DEFAULT ''"), ("agent_id", "TEXT"),
                                 ("assignment_reason", "TEXT NOT NULL DEFAULT ''"), ("due_at", "TEXT"),
                                 ("routing_locked", "INTEGER NOT NULL DEFAULT 0")]:
            if key not in columns:
                c.execute(f"ALTER TABLE cases ADD COLUMN {key} {declaration}")
        if "owner_session" not in {r[1] for r in c.execute("PRAGMA table_info(requests)")}:
            c.execute("ALTER TABLE requests ADD COLUMN owner_session TEXT")
        c.execute("INSERT OR IGNORE INTO settings VALUES('automation',?)", (json.dumps(DEFAULTS, ensure_ascii=False),))


def notify(c, owner, fingerprint, title, detail, target):
    if owner == "system":
        return
    c.execute("INSERT OR IGNORE INTO notifications(id,owner,fingerprint,title,detail,target,created_at) VALUES(?,?,?,?,?,?,?)",
              (store.uid("NTF"), owner, fingerprint, title, detail, target, store.now()))


def signal(c, fingerprint, category, severity, title, detail, target, active=True):
    row = c.execute("SELECT * FROM alerts WHERE fingerprint=?", (fingerprint,)).fetchone()
    if not active:
        if row and row["state"] != "resolved":
            c.execute("UPDATE alerts SET state='resolved',updated_at=?,revision=revision+1 WHERE id=?", (store.now(), row["id"]))
        return
    if row:
        if row["state"] == "resolved" or row["severity"] != severity:
            c.execute("UPDATE alerts SET state='open',severity=?,title=?,detail=?,occurrences=occurrences+1,updated_at=?,revision=revision+1 WHERE id=?",
                      (severity, title, detail, store.now(), row["id"]))
        elif row["detail"] != detail:
            c.execute("UPDATE alerts SET detail=?,updated_at=?,revision=revision+1 WHERE id=?", (detail, store.now(), row["id"]))
    else:
        c.execute("INSERT INTO alerts(id,fingerprint,category,severity,title,detail,target,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,'open',?,?)",
                  (store.uid("ALT"), fingerprint, category, severity, title, detail, target, store.now(), store.now()))


def enqueue(c, kind, ids, actor, retry_of=None):
    try:
        _, docs = corpus.selected(ids)
    except (ValueError, OSError, KeyError):
        raise HTTPException(422, "검증된 원문 목록에서 서로 다른 문서 1~5개를 선택해 주세요.") from None
    if kind == "reindex" and not any(d["answer_count"] or d["review_count"] for d in docs):
        raise HTTPException(422, "검색 구간이 있는 문서를 선택해 주세요.")
    documents = json.dumps(sorted(ids))
    if c.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0] >= 5:
        raise HTTPException(429, "진행 중인 작업이 많습니다. 완료 후 다시 요청해 주세요.")
    if c.execute("SELECT id FROM jobs WHERE state IN ('queued','running') AND kind=? AND documents=?", (kind, documents)).fetchone():
        raise HTTPException(409, "같은 문서의 작업이 이미 대기 또는 실행 중입니다.")
    job_id = store.uid("JOB")
    c.execute("INSERT INTO jobs(id,kind,state,documents,created_at,updated_at,message,retry_of) VALUES(?,?,'queued',?,?,?,'작업 대기 중',?)",
              (job_id, kind, documents, store.now(), store.now(), retry_of))
    store.audit(c, actor, "job_queued", job_id, dict(kind=kind, documents=ids, staging_only=True))
    return job_id


def route_case(c, case_id, force=False):
    row = c.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not row or row["state"] in {"resolved", "cancelled"} or (row["routing_locked"] and not force):
        return
    config = json.loads(c.execute("SELECT value FROM settings WHERE id='automation'").fetchone()[0])
    rule = next(r for r in config["routing"] if r["category"] == row["category"])
    candidates = c.execute("""SELECT a.*,count(k.id) AS load FROM agents a LEFT JOIN cases k
        ON k.agent_id=a.id AND k.id!=? AND k.state NOT IN ('resolved','cancelled')
        WHERE a.active=1 AND a.team=? GROUP BY a.id HAVING count(k.id)<a.capacity
        ORDER BY load ASC,a.id ASC""", (case_id, rule["team"])).fetchall()
    agent = candidates[0] if candidates else None
    reason = "분류 규칙 → 해당 팀의 처리 중 문의가 가장 적은 담당자" if agent else "분류 규칙 → 팀 대기함 · 활동 중인 담당자 또는 처리 여유 없음"
    due = row["due_at"] or (datetime.now(timezone.utc) + timedelta(hours=rule["sla_hours"])).isoformat(timespec="seconds")
    c.execute("UPDATE cases SET team=?,agent_id=?,assignment_reason=?,due_at=?,routing_locked=0,revision=revision+1,updated_at=? WHERE id=?",
              (rule["team"], agent["id"] if agent else None, reason, due, store.now(), case_id))
    store.audit(c, "local_router", "case_routed", case_id, dict(team=rule["team"], agent_id=agent["id"] if agent else None))
    notify(c, row["owner"], f"route:{case_id}:{agent['id'] if agent else 'queue'}", "문의 접수·배정 안내",
           rule["team"] + (" · " + agent["name"] if agent else " · 담당자 배정 대기"), "/hr/requests")


def observe_job(job_id):
    rows = store.rows("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not rows or rows[0]["kind"] != "recollect" or rows[0]["state"] != "succeeded":
        return
    report = json.loads(rows[0]["report"])
    with store.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        for doc in report["documents"]:
            sha = doc["downloaded_sha256"]
            path = store.DATA / "artifacts" / job_id / (doc["id"] + ".source")
            if corpus.sha_file(path) != sha:
                raise ValueError("수집 파일 해시가 보고서와 다릅니다.")
            changed = sha != doc["original_sha256"]
            c.execute("INSERT OR REPLACE INTO source_checks VALUES(?,?,?,?,?,?,?)",
                      (doc["id"], doc["title"], doc["original_sha256"], sha, store.now(), job_id, int(changed)))
            # Only the latest observed bytes may be accepted. A return to baseline also supersedes a candidate.
            stale = c.execute("SELECT id FROM source_versions WHERE document_id=? AND sha256!=? AND state IN ('pending','accepted')", (doc["id"], sha)).fetchall()
            for old in stale:
                c.execute("UPDATE source_versions SET state='superseded' WHERE id=?", (old[0],))
                for prior in c.execute("SELECT id FROM approvals WHERE version_id=? AND state IN ('pending','needs_info')", (old[0],)).fetchall():
                    event(c, prior[0], "local_watcher", "superseded", "더 최근의 공식 파일이 확인되어 이 후보의 승인을 중지했습니다.")
                c.execute("UPDATE approvals SET state='superseded',revision=revision+1,updated_at=? WHERE version_id=? AND state IN ('pending','needs_info')", (store.now(), old[0]))
                signal(c, "source:" + old[0], "source", "warning", "", "", "", False)
            if not changed:
                continue
            existing = c.execute("SELECT * FROM source_versions WHERE document_id=? AND sha256=?", (doc["id"], sha)).fetchone()
            if existing and existing["state"] != "superseded":
                continue
            version_id = existing["id"] if existing else store.uid("VER")
            if existing:
                c.execute("UPDATE source_versions SET state='pending',job_id=?,checked_at=? WHERE id=?", (job_id, store.now(), version_id))
            else:
                c.execute("INSERT INTO source_versions VALUES(?,?,?,?,?,?,?,?)",
                          (version_id, doc["id"], doc["title"], doc["original_sha256"], sha, job_id, "pending", store.now()))
            approval_id = store.uid("APR")
            c.execute("INSERT INTO approvals(id,owner,requester,kind,title,document_id,version_id,reason,created_at,updated_at) VALUES(?,'system','규정 변경 감지','source_change',?,?,?,?,?,?)",
                      (approval_id, doc["title"], doc["id"], version_id, "공식 출처의 파일 바이트가 보존 원문과 달라졌습니다. 내용 변경 여부는 원문 검토가 필요합니다.", store.now(), store.now()))
            event(c, approval_id, "local_watcher", "pending", "공식 파일 변경 후보 · 원본과 답변 범위 유지")
            signal(c, "source:" + version_id, "source", "warning", "규정 파일 변경 후보", doc["title"] + " · 검토 전까지 답변 원문 유지", "/hr/admin/approvals")
        store.audit(c, "local_watcher", "source_check_completed", job_id, dict(active_service_changed=False))


def run_job(job_id, kind, ids):
    corpus.run_job(job_id, kind, ids)
    try:
        observe_job(job_id)
    except (ValueError, OSError, KeyError):
        with store.connect() as c:
            signal(c, "observe:" + job_id, "source", "critical", "변경 감지 기록 확인 필요", "수집 결과의 무결성을 확인하지 못했습니다. 기존 답변 원문을 유지했습니다.", "/hr/admin/jobs")
    reconcile()


def event(c, approval_id, actor, state, note):
    c.execute("INSERT INTO approval_events(approval_id,at,actor,state,note) VALUES(?,?,?,?,?)", (approval_id, store.now(), actor, state, note))


def approval_items(owner=None):
    sql = "SELECT * FROM approvals" + (" WHERE owner=?" if owner else "") + " ORDER BY updated_at DESC LIMIT 200"
    with store.connect() as c:
        rows = [dict(r) for r in c.execute(sql, (owner,) if owner else ())]
        for row in rows:
            row.pop("owner", None)
            row["events"] = [dict(e) for e in c.execute("SELECT at,actor,state,note FROM approval_events WHERE approval_id=? ORDER BY id", (row["id"],))]
            version = c.execute("SELECT * FROM source_versions WHERE id=?", (row["version_id"],)).fetchone()
            row["version"] = dict(version) if version else None
    return rows


def decide(approval_id, state, note, revision, session):
    job = None
    with store.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if not row or row["revision"] != revision or row["state"] != "pending":
            raise HTTPException(409, "최신 승인 대기 건을 다시 불러와 주세요.")
        if row["owner"] == session["id"]:
            raise HTTPException(403, "신청한 접속에서는 본인 요청을 승인할 수 없습니다.")
        if state == "approved" and row["kind"] == "source_check":
            job_id = enqueue(c, row["job_kind"], [row["document_id"]], session["actor"])
            job = (job_id, row["job_kind"], [row["document_id"]])
        elif state == "approved":
            version = c.execute("SELECT * FROM source_versions WHERE id=?", (row["version_id"],)).fetchone()
            latest = c.execute("SELECT last_sha FROM source_checks WHERE document_id=?", (row["document_id"],)).fetchone()
            if not version or version["state"] != "pending" or not latest or latest[0] != version["sha256"]:
                raise HTTPException(409, "최신 변경 후보가 아닙니다. 원문을 다시 점검해 주세요.")
            path = store.DATA / "artifacts" / version["job_id"] / (version["document_id"] + ".source")
            if not path.is_file() or corpus.sha_file(path) != version["sha256"]:
                raise HTTPException(409, "보관 파일 해시를 확인하지 못했습니다.")
            c.execute("UPDATE source_versions SET state='accepted' WHERE id=?", (version["id"],))
            signal(c, "source:" + version["id"], "source", "warning", "", "", "", False)
        elif row["kind"] == "source_change" and state == "rejected":
            c.execute("UPDATE source_versions SET state='held' WHERE id=?", (row["version_id"],))
            signal(c, "source:" + row["version_id"], "source", "warning", "", "", "", False)
        c.execute("UPDATE approvals SET state=?,note=?,reviewer=?,job_id=?,revision=revision+1,updated_at=? WHERE id=?",
                  (state, note, session["actor"], job[0] if job else None, store.now(), approval_id))
        event(c, approval_id, session["actor"], state, note)
        notify(c, row["owner"], f"approval:{approval_id}:{revision+1}", "승인 요청 처리 안내", row["title"] + " · " + note, "/hr/inbox")
        store.audit(c, session["actor"], "approval_decided", approval_id, dict(state=state, active_service_changed=False))
    return job


def reconcile():
    config = store.setting("automation")
    policy = store.setting("policy")
    month = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m")
    with store.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        requests = c.execute("SELECT * FROM requests WHERE day LIKE ? AND completed_at IS NOT NULL ORDER BY completed_at", (month + "%",)).fetchall()
        known = sum((Decimal(r["cost_usd"]) for r in requests if r["cost_usd"] is not None), Decimal(0))
        threshold = Decimal(policy["monthly_budget_usd"]) * Decimal(config["cost_warning_percent"]) / 100
        signal(c, "budget:" + month, "cost", "critical" if known >= Decimal(policy["monthly_budget_usd"]) else "warning",
               "월 비용 한도 도달" if known >= Decimal(policy["monthly_budget_usd"]) else "월 비용 주의 구간",
               f"수집된 확정 사용량의 예상 비용 ${known:.6f} / 설정 예산 ${policy['monthly_budget_usd']} · 공급사 청구 총액 아님",
               "/hr/admin/usage", bool(requests) and known >= threshold)
        unknown = sum(r["cost_usd"] is None for r in requests)
        signal(c, "unknown-cost:" + month, "cost", "warning", "비용 미확인 요청", f"완료 요청 {unknown}건의 사용량 또는 요금표를 확인해야 합니다. 미확인 비용은 0원으로 합산하지 않습니다.", "/hr/admin/usage", unknown > 0)
        for row in requests[-1000:]:
            failed = row["status"] is not None and row["status"] >= 500
            slow = (row["latency_ms"] or 0) >= config["slow_seconds"] * 1000
            signal(c, "quality:" + row["id"], "quality", "critical" if failed else "warning",
                   "답변 연결 실패" if failed else "답변 지연 기준 초과",
                   f"{row['id']} · HTTP {row['status']} · {row['latency_ms']}ms · 답변 의미 정확도 평가는 별도",
                   "/hr/admin/alerts", failed or slow)
        for row in c.execute("SELECT * FROM cases").fetchall():
            opened = row["state"] not in {"resolved", "cancelled"}
            signal(c, "unassigned:" + row["id"], "routing", "warning", "담당자 배정 대기", row["title"] + " · " + row["team"], "/hr/admin/cases", opened and not row["agent_id"])
            signal(c, "overdue:" + row["id"], "routing", "critical", "문의 처리 목표 시간 초과", row["title"], "/hr/admin/cases", opened and bool(row["due_at"]) and row["due_at"] < store.now())
            agent = c.execute("SELECT active FROM agents WHERE id=?", (row["agent_id"],)).fetchone() if row["agent_id"] else None
            signal(c, "inactive-agent:" + row["id"], "routing", "warning", "문의 담당자 재배정 필요", row["title"] + " · 기존 담당자가 배정 중지 상태입니다.", "/hr/admin/cases", opened and bool(agent) and not agent[0])
        for row in c.execute("SELECT * FROM feedback").fetchall():
            signal(c, "feedback:" + row["id"], "quality", "warning", "직원의 답변 검토 요청", row["request_id"] + " · " + row["reason"], "/hr/admin/alerts", row["state"] == "open")
        for row in c.execute("SELECT id,state FROM jobs WHERE state IN ('failed','interrupted','succeeded') ORDER BY created_at DESC LIMIT 100"):
            signal(c, "job:" + row["id"], "source", "warning", "자료 점검 작업 확인 필요", row["id"] + " · " + row["state"], "/hr/admin/jobs", row["state"] in {"failed", "interrupted"})


def tick(submit):
    reconcile()
    with store.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        config = json.loads(c.execute("SELECT value FROM settings WHERE id='automation'").fetchone()[0])
        runtime = c.execute("SELECT * FROM watch_runtime WHERE id=1").fetchone()
        if not config["watch_enabled"] or not config["watch_documents"] or runtime["next_due"] > time.time():
            return
        if runtime["last_job"] and c.execute("SELECT id FROM jobs WHERE id=? AND state IN ('queued','running')", (runtime["last_job"],)).fetchone():
            return
        try:
            job_id = enqueue(c, "recollect", config["watch_documents"], "scheduled_watcher")
        except HTTPException as error:
            c.execute("UPDATE watch_runtime SET next_due=?,last_error=? WHERE id=1", (time.time()+60, str(error.detail)))
            return
        c.execute("UPDATE watch_runtime SET next_due=?,last_job=?,last_error='' WHERE id=1", (time.time()+config["watch_interval_minutes"]*60, job_id))
    submit(run_job, job_id, "recollect", config["watch_documents"])


def refresh_safely():
    # Alert bookkeeping must not replace a completed upstream answer with an error.
    try:
        reconcile()
    except Exception:
        try:
            with store.connect() as c:
                c.execute("UPDATE watch_runtime SET last_error='알림 집계를 완료하지 못했습니다. 운영 기록을 확인해 주세요.' WHERE id=1")
        except Exception:
            # Do not discard an already received answer if the local operations DB is unavailable.
            pass


def start_scheduler(submit):
    stop = threading.Event()
    def loop():
        while not stop.wait(30):
            try:
                tick(submit)
            except Exception:
                with store.connect() as c:
                    c.execute("UPDATE watch_runtime SET last_error='자동 점검을 완료하지 못했습니다. 운영 기록을 확인해 주세요.' WHERE id=1")
    thread = threading.Thread(target=loop, daemon=True, name="klink-automation-clock")
    thread.start()
    return stop, thread
