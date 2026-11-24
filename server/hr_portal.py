"""Staff portal and isolated, persistent demo directory."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import Depends, FastAPI, Header
from pydantic import BaseModel, ConfigDict, Field

KST = timezone(timedelta(hours=9))
def today():
    return datetime.now(KST).date()


class ContactUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=160)
    address: str = Field(default="", max_length=240)


class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    effective_on: date
    kind: Literal["부서 이동", "승진", "보직 변경"]
    department: str = Field(min_length=1, max_length=80)
    position: str = Field(min_length=1, max_length=80)
    grade: str = Field(min_length=1, max_length=40)
    note: str = Field(default="", max_length=400)


class ContactDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    decision: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=400)


def seed_profiles(mock_path):
    records = json.loads(mock_path.read_text(encoding="utf-8")) if mock_path.exists() else {}
    entries = (
        ("DEV-0001", "김하늘", "정보통신처", "차장", "3직급", "2012-03-01", "1988-03-15"),
        ("DEV-0002", "이서윤", "고객지원팀", "대리", "5직급", "2021-07-01", "1995-09-18"),
        ("DEV-0090", "박지민", "인사팀", "팀장", "2직급", "2011-02-01", "1987-05-10"),
    )
    for no, name, dept, position, grade, hired_on, birth in entries:
        record = records.get(no, {})
        contact = record.get("personal") or {}
        profile = {
            "basic": {"employee_no": no, "name": name, "department": dept, "position": position,
                      "grade": record.get("grade") or grade, "job_type": "사무", "birth_date": birth,
                      "hired_on": record.get("hired_on") or hired_on, "status": "재직"},
            "personal": {"employment_type": contact.get("employment_type") or "정규직",
                         "phone": "010-0000-" + no[-4:], "email": no.lower() + "@example.test",
                         "address": "서울특별시 (시연용 주소)"},
            "appointments": [{**entry, "note": ""} for entry in record.get("appointments", [])],
            **{key: record.get(key, []) for key in ("academic", "career", "certificates", "languages", "awards", "leaves", "family")},
            "trainings": record.get("education", []),
        }
        yield no, profile


class Directory:
    def __init__(self, path, mock_path):
        self.path = path
        self.mock_path = mock_path

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                db.execute("CREATE TABLE IF NOT EXISTS employees (number TEXT PRIMARY KEY, profile TEXT NOT NULL)")
                db.execute("""CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY, employee TEXT NOT NULL REFERENCES employees(number),
                    effective_on TEXT NOT NULL, data TEXT NOT NULL, created_by TEXT NOT NULL)""")
                db.execute("""CREATE TABLE IF NOT EXISTS contact_requests (
                    id INTEGER PRIMARY KEY, employee TEXT NOT NULL REFERENCES employees(number),
                    submitted_at TEXT NOT NULL, changes TEXT NOT NULL, status TEXT NOT NULL,
                    decided_at TEXT, decided_by TEXT, reason TEXT)""")
                db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_pending_contact_request
                    ON contact_requests(employee) WHERE status = 'pending'""")
                if not db.execute("SELECT 1 FROM employees LIMIT 1").fetchone():
                    db.executemany("INSERT OR IGNORE INTO employees VALUES (?, ?)",
                                   [(no, json.dumps(profile, ensure_ascii=False)) for no, profile in seed_profiles(self.mock_path)])
                yield db
        finally:
            db.close()

    @staticmethod
    def read(db, number, include_pending=False):
        row = db.execute("SELECT profile FROM employees WHERE number = ?", (number,)).fetchone()
        if row is None:
            return None
        profile = json.loads(row["profile"])
        as_of = today().isoformat()
        rows = db.execute("""SELECT id, effective_on, data FROM appointments WHERE employee = ?
                             ORDER BY effective_on, id""", (number,)).fetchall()
        history = [{**entry, "status": "반영 완료"} for entry in profile.get("appointments", [])]
        job = profile["basic"]
        scheduled_job = {key: job[key] for key in ("department", "position", "grade")}
        for entry in rows:
            change = json.loads(entry["data"])
            pending = entry["effective_on"] > as_of
            before = scheduled_job.copy()
            scheduled_job.update({key: change[key] for key in before})
            if not pending:
                job.update(scheduled_job)
            if include_pending or not pending:
                history.append({"id": entry["id"], "date": entry["effective_on"], "type": change["kind"],
                                "dept": change["department"], "position": change["position"],
                                "grade": change["grade"], "before_department": before["department"],
                                "before_position": before["position"], "before_grade": before["grade"],
                                "status": "예정" if pending else "반영 완료",
                                "note": change["note"] if include_pending else ""})
        profile["appointments"] = sorted(history, key=lambda entry: entry.get("date") or "", reverse=True)
        return profile


    @contextmanager
    def contact_db(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                db.execute("""CREATE TABLE IF NOT EXISTS staff_contact_requests (
                    id INTEGER PRIMARY KEY, org TEXT NOT NULL, member TEXT NOT NULL,
                    employee TEXT, employee_name TEXT, submitted_at TEXT NOT NULL,
                    changes TEXT NOT NULL, status TEXT NOT NULL, decided_at TEXT,
                    decided_by TEXT, reason TEXT)""")
                db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS staff_pending_contact
                    ON staff_contact_requests(org, member) WHERE status='pending'""")
                db.execute("""CREATE TABLE IF NOT EXISTS employment_certificates (
                    org TEXT NOT NULL, member TEXT NOT NULL, request_key TEXT NOT NULL,
                    number TEXT PRIMARY KEY, issued_at TEXT NOT NULL, recipient TEXT NOT NULL,
                    purpose TEXT NOT NULL, pdf BLOB NOT NULL, UNIQUE(org,member,request_key))""")
                yield db
        finally:
            db.close()

    @staticmethod
    def approved_contact(db, user):
        values = {}
        for row in db.execute("""SELECT changes FROM staff_contact_requests
                WHERE org=? AND member=? AND status='approved' ORDER BY id""",
                (user["organization_id"], user["membership_id"])):
            values.update(json.loads(row["changes"]))
        return values


def install_portal(app: FastAPI, current_user, ApiError, directory: Directory, base_personal, employee_profile=None):
    """employee_profile(user): DB에 없는 직급·입사일·재직 상태를 채운 직원 정보. 없으면 DB 값만 쓴다."""
    def employee_of(user):
        return employee_profile(user) if employee_profile else (user.get("employee") or {})

    def demo_only():
        # The local workflow store has no company-account linkage and is disabled.
        raise ApiError(404, "not_found", "이 환경에서 사용할 수 없는 기능입니다.")

    def portal_user(authorization: str | None = Header(None)):
        return current_user(authorization)

    def demo_admin(user=Depends(portal_user)):
        demo_only()
        if user["role"] != "admin":
            raise ApiError(403, "forbidden", "인사 담당자만 사용할 수 있어요.")
        return user

    def require_employee(db, number, admin=False):
        profile = directory.read(db, number, include_pending=admin)
        if profile is None:
            raise ApiError(404, "not_found", "직원을 찾을 수 없어요.")
        return profile

    @app.get("/v1/hr/me")
    def my_profile(user=Depends(portal_user)):
        employee = employee_of(user)
        profile = {
            "basic": {"employee_no": employee.get("employee_no"),
                      "name": employee.get("display_name") or user["display_name"],
                      "department": employee.get("department_name"), "position": employee.get("position_title"),
                      "grade": employee.get("grade"), "job_type": employee.get("job_type"),
                      "birth_date": employee.get("birth_date"), "hired_on": employee.get("hired_on"),
                      "status": employee.get("employment_status")},
            "personal": {key: employee.get(key) for key in ("employment_type", "phone", "email", "address")},
        }
        with directory.contact_db() as db:
            profile["personal"].update(base_personal(user))
            profile["personal"].update(directory.approved_contact(db, user))
        return {"profile": profile, "demo": False, "can_manage": False,
                "role": user["role"], "as_of": today().isoformat()}

    @app.get("/v1/hr/employees")
    def employees(user=Depends(demo_admin)):
        with directory.connect() as db:
            numbers = [row["number"] for row in db.execute("SELECT number FROM employees ORDER BY number")]
            return [require_employee(db, number)["basic"] for number in numbers]

    @app.get("/v1/hr/employees/{number}")
    def employee(number: str, user=Depends(demo_admin)):
        with directory.connect() as db:
            return require_employee(db, number, admin=True)

    @app.patch("/v1/hr/employees/{number}/contact")
    def update_contact(number: str, body: ContactUpdate, user=Depends(demo_admin)):
        with directory.connect() as db:
            db.execute("UPDATE employees SET profile = json_set(profile, '$.personal.phone', ?, "
                       "'$.personal.email', ?, '$.personal.address', ?) WHERE number = ?",
                       (body.phone, body.email, body.address, number))
            return require_employee(db, number, admin=True)

    @app.post("/v1/hr/employees/{number}/appointments", status_code=201)
    def create_appointment(number: str, body: AppointmentCreate, user=Depends(demo_admin)):
        if body.effective_on < today():
            raise ApiError(422, "invalid_request", "적용일은 오늘 이후 날짜를 선택해 주세요.")
        with directory.connect() as db:
            require_employee(db, number, admin=True)
            db.execute("INSERT INTO appointments (employee, effective_on, data, created_by) VALUES (?, ?, ?, ?)",
                       (number, body.effective_on.isoformat(), body.model_dump_json(), user["number"]))
            return require_employee(db, number, admin=True)

    @app.get("/v1/hr/organization")
    def organization(user=Depends(portal_user)):
        demo_only()
        with directory.connect() as db:
            numbers = [row["number"] for row in db.execute("SELECT number FROM employees ORDER BY number")]
            display_fields = ("name", "department", "position", "grade")
            return [{key: require_employee(db, number)["basic"].get(key) for key in display_fields}
                    for number in numbers]

    def reviewer(user=Depends(portal_user)):
        if user["role"] != "admin":
            raise ApiError(403, "forbidden", "조직 관리자만 심사할 수 있어요.")
        return user

    def requests_for(db, user, own=True):
        sql = """SELECT id, employee, employee_name, submitted_at, changes, status, decided_at, reason
                 FROM staff_contact_requests WHERE org=?"""
        args = [user["organization_id"]]
        if own:
            sql += " AND member=?"
            args.append(user["membership_id"])
        return [{**dict(r), "changes": json.loads(r["changes"])}
                for r in db.execute(sql + " ORDER BY id DESC", args)]

    @app.get("/v1/hr/me/contact-requests")
    def own_contact_requests(user=Depends(portal_user)):
        with directory.contact_db() as db:
            return requests_for(db, user)

    @app.post("/v1/hr/me/contact-requests", status_code=201)
    def request_contact(body: ContactUpdate, user=Depends(portal_user)):
        with directory.contact_db() as db:
            db.execute("BEGIN IMMEDIATE")
            current = {**base_personal(user), **directory.approved_contact(db, user)}
            changes = {k: v for k, v in body.model_dump(exclude_unset=True).items()
                       if v != (current.get(k) or "")}
            if not changes:
                raise ApiError(422, "no_changes", "변경할 내용을 입력해 주세요.")
            try:
                db.execute("""INSERT INTO staff_contact_requests
                    (org,member,employee,employee_name,submitted_at,changes,status)
                    VALUES (?,?,?,?,?,?,'pending')""",
                    (user["organization_id"], user["membership_id"],
                     (user.get("employee") or {}).get("employee_no"), user["display_name"],
                     datetime.now(KST).isoformat(), json.dumps(changes, ensure_ascii=False)))
            except sqlite3.IntegrityError:
                raise ApiError(409, "pending_request", "처리 대기 중인 변경 신청이 있어요.")
            return requests_for(db, user)[0]

    @app.post("/v1/hr/me/contact-requests/{request_id}/cancel")
    def cancel_contact(request_id: int, user=Depends(portal_user)):
        owner = (request_id, user["organization_id"], user["membership_id"])
        with directory.contact_db() as db:
            updated = db.execute("""UPDATE staff_contact_requests
                SET status='cancelled', decided_at=?, decided_by=?
                WHERE id=? AND org=? AND member=? AND status='pending'""",
                (datetime.now(KST).isoformat(), user["membership_id"], *owner))
            if not updated.rowcount:
                row = db.execute("""SELECT status FROM staff_contact_requests
                    WHERE id=? AND org=? AND member=?""", owner).fetchone()
                if not row:
                    raise ApiError(404, "not_found", "신청을 찾을 수 없어요.")
                if row["status"] != "cancelled":
                    raise ApiError(409, "already_decided", "이미 처리된 신청이에요. 최신 상태를 확인해 주세요.")
            return {"id": request_id, "status": "cancelled"}

    @app.get("/v1/hr/contact-requests")
    def review_queue(user=Depends(reviewer)):
        with directory.contact_db() as db:
            return requests_for(db, user, own=False)

    @app.post("/v1/hr/contact-requests/{request_id}/decision")
    def review_contact(request_id: int, body: ContactDecision, user=Depends(reviewer)):
        if body.decision == "rejected" and not body.reason:
            raise ApiError(422, "invalid_request", "반려 사유를 입력해 주세요.")
        with directory.contact_db() as db:
            result = db.execute("""UPDATE staff_contact_requests
                SET status=?, decided_at=?, decided_by=?, reason=?
                WHERE org=? AND id=? AND status='pending'""",
                (body.decision, datetime.now(KST).isoformat(), user["membership_id"],
                 body.reason, user["organization_id"], request_id))
            if not result.rowcount:
                raise ApiError(409, "already_decided", "이미 처리됐거나 찾을 수 없는 신청입니다.")
            return {"id": request_id, "status": body.decision}

    return portal_user
