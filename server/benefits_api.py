"""Isolated employee-benefit BFF. Production identities cannot enter the legacy shared chat."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from threading import RLock

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

try:
    from .benefit_rules import BenefitProfile, CATALOG, DEMO_PROFILE, catalog_item, evaluate
    from . import local_evidence, benefit_explanation, supabase_bridge as supabase
except ImportError:
    from benefit_rules import BenefitProfile, CATALOG, DEMO_PROFILE, catalog_item, evaluate
    import local_evidence
    import benefit_explanation
    import supabase_bridge as supabase

router = APIRouter(prefix="/api/benefits", tags=["benefits"])
COOKIE = "klink_benefits_session"
SESSIONS: dict[str, dict] = {}
LOCK = RLock()


def _cookie(response, token):
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=os.getenv("KLINK_SECURE_COOKIE") == "true", max_age=3600, path="/api/benefits")


def _create_session(response: Response, **attributes):
    token = secrets.token_urlsafe(36)
    with LOCK:
        expired = [k for k, v in SESSIONS.items() if v["expires"] < time.time()]
        for key in expired:
            SESSIONS.pop(key, None)
        if len(SESSIONS) >= 1000:
            raise HTTPException(503, "현재 접속자가 많아요. 잠시 후 다시 시도해 주세요.")
        session = dict(profile=BenefitProfile(), saved=set(), prepared=set(), explanations={}, explaining=set(), expires=time.time() + 3600, **attributes)
        SESSIONS[hashlib.sha256(token.encode()).hexdigest()] = session
    _cookie(response, token)
    return session


def current(request: Request):
    key = hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest()
    with LOCK:
        session = SESSIONS.get(key)
    if not session or session["expires"] < time.time():
        raise HTTPException(401, "혜택 화면에 다시 로그인해 주세요.")
    if session["mode"] == "supabase":
        try:
            if supabase.identity(session["access_token"]) != session["uid"]:
                raise supabase.IntegrationUnavailable()
        except supabase.IntegrationUnavailable:
            with LOCK:
                SESSIONS.pop(key, None)
            raise HTTPException(401, "직원 계정 인증을 다시 진행해 주세요.") from None
    return session


def public_session(session):
    return dict(mode=session["mode"], name="가상 직원" if session["mode"] == "demo" else "로그인한 직원", expires_in=3600,
                production_eligibility_verified=False)


@router.get("/config")
def config():
    return dict(demo_enabled=os.getenv("KLINK_BENEFITS_DEMO", "true") == "true",
                catalog="synthetic", production_eligibility_verified=False,
                supabase=supabase.connection_status(), local_evidence_configured=bool(local_evidence.corpus_path()),
                llm_configured=all(benefit_explanation.settings()))


@router.post("/session/demo")
def start_demo(response: Response):
    if os.getenv("KLINK_BENEFITS_DEMO", "true") != "true":
        raise HTTPException(404, "시연 모드가 비활성화되어 있어요.")
    return public_session(_create_session(response, mode="demo"))


class EmployeeLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


@router.post("/session/login")
def employee_login(payload: EmployeeLogin, response: Response):
    try:
        result = supabase.login(payload.email, payload.password)
        uid = supabase.identity(result["access_token"])
        # Only load through the employee's JWT and RLS. No service-role fallback.
        stored = supabase.get_profile(result["access_token"], uid)
        validated = BenefitProfile(**stored).consented() if stored else BenefitProfile()
        session = _create_session(response, mode="supabase", uid=uid, access_token=result["access_token"])
        session["profile"] = validated
        return public_session(session)
    except (supabase.IntegrationUnavailable, KeyError, ValueError):
        raise HTTPException(503, "직원 로그인 또는 개인 조건 저장소가 준비되지 않았어요. 계정·키·DB 권한을 확인해 주세요.") from None


@router.get("/session")
def me(session=Depends(current)):
    return public_session(session)


@router.delete("/session", status_code=204)
def logout(request: Request, response: Response):
    key = hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest()
    with LOCK:
        SESSIONS.pop(key, None)
    response.delete_cookie(COOKIE, path="/api/benefits")


@router.get("/profile")
def profile(session=Depends(current)):
    return session["profile"].consented()


@router.put("/profile")
def update_profile(payload: BenefitProfile, session=Depends(current)):
    profile = payload.consented()
    if session["mode"] == "supabase":
        try:
            supabase.put_profile(session["access_token"], session["uid"], profile.model_dump(mode="json"))
        except supabase.IntegrationUnavailable:
            raise HTTPException(503, "조건을 저장하지 못했어요. 이전 조건을 유지하고 있어요.") from None
    session["profile"] = profile
    session["prepared"].clear()
    return profile


@router.post("/profile/example")
def load_example(session=Depends(current)):
    if session["mode"] != "demo":
        raise HTTPException(403, "직원 프로필에는 예시 조건을 저장하지 않아요.")
    session["profile"] = DEMO_PROFILE.model_copy(deep=True)
    return session["profile"]


@router.delete("/profile", status_code=204)
def revoke(session=Depends(current)):
    if session["mode"] == "supabase":
        try:
            supabase.delete_profile(session["access_token"], session["uid"])
        except supabase.IntegrationUnavailable:
            raise HTTPException(503, "서버에서 동의 정보를 삭제하지 못했어요. 다시 시도해 주세요.") from None
    session["profile"] = BenefitProfile()
    session["prepared"].clear()


@router.get("/recommendations")
def recommendations(session=Depends(current)):
    cards = [evaluate(p, session["profile"], company="DEMO" if session["mode"] == "demo" else "KTCS") for p in CATALOG]
    for card in cards:
        card.update(saved=card["id"] in session["saved"], prepared=card["id"] in session["prepared"])
    return dict(mode=session["mode"], cards=cards, counts={s: sum(c["status"] == s for c in cards) for s in ("eligible", "needs_review", "ineligible")},
                production_eligibility_verified=False, total_verified_amount=None)


class Bookmark(BaseModel):
    saved: bool


@router.put("/{benefit_id}/bookmark")
def bookmark(benefit_id: str, payload: Bookmark, session=Depends(current)):
    if not catalog_item(benefit_id):
        raise HTTPException(404, "혜택을 찾을 수 없어요.")
    if payload.saved:
        session["saved"].add(benefit_id)
    else:
        session["saved"].discard(benefit_id)
    return dict(saved=payload.saved)


@router.post("/{benefit_id}/prepare")
def prepare(benefit_id: str, session=Depends(current)):
    policy = catalog_item(benefit_id)
    if not policy:
        raise HTTPException(404, "혜택을 찾을 수 없어요.")
    card = evaluate(policy, session["profile"], company="DEMO" if session["mode"] == "demo" else "KTCS")
    # Re-evaluate on the server, never trust the status shown before a profile change.
    if card["status"] != "eligible" or session["mode"] != "demo":
        raise HTTPException(409, "조건을 먼저 확인해 주세요. 실제 신청은 아직 연결되지 않았어요.")
    session["prepared"].add(benefit_id)
    return dict(status="demo_preparation_only", checklist=policy["checklist"], submitted=False,
                message="준비 목록을 저장했어요. 실제 신청·결재가 제출되지 않았어요.")


@router.post("/{benefit_id}/explanation")
def explain(benefit_id: str, session=Depends(current)):
    policy = catalog_item(benefit_id)
    if not policy:
        raise HTTPException(404, "혜택을 찾을 수 없어요.")
    if session["mode"] != "demo":
        raise HTTPException(409, "승인된 회사 규정이 연결된 뒤 이용할 수 있어요.")
    with LOCK:
        if benefit_id in session["explanations"]:
            return session["explanations"][benefit_id]
        if session["explaining"]:
            raise HTTPException(429, "진행 중인 규정 설명이 끝난 뒤 다시 요청해 주세요.")
        if session.get("last_explanation", 0) > time.time() - 10:
            raise HTTPException(429, "잠시 후 다른 규정 설명을 요청해 주세요.")
        session["explaining"].add(benefit_id)
        session["last_explanation"] = time.time()
    try:
        result = benefit_explanation.generate(policy)
        session["explanations"][benefit_id] = result
        return result
    except benefit_explanation.ExplanationUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
    finally:
        with LOCK:
            session["explaining"].discard(benefit_id)


@router.get("/evidence/search")
def evidence_search(q: str = "복지", session=Depends(current)):
    if not 2 <= len(q.strip()) <= 100:
        raise HTTPException(400, "검색어는 2~100자로 입력해 주세요.")
    # The local corpus is a research demo, never a live employee's authorized knowledge base.
    if session["mode"] != "demo":
        raise HTTPException(403, "직원 계정의 자료 접근 범위가 아직 연결되지 않았어요.")
    return local_evidence.search(q)


@router.get("/evidence/{source_id}")
def evidence_source(source_id: str, session=Depends(current)):
    if session["mode"] != "demo":
        raise HTTPException(403, "자료 접근 범위를 확인해 주세요.")
    row = local_evidence.source(source_id)
    if not row:
        raise HTTPException(404, "허용된 원문이 아니거나 원문 해시가 일치하지 않아요.")
    return row
