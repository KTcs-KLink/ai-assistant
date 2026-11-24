"""교육 화면: 직무교육 50시간 목표, 필수교육 수강·수료, 추천교육, 이수 이력.

KT지니어스에서 수강을 시작하면 수강 기록을 남기고, 진도 100%가 되면 서버가 바로 이수 처리한다.
직원이 이수 사실을 따로 입력하지 않는다. 지금은 KT지니어스 연동 대신 시연용 강의실이
진도를 보낸다(POST .../progress). 실제 연동 시 KT지니어스 수료 통지를 같은 complete()로 받으면 된다.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header
from pydantic import BaseModel, ConfigDict, Field

KST = timezone(timedelta(hours=9))


class Progress(BaseModel):
    model_config = ConfigDict(extra="forbid")
    percent: int = Field(ge=0, le=100)


def now():
    return datetime.now(KST)


class LearningStore:
    def __init__(self, db_path, catalog_path):
        self.db_path, self.catalog_path = db_path, catalog_path

    def catalog(self):
        try:
            return json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"provider": "KT지니어스", "goal_hours": 50, "courses": []}

    @contextmanager
    def connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                db.execute("""CREATE TABLE IF NOT EXISTS learning_enrollments (
                    org TEXT NOT NULL, member TEXT NOT NULL, course_id TEXT NOT NULL, year INTEGER NOT NULL,
                    status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
                    enrolled_at TEXT NOT NULL, completed_at TEXT,
                    PRIMARY KEY (org, member, course_id, year))""")
                yield db
        finally:
            db.close()

    def enrollments(self, user, year=None):
        year = year or now().year
        with self.connect() as db:
            return {r["course_id"]: dict(r) for r in db.execute(
                "SELECT * FROM learning_enrollments WHERE org=? AND member=? AND year=?",
                (user.get("organization_id"), user.get("membership_id"), year))}

    def completions(self, user):
        """KT지니어스에서 자동 이수된 과정을 인사기록 교육 이력 형식으로 돌려준다."""
        if not user.get("membership_id"):
            return []
        courses = {c["id"]: c for c in self.catalog()["courses"]}
        provider = self.catalog().get("provider", "KT지니어스")
        out = []
        with self.connect() as db:
            for r in db.execute("""SELECT * FROM learning_enrollments WHERE org=? AND member=? AND status='completed'""",
                                (user.get("organization_id"), user.get("membership_id"))):
                c = courses.get(r["course_id"])
                if not c:
                    continue
                out.append({"code": c.get("mandatory_code"), "title": c["title"], "category": "사이버",
                            "institution": provider, "start": r["enrolled_at"][:10], "completed_on": r["completed_at"][:10],
                            "hours": c["hours"], "track": "job" if c["type"] == "job" else None,
                            "course_id": c["id"], "auto": True})
        return out


def install_learning(app: FastAPI, current_user, ApiError, store: LearningStore, hr_record, employee_profile, mandatory_rules):
    def user_dep(authorization: str | None = Header(None)):
        return current_user(authorization)

    def course_of(course_id):
        course = next((c for c in store.catalog()["courses"] if c["id"] == course_id), None)
        if not course:
            raise ApiError(404, "not_found", "과정을 찾을 수 없어요.")
        return course

    def reasons_for(course, employee, record, remaining):
        m = course.get("match") or {}
        dept, job = employee.get("department_name") or "", employee.get("job_type") or ""
        hired = employee.get("hired_on") or record.get("hired_on")
        out = []
        if dept and any(d in dept for d in m.get("departments", [])):
            out.append(f"{dept} 업무와 바로 연결되는 과정이에요.")
        if job and job in m.get("job_types", []):
            out.append(f"{job} 직군 권장 과정이에요.")
        if m.get("new_hire") and hired and (date.today() - date.fromisoformat(str(hired)[:10])).days < 366:
            out.append("입사 1년 차에게 권장하는 과정이에요.")
        certs = [c["name"] for c in record.get("certificates") or []]
        for name in m.get("certificates", []):
            if name in certs:
                out.append(f"보유 자격 {name}과 이어지는 과정이에요.")
        if out and remaining > 0:
            left = remaining - course["hours"]
            out.append(f"들으면 직무교육 목표까지 {left:g}시간 남아요." if left > 0 else "들으면 올해 직무교육 50시간을 채워요.")
        return out

    @app.get("/v1/me/learning")
    def my_learning(user=Depends(user_dep)):
        today = now().date()
        year = today.year
        cat = store.catalog()
        goal = cat.get("goal_hours", 50)
        record = hr_record(user) or {}
        employee = employee_profile(user)
        education = record.get("education") or []
        this_year = [e for e in education if (e.get("completed_on") or "").startswith(str(year))]
        job_done = sum(float(e.get("hours") or 0) for e in this_year if e.get("track") == "job")
        remaining = max(0, goal - job_done)
        enrolled = store.enrollments(user, year)
        courses = cat["courses"]

        def state(cid):
            e = enrolled.get(cid)
            if not e:
                return {"status": "not_started", "progress": 0, "enrolled_at": None}
            return {"status": "completed" if e["status"] == "completed" else "in_progress",
                    "progress": e["progress"], "enrolled_at": e["enrolled_at"][:10]}

        mandatory = []
        for rule in mandatory_rules:
            if rule["cycle"] != "yearly":
                continue
            course = next((c for c in courses if c.get("mandatory_code") == rule["code"]), None)
            done = sorted((e for e in this_year if e.get("code") == rule["code"]),
                          key=lambda e: e.get("completed_on") or "", reverse=True)
            st = state(course["id"]) if course else {"status": "not_started", "progress": 0, "enrolled_at": None}
            if done:
                st = {**st, "status": "completed", "progress": 100}
            mandatory.append({"code": rule["code"], "title": rule["title"], "due": f"{year}-12-31",
                              "hours": rule.get("hours") or (course or {}).get("hours"),
                              "basis": rule["basis"], "rule": rule["rule"],
                              "course": {k: course[k] for k in ("id", "title", "hours", "format")} if course else None,
                              "completed_on": done[0]["completed_on"] if done else None,
                              "auto": bool(done and done[0].get("auto")), **st})

        taken = {e.get("course_id") for e in this_year if e.get("course_id")}
        recommended = []
        for c in courses:
            if c["type"] != "job" or c["id"] in taken:
                continue
            reasons = reasons_for(c, employee, record, remaining)
            if not reasons:
                continue
            recommended.append({k: c.get(k) for k in ("id", "title", "hours", "format", "desc")}
                               | {"provider": cat.get("provider"), "reasons": reasons, **state(c["id"])})
        recommended.sort(key=lambda c: (c["status"] == "not_started", -len(c["reasons"])))

        history = sorted(({"title": e.get("title"), "category": e.get("category"),
                           "institution": e.get("institution"), "start": e.get("start"),
                           "completed_on": e.get("completed_on"), "hours": e.get("hours"),
                           "track": "직무" if e.get("track") == "job" else "필수" if e.get("code") else "기타",
                           "auto": bool(e.get("auto"))} for e in education),
                         key=lambda e: e["completed_on"] or "", reverse=True)
        return {"year": year, "provider": cat.get("provider"),
                "goal": {"target": goal, "done": job_done, "remaining": remaining,
                         "percent": min(100, round(job_done / goal * 100)) if goal else 100},
                "mandatory": mandatory, "recommended": recommended[:4], "history": history}

    @app.post("/v1/me/learning/{course_id}/enroll")
    def enroll(course_id: str, user=Depends(user_dep)):
        """신청·수강 시작. 이미 신청했으면 그대로 돌려준다."""
        course_of(course_id)
        with store.connect() as db:
            db.execute("""INSERT OR IGNORE INTO learning_enrollments
                (org, member, course_id, year, status, progress, enrolled_at) VALUES (?,?,?,?, 'enrolled', 0, ?)""",
                (user["organization_id"], user["membership_id"], course_id, now().year, now().isoformat()))
        return store.enrollments(user)[course_id]

    @app.post("/v1/me/learning/{course_id}/progress")
    def progress(course_id: str, body: Progress, user=Depends(user_dep)):
        """KT지니어스 진도 보고(시연용 강의실이 보냄). 100%가 되면 바로 이수 처리한다."""
        course_of(course_id)
        key = (user["organization_id"], user["membership_id"], course_id, now().year)
        with store.connect() as db:
            row = db.execute("""SELECT * FROM learning_enrollments WHERE org=? AND member=? AND course_id=? AND year=?""",
                             key).fetchone()
            if not row:
                raise ApiError(409, "not_enrolled", "먼저 수강 신청을 해 주세요.")
            if row["status"] == "completed":
                return dict(row)
            percent = max(row["progress"], body.percent)
            done = percent >= 100
            db.execute("""UPDATE learning_enrollments SET progress=?, status=?, completed_at=?
                WHERE org=? AND member=? AND course_id=? AND year=?""",
                (percent, "completed" if done else "enrolled", now().isoformat() if done else None, *key))
            return dict(db.execute("""SELECT * FROM learning_enrollments WHERE org=? AND member=? AND course_id=? AND year=?""",
                                   key).fetchone())
