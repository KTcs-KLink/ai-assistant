"""Local employment certificate issuance for authenticated organization members."""
import os
from datetime import datetime
from html import escape
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from hr_portal import KST


class CertificateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    recipient: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=120)
    request_id: UUID


def certificate_html(employee, body, number, issued, confirmed):
    rows = [
        ("성명", employee.get("display_name")), ("사번", employee.get("employee_no")),
        ("소속", employee.get("department_name")), ("직위", employee.get("position_title")),
        ("입사일", str(employee.get("hired_on") or "").replace("-", ". ") or None),
        ("제출처", body.recipient), ("용도", body.purpose),
    ]
    cells = "".join(f"<tr><th>{label}</th><td>{escape(str(value or '미등록'))}</td></tr>"
                    for label, value in rows)
    statement = ("위 사람이 발급일 현재 재직 중임을 증명합니다." if confirmed else
                 "재직 상태가 등록되지 않아 인사기록 확인용으로 발급합니다.")
    return f"""<!doctype html><html lang="ko"><meta charset="utf-8"><title>재직증명서</title>
    <style>@page{{size:A4;margin:22mm}}*{{box-sizing:border-box}}
    body{{font:15px/1.55 'Malgun Gothic','Noto Sans CJK KR',sans-serif;color:#192923;margin:0}}
    header{{border-bottom:2px solid #295845;padding-bottom:12px;font-size:13px}}
    h1{{text-align:center;margin:52px 0 40px;font-size:32px;letter-spacing:6px}}
    table{{width:100%;border-collapse:collapse;table-layout:fixed}}
    th,td{{padding:12px;border-bottom:1px solid #cbd4cd;text-align:left;overflow-wrap:anywhere}}
    th{{width:25%;background:#f1f5f2}}p,footer{{text-align:center}}p{{margin:45px 0}}
    footer{{font-size:13px;color:#47554d}} </style><header>K-LINK 인사 포털 · {escape(number)}</header>
    <h1>재직증명서</h1><table>{cells}</table><p>{statement}</p>
    <footer>{issued:%Y년 %m월 %d일}<br>K-LINK 인사 포털 · 로컬 발급본 (직인 미포함)</footer></html>"""


def render_pdf(html):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        options = {}
        if not Path(playwright.chromium.executable_path).exists() and os.name == "nt":
            options["channel"] = "msedge"
        browser = playwright.chromium.launch(**options)
        try:
            page = browser.new_page()
            page.set_content(html)
            return page.pdf(prefer_css_page_size=True, print_background=True)
        finally:
            browser.close()


def install_certificates(app, current_user, directory, ApiError):
    """증명서는 인증된 직원의 회사 DB 인사정보로 발급한다."""
    route = "/v1/me/employment-certificates"

    def document(user, body, number, issued):
        employee = user.get("employee") or {}
        if not employee.get("employee_no") or not employee.get("display_name"):
            raise ApiError(422, "missing_profile", "사번과 성명이 등록된 후 발급할 수 있어요.")
        status = str(employee.get("employment_status") or "").strip().lower()
        if status and status not in {"재직", "재직중", "재직 중", "active", "employed"}:
            raise ApiError(422, "employment_status", "인사정보의 재직 상태를 확인해 주세요.")
        return certificate_html(employee, body, number, issued, bool(status))

    def scope(user):
        return user["organization_id"], user["membership_id"]

    @app.post(route + "/preview")
    def preview(body: CertificateRequest, user=Depends(current_user)):
        return {"html": document(user, body, "미리보기", datetime.now(KST))}

    @app.get(route)
    def history(user=Depends(current_user)):
        with directory.contact_db() as db:
            return [dict(row) for row in db.execute("""SELECT number, issued_at, recipient, purpose
                FROM employment_certificates WHERE org=? AND member=? ORDER BY issued_at DESC""", scope(user))]

    @app.post(route, status_code=201)
    def issue(body: CertificateRequest, user=Depends(current_user)):
        owner = scope(user)
        key = (*owner, str(body.request_id))
        existing = "SELECT number FROM employment_certificates WHERE org=? AND member=? AND request_key=?"
        with directory.contact_db() as db:
            row = db.execute(existing, key).fetchone()
            if row:
                return dict(row)
        issued = datetime.now(KST)
        number = f"HR-{issued:%Y%m%d}-{uuid4().hex[:16].upper()}"
        html = document(user, body, number, issued)
        try:
            pdf = render_pdf(html)
        except Exception as error:
            raise ApiError(503, "pdf_unavailable", "PDF를 만들 수 없어요. 서버의 Playwright와 Chromium 설치 상태를 확인해 주세요.") from error
        with directory.contact_db() as db:
            db.execute("""INSERT INTO employment_certificates
                (org,member,request_key,number,issued_at,recipient,purpose,pdf) VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(org,member,request_key) DO NOTHING""",
                (*key, number, issued.isoformat(), body.recipient, body.purpose, pdf))
            return dict(db.execute(existing, key).fetchone())

    @app.get(route + "/{number}/pdf")
    def download(number: str, user=Depends(current_user)):
        with directory.contact_db() as db:
            row = db.execute("SELECT pdf FROM employment_certificates WHERE org=? AND member=? AND number=?",
                             (*scope(user), number)).fetchone()
        if not row:
            raise ApiError(404, "not_found", "발급 내역을 찾을 수 없어요.")
        return Response(row["pdf"], media_type="application/pdf", headers={
            "Cache-Control": "private, no-store", "Content-Disposition": f'attachment; filename="{number}.pdf"'})
