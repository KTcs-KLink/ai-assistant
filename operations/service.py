from __future__ import annotations

import csv
import io
import json
import re
import secrets
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from . import corpus, meter, store

UPSTREAM = "http://127.0.0.1:8846"
ORIGINS = {"http://127.0.0.1:8825", "http://localhost:8825", "http://127.0.0.1:8848", "http://testserver"}
ROLES = {
    "employee": {"cases_own"},
    "hr_admin": {"cases", "reviews", "sources", "health"},
    "data_admin": {"sources", "jobs", "reviews", "health"},
    "analyst": {"usage", "audit", "health"},
    "owner": {"cases", "reviews", "sources", "jobs", "usage", "settings", "audit", "health"},
}
PRIVATE = re.compile(r"(?:sk-[A-Za-z0-9_-]{12,}|\b\d{6}[- ]?[1-4]\d{6}\b|(?:010|011)[- ]?\d{3,4}[- ]?\d{4}|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:api[_ -]?key|access[_ -]?token|password)\s*[:=])", re.I)
RUNNER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="klink-local-ops")


@asynccontextmanager
async def lifespan(app):
    store.init()
    yield


app = FastAPI(title="KLINK Local Operations", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.middleware("http")
async def boundary(request: Request, call_next):
    if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        return JSONResponse({"detail": "로컬 체험 서비스입니다."}, status_code=403)
    if request.headers.get("host", "").split(":")[0] not in {"127.0.0.1", "localhost", "testserver"}:
        return JSONResponse({"detail": "허용된 접속 주소가 아닙니다."}, status_code=403)
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("origin") not in ORIGINS:
        return JSONResponse({"detail": "같은 화면에서 요청해 주세요."}, status_code=403)
    if int(request.headers.get("content-length", "0")) > 32768:
        return JSONResponse({"detail": "요청 한도를 넘었습니다."}, status_code=413)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Demo(Strict):
    role: Literal["employee", "hr_admin", "data_admin", "analyst", "owner"] = "employee"


def public(session):
    return dict(role=session["role"], actor=session["actor"], permissions=sorted(ROLES[session["role"]]),
                mode="LOCAL_DEMO", sso_connected=False, production_authorized=False)


def session_for(request, admin=False):
    key = store.hash_token(request.cookies.get("klink_ops_admin" if admin else "klink_ops_employee", ""))
    rows = store.rows("SELECT * FROM sessions WHERE id=? AND expires>?", (key, time.time()))
    if not rows:
        raise HTTPException(401, "관리자 체험을 시작해 주세요." if admin else "문의 기능의 직원 체험을 시작해 주세요.")
    session = rows[0]
    if admin and session["role"] == "employee":
        raise HTTPException(403, "관리자 권한이 필요합니다.")
    return session


def permission(name):
    def check(request: Request):
        session = session_for(request, admin=True)
        if name not in ROLES[session["role"]]:
            raise HTTPException(403, "현재 체험 역할에는 이 작업 권한이 없습니다.")
        return session
    return check


def safe_text(text):
    value = unicodedata.normalize("NFKC", text).strip()
    if PRIVATE.search(value):
        raise HTTPException(422, "개인정보나 키 없이 일반적인 업무 내용만 입력해 주세요.")
    return value


@app.get("/api/control/health")
def health():
    return dict(app="KLINK_LOCAL_OPERATIONS", version="2026-11-08", mode="LOCAL_DEMO", upstream=UPSTREAM,
                supabase_ingestion="HOLD", production_ready=False)


@app.post("/api/control/session/demo")
def start_demo(payload: Demo, response: Response):
    token = secrets.token_urlsafe(32)
    actor = ("직원 체험 " if payload.role == "employee" else "관리자 체험 ") + secrets.token_hex(2)
    with store.connect() as c:
        c.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
        if c.execute("SELECT count(*) FROM sessions").fetchone()[0] >= 100:
            raise HTTPException(429, "활성 체험 접속 수 한도에 도달했습니다.")
        c.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", (store.hash_token(token), payload.role, actor, time.time(), time.time()+28800))
        store.audit(c, actor, "demo_session_started", detail=dict(role=payload.role, production_authorized=False))
    response.set_cookie("klink_ops_employee" if payload.role == "employee" else "klink_ops_admin", token,
                        httponly=True, samesite="strict", max_age=28800, path="/api/control")
    return public(dict(role=payload.role, actor=actor))


@app.get("/api/control/session")
def me(request: Request, admin: bool = False):
    return public(session_for(request, admin))


@app.delete("/api/control/session", status_code=204)
def logout(request: Request, response: Response, admin: bool = False):
    cookie = "klink_ops_admin" if admin else "klink_ops_employee"
    with store.connect() as c:
        c.execute("DELETE FROM sessions WHERE id=?", (store.hash_token(request.cookies.get(cookie, "")),))
    response.delete_cookie(cookie, path="/api/control")


class CaseIn(Strict):
    title: str = Field(min_length=2, max_length=100)
    category: Literal["규정 문의", "양식 문의", "AI 답변 확인", "서비스 이용"]
    body: str = Field(min_length=5, max_length=1500)


@app.get("/api/control/cases")
def own_cases(request: Request):
    s = session_for(request)
    return dict(items=store.rows("SELECT id,title,category,body,state,reply,created_at,updated_at,revision FROM cases WHERE owner=? ORDER BY created_at DESC", (s["id"],)), mode="LOCAL_DEMO", actual_hr_submission=False)


@app.post("/api/control/cases", status_code=201)
def create_case(payload: CaseIn, request: Request):
    s = session_for(request)
    title, body = safe_text(payload.title), safe_text(payload.body)
    case_id = store.uid("HR")
    with store.connect() as c:
        if c.execute("SELECT count(*) FROM cases WHERE owner=?", (s["id"],)).fetchone()[0] >= 100:
            raise HTTPException(429, "체험 문의 한도에 도달했습니다.")
        c.execute("INSERT INTO cases(id,owner,title,category,body,state,created_at,updated_at) VALUES(?,?,?,?,?,'received',?,?)",
                  (case_id, s["id"], title, payload.category, body, store.now(), store.now()))
        store.audit(c, s["actor"], "case_created", case_id, dict(category=payload.category))
    return dict(id=case_id, state="received", actual_hr_submission=False)


@app.post("/api/control/cases/{case_id}/cancel")
def cancel_case(case_id: str, request: Request):
    s = session_for(request)
    with store.connect() as c:
        item = c.execute("SELECT state FROM cases WHERE id=? AND owner=?", (case_id, s["id"])).fetchone()
        if not item:
            raise HTTPException(404, "본인의 문의를 찾을 수 없습니다.")
        if item[0] in {"resolved", "cancelled"}:
            raise HTTPException(409, "이미 종료된 문의입니다.")
        c.execute("UPDATE cases SET state='cancelled',revision=revision+1,updated_at=? WHERE id=?", (store.now(), case_id))
        store.audit(c, s["actor"], "case_cancelled", case_id)
    return dict(id=case_id, state="cancelled")


@app.get("/api/control/admin/cases")
def cases(s=Depends(permission("cases"))):
    return dict(items=store.rows("SELECT id,title,category,body,state,reply,created_at,updated_at,revision FROM cases ORDER BY updated_at DESC LIMIT 300"), mode="LOCAL_DEMO", actual_hr_submission=False)


class CaseUpdate(Strict):
    state: Literal["received", "in_review", "awaiting_info", "resolved"]
    reply: str = Field(max_length=1500)
    revision: int = Field(ge=1)


@app.patch("/api/control/admin/cases/{case_id}")
def update_case(case_id: str, payload: CaseUpdate, s=Depends(permission("cases"))):
    reply = safe_text(payload.reply)
    if payload.state in {"awaiting_info", "resolved"} and len(reply) < 5:
        raise HTTPException(422, "처리 안내를 다섯 글자 이상 작성해 주세요.")
    with store.connect() as c:
        changed = c.execute("UPDATE cases SET state=?,reply=?,updated_at=?,revision=revision+1 WHERE id=? AND revision=? AND state!='cancelled'",
                            (payload.state, reply, store.now(), case_id, payload.revision)).rowcount
        if not changed:
            raise HTTPException(409, "문의 상태가 변경됐습니다. 다시 불러온 뒤 처리해 주세요.")
        store.audit(c, s["actor"], "case_updated", case_id, dict(state=payload.state, actual_hr_submission=False))
    return dict(id=case_id, state=payload.state)


@app.get("/api/control/admin/sources")
def sources(q: str = Query("", max_length=100), scope: Literal["all", "answer", "review"] = "all", s=Depends(permission("sources"))):
    try:
        data = corpus.load()
    except (OSError, ValueError, KeyError):
        raise HTTPException(503, "검증된 원문 목록을 확인하지 못했습니다. 기존 서비스는 변경하지 않았습니다.") from None
    items = [d for d in data["documents"] if q.casefold() in d["title"].casefold() and (scope == "all" or d[scope+"_count"] > 0)]
    return dict(items=items, total=len(data["documents"]), answer_units=sum(d["answer_count"] for d in data["documents"]),
                review_units=sum(d["review_count"] for d in data["documents"]), excluded_units=sum(d["excluded_count"] for d in data["documents"]),
                manifest_sha256=corpus.MANIFEST_SHA, production_approved=False)


@app.get("/api/control/admin/sources/{document_id}/excerpts")
def source_excerpts(document_id: str, s=Depends(permission("sources"))):
    try:
        data, docs = corpus.selected([document_id])
    except (ValueError, OSError, KeyError):
        raise HTTPException(404, "허용된 원문을 찾을 수 없습니다.") from None
    candidates = [r for r in data["manifest"]["units"] if r["unit_id"] == document_id and r["structural_verified"]]
    candidates.sort(key=lambda row: not row["answer_eligible"])
    items = []
    for meta in candidates[:3]:
        row = data["units"][meta["id"]]
        items.append(dict(id=row["id"], text=row["text"], section=" > ".join(row["heading_path"]) if isinstance(row["heading_path"], list) else row["heading_path"],
                          sha256=row["text_sha256"], answer_eligible=bool(meta["answer_eligible"]), human_approved=False, ktcs_applicable=False))
    return dict(items=items, document=docs[0], used_for_generation=False)


class JobIn(Strict):
    kind: Literal["verify", "recollect", "reindex"]
    documents: list[str] = Field(min_length=1, max_length=5)


def queue_job(payload, s, retry_of=None):
    try:
        _, documents_to_process = corpus.selected(payload.documents)
    except (ValueError, OSError, KeyError):
        raise HTTPException(422, "검증된 원문 목록에서 1~5개 문서를 선택해 주세요.") from None
    if payload.kind == "reindex" and not any(d["answer_count"] or d["review_count"] for d in documents_to_process):
        raise HTTPException(422, "검색 구간이 있는 문서를 선택해 주세요. 원본만 보존된 문서는 분할·검토가 먼저 필요합니다.")
    job_id = store.uid("JOB")
    documents = json.dumps(sorted(payload.documents))
    with store.connect() as c:
        if c.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0] >= 5:
            raise HTTPException(429, "진행 중인 작업이 많습니다. 완료 후 다시 요청해 주세요.")
        if c.execute("SELECT id FROM jobs WHERE state IN ('queued','running') AND kind=? AND documents=?", (payload.kind, documents)).fetchone():
            raise HTTPException(409, "같은 문서의 작업이 이미 대기 또는 실행 중입니다.")
        c.execute("INSERT INTO jobs(id,kind,state,documents,created_at,updated_at,message,retry_of) VALUES(?,?,'queued',?,?,?,'작업 대기 중',?)",
                  (job_id, payload.kind, documents, store.now(), store.now(), retry_of))
        store.audit(c, s["actor"], "job_queued", job_id, dict(kind=payload.kind, documents=payload.documents, staging_only=True))
    RUNNER.submit(corpus.run_job, job_id, payload.kind, payload.documents)
    return dict(id=job_id, state="queued", active_service_changed=False)


@app.post("/api/control/admin/jobs", status_code=202)
def create_job(payload: JobIn, s=Depends(permission("jobs"))):
    return queue_job(payload, s)


@app.get("/api/control/admin/jobs")
def jobs(s=Depends(permission("jobs"))):
    items = store.rows("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 100")
    for item in items:
        item["documents"] = json.loads(item["documents"])
        item["report"] = json.loads(item["report"]) if item["report"] else None
    return dict(items=items, scope="STAGING_ONLY", supabase_ingestion="HOLD")


@app.post("/api/control/admin/jobs/{job_id}/cancel")
def cancel_job(job_id: str, s=Depends(permission("jobs"))):
    with store.connect() as c:
        if not c.execute("UPDATE jobs SET state='cancelled',message='사용자가 중지 요청 · 기존 서비스 유지',updated_at=? WHERE id=? AND state IN ('queued','running')", (store.now(), job_id)).rowcount:
            raise HTTPException(409, "중지할 수 있는 진행 중 작업이 아닙니다.")
        store.audit(c, s["actor"], "job_cancelled", job_id)
    return dict(id=job_id, state="cancelled")


@app.post("/api/control/admin/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, s=Depends(permission("jobs"))):
    records = store.rows("SELECT * FROM jobs WHERE id=? AND state IN ('failed','cancelled','interrupted')", (job_id,))
    if not records:
        raise HTTPException(409, "실패·중단된 작업만 새 버전으로 재시도할 수 있습니다.")
    row = records[0]
    return queue_job(JobIn(kind=row["kind"], documents=json.loads(row["documents"])), s, job_id)


@app.get("/api/control/admin/jobs/{job_id}/report")
def report(job_id: str, s=Depends(permission("jobs"))):
    row = store.rows("SELECT report FROM jobs WHERE id=?", (job_id,))
    if not row or not row[0]["report"]:
        raise HTTPException(404, "완료된 작업 보고서가 없습니다.")
    return JSONResponse(json.loads(row[0]["report"]), headers={"Content-Disposition": f'attachment; filename="{job_id}.json"'})


class ReviewIn(Strict):
    document_id: str = Field(max_length=100)
    state: Literal["in_review", "held", "reviewed"]
    note: str = Field(min_length=5, max_length=1000)
    revision: int = Field(ge=0)


@app.get("/api/control/admin/reviews")
def reviews(s=Depends(permission("reviews"))):
    return dict(items=store.rows("SELECT * FROM reviews ORDER BY updated_at DESC"), answer_eligibility_changed=False, human_approval=False)


@app.put("/api/control/admin/reviews")
def save_review(payload: ReviewIn, s=Depends(permission("reviews"))):
    try:
        corpus.selected([payload.document_id])
    except (ValueError, OSError, KeyError):
        raise HTTPException(422, "허용된 원문 목록에서 선택해 주세요.") from None
    note = safe_text(payload.note)
    with store.connect() as c:
        existing = c.execute("SELECT revision FROM reviews WHERE id=?", (payload.document_id,)).fetchone()
        if (existing[0] if existing else 0) != payload.revision:
            raise HTTPException(409, "다른 검토 기록이 저장됐습니다. 다시 확인해 주세요.")
        c.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,note=excluded.note,reviewer=excluded.reviewer,updated_at=excluded.updated_at,revision=excluded.revision",
                  (payload.document_id, payload.state, note, s["actor"], store.now(), payload.revision+1))
        store.audit(c, s["actor"], "review_recorded", payload.document_id, dict(state=payload.state, answer_eligibility_changed=False))
    return dict(document_id=payload.document_id, revision=payload.revision+1, answer_eligibility_changed=False, human_approval=False)


@app.get("/api/control/admin/usage")
def usage(days: int = Query(7, ge=1, le=90), s=Depends(permission("usage"))):
    if days not in {1, 7, 30, 90}:
        raise HTTPException(422, "1·7·30·90일 중 선택해 주세요.")
    return meter.summary(days)


@app.get("/api/control/admin/usage/requests/{request_id}")
def usage_detail(request_id: str, s=Depends(permission("usage"))):
    rows = store.rows("SELECT * FROM requests WHERE id=?", (request_id,))
    if not rows:
        raise HTTPException(404, "집계된 요청을 찾을 수 없습니다.")
    return dict(request=rows[0], generations=store.rows("SELECT phase,model,input_tokens,output_tokens,cached_tokens,write_tokens,cost_usd,rate_snapshot FROM generations WHERE request_id=? ORDER BY id", (request_id,)),
                questions_stored=False, answers_stored=False, cost_is_invoice=False)


@app.get("/api/control/admin/usage/export")
def export_usage(s=Depends(permission("usage"))):
    rows = store.rows("SELECT started_at,status,latency_ms,call_count,usage_complete,input_tokens,output_tokens,cached_tokens,cost_usd,model FROM requests ORDER BY started_at DESC LIMIT 10000")
    stream = io.StringIO()
    writer = csv.writer(stream)
    columns = ["started_at", "status", "latency_ms", "call_count", "usage_complete", "input_tokens", "output_tokens", "cached_tokens", "cost_usd", "model"]
    writer.writerow(columns)
    for row in rows:
        writer.writerow([("'"+v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v) for v in (row[k] for k in columns)])
    return Response("\ufeff" + stream.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="klink-usage.csv"'})


class PolicyIn(Strict):
    monthly_budget_usd: Decimal = Field(ge=Decimal("0.01"), le=100000)
    daily_request_limit: int = Field(ge=1, le=10000)
    budget_action: Literal["observe", "block"]
    maintenance: bool
    revision: int = Field(ge=1)


@app.get("/api/control/admin/settings")
def settings(s=Depends(permission("health"))):
    return dict(policy=store.setting("policy"), rates=store.setting("rates"), permissions={key: sorted(v) for key, v in ROLES.items()},
                integrations=[dict(id="hr", name="한전 원문·AI 답변", state="local", detail="8846 기존 검색·지정 모델 유지"),
                              dict(id="db", name="운영 기록 저장소", state="local", detail="로컬 SQLite · 체험 문의·작업·사용량·감사 기록"),
                              dict(id="sso", name="조직 인증·SSO", state="unconnected", detail="실제 직원 권한 연결 전 · 현재 역할 체험"),
                              dict(id="supabase", name="Supabase 적재", state="held", detail="HOLD · 클라우드 쓰기·SQL 미실행"),
                              dict(id="activation", name="검색 버전 서비스 반영", state="held", detail="스테이징 검사 후 별도 반영 연결 필요"),
                              dict(id="billing", name="공급자 청구서 대조", state="unconnected", detail="응답 토큰×단가 추정 · 실제 청구 API 미연결")])


@app.put("/api/control/admin/settings")
def save_settings(payload: PolicyIn, s=Depends(permission("settings"))):
    with store.connect() as c:
        current = json.loads(c.execute("SELECT value FROM settings WHERE id='policy'").fetchone()[0])
        if current["revision"] != payload.revision:
            raise HTTPException(409, "설정이 변경됐습니다. 최신 설정을 불러와 주세요.")
        current.update(payload.model_dump(mode="json"), revision=current["revision"]+1, updated_at=store.now())
        c.execute("UPDATE settings SET value=? WHERE id='policy'", (json.dumps(current),))
        store.audit(c, s["actor"], "policy_saved", detail=current)
    return current


class RateIn(Strict):
    model: str = Field(pattern=r"^[a-zA-Z0-9._-]{1,80}$")
    input: Decimal = Field(ge=0, le=100000)
    cached: Decimal = Field(ge=0, le=100000)
    write: Decimal = Field(ge=0, le=100000)
    output: Decimal = Field(ge=0, le=100000)


@app.put("/api/control/admin/rates")
def save_rate(payload: RateIn, s=Depends(permission("settings"))):
    with store.connect() as c:
        rates = json.loads(c.execute("SELECT value FROM settings WHERE id='rates'").fetchone()[0])
        prior = next((r for r in rates if r["model"] == payload.model), None)
        row = dict(**payload.model_dump(mode="json"), revision=(prior or {}).get("revision", 0)+1,
                   reference="관리자 입력", checked_at=store.now(), tier="Administrator configured estimate")
        rates = [r for r in rates if r["model"] != row["model"]] + [row]
        c.execute("UPDATE settings SET value=? WHERE id='rates'", (json.dumps(rates),))
        store.audit(c, s["actor"], "rate_saved_future_requests_only", payload.model, row)
    return dict(rate=row, historical_costs_changed=False)


@app.get("/api/control/admin/audit")
def audit_log(s=Depends(permission("audit"))):
    return dict(items=store.rows("SELECT * FROM audit ORDER BY id DESC LIMIT 300"), scope="LOCAL_OPERATIONS_ONLY_NOT_PROVIDER_ACCOUNT_AUDIT")


@app.get("/api/control/admin/overview")
def overview(s=Depends(permission("health"))):
    data = corpus.load()
    return dict(source_count=sum(d["answer_count"] for d in data["documents"]), review_count=sum(d["review_count"] for d in data["documents"]),
                document_count=len(data["documents"]), approved_count=0, ktcs_applicable=False,
                cases=store.rows("SELECT state,count(*) AS count FROM cases GROUP BY state") if "cases" in ROLES[s["role"]] else [],
                jobs=store.rows("SELECT id,kind,state,progress,message,created_at FROM jobs ORDER BY created_at DESC LIMIT 5") if "jobs" in ROLES[s["role"]] else [],
                usage=meter.summary(7) if "usage" in ROLES[s["role"]] else None,
                mode="LOCAL_DEMO", production_ready=False, metering_scope="Since gateway start, not entire provider account")


@app.post("/api/control/admin/diagnostics")
async def diagnostics(s=Depends(permission("health"))):
    result = dict(database=True, corpus=False, upstream=False, supabase_checked=False, credentials_exposed=False, at=store.now())
    try:
        corpus.load()
        result["corpus"] = True
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.get(UPSTREAM + "/api/benefits/hr/capabilities")
            caps = response.json()
            result["upstream"] = response.status_code == 200 and caps.get("source_scope") == "expanded"
            result["capabilities"] = caps
    except (OSError, ValueError, httpx.HTTPError):
        pass
    with store.connect() as c:
        store.audit(c, s["actor"], "diagnostics_run", detail=result)
    return result


class Question(Strict):
    question: str = Field(min_length=2, max_length=500)


@app.post("/api/benefits/hr/answer")
async def metered_answer(payload: Question, request: Request):
    safe_text(payload.question)
    cookie = request.headers.get("cookie", "")
    headers = {"cookie": cookie, "origin": UPSTREAM}
    async with httpx.AsyncClient(timeout=540, trust_env=False) as client:
        try:
            auth = await client.get(UPSTREAM + "/api/benefits/session", headers=headers, timeout=10)
            if auth.status_code != 200 or auth.json().get("mode") != "demo":
                raise HTTPException(401, "한전 참고자료 체험 접속을 다시 시작해 주세요.")
        except httpx.HTTPError:
            raise HTTPException(503, "기존 인사 서비스 연결을 확인해 주세요.") from None
        request_id, blocked = meter.start_request()
        if blocked:
            raise HTTPException(*blocked)
        started = time.monotonic()
        try:
            upstream = await client.post(UPSTREAM + "/api/benefits/hr/answer", json=payload.model_dump(), headers=headers)
            body = upstream.json()
            meter.finish(request_id, upstream.status_code, round((time.monotonic()-started)*1000), body)
            return JSONResponse(body, status_code=upstream.status_code, headers={"X-Klink-Meter-Id": request_id})
        except (httpx.HTTPError, ValueError):
            meter.finish(request_id, 502, round((time.monotonic()-started)*1000))
            raise HTTPException(502, "답변 연결이 완료되지 않았습니다. 이미 시작한 모델 처리의 사용량은 미확인으로 남겼습니다.") from None
