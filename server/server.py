"""K-LINK 화면과 API를 함께 띄운다. API는 팀 노션 「API 계약」 초안을 따른다.

    GET  /                                  화면 (static/index.html)
    GET  /v1/me                             본인 정보
    GET  /v1/conversations                  내 대화 목록
    POST /v1/conversations                  새 대화
    PATCH/DELETE /v1/conversations/{id}     제목 변경 / 삭제(soft)
    GET  /v1/conversations/{id}/messages    대화 메시지
    POST /v1/answers                        답변 작업 접수 (202) → 백그라운드에서 검색·생성·인용 검사
    GET  /v1/answers/{id}                   작업 상태와 결과 (화면이 2초 간격으로 조회)
    PUT/DELETE /v1/answers/{id}/feedback    답변 피드백
    GET  /v1/sources/{citation_id}          출처 상세
    GET  /healthz, /readyz                  운영 확인
    POST /api/fill                          사용자의 말 → 서류 칸 값 (계약 밖, 서류 API 확정 전 임시)

아직 계약과 다른 점
- 대화·답변·피드백은 서버 메모리에 저장한다. 서버를 끄면 사라진다. 팀 DB에 테이블이 생기면 Store만 바꾼다.
- SUPABASE_URL이 .env에 없으면 로그인 없이 개발용 사용자로 동작한다. 있으면 Bearer 토큰을 Supabase Auth로 확인하고,
  팀 DB(DATABASE_URL, 사용자 권한·RLS 적용)에서 조직 소속과 역할을 읽는다. org_admin → admin, 그 외 → member.
- 관리자 API와 문서 API(/v1/documents, /v1/admin/...)는 아직 없다.
- 계약 밖 임시 API: GET /api/config(로그인 설정), GET /v1/me/employee(서류 자동 채우기용 직원 정보),
  GET /v1/me/training-status(필수교육 미이수 알림, 이력은 data/hr_mock.json 시연용).
  GET /v1/me/hr-card(나의 인사카드: 기본정보·학력·경력·자격·교육이력).
  POST /api/minutes(회의 내용 텍스트 → 회의록 칸·요약).
- 규정 검색은 MCP 대신 knowledge-mcp 검색 모듈을 직접 부른다. mode는 qa만 지원한다.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

HERE = Path(__file__).resolve().parent
ANSWER_DIR = HERE.parent / "prototypes" / "answer"
sys.path.insert(0, str(ANSWER_DIR))

import httpx  # noqa: E402
import openai  # noqa: E402
import psycopg  # noqa: E402
from answer import (DEFAULT_MODEL, MIN_SCORE, SYSTEM_PROMPT, build_context,  # noqa: E402
                    load_search_index, validate_citations)
from dotenv import load_dotenv  # noqa: E402
from fastapi import Depends, FastAPI, Header, Query, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from employment_certificates import install_certificates
from hr_portal import Directory, install_portal  # noqa: E402
from welfare import install_welfare  # noqa: E402
from learning import LearningStore, install_learning  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

# 서버 폴더의 .env가 없으면 답변 프로토타입의 .env(OPENAI_API_KEY, SUPABASE_URL 등)를 쓰고,
# DB 접속 주소(DATABASE_URL)는 knowledge-mcp의 .env에서도 찾는다. 먼저 읽은 값이 우선한다.
load_dotenv(HERE / ".env")
load_dotenv(ANSWER_DIR / ".env")
load_dotenv(Path(os.getenv("KNOWLEDGE_MCP_DIR") or HERE.parents[1] / "knowledge-mcp") / ".env")

PROMPT_VERSION = "answer-v1"
RETRIEVER_VERSION = "bge-m3+bm25-rrf+bge-reranker-v2-m3"
CORPUS_VERSION_ID = str(uuid5(NAMESPACE_URL, "klink:corpus:local-index"))

state = {}
search_lock = threading.Lock()  # 검색 모델(GPU)은 한 번에 하나씩 쓴다.
jobs = ThreadPoolExecutor(max_workers=2)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stable_id(kind, key):
    """로컬 색인의 문자열 ID(SRC-0001 등)를 계약의 UUID로 바꾼다. 같은 입력이면 항상 같은 값이다."""
    return str(uuid5(NAMESPACE_URL, f"klink:{kind}:{key}"))


@asynccontextmanager
async def lifespan(app):
    state["model"] = os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
    state["ready"] = True
    try:
        yield
    finally:
        state["ready"] = False
        jobs.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="K-LINK", lifespan=lifespan)


# ---------------------------------------------------------------- 공통: 요청 ID, 오류 형식, 인증

def model_client():
    if not os.getenv("OPENAI_API_KEY"):
        raise ApiError(503, "model_unavailable", "OpenAI API 키를 설정하면 AI 기능을 이용할 수 있어요.")
    # 인사 포털 시작은 AI 모델, 색인, API 키에 의존하지 않는다.
    return openai.OpenAI()


class ApiError(Exception):
    def __init__(self, status, code, message, retryable=False, details=None, headers=None):
        self.status, self.code, self.message = status, code, message
        self.retryable, self.details, self.headers = retryable, details or [], headers


def error_body(request, code, message, retryable=False, details=None):
    return {"code": code, "message": message, "request_id": request.state.request_id,
            "retryable": retryable, "details": details or []}


@app.middleware("http")
async def request_id(request: Request, call_next):
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    if request.url.path.startswith("/v1"):
        response.headers["Cache-Control"] = "private, no-store"
    return response


@app.exception_handler(ApiError)
async def api_error(request, exc: ApiError):
    return JSONResponse(error_body(request, exc.code, exc.message, exc.retryable, exc.details),
                        status_code=exc.status, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc: RequestValidationError):
    details = [{"field": ".".join(str(part) for part in err["loc"][1:]) or str(err["loc"][0]),
                "reason": err["msg"]} for err in exc.errors()]
    return JSONResponse(error_body(request, "invalid_request", "요청 값을 확인해 주세요.", details=details),
                        status_code=422)


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc: StarletteHTTPException):
    code = {401: "unauthenticated", 403: "forbidden", 404: "not_found", 405: "invalid_request"}.get(
        exc.status_code, "invalid_request")
    return JSONResponse(error_body(request, code, "대상을 조회할 수 없습니다." if exc.status_code == 404
                                   else str(exc.detail)), status_code=exc.status_code)


class Database:
    """팀 Supabase Postgres에 서버가 직접 붙는다(Data API는 꺼져 있다).

    as_user()는 트랜잭션마다 role을 authenticated로 바꾸고 JWT sub를 넣어, 팀 DB의 RLS 정책이
    로그인한 사용자 기준으로 그대로 적용되게 한다. 서버 코드가 실수해도 남의 행은 보이지 않는다.
    """

    def __init__(self, url):
        self.url, self.conn, self.lock = url, None, threading.Lock()

    def as_user(self, user_id, sql, params=()):
        with self.lock:
            for attempt in (1, 2):
                try:
                    if self.conn is None or self.conn.closed:
                        self.conn = psycopg.connect(self.url, connect_timeout=10)
                    with self.conn.transaction(), self.conn.cursor() as cur:
                        cur.execute("set local role authenticated")
                        cur.execute("select set_config('request.jwt.claims', %s, true)",
                                    (json.dumps({"sub": user_id, "role": "authenticated"}),))
                        cur.execute(sql, params)
                        return cur.fetchall()
                except psycopg.OperationalError:
                    self.conn = None  # 끊긴 연결은 한 번 다시 연결해 본다.
                    if attempt == 2:
                        raise ApiError(503, "database_unavailable", "데이터베이스에 연결할 수 없습니다.", retryable=True)


database = Database(os.getenv("DATABASE_URL")) if os.getenv("DATABASE_URL") else None
ADMIN_ROLES = {"org_admin"}
token_cache = {}  # 토큰 해시 → (만료 시각, 사용자). 답변 조회가 2초마다 오므로 매번 Auth·DB를 부르지 않는다.
UNAUTHENTICATED = ("unauthenticated", "로그인이 필요하거나 세션이 만료되었습니다.")


def load_member(user_id, email):
    """조직 소속·역할·직원 정보를 그 사용자의 권한(RLS)으로 읽는다."""
    rows = database.as_user(user_id, """
        select m.id, m.organization_id,
               coalesce((select array_agg(r.role_code) from app.membership_roles r
                         where r.membership_id = m.id and r.organization_id = m.organization_id), '{}'),
               (select to_jsonb(e) from app.employee_profiles e
                where e.membership_id = m.id and e.organization_id = m.organization_id)
        from app.organization_memberships m
        where m.auth_user_id = %s and m.status = 'active'
        order by m.joined_at limit 1""", (user_id,))
    if not rows:
        raise ApiError(403, "forbidden", "초대된 조직 구성원만 사용할 수 있습니다.")
    membership_id, organization_id, roles, employee = rows[0]
    employee = employee or {}
    return {"user_id": user_id,
            "display_name": employee.get("display_name") or (email or "").split("@")[0],
            "role": "admin" if ADMIN_ROLES & set(roles) else "member",
            "membership_id": str(membership_id), "organization_id": str(organization_id),
            "roles": list(roles), "employee": employee}


def current_user(authorization: str | None = Header(None)):
    """Supabase access token을 확인하고 팀 DB에서 소속·역할을 읽는다. SUPABASE_URL이 없으면 개발용 사용자."""
    url = os.getenv("SUPABASE_URL")
    if not url:
        raise ApiError(503, "auth_unavailable", "회사 계정 로그인 설정을 확인해 주세요.")
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError(401, *UNAUTHENTICATED)
    key = hashlib.sha256(authorization.encode()).hexdigest()
    cached = token_cache.get(key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    try:
        r = httpx.get(f"{url.rstrip('/')}/auth/v1/user", timeout=10,
                      headers={"Authorization": authorization, "apikey": os.getenv("SUPABASE_ANON_KEY", "")})
    except httpx.HTTPError:
        raise ApiError(503, "auth_unavailable", "로그인 확인 서비스에 연결할 수 없습니다.", retryable=True)
    if r.status_code != 200:
        raise ApiError(401, *UNAUTHENTICATED)
    auth_user = r.json()
    if database is None:
        raise ApiError(503, "database_unavailable", "서버에 DATABASE_URL이 설정되지 않았습니다.")
    user = load_member(auth_user["id"], auth_user.get("email"))
    if len(token_cache) > 1000:
        token_cache.clear()
    token_cache[key] = (time.monotonic() + 60, user)
    return user


# ---------------------------------------------------------------- 저장소 (임시: 메모리)

class Store:
    """대화·메시지·답변·인용·피드백. 팀 DB 테이블이 생기면 이 클래스만 Supabase로 바꾼다."""

    def __init__(self):
        self.lock = threading.RLock()
        self.conversations, self.answers, self.citations, self.feedback = {}, {}, {}, {}
        self.requests = {}  # (user, 작업 종류, client_request_id) → (본문, 결과 ID)

    def idempotent(self, user, kind, client_request_id, body):
        """같은 ID·같은 본문이면 기존 결과 ID, 같은 ID·다른 본문이면 409, 처음이면 None."""
        key = (user, kind, str(client_request_id))
        if key in self.requests:
            saved_body, result_id = self.requests[key]
            if saved_body != body:
                raise ApiError(409, "idempotency_conflict", "동일 요청 ID에 다른 내용이 전달되었습니다.")
            return result_id
        return None

    def own_conversation(self, user, conversation_id):
        conversation = self.conversations.get(str(conversation_id))
        if not conversation or conversation["owner"] != user or conversation["deleted"]:
            raise ApiError(404, "not_found", "대상을 조회할 수 없습니다.")
        return conversation

    def own_answer(self, user, answer_id):
        answer = self.answers.get(str(answer_id))
        if not answer or answer["owner"] != user:
            raise ApiError(404, "not_found", "대상을 조회할 수 없습니다.")
        return answer


store = Store()


def page(items, cursor, limit):
    start = int(cursor) if cursor and cursor.isdigit() else 0
    chunk = items[start:start + limit]
    return {"items": chunk, "next_cursor": str(start + limit) if start + limit < len(items) else None}


def public(record, fields):
    return {field: record[field] for field in fields}


CONVERSATION_FIELDS = ("id", "title", "created_at", "updated_at", "pending_answer_id")
MESSAGE_FIELDS = ("id", "role", "content", "sequence", "answer_id", "access", "created_at")
ANSWER_FIELDS = ("id", "conversation_id", "input_message_id", "output_message_id", "status", "phase", "result",
                 "error", "versions", "created_at", "completed_at", "duration_ms", "request_id")


# ---------------------------------------------------------------- 사용자 · 대화

@app.get("/v1/me")
def me(user=Depends(current_user)):
    return public(user, ("user_id", "display_name", "role"))


EMPLOYEE_FIELDS = ("employee_no", "display_name", "department_name", "job_type", "position_title", "birth_date",
                   "hired_on")


HR_MOCK_PATH = HERE / "data" / "hr_mock.json"
hr_directory = Directory(Path(os.getenv("KLINK_HR_DB") or HERE / "data" / "ehr.sqlite3"), HR_MOCK_PATH)
learning_store = LearningStore(hr_directory.path, HERE / "data" / "learning_catalog.json")



def hr_record(user):
    """시연용 인사 이력(직급·승진 대상·교육 이수). 팀 DB에 테이블이 생기면 DB 조회로 바꾼다."""
    try:
        data = json.loads(HR_MOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    record = data.get((user.get("employee") or {}).get("employee_no") or "")
    auto = learning_store.completions(user)  # KT지니어스에서 자동 이수된 과정
    if not auto:
        return record
    record = dict(record or {})
    record["education"] = list(record.get("education") or []) + auto
    return record


def base_personal(user):
    personal = dict((hr_record(user) or {}).get("personal") or {})
    employee = user.get("employee") or {}
    for key in ("employment_type", "phone", "email", "address"):
        if employee.get(key) is not None:
            personal[key] = employee[key]
    return personal


def employee_profile(user):
    """팀 DB 직원 정보에, DB에 아직 칸이 없는 값을 시연용 인사기록으로 채운 사본.

    화면 표시용 직급과 입사일만 보완한다.
    """
    employee = dict(user.get("employee") or {})
    record = hr_record(user) or {}
    for key in ("grade", "hired_on"):
        if not employee.get(key):
            employee[key] = record.get(key)
    return employee


install_portal(app, current_user, ApiError, hr_directory, base_personal, employee_profile)
install_certificates(app, current_user, hr_directory, ApiError)
install_welfare(app, current_user, ApiError, hr_directory.path, hr_record, employee_profile)


@app.get("/v1/me/employee")
def my_employee(user=Depends(current_user)):
    """서류 자동 채우기용 직원 정보 (계약 밖, 서류 API 확정 전 임시). 팀 DB에 아직 없는 칸은 null.
    직급·입사일은 팀 DB에 칸이 없어 시연용 인사기록에서 가져온다(employee_profile)."""
    employee = employee_profile(user)
    result = {field: employee.get(field) for field in EMPLOYEE_FIELDS}
    result["grade"] = employee.get("grade")
    return result


# 필수교육 기준 (T-01). 근거 조항은 검색 데이터의 원문과 쪽수에 맞춘다.
MANDATORY_TRAININGS = (
    {"code": "workplace_harassment", "title": "직장 내 괴롭힘 예방교육", "cycle": "yearly", "hours": 1,
     "rule": {"doc": "취업규칙", "article": "제93조(직장 내 괴롭힘 예방교육)", "page": 12},
     "basis": "1년에 1회 이상, 1회에 1시간 이상 받아야 해요."},
    {"code": "sexual_harassment", "title": "성희롱·성폭력 예방교육", "cycle": "yearly", "hours": None,
     "rule": {"doc": "성희롱예방지침", "article": "제8조(성희롱·성폭력 예방교육)", "page": 7},
     "basis": "연 1회 이상 받아야 해요."},
    {"code": "disability_awareness", "title": "장애인 인식개선 교육", "cycle": "yearly", "hours": 1,
     "rule": {"doc": "장애인고용촉진 및 직업재활법", "article": "제5조의2(직장 내 장애인 인식개선 교육)", "page": None},
     "basis": "법정의무교육이에요. 연 1회 이상 받아야 해요."},
    {"code": "privacy", "title": "개인정보보호 교육", "cycle": "yearly", "hours": 2,
     "rule": {"doc": "개인정보 보호법", "article": "제28조(개인정보취급자에 대한 감독)", "page": None},
     "basis": "개인정보를 다루는 직원은 정기적으로 교육을 받아야 해요."},
    {"code": "promotion", "title": "승진 필수교육", "cycle": "promotion", "hours": None,
     "rule": {"doc": "인사관리규정", "article": "제35조의3(2직급 이상에의 승진시 필수교육 이수)", "page": 9},
     "basis": "2직급 이상으로 승진하려면 직급별 필수교육을 이수해야 해요."},
)
install_learning(app, current_user, ApiError, learning_store, hr_record, employee_profile, MANDATORY_TRAININGS)


def hr_history_items(employee, record, name, fields):
    """Return display fields for the authenticated employee's history, if available."""
    rows = employee.get(name)
    if not isinstance(rows, list):
        rows = record.get(name)
    return [{field: row[field] for field in fields if isinstance(row.get(field), str)}
            for row in rows if isinstance(row, dict) and any(isinstance(row.get(field), str) and row[field].strip()
                                                            for field in fields)] if isinstance(rows, list) else []


@app.get("/v1/me/hr-card")
def my_hr_card(user=Depends(current_user)):
    """나의 인사카드 (계약 밖, e-HR 직원 화면). 기본정보는 팀 DB, 나머지는 시연용 인사 데이터에서 온다.

    이력이 없으면 각 목록이 빈 배열이고 has_history=false다. 화면은 '인사팀 확인 필요'를 띄운다.
    """
    employee = user.get("employee") or {}
    record = hr_record(user) or {}
    portal_profile = user.get("portal_profile") or {}
    year = str(datetime.now(timezone(timedelta(hours=9))).year)
    trainings = sorted(record.get("education") or [], key=lambda e: e.get("completed_on") or "", reverse=True)
    this_year = [e for e in trainings if (e.get("completed_on") or "").startswith(year)]
    overseas_trips = hr_history_items(employee, record, "overseas_trips",
                                      ("country", "city", "purpose", "start_on", "end_on"))
    projects = hr_history_items(employee, record, "projects",
                                ("name", "role", "start_on", "end_on", "status", "description"))
    with hr_directory.contact_db() as db:
        personal = {**base_personal(user), **hr_directory.approved_contact(db, user)}
    return {
        "has_history": bool(record or overseas_trips or projects),
        "photo_url": employee.get("photo_url") if isinstance(employee.get("photo_url"), str) else None,
        "basic": {"employee_no": employee.get("employee_no"), "name": employee.get("display_name") or user.get("display_name"),
                  "department": employee.get("department_name"), "position": employee.get("position_title"),
                  "grade": employee.get("grade") or record.get("grade"), "job_type": employee.get("job_type"),
                  "birth_date": employee.get("birth_date"), "hired_on": employee.get("hired_on") or record.get("hired_on")},
        "personal": personal,
        "family": record.get("family") or [],
        "appointments": sorted(portal_profile.get("appointments", record.get("appointments")) or [],
                               key=lambda a: a.get("date") or "", reverse=True),
        "academic": record.get("academic") or [],
        "military": record.get("military") or {},
        "career": record.get("career") or [],
        "certificates": record.get("certificates") or [],
        "languages": record.get("languages") or [],
        "awards": record.get("awards") or [],
        "evaluations": record.get("evaluations") or [],
        "leaves": record.get("leaves") or [],
        "overseas_trips": overseas_trips,
        "projects": projects,
        "trainings": [{key: e.get(key) for key in ("title", "category", "institution", "start", "completed_on", "hours", "auto")}
                      for e in trainings],
        "summary": {"year": int(year), "year_hours": sum(e.get("hours") or 0 for e in this_year),
                    "year_count": len(this_year)},
    }


@app.get("/v1/me/leave")
def my_leave(user=Depends(current_user)):
    """인사 홈 연차 카드 (계약 밖). 팀 DB 연차 스냅숏(본인 것만, RLS)을 먼저 보고, 없으면 시연용 인사기록을 쓴다."""
    return leave_balance(user)


def leave_balance(user):
    employee = user.get("employee") or {}
    if database and employee.get("id"):
        rows = database.as_user(user["user_id"], """
            select period_start, period_end, granted_days, used_days, as_of from app.leave_balance_snapshots
            where employee_id = %s and as_of <= now() order by as_of desc limit 1""", (employee["id"],))
        if rows:
            start, end, granted, used, as_of = rows[0]
            return {"source": "db", "period_start": start.isoformat(), "period_end": end.isoformat(),
                    "granted_days": float(granted), "used_days": float(used),
                    "remaining_days": float(granted - used), "as_of": as_of.date().isoformat()}
    leave = (hr_record(user) or {}).get("leave")
    if not leave:
        return {"source": None}
    granted, used = leave["granted_days"], leave["used_days"]
    return {"source": "demo", "period_start": leave["period_start"], "period_end": leave["period_end"],
            "granted_days": granted, "used_days": used, "remaining_days": granted - used, "as_of": leave.get("as_of")}


@app.get("/v1/me/alerts")
def my_alerts(user=Depends(current_user)):
    """인사기록에서 본인이 챙겨야 할 일을 먼저 찾아 알린다 (계약 밖). 필수교육은 training-status가 따로 다룬다.

    - 연차: 남은 연차가 있고 소멸일이 60일 이내
    - 어학: 성적 유효기간 만료 또는 90일 이내 만료
    - 자격증: 취득했지만 기술정보수당 미신고
    """
    today = datetime.now(timezone(timedelta(hours=9))).date()
    record = hr_record(user) or {}
    items = []

    leave = leave_balance(user)
    if leave.get("source") and leave["remaining_days"] > 0:
        end = date.fromisoformat(leave["period_end"])
        left = (end - today).days
        if 0 <= left <= 60:
            n = leave["remaining_days"]
            n = int(n) if float(n).is_integer() else n
            items.append({"code": "leave", "title": f"연차 {n}일이 {left}일 뒤 소멸돼요",
                          "detail": f"{end.isoformat().replace('-', '.')}까지 쓰지 않으면 사라지고, 사용촉진 후에는 보상되지 않아요.",
                          "due": end.isoformat(), "action": {"kind": "form", "target": "leave", "label": "사용계획서 작성"},
                          "ref": "leave"})

    for lang in record.get("languages") or []:
        until = lang.get("valid_until")
        if not until:
            continue
        left = (date.fromisoformat(until) - today).days
        if -365 <= left <= 90:
            name = f"{lang.get('test')} {lang.get('score')}".strip()
            items.append({"code": "language", "title": f"{name} 성적이 {'만료됐어요' if left < 0 else f'{left}일 뒤 만료돼요'}",
                          "detail": f"유효기간 {until.replace('-', '.')}. 어학 요건이 필요한 인사(승진·해외연수 등)에 쓰려면 새 성적을 등록하세요.",
                          "due": until, "action": {"kind": "card", "target": "certs", "label": "자격·어학 보기"}, "ref": None})

    for cert in record.get("certificates") or []:
        if cert.get("allowance") == "미신고":
            items.append({"code": "cert", "title": f"{cert.get('name')} 기술정보수당 신고가 필요해요",
                          "detail": f"{str(cert.get('acquired_on') or '').replace('-', '.')} 취득한 자격이 아직 신고되지 않았어요.",
                          "due": None, "action": {"kind": "form", "target": "cert", "label": "신고서 작성"}, "ref": "cert"})

    order = {"leave": 0, "cert": 1, "language": 2}
    items.sort(key=lambda a: (order.get(a["code"], 9), a["due"] or "9999"))
    return {"as_of": today.isoformat(), "items": items}


NOTICES_PATH = HERE / "data" / "notices.json"


@app.get("/v1/notices")
def notices(user=Depends(current_user)):
    """인사 공지 (계약 밖, 시연용 data/notices.json). 최신순 5건."""
    try:
        items = json.loads(NOTICES_PATH.read_text(encoding="utf-8")).get("items", [])
    except (OSError, json.JSONDecodeError):
        return []
    return sorted(items, key=lambda n: n.get("date") or "", reverse=True)[:5]


@app.get("/v1/me/training-status")
def my_training_status(user=Depends(current_user)):
    """필수교육 기준과 이수 이력을 비교해 올해 미이수·승진 요건 미충족 항목을 돌려준다 (계약 밖, T-01).

    이력이 아예 없으면 has_history=false로 알려 화면이 '이력 확인 필요'를 띄우게 한다.
    """
    record = hr_record(user)
    if record is None:
        return {"has_history": False, "items": []}
    today = datetime.now(timezone(timedelta(hours=9))).date()
    done = sorted(record.get("education") or [], key=lambda e: e.get("completed_on") or "", reverse=True)
    items = []
    for rule in MANDATORY_TRAININGS:
        mine = [e for e in done if e.get("code") == rule["code"]]
        last = mine[0]["completed_on"] if mine else None
        if rule["cycle"] == "yearly":
            completed = bool(last and last.startswith(str(today.year)))
            due = f"{today.year}-12-31"
            reason = (f"{today.year}년에 이수했어요." if completed else
                      f"{today.year}년에는 아직 이수하지 않았어요." + (f" 마지막 이수: {last.replace('-', '.')}" if last else ""))
        else:
            target = record.get("promotion_target")
            if target not in ("2직급", "1직급"):
                continue  # 2직급 이상 승진 대상자만 해당한다.
            completed, due = bool(last), None
            reason = (f"{target} 승진 대상자예요. " +
                      ("필수교육을 이수했어요." if completed else "승진 전에 직급별 필수교육을 이수해야 해요."))
        items.append({"code": rule["code"], "title": rule["title"], "status": "completed" if completed else "missing",
                      "due": due, "last_completed_on": last, "reason": reason, "basis": rule["basis"],
                      "hours": rule["hours"], "rule": rule["rule"]})
    return {"has_history": True, "items": items}


@app.get("/api/config")
def config():
    """화면이 Supabase 로그인을 시작하는 데 필요한 공개 값. anon(publishable) 키는 공개용이다."""
    url = os.getenv("SUPABASE_URL")
    return {"auth": bool(url), "supabase_url": url, "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY") if url else None}


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    client_request_id: UUID


class ConversationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)


@app.get("/v1/conversations")
def list_conversations(cursor: str | None = None, limit: int = Query(20, ge=1, le=100), user=Depends(current_user)):
    with store.lock:
        mine = [c for c in store.conversations.values() if c["owner"] == user["user_id"] and not c["deleted"]]
        mine.sort(key=lambda c: c["updated_at"], reverse=True)
        return page([public(c, CONVERSATION_FIELDS) for c in mine], cursor, limit)


@app.post("/v1/conversations", status_code=201)
def create_conversation(body: ConversationCreate, user=Depends(current_user)):
    uid = user["user_id"]
    with store.lock:
        existing = store.idempotent(uid, "conversation", body.client_request_id, body.title)
        if existing:
            return public(store.conversations[existing], CONVERSATION_FIELDS)
        conversation = {"id": str(uuid4()), "title": body.title, "created_at": now(), "updated_at": now(),
                        "pending_answer_id": None, "owner": uid, "deleted": False, "messages": []}
        store.conversations[conversation["id"]] = conversation
        store.requests[(uid, "conversation", str(body.client_request_id))] = (body.title, conversation["id"])
        return public(conversation, CONVERSATION_FIELDS)


@app.patch("/v1/conversations/{conversation_id}")
def rename_conversation(conversation_id: UUID, body: ConversationUpdate, user=Depends(current_user)):
    with store.lock:
        conversation = store.own_conversation(user["user_id"], conversation_id)
        conversation.update(title=body.title, updated_at=now())
        return public(conversation, CONVERSATION_FIELDS)


@app.delete("/v1/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: UUID, user=Depends(current_user)):
    with store.lock:
        store.own_conversation(user["user_id"], conversation_id)["deleted"] = True
    return Response(status_code=204)


@app.get("/v1/conversations/{conversation_id}/messages")
def list_messages(conversation_id: UUID, cursor: str | None = None, limit: int = Query(20, ge=1, le=100),
                  user=Depends(current_user)):
    with store.lock:
        conversation = store.own_conversation(user["user_id"], conversation_id)
        return page([public(m, MESSAGE_FIELDS) for m in conversation["messages"]], cursor, limit)


# ---------------------------------------------------------------- 답변

class AnswerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: UUID
    question: str = Field(min_length=1, max_length=4000, pattern=r"\S")
    mode: Literal["qa", "summary", "compare", "procedure"]
    selected_version_ids: list[UUID] = Field(max_length=2)
    client_request_id: UUID


def add_message(conversation, role, content, answer_id):
    message = {"id": str(uuid4()), "role": role, "content": content, "sequence": len(conversation["messages"]) + 1,
               "answer_id": answer_id, "access": "available", "created_at": now()}
    conversation["messages"].append(message)
    conversation["updated_at"] = message["created_at"]
    return message


def accepted(answer):
    url = f"/v1/answers/{answer['id']}"
    return JSONResponse({"answer_id": answer["id"], "status": answer["status"], "status_url": url,
                         "request_id": answer["request_id"]}, status_code=202, headers={"Location": url})


@app.post("/v1/answers", status_code=202)
def create_answer(body: AnswerCreate, request: Request, user=Depends(current_user)):
    uid = user["user_id"]
    if len(set(body.selected_version_ids)) != len(body.selected_version_ids):
        raise ApiError(422, "invalid_request", "선택 판본을 확인해 주세요.",
                       details=[{"field": "selected_version_ids", "reason": "같은 판본을 두 번 선택할 수 없습니다."}])
    if body.mode != "qa" or body.selected_version_ids:
        # 판본 목록 API(/v1/documents)가 아직 없어 문서 선택과 요약·비교·절차 모드는 받지 않는다.
        raise ApiError(422, "invalid_request", "현재는 qa 모드와 빈 selected_version_ids만 지원합니다.",
                       details=[{"field": "mode", "reason": "summary/compare/procedure는 준비 중입니다."}])
    normalized = json.dumps({"c": str(body.conversation_id), "q": " ".join(body.question.split()), "m": body.mode})
    with store.lock:
        existing = store.idempotent(uid, "answer", body.client_request_id, normalized)
        if existing:
            return accepted(store.answers[existing])
        conversation = store.own_conversation(uid, body.conversation_id)
        pending = store.answers.get(conversation["pending_answer_id"] or "")
        if pending and pending["status"] in ("queued", "running"):
            raise ApiError(409, "conversation_busy", "이전 질문의 답변을 만드는 중입니다. 완료 후 다시 질문해 주세요.")
        answer_id = str(uuid4())
        message = add_message(conversation, "user", body.question, answer_id)
        answer = {"id": answer_id, "conversation_id": conversation["id"], "input_message_id": message["id"],
                  "output_message_id": None, "status": "queued", "phase": "queued", "result": None, "error": None,
                  "versions": {"corpus_version_id": CORPUS_VERSION_ID, "model": state["model"],
                               "prompt_version": PROMPT_VERSION, "retriever_version": RETRIEVER_VERSION},
                  "created_at": now(), "completed_at": None, "duration_ms": None,
                  "request_id": request.state.request_id, "owner": uid, "question": body.question,
                  "started": time.monotonic()}
        store.answers[answer_id] = answer
        conversation["pending_answer_id"] = answer_id
        store.requests[(uid, "answer", str(body.client_request_id))] = (normalized, answer_id)
    jobs.submit(run_answer, answer_id)
    return accepted(answer)


def make_citation(owner, label, hit):
    source = hit["source_id"]
    citation = {
        "id": str(uuid4()), "label": label,
        "child_chunk_id": stable_id("chunk", hit["chunk_id"]),
        "document_id": stable_id("document", source),
        "document_version_id": stable_id("version", source),
        "build_id": stable_id("build", source),
        "external_citation_id": hit["chunk_id"],
        "title": hit["doc_title"],
        "edition_label": "로컬 색인본",
        # 실제로 모델에 넘긴 본문 전체를 인용문으로 둔다. 따라서 '제공 본문 안의 연속 문자열' 조건을 항상 만족한다.
        "quotes": [hit["text"]],
        "location": {"article": (hit.get("heading_path") or "").split(" > ")[-1] or hit.get("article_no"),
                     "page_start": hit.get("page_start"), "page_end": hit.get("page_end"),
                     "line_start": None, "line_end": None},
        "original_verification": "unverified",
        "currency_status": "unverified",
    }
    store.citations[citation["id"]] = {"owner": owner, "citation": citation}
    return citation


MODEL_ERRORS = (
    (openai.AuthenticationError, "model_access_error", "모델 접근 권한을 확인할 수 없습니다.", False),
    (openai.PermissionDeniedError, "model_access_error", "모델 접근 권한을 확인할 수 없습니다.", False),
    (openai.RateLimitError, "model_quota", "모델 사용 한도에 도달했습니다.", True),
    (openai.APITimeoutError, "timeout", "모델 응답 시간이 초과되었습니다.", True),
    (openai.APIConnectionError, "model_network_error", "모델 연결 중 오류가 발생했습니다.", True),
)


# 직원이 흔히 쓰는 줄임말·구어체를 규정 원문 표현으로 바꿔 검색한다. 규정에는 "정보처리기사", "취득"으로 적혀 있어
# "정처기 땀"처럼 물으면 BM25·임베딩 모두 근거를 놓친다. 근본 해결은 질문 재작성(멀티쿼리)이고, 이건 자주 나오는 말만 막는다.
QUERY_ALIASES = (
    (r"정처산기", "정보처리산업기사"),
    (r"정처기", "정보처리기사"),
    (r"정보보안기사|정보보안기", "정보보안기사"),
    (r"컴활", "컴퓨터활용능력"),
    (r"외부\s*(교육|연수)", "위탁교육"),  # 규정은 "외부교육"이 아니라 "위탁교육"(인사관리규정 제64조)으로 쓴다.
    (r"(땄|땀|따냈|붙었|합격했)(어요|습니다|는데|어|음|다)?", "취득했"),
)


def normalize_query(question):
    import re
    query = question
    for pattern, replacement in QUERY_ALIASES:
        query = re.sub(pattern, replacement, query)
    return query


def run_answer(answer_id):
    """접수된 답변 작업을 처리한다: 검색(retrieval) → 생성(generation) → 인용 검사(citation_check)."""
    answer = store.answers[answer_id]

    def phase(name):
        with store.lock:
            answer.update(status="running", phase=name)

    def finish(result=None, error=None):
        with store.lock:
            conversation = store.conversations[answer["conversation_id"]]
            answer.update(status="failed" if error else "completed", phase=None, result=result, error=error,
                          completed_at=now(), duration_ms=int((time.monotonic() - answer["started"]) * 1000))
            if result:
                answer["output_message_id"] = add_message(conversation, "assistant", result["answer"], answer_id)["id"]
            if conversation["pending_answer_id"] == answer_id:
                conversation["pending_answer_id"] = None

    def fail(code, message, retryable=False):
        finish(error={"code": code, "message": message, "request_id": answer["request_id"],
                      "retryable": retryable, "details": []})

    def insufficient(text, limitation):
        finish(result={"decision": "insufficient_evidence", "answer": text, "citations": [],
                       "limitations": [limitation], "coverage": "partial", "access": "available"})

    try:
        client = model_client()
        phase("retrieval")
        query = normalize_query(answer["question"])
        with search_lock:
            if "index" not in state:
                state["index"] = load_search_index()
            hits = [hit for hit in state["index"].search(query, top_k=5) if hit["score"] >= MIN_SCORE]
        if not hits:
            return insufficient("제공된 규정에서 관련 조항을 찾지 못했습니다.",
                                "질문과 맞는 규정 조항을 찾지 못했습니다. 규정에 나올 만한 표현으로 바꿔 물어봐 주세요.")
        phase("generation")
        asked = answer["question"] if query == answer["question"] else f"{answer['question']}\n(규정 용어로 바꾸면: {query})"
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"[근거]\n{build_context(hits)}\n\n[질문]\n{asked}"}]
        try:
            response = client.chat.completions.create(model=state["model"], messages=messages)
        except openai.APIError as exc:
            for kind, code, message, retryable in MODEL_ERRORS:
                if isinstance(exc, kind):
                    return fail(code, message, retryable)
            return fail("execution_unknown", "답변 생성 중 알 수 없는 오류가 발생했습니다.")
        text = (response.choices[0].message.content or "").strip()
        phase("citation_check")
        if not text:
            return fail("generation_invalid", "답변을 만들지 못했습니다.", True)
        used, invalid = validate_citations(text, len(hits))
        if invalid:
            return fail("citation_invalid", "답변의 근거 번호를 확인하지 못했습니다.", True)
        if not used:
            return insufficient(text, "답변에 연결된 규정 조항이 없습니다. 담당 부서에 확인해 주세요.")
        with store.lock:
            citations = [make_citation(answer["owner"], n, hits[n - 1]) for n in used]
        finish(result={"decision": "answered", "answer": text, "citations": citations, "limitations": [],
                       "coverage": "partial", "access": "available"})
    except ApiError as exc:
        fail(exc.code, exc.message, exc.retryable)
    except (Exception, SystemExit):  # 검색 인덱스를 열지 못해도 포털은 계속 사용할 수 있다.
        fail("knowledge_unavailable", "근거 검색 중 오류가 발생했습니다.", True)


@app.get("/v1/answers/{answer_id}")
def get_answer(answer_id: UUID, user=Depends(current_user)):
    with store.lock:
        return public(store.own_answer(user["user_id"], answer_id), ANSWER_FIELDS)


class FeedbackBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    helpful: bool
    problem_type: Literal["incorrect", "missing_condition", "citation", "unclear", "other"] | None
    comment: str | None = Field(max_length=2000)


@app.put("/v1/answers/{answer_id}/feedback")
def put_feedback(answer_id: UUID, body: FeedbackBody, user=Depends(current_user)):
    with store.lock:
        store.own_answer(user["user_id"], answer_id)
        saved = store.feedback.get(str(answer_id)) or {"id": str(uuid4()), "answer_id": str(answer_id)}
        saved.update(helpful=body.helpful, problem_type=body.problem_type, comment=body.comment, updated_at=now())
        store.feedback[str(answer_id)] = saved
        return saved


@app.delete("/v1/answers/{answer_id}/feedback", status_code=204)
def delete_feedback(answer_id: UUID, user=Depends(current_user)):
    with store.lock:
        store.own_answer(user["user_id"], answer_id)
        if not store.feedback.pop(str(answer_id), None):
            raise ApiError(404, "not_found", "대상을 조회할 수 없습니다.")
    return Response(status_code=204)


@app.get("/v1/sources/{citation_id}")
def get_source(citation_id: UUID, user=Depends(current_user)):
    with store.lock:
        saved = store.citations.get(str(citation_id))
        if not saved or saved["owner"] != user["user_id"]:
            raise ApiError(404, "not_found", "대상을 조회할 수 없습니다.")
        return saved["citation"]


# ---------------------------------------------------------------- 운영

@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    if not state.get("ready"):
        return JSONResponse({"status": "not_ready"}, status_code=503)
    return {"status": "ok"}


# ---------------------------------------------------------------- 서류 칸 채우기 (계약 밖, 임시)

FILL_PROMPT = """당신은 사내 서류 작성 도우미입니다. 사용자의 말에서 양식 칸에 들어갈 값을 뽑아 JSON으로만 답합니다.

형식: {{"values": {{"칸 key": "값"}}, "reply": "채운 내용과 아직 필요한 내용을 한두 문장으로 안내"}}

- 사용자가 말하지 않은 값은 만들지 않습니다. 확실하지 않으면 비워 두고 reply에서 물어봅니다.
- 날짜는 YYYY-MM-DD로 씁니다. 오늘은 {today}입니다. "지난달 24일"처럼 상대적인 표현은 오늘 기준으로 바꿉니다.
- 숫자 칸(type number)은 숫자만 씁니다. "30만 원" → "300000"
- 한 표현이 여러 칸에 걸치면 나눠 넣습니다. 예: "정보처리기사" → 자격증 종목 "정보처리", 등급 "기사"
- 이미 값이 있는 칸도 사용자가 바꾸라고 하면 바꿉니다.
- 서술형 칸(type textarea: 주요 내용, 교육효과, 건의사항, 신고사유 등)은 사용자의 메모를 그대로 옮기지 않고 공문서 문장으로 다듬습니다.
  1~3문장, "~함", "~할 수 있음", "~을 건의함"처럼 명사형으로 끝냅니다. 사용자가 말하지 않은 사실(수치, 기관명, 성과)은 덧붙이지 않습니다.
  예: "엑셀 자동화 배워서 보고서 금방 써짐" → "엑셀 자동화 기법을 익혀 정기 보고서 작성 시간을 단축할 수 있음."
- "~에 추가해 줘"처럼 덧붙이라고 하면 기존 내용을 지우지 않고 뒤에 붙입니다.
- 현재 값이 "- "나 "1. " 목록으로 되어 있으면(회의록 등) 문장 수 제한 없이 그 목록 형식을 유지합니다.
- 칸 목록에 없는 key는 쓰지 않습니다.
- reply는 "~해요" 말투의 한국어로 씁니다."""


class FillRequest(BaseModel):
    form: str
    fields: list[dict]
    values: dict = {}
    message: str


@app.post("/api/fill")
def fill(body: FillRequest):
    """사용자의 말에서 양식 칸 값을 뽑는다. 내 정보(auto) 칸과 첨부 칸은 프론트에서 빼고 보낸다."""
    message = body.message.strip()
    if not message:
        raise ApiError(422, "invalid_request", "내용을 입력해 주세요.")
    allowed = {field["key"]: field for field in body.fields if field.get("key")}
    today = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
    fields = [{"key": key, "label": field.get("label"), "type": field.get("type"),
               "현재 값": body.values.get(key) or ""} for key, field in allowed.items()]
    messages = [{"role": "system", "content": FILL_PROMPT.format(today=today)},
                {"role": "user", "content": json.dumps({"양식": body.form, "칸": fields, "사용자의 말": message},
                                                       ensure_ascii=False)}]
    response = model_client().chat.completions.create(model=state["model"], messages=messages,
                                                       response_format={"type": "json_object"})
    try:
        result = json.loads(response.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        result = {}
    values = {key: str(value).strip() for key, value in (result.get("values") or {}).items()
              if key in allowed and value not in (None, "")}
    return {"values": values, "reply": result.get("reply") or ""}


# ---------------------------------------------------------------- 회의록·요약 (계약 밖, 1차: 텍스트 입력)

MINUTES_FIELDS = ("title", "date", "time", "place", "attendees", "agenda", "discussion", "decisions", "actions",
                  "summary")
MINUTES_MAX_CHARS = 60000   # 대략 1시간 30분 분량 녹취록. 넘으면 나눠서 넣어 달라고 한다.
MINUTES_CHUNK_CHARS = 12000  # 이보다 길면 부분별로 먼저 정리한 뒤 합친다.

MINUTES_PROMPT = """당신은 사내 회의록 작성 도우미입니다. 회의 내용(메모, 녹취록, 화상회의 자막)을 읽고 회의록 칸을 JSON으로만 채웁니다.

형식: {"values": {"칸 key": "값"}, "reply": "안내"}

칸:
- title: 회의명. 내용에 없으면 안건을 바탕으로 짧게 짓고, reply에서 확인을 부탁합니다.
- date: 회의 날짜 YYYY-MM-DD. 오늘은 {today}입니다. "어제", "11/18"처럼 쓰면 바꿉니다. 없으면 빈 문자열.
- time: "14:00~15:00"처럼. 시작 시각만 있으면 "14:00~". 없으면 빈 문자열.
- place: 장소. 없으면 빈 문자열.
- attendees: 참석자 "이름 직위" 쉼표로 구분. 없으면 빈 문자열.
- agenda: 안건 "1. ..." 번호 목록.
- discussion: 논의 내용 "- " 목록만 씁니다(번호 목록과 섞지 않음). 안건이 둘 이상이면 줄 앞에 "[안건 1]"처럼 붙입니다. 각 줄은 "~함", "~하기로 의견을 모음"처럼 공문서 문장으로 끝냅니다.
- decisions: 확정된 결정 사항 "- " 목록. 없으면 "결정 사항 없음".
- actions: 후속 조치 "- 할 일 (담당: 이름, 기한: YYYY-MM-DD)" 목록. 담당자나 기한이 내용에 없으면 그 자리에 "확인 필요". 없으면 "후속 조치 없음".
- summary: 회의 전체를 3줄 이내로 요약. 줄마다 "- "로 시작.

규칙:
- 회의 내용에 없는 사실(숫자, 이름, 날짜, 결정)을 만들지 않습니다.
- 숫자, 금액, 날짜, 고유명사는 원문 그대로 씁니다.
- 의견만 나오고 확정되지 않은 것은 decisions가 아니라 discussion에 둡니다.
- 인사말, 잡담, 회의와 관계없는 말은 뺍니다.
- "확인해 볼게요" 같은 맞장구나 반복되는 말은, 무엇을 할지 구체적이지 않으면 후속 조치로 넣지 않습니다.
- 개인적인 사정(건강, 가족 등)은 회의록에 옮기지 않습니다.
- reply는 비어 있는 칸과 확인이 필요한 내용을 "~해요" 말투로 한두 문장 안내합니다."""

MINUTES_NOTES_PROMPT = """긴 회의 녹취록의 일부입니다. 이 부분에서 나온 안건, 논의, 결정, 할 일(담당자·기한 포함), 날짜·장소·참석자 정보를
빠짐없이 짧은 메모로 정리합니다. 숫자와 이름은 원문 그대로 쓰고, 없는 내용은 만들지 않습니다. 인사말과 잡담은 뺍니다."""


class MinutesRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=MINUTES_MAX_CHARS)


def split_text(text, size):
    """문단 경계를 지키며 size 글자 안팎으로 나눈다. 문단 하나가 너무 길면 그 문단을 잘라 넣는다."""
    parts, current = [], ""
    for paragraph in text.split("\n"):
        while len(paragraph) > size:
            parts.append(paragraph[:size])
            paragraph = paragraph[size:]
        if len(current) + len(paragraph) + 1 > size and current:
            parts.append(current)
            current = ""
        current += paragraph + "\n"
    if current.strip():
        parts.append(current)
    return parts


@app.post("/api/minutes")
def minutes(body: MinutesRequest, user=Depends(current_user)):
    """회의 내용을 회의록 칸 값과 요약으로 정리한다. 녹음 파일(STT)은 2차에서 다룬다."""
    text = body.transcript.strip()
    if not text:
        raise ApiError(422, "invalid_request", "회의 내용을 붙여 넣어 주세요.")
    try:
        client = model_client()
        if len(text) > MINUTES_CHUNK_CHARS:
            notes = []
            for number, part in enumerate(split_text(text, MINUTES_CHUNK_CHARS), 1):
                response = client.chat.completions.create(model=state["model"], messages=[
                    {"role": "system", "content": MINUTES_NOTES_PROMPT},
                    {"role": "user", "content": part}])
                notes.append(f"[{number}부분]\n{response.choices[0].message.content or ''}")
            text = "다음은 긴 회의를 부분별로 정리한 메모입니다.\n\n" + "\n\n".join(notes)
        today = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
        response = client.chat.completions.create(
            model=state["model"], response_format={"type": "json_object"},
            messages=[{"role": "system", "content": MINUTES_PROMPT.replace("{today}", today)},
                      {"role": "user", "content": text}])
    except openai.APIError:
        raise ApiError(503, "model_unavailable", "지금은 회의록을 만들 수 없어요. 잠시 후 다시 시도해 주세요.",
                       retryable=True)
    try:
        result = json.loads(response.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        result = {}
    values = {key: str(value).strip() for key, value in (result.get("values") or {}).items()
              if key in MINUTES_FIELDS and value not in (None, "") and str(value).strip()}
    return {"values": values, "reply": result.get("reply") or ""}


@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/assistant", include_in_schema=False)
def assistant_redirect():
    return RedirectResponse("/#qa", status_code=302)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
