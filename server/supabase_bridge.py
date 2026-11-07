"""Server-only Supabase REST bridge. Never use the secret/service role for employee reads."""
from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import dotenv_values


class IntegrationUnavailable(Exception):
    pass


def settings() -> tuple[str, str]:
    path = os.getenv("KLINK_ENV_FILE")
    values = dotenv_values(Path(path)) if path and Path(path).is_file() else {}
    url = (os.getenv("SUPABASE_URL") or values.get("SUPABASE_URL") or "").rstrip("/")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY") or values.get("SUPABASE_PUBLISHABLE_KEY") or ""
    if not url.startswith("https://") or not url.endswith(".supabase.co"):
        return "", ""
    if not key.startswith(("sb_publishable_", "eyJ")):
        return "", ""
    return url, key


def call(method: str, path: str, *, token: str | None = None, payload=None, prefer=None):
    url, key = settings()
    if not url or not key:
        raise IntegrationUnavailable("Supabase 서버 설정이 필요해요.")
    headers = {"apikey": key}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if prefer:
        headers["Prefer"] = prefer
    try:
        with httpx.Client(timeout=12, follow_redirects=False) as client:
            result = client.request(method, url + path, headers=headers, json=payload)
        if result.status_code >= 300:
            # Provider bodies and exceptions may contain personal information. Never return them.
            raise IntegrationUnavailable("Supabase 인증·데이터 연결을 확인해 주세요.")
        return result.json() if result.content else None
    except (httpx.HTTPError, ValueError):
        raise IntegrationUnavailable("Supabase에 연결하지 못했어요.") from None


def connection_status() -> dict:
    if not all(settings()):
        return dict(status="not_configured", message="Supabase 서버 설정이 필요해요.")
    try:
        call("GET", "/auth/v1/settings")
    except IntegrationUnavailable:
        return dict(status="unavailable", message="Supabase 키 또는 프로젝트 접근을 확인해 주세요.")
    # REST's root OpenAPI route may return 401 even for a valid publishable key.
    # Probe only zero rows; never read an employee directory or a real profile here.
    url, key = settings()
    try:
        headers = {"apikey": key}
        if key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {key}"
        with httpx.Client(timeout=8, follow_redirects=False) as client:
            result = client.get(url + "/rest/v1/klink_benefit_profiles?select=user_id&limit=0", headers=headers)
        try:
            body = result.json()
            code = body.get("code") if isinstance(body, dict) else None
        except ValueError:
            code = None
        if result.status_code == 503:
            return dict(status="database_unavailable", auth_reachable=True, database_reachable=False,
                        error_code=code if code in {"PGRST000", "PGRST001", "PGRST002", "PGRST003"} else None,
                        message="공개 키 인증은 확인됐지만 DB 연결이 원활하지 않아요. 프로젝트 관리 설정을 확인해 주세요.")
        if code == "PGRST205":
            return dict(status="schema_required", auth_reachable=True, database_reachable=True,
                        message="인증 연결 확인 · 개인 조건 테이블 준비가 필요해요.")
        return dict(status="reachable", auth_reachable=True, database_reachable=result.status_code < 500,
                    message="인증 연결 확인 · 직원 로그인과 본인 데이터 권한 검증은 별도 필요")
    except httpx.HTTPError:
        return dict(status="database_unavailable", auth_reachable=True, database_reachable=False,
                    message="인증 연결 확인 · 데이터 저장소에 연결하지 못했어요.")


def login(email: str, password: str) -> dict:
    return call("POST", "/auth/v1/token?grant_type=password", payload=dict(email=email, password=password))


def identity(token: str) -> str:
    user = call("GET", "/auth/v1/user", token=token)
    if not user.get("id") or user.get("is_anonymous"):
        raise IntegrationUnavailable("직원 계정 인증이 필요해요.")
    return user["id"]


def get_profile(token: str, uid: str) -> dict | None:
    rows = call("GET", f"/rest/v1/klink_benefit_profiles?user_id=eq.{uid}&select=profile&limit=1", token=token)
    return rows[0]["profile"] if rows else None


def put_profile(token: str, uid: str, profile: dict):
    call("POST", "/rest/v1/klink_benefit_profiles?on_conflict=user_id", token=token,
         payload=dict(user_id=uid, profile=profile, consent_version="2026-11-07"), prefer="resolution=merge-duplicates,return=minimal")


def delete_profile(token: str, uid: str):
    call("DELETE", f"/rest/v1/klink_benefit_profiles?user_id=eq.{uid}", token=token)
