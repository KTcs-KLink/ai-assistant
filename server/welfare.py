"""복리후생 신청과 자동 심사: 출산축하금, 학자금, 경조휴가.

직원이 신청하면 규정(지식베이스에 있는 조항)과 본인 인사기록을 대조해 지급액·휴가일수와
확인할 점을 계산한다. 인사 담당자는 그 결과를 보고 승인·반려만 한다.
금액·일수는 LLM이 아니라 아래 규칙으로 계산한다(규정에 없는 값은 만들지 않는다).
"""
from __future__ import annotations

import calendar
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header
from pydantic import BaseModel, ConfigDict, Field

KST = timezone(timedelta(hours=9))
QUOTES = Path(__file__).resolve().parent / "data" / "regulation_quotes.json"


def today():
    return datetime.now(KST).date()


def with_quotes(basis, path):
    """규정 원문 인용은 저장소에 두지 않고 로컬 data/regulation_quotes.json에서 읽는다. 없으면 조항만 보여 준다."""
    try:
        quotes = json.loads(path.read_text(encoding="utf-8")).get("quotes", {})
    except (OSError, json.JSONDecodeError):
        quotes = {}
    return [{**b, "quote": quotes.get(f"{b['doc']} {b['article']}")} for b in basis]


def won(n):
    return f"{int(n):,}원"


def dot(d):
    return d.isoformat().replace("-", ".") if isinstance(d, date) else str(d or "").replace("-", ".")


BASIS = {
    "birth": [
        {"doc": "연봉 및 복리후생관리규정 시행세칙", "article": "제56조 ①", "page": "p.8"},
        {"doc": "연봉 및 복리후생관리규정 시행세칙", "article": "부칙 <2024.5.22>", "page": "부칙"},
    ],
    "tuition": [
        {"doc": "연봉 및 복리후생관리규정 시행세칙", "article": "제53조", "page": "p.8"},
        {"doc": "복지업무 실무지침", "article": "제4조", "page": "p.7"},
        {"doc": "복지업무 실무지침", "article": "제5조", "page": "p.7"},
    ],
    "condolence": [
        {"doc": "취업규칙", "article": "제30조 ①", "page": "p.5"},
        {"doc": "취업관리시행세칙", "article": "제5조 ①·⑤", "page": "p.1"},
    ],
}

CONDOLENCE = {  # 취업규칙 제30조 ① 표
    "own_wedding": ("본인 결혼", 5),
    "child_wedding": ("자녀 결혼", 1),
    "spouse_birth": ("배우자 출산", 20),
    "spouse_death": ("배우자 사망", 5),
    "parent_death": ("본인 및 배우자의 부모 사망", 5),
    "grandparent_death": ("본인 및 배우자의 조부모·외조부모 사망", 3),
    "child_death": ("자녀와 그 자녀의 배우자 사망", 3),
    "sibling_death": ("본인 및 배우자의 형제자매 사망", 3),
    "adoption": ("입양특례법에 따른 자녀 입양", 20),
}
CONDOLENCE_DOCS = {
    "own_wedding": "청첩장 또는 혼인관계증명서", "child_wedding": "청첩장 또는 혼인관계증명서",
    "spouse_birth": "출생증명서 또는 가족관계증명서", "adoption": "입양 허가·신고 서류",
}
ORDINAL = {1: "첫째", 2: "둘째", 3: "셋째", 4: "넷째", 5: "다섯째", 6: "여섯째"}
TUITION_ITEMS = ("입학금", "수업료", "육성회비", "학생회비", "실험실습비")
KINDS = {"birth": "출산축하금", "tuition": "학자금", "condolence": "경조휴가"}


class Birth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    child_name: str = Field(min_length=1, max_length=40)
    birth_date: date
    count: int = Field(1, ge=1, le=4)  # 한 번에 낳은 자녀 수


class Tuition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    child_name: str = Field(min_length=1, max_length=40)
    level: Literal["high", "univ", "overseas"]
    school: str = Field(min_length=1, max_length=80)
    term: str = Field(min_length=1, max_length=20)
    fees: dict[str, int] = Field(default_factory=dict)  # 항목명 → 원(해외는 달러)
    other_fees: int = Field(0, ge=0)  # 기숙사비 등 등록금 범위 밖


class Condolence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal[tuple(CONDOLENCE)]  # type: ignore[valid-type]
    event_date: date
    start_date: date
    days: int = Field(ge=1, le=30)
    twins: bool = False
    remote: bool = False


class WelfareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["birth", "tuition", "condolence"]
    data: dict


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    reason: str = Field("", max_length=400)


MODELS = {"birth": Birth, "tuition": Tuition, "condolence": Condolence}


def age_on(birth, on):
    b = date.fromisoformat(birth) if isinstance(birth, str) else birth
    return on.year - b.year - ((on.month, on.day) < (b.month, b.day))


def add_workdays(start, days):
    """시작일부터 토·일을 빼고 days일째 되는 날. 공휴일은 알 수 없어 담당자 확인으로 남긴다."""
    d, n = start, 0
    while True:
        if d.weekday() < 5:
            n += 1
            if n == days:
                return d
        d += timedelta(days=1)


def next_base_date(level, on):
    months = (2, 5, 8, 11) if level == "high" else (2, 8)
    for year in (on.year, on.year + 1):
        for m in months:
            d = date(year, m, calendar.monthrange(year, m)[1])
            if d >= on:
                return d


def review(kind, data, record, employee, others, on=None):
    """규칙 심사. others: 같은 직원의 다른 신청(취소·반려 제외) [(kind, data)]."""
    on = on or today()
    checks, result = [], {}

    def ok(t): checks.append({"level": "ok", "text": t})
    def warn(t): checks.append({"level": "warn", "text": t})
    def fail(t): checks.append({"level": "fail", "text": t})
    def info(t): checks.append({"level": "info", "text": t})

    family = (record or {}).get("family") or []
    children = sorted((f for f in family if f.get("relation") == "자녀" and f.get("birth_date")),
                      key=lambda f: f["birth_date"])
    hired = employee.get("hired_on")
    hired = date.fromisoformat(str(hired)[:10]) if hired else None

    if kind == "birth":
        b = Birth(**data)
        listed = next((c for c in children if c["name"] == b.child_name), None)
        older = [c for c in children if c["birth_date"] < b.birth_date.isoformat() and c is not listed]
        if listed:
            ok(f"가족사항에 등록된 자녀예요 ({b.child_name}, {dot(listed['birth_date'])}).")
            if listed["birth_date"] != b.birth_date.isoformat():
                warn(f"입력한 출생일({dot(b.birth_date)})이 가족사항({dot(listed['birth_date'])})과 달라요.")
        else:
            warn("가족사항에 아직 없는 자녀예요. 부양가족 신고(가족사항 변경)를 같이 해 주세요.")
        orders = [len(older) + 1 + i for i in range(b.count)]
        amounts = [3_000_000 if o >= 3 else 2_000_000 if o == 2 else 0 for o in orders]
        order_text = ", ".join(ORDINAL.get(o, f"{o}번째") for o in orders)
        if b.birth_date > on:
            fail("출생일이 오늘 이후예요. 출생 후에 신청할 수 있어요.")
        if b.birth_date < date(2024, 1, 1):
            fail(f"출생일({dot(b.birth_date)})이 2024.1.1. 이전이라 대상이 아니에요 (부칙 <2024.5.22>).")
        else:
            ok("2024.1.1. 이후 출생이라 적용 시점 요건을 충족해요 (부칙 <2024.5.22>).")
        if hired and b.birth_date < hired:
            fail(f"입사일({dot(hired)}) 전에 태어난 자녀는 대상이 아니에요 (부칙 <2024.5.22>).")
        elif hired:
            ok(f"입사({dot(hired)}) 후 출생이에요.")
        if sum(amounts) == 0:
            fail(f"{order_text} 자녀예요. 출산축하금은 둘째 자녀부터 지급해요.")
        else:
            ok(f"가족사항 기준 {order_text} 자녀예요" + (" (첫째는 지급 대상 아님)" if 0 in amounts else "") + ".")
        if sum(amounts) and b.count > 1:
            info("쌍둥이 이상은 자녀별로 순서를 매겨 계산했어요.")
        if any(k == "birth" and d.get("child_name") == b.child_name for k, d in others):
            fail("같은 자녀로 이미 신청한 내역이 있어요 (자녀당 1회).")
        result = {"amount": sum(amounts), "amount_text": won(sum(amounts)), "pay_type": "지급",
                  "headline": f"{order_text} 자녀 출산축하금 {won(sum(amounts))}"}
        docs = ["출생 확인 서류 (가족관계증명서 또는 출생증명서)"]

    elif kind == "tuition":
        t = Tuition(**data)
        child = next((c for c in children if c["name"] == t.child_name), None)
        if child:
            age = age_on(child["birth_date"], on)
            ok(f"가족사항에 등록된 자녀예요 ({t.child_name}, 만 {age}세).")
            if age < 14:
                fail(f"{t.child_name} 님은 만 {age}세라 고등학교·대학교 재학 연령이 아니에요. 자녀 정보를 확인해 주세요.")
        else:
            warn("가족사항에 없는 자녀예요. 직원의 자녀인지 가족관계증명서로 확인이 필요해요.")
        fees = {k: max(0, int(v or 0)) for k, v in t.fees.items() if k in TUITION_ITEMS}
        covered = sum(fees.values())
        if t.other_fees:
            warn(f"등록금 범위(입학금·수업료·육성회비·학생회비·실험실습비) 밖 금액 {t.other_fees:,}은 제외했어요.")
        if covered <= 0:
            fail("인정되는 등록금 항목 금액이 없어요.")
        base = next_base_date(t.level, on)
        if t.level == "high":
            result = {"amount": covered, "amount_text": won(covered), "pay_type": "지급 (연간 한도 내)",
                      "headline": f"고등학교 학자금 {won(covered)} 지급 신청"}
            warn("고등학교는 연간 한도(공무원 자녀학비보조수당 상한) 안에서만 지급돼요. 한도 금액은 규정집에 없어 담당자가 확인해요.")
        elif t.level == "univ":
            result = {"amount": covered, "amount_text": won(covered), "pay_type": "무이자 대부 (상환 필요)",
                      "headline": f"대학교 학자금 {won(covered)} 무이자 대부"}
            warn("대학교 학자금은 지급이 아니라 무이자 대부예요. 나중에 갚아야 해요.")
        else:
            capped = min(covered, 10_000)
            result = {"amount": capped, "amount_text": f"${capped:,}", "pay_type": "무이자 대부 (상환 필요)",
                      "headline": f"해외대학교 학자금 ${capped:,} 무이자 대부"}
            warn("해외대학교 학자금은 무이자 대부이고, 지급월 첫 근무일 환율(현찰 살 때)로 원화 환산해요.")
            if covered > 10_000:
                fail(f"연간 한도 $10,000을 넘는 ${covered - 10_000:,}은 대부할 수 없어요.")
        ok(f"다음 지급기준일은 {dot(base)}이에요. 이날 재학(입학) 중이어야 해요.")
        if any(k == "tuition" and d.get("child_name") == t.child_name and d.get("term") == t.term for k, d in others):
            fail(f"{t.child_name} 님 {t.term} 학자금은 이미 신청했어요.")
        docs = ["등록금 고지서 또는 납입영수증", "재학(입학)증명서"]

    else:
        c = Condolence(**data)
        label, base_days = CONDOLENCE[c.reason]
        if c.reason == "spouse_birth" and c.twins:
            base_days = 25
        allowed = base_days + (2 if c.remote else 0)
        end = add_workdays(c.start_date, c.days)
        if c.days > allowed:
            fail(f"{label} 휴가는 {base_days}일" + (" (+원격지 최대 2일)" if c.remote else "") + f"이에요. {c.days}일은 신청할 수 없어요.")
        else:
            ok(f"{label} 휴가 {base_days}일 중 {c.days}일 신청이에요" + (" (원격지 가산 포함 최대 " + str(allowed) + "일)" if c.remote else "") + ".")
        if c.remote:
            warn("원격지 가산은 왕복 최단 8시간 이상 걸리는 경우만 인정돼요. 담당자가 확인해요.")
        if c.reason == "own_wedding":
            if not (c.event_date <= c.start_date and end <= c.event_date + timedelta(days=90)):
                fail(f"본인 결혼 휴가는 결혼일({dot(c.event_date)})부터 90일 이내({dot(c.event_date + timedelta(days=90))}까지)에 써야 해요.")
            else:
                ok("결혼일부터 90일 이내 사용이에요.")
        elif c.reason == "spouse_birth":
            lo, hi = c.event_date - timedelta(days=30), c.event_date + timedelta(days=150 if c.twins else 120)
            if not (lo <= c.start_date and end <= hi):
                fail(f"배우자 출산 휴가는 {dot(lo)}~{dot(hi)} 안에서 써야 해요.")
            else:
                ok(f"사용 가능 기간({dot(lo)}~{dot(hi)}) 안이에요. 최대 {5 if c.twins else 3}회까지 나눠 쓸 수 있어요.")
        elif c.reason != "adoption":
            if not (c.start_date <= add_workdays(c.event_date + timedelta(days=1), 1) and end >= c.event_date):
                fail(f"경조사 휴가는 발생일({dot(c.event_date)})을 포함해 연속으로 써야 해요. 근무시간 뒤 발생했다면 다음 근무일부터 시작할 수 있어요.")
            else:
                ok("발생일을 포함한 연속 사용이에요.")
        need = {"spouse_birth": "배우자", "spouse_death": "배우자", "child_wedding": "자녀", "child_death": "자녀"}.get(c.reason)
        if need and not any(f.get("relation") == need for f in family):
            warn(f"가족사항에 {need}가 없어요. 증빙으로 관계를 확인해야 해요.")
        elif need:
            ok(f"가족사항에 {need}가 등록돼 있어요.")
        for k, d in others:
            if k != "condolence":
                continue
            s = date.fromisoformat(d["start_date"])
            e = add_workdays(s, int(d["days"]))
            if s <= end and c.start_date <= e:
                warn(f"이미 신청한 경조휴가({dot(s)}~{dot(e)})와 기간이 겹쳐요.")
        info("토·일은 일수에서 뺐어요. 공휴일이 끼면 담당자가 종료일을 조정해요.")
        result = {"days": c.days, "start": c.start_date.isoformat(), "end": end.isoformat(),
                  "pay_type": "유급 휴가",
                  "headline": f"{label} 휴가 {c.days}일 ({dot(c.start_date)}~{dot(end)})"}
        docs = [CONDOLENCE_DOCS.get(c.reason, "부고 등 경조사 확인 서류")]
        if "death" in c.reason or c.reason.endswith("wedding"):
            info("경조금(돈)은 규정집에 지급 기준이 없어 이 신청에서 계산하지 않아요.")

    levels = {c["level"] for c in checks}
    verdict = "fail" if "fail" in levels else "check" if "warn" in levels else "ok"
    summary = {"ok": "규정 요건을 모두 충족해요.", "check": "요건은 충족하지만 담당자 확인이 필요한 항목이 있어요.",
               "fail": "규정 요건을 충족하지 못한 항목이 있어요."}[verdict]
    return {"kind": kind, "title": KINDS[kind], "verdict": verdict, "summary": summary, **result,
            "checks": checks, "documents": docs, "basis": with_quotes(BASIS[kind], QUOTES), "reviewed_on": on.isoformat()}


def install_welfare(app: FastAPI, current_user, ApiError, db_path, hr_record, employee_profile):
    @contextmanager
    def connect():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(db_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                db.execute("""CREATE TABLE IF NOT EXISTS welfare_requests (
                    id INTEGER PRIMARY KEY, org TEXT NOT NULL, member TEXT NOT NULL,
                    employee TEXT, employee_name TEXT, kind TEXT NOT NULL, data TEXT NOT NULL,
                    review TEXT NOT NULL, status TEXT NOT NULL, submitted_at TEXT NOT NULL,
                    decided_at TEXT, decided_by TEXT, reason TEXT)""")
                yield db
        finally:
            db.close()

    def user_dep(authorization: str | None = Header(None)):
        return current_user(authorization)

    def reviewer(user=Depends(user_dep)):
        if user["role"] != "admin":
            raise ApiError(403, "forbidden", "인사 담당자만 심사할 수 있어요.")
        return user

    def row_out(r):
        return {"id": r["id"], "kind": r["kind"], "title": KINDS[r["kind"]], "employee": r["employee"],
                "employee_name": r["employee_name"], "data": json.loads(r["data"]), "review": json.loads(r["review"]),
                "status": r["status"], "submitted_at": r["submitted_at"], "decided_at": r["decided_at"],
                "reason": r["reason"]}

    def others_of(db, user, exclude=None):
        return [(r["kind"], json.loads(r["data"])) for r in db.execute(
            """SELECT id, kind, data FROM welfare_requests WHERE org=? AND member=?
               AND status IN ('pending','approved')""", (user["organization_id"], user["membership_id"]))
            if r["id"] != exclude]

    def run(user, body, db):
        model = MODELS[body.kind]
        try:
            data = model(**body.data).model_dump(mode="json")
        except Exception as error:  # pydantic ValidationError
            raise ApiError(422, "invalid_request", "입력값을 확인해 주세요.", details=[{"message": str(error)[:300]}])
        return data, review(body.kind, data, hr_record(user), employee_profile(user), others_of(db, user))

    @app.post("/v1/welfare/review")
    def preview(body: WelfareRequest, user=Depends(user_dep)):
        """제출 전 자동 심사 미리보기 (저장하지 않음)."""
        with connect() as db:
            return run(user, body, db)[1]

    @app.post("/v1/welfare/requests", status_code=201)
    def submit(body: WelfareRequest, user=Depends(user_dep)):
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            data, result = run(user, body, db)
            cur = db.execute("""INSERT INTO welfare_requests
                (org, member, employee, employee_name, kind, data, review, status, submitted_at)
                VALUES (?,?,?,?,?,?,?,'pending',?)""",
                (user["organization_id"], user["membership_id"], (user.get("employee") or {}).get("employee_no"),
                 user["display_name"], body.kind, json.dumps(data, ensure_ascii=False),
                 json.dumps(result, ensure_ascii=False), datetime.now(KST).isoformat()))
            return row_out(db.execute("SELECT * FROM welfare_requests WHERE id=?", (cur.lastrowid,)).fetchone())

    @app.get("/v1/welfare/requests")
    def mine(user=Depends(user_dep)):
        with connect() as db:
            return [row_out(r) for r in db.execute("""SELECT * FROM welfare_requests WHERE org=? AND member=?
                ORDER BY id DESC""", (user["organization_id"], user["membership_id"]))]

    @app.post("/v1/welfare/requests/{request_id}/cancel")
    def cancel(request_id: int, user=Depends(user_dep)):
        with connect() as db:
            done = db.execute("""UPDATE welfare_requests SET status='cancelled', decided_at=?, decided_by=?
                WHERE id=? AND org=? AND member=? AND status='pending'""",
                (datetime.now(KST).isoformat(), user["membership_id"], request_id,
                 user["organization_id"], user["membership_id"]))
            if not done.rowcount:
                raise ApiError(409, "already_decided", "이미 처리됐거나 찾을 수 없는 신청이에요.")
            return {"id": request_id, "status": "cancelled"}

    @app.get("/v1/admin/welfare")
    def queue(user=Depends(reviewer)):
        with connect() as db:
            return [row_out(r) for r in db.execute(
                "SELECT * FROM welfare_requests WHERE org=? AND status!='cancelled' ORDER BY status!='pending', id DESC",
                (user["organization_id"],))]

    @app.post("/v1/admin/welfare/{request_id}/decision")
    def decide(request_id: int, body: Decision, user=Depends(reviewer)):
        if body.decision == "rejected" and not body.reason.strip():
            raise ApiError(422, "invalid_request", "반려 사유를 입력해 주세요.")
        with connect() as db:
            done = db.execute("""UPDATE welfare_requests SET status=?, decided_at=?, decided_by=?, reason=?
                WHERE id=? AND org=? AND status='pending'""",
                (body.decision, datetime.now(KST).isoformat(), user["membership_id"], body.reason.strip(),
                 request_id, user["organization_id"]))
            if not done.rowcount:
                raise ApiError(409, "already_decided", "이미 처리됐거나 찾을 수 없는 신청이에요.")
            return {"id": request_id, "status": body.decision}
