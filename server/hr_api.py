"""HR priorities 1-6 BFF. The cookie remains scoped to /api/benefits; no keys enter clients."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import os
import unicodedata
import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import Field

try:
    from .benefits_api import current
    from . import hr_policy, hr_evidence, hr_answer, hr_forms, hr_runtime, hr_source_scope
    from .hr_policy import StrictModel
except ImportError:
    from benefits_api import current
    import hr_policy, hr_evidence, hr_answer, hr_forms, hr_runtime, hr_source_scope
    from hr_policy import StrictModel

router = APIRouter(prefix="/api/benefits/hr", tags=["hr-domain"])


@router.get("/capabilities")
def capabilities():
    return dict(app="KLINK_HR_DOMAIN", version="2026-11-07", quality_version="hr-quality-closeout-20261107",
        retrieval_mode="hybrid" if os.getenv("KLINK_HR_RETRIEVAL") == "hybrid" else "bm25",
        question_understanding="llm" if os.getenv("KLINK_HR_INTENT_MODE") == "llm" else "off",
        source_scope="expanded" if hr_source_scope.expanded() else "baseline",
        review_domains='reclassified' if os.getenv('KLINK_HR_REVIEW_DOMAINS')=='reclassified' else 'baseline',
        demo_scope="KEPCO_REFERENCE_AND_SYNTHETIC_BENEFITS", production_ready=False)


def catalog(session: dict) -> list[dict]:
    try:
        policies, approvals = (hr_policy.demo_policies(), []) if session["mode"] == "demo" else hr_policy.registry()
        company = "DEMO" if session["mode"] == "demo" else "KTCS"
        return [hr_policy.evaluate(p, session["profile"], approvals, company=company) for p in policies]
    except (OSError, ValueError, KeyError):
        raise HTTPException(503, "규정·승인 기록의 버전과 원문 무결성을 확인하지 못했어요.") from None


def plans(session: dict, cards: list[dict]) -> list[dict]:
    state, by_id = hr_runtime.state(session), {c["id"]: c for c in cards}
    for plan in state["plans"].values():
        card = by_id.get(plan["benefit_id"])
        if not card or card["policy_sha256"] != plan["policy_sha256"] or plan["conditions_revision"] != state["revision"] or card["status"] != "eligible":
            if not plan["stale"]:
                hr_runtime.record("plan_stale")
            plan.update(stale=True, checked=[])
    return deepcopy(list(state["plans"].values()))


@router.get("/catalog")
def recommendations(session=Depends(current)):
    cards, state = catalog(session), hr_runtime.state(session)
    return dict(company="DEMO" if session["mode"] == "demo" else "KTCS", synthetic=session["mode"] == "demo",
        cards=cards, counts={s: sum(c["status"] == s for c in cards) for s in ("eligible", "needs_review", "ineligible")},
        conditions_revision=state["revision"], production_eligibility_verified=bool(cards) and all(c["production_verified"] for c in cards),
        configuration_required=not cards, total_verified_amount=None, actual_submission_enabled=False,
        profile_source="consented_self_report_not_authoritative_hr", decision_scope="recommendation_only")


@router.get("/evidence")
def evidence(q: str = "병가", session=Depends(current)):
    if session["mode"] != "demo":
        raise HTTPException(403, "KTcs 직원용 승인 원문·자료 접근권한은 연결 전이에요.")
    if not 2 <= len(q.strip()) <= 500 or hr_evidence.PRIVATE.search(q):
        raise HTTPException(422, "개인정보나 키 없이 일반적인 인사 업무 검색어를 입력해 주세요.")
    try:
        return dict(**hr_evidence.summary(), results=hr_evidence.search(q, limit=5))
    except (OSError, ValueError, KeyError):
        raise HTTPException(503, "허용된 인사 원문을 확인하지 못했어요.") from None


@router.get("/sources/{source_id}")
def source(source_id: str, session=Depends(current)):
    if session["mode"] != "demo":
        raise HTTPException(403, "직원 자료 접근권한이 연결 전이에요.")
    try:
        row = hr_evidence.source(source_id)
    except (OSError, ValueError, KeyError):
        row = None
    if not row:
        raise HTTPException(404, "허용된 인사 원문이 아니거나 본문이 변경됐어요.")
    return row


@router.get("/review-evidence")
def review_evidence(q: str, category: Literal['hr_candidates','hr','non_hr','mixed','needs_review','all']='hr_candidates',session=Depends(current)):
    if session['mode'] != 'demo':
        raise HTTPException(403, '추가 검토 원문은 한전 공개자료 체험에서만 확인해요.')
    if not 2 <= len(q.strip()) <= 500 or hr_evidence.PRIVATE.search(unicodedata.normalize('NFKC',q)):
        raise HTTPException(422, '개인정보나 키 없이 일반 인사 검색어를 입력해 주세요.')
    try:
        return dict(company='KEPCO', ktcs_applicable=False, human_approved=False,
            answer_eligible=False, used_for_generation=False, method='source_only_fts5_bm25',
            domain_filter=category,domain_separation_enabled=os.getenv('KLINK_HR_REVIEW_DOMAINS')=='reclassified',
            notice='파일·문자 위치 대조만 통과한 추가 검토 원문입니다. 업무 범위·표 구조·적용 대상 확인이 남아 답변 근거로 사용하지 않습니다.',
            results=hr_evidence.review_search(q,category=category))
    except (OSError,ValueError,KeyError):
        raise HTTPException(503, '추가 검토 원문의 검증 기록을 확인하지 못했어요.') from None


class Question(StrictModel):
    question: str = Field(min_length=2, max_length=500)


@router.post("/answer")
def answer(payload: Question, session=Depends(current)):
    if session["mode"] != "demo":
        raise HTTPException(409, "직원 질문은 승인된 KTcs 자료와 조직 접근권한 연결 후 제공해요.")
    if hr_evidence.PRIVATE.search(unicodedata.normalize('NFKC',payload.question)):
        raise HTTPException(422, "개인정보나 키 없이 일반적인 인사 업무 질문을 입력해 주세요.")
    hr_runtime.limit("answer", str(id(session)), 3, 60)
    with hr_runtime.LOCK:
        state = hr_runtime.state(session)
        if state["answering"]:
            raise HTTPException(429, "이전 답변이 끝난 뒤 다시 요청해 주세요.")
        state["answering"] = True
    try:
        result = hr_answer.generate(payload.question)
        hr_runtime.record("answer_checked")
        return result
    except hr_answer.AnswerUnavailable as error:
        hr_runtime.record("answer_rejected")
        raise HTTPException(429 if error.code == "PROVIDER_RATE_LIMITED" else 503, str(error), headers={"X-Klink-RAG-Failure": error.code}) from None
    except (OSError, ValueError, KeyError):
        hr_runtime.record("answer_rejected")
        raise HTTPException(503, "근거와 인용을 확인한 인사 답변을 가져오지 못했어요. 질문 범위·허용 원문·서버 설정을 확인해 주세요.") from None
    finally:
        with hr_runtime.LOCK:
            state["answering"] = False


@router.get("/forms")
def forms(session=Depends(current)):
    try:
        return dict(forms=hr_forms.listing(), company="KTCS", actual_submission_enabled=False)
    except (OSError, ValueError):
        raise HTTPException(503, "양식의 출처·승인·파일 무결성을 확인하지 못했어요.") from None


@router.get("/forms/{form_id}/download")
def download(form_id: str, session=Depends(current)):
    if session["mode"] != "supabase":
        raise HTTPException(403, "회사 양식은 인가된 직원 계정에서만 내려받을 수 있어요.")
    try:
        item = hr_forms.verified().get(form_id)
    except (OSError, ValueError):
        item = None
    if not item:
        raise HTTPException(409, "승인된 회사 공식 빈 양식이 연결되지 않았어요.")
    return FileResponse(item[1], filename=item[0].filename, media_type="application/octet-stream", headers={"Cache-Control": "no-store"})


class Prepare(StrictModel):
    conditions_revision: str = Field(min_length=8, max_length=100)
    policy_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.get("/preparations")
def preparations(session=Depends(current)):
    return dict(plans=plans(session, catalog(session)), actual_submission_enabled=False)


@router.post("/preparations/{benefit_id}")
def prepare(benefit_id: str, payload: Prepare, session=Depends(current)):
    cards, state = catalog(session), hr_runtime.state(session)
    card = next((c for c in cards if c["id"] == benefit_id), None)
    if not card:
        raise HTTPException(404, "혜택을 찾을 수 없어요.")
    if payload.conditions_revision != state["revision"] or payload.policy_sha256 != card["policy_sha256"]:
        raise HTTPException(409, "추천 조건이나 규정이 변경됐어요. 최신 내용을 다시 확인해 주세요.")
    with hr_runtime.LOCK:
        existing = next((p for p in state["plans"].values() if p["benefit_id"] == benefit_id), None)
        if existing and (existing["stale"] or existing["policy_sha256"] != card["policy_sha256"] or existing["conditions_revision"] != state["revision"]):
            state["plans"].pop(existing["id"], None)
            existing = None
        item = existing or dict(id=secrets.token_urlsafe(16), benefit_id=benefit_id, title=card["title"],
            policy_sha256=card["policy_sha256"], policy_version=card["policy_version"], conditions_revision=state["revision"],
            checklist=card["checklist"], checked=[], stale=card["status"] != "eligible", submitted=False, form_id=card["form_id"])
        state["plans"][item["id"]] = item
    hr_runtime.record("plan_created")
    return deepcopy(item)


class Check(StrictModel):
    index: int = Field(strict=True, ge=0, le=24)
    checked: bool = Field(strict=True)


@router.patch("/preparations/{plan_id}")
def check(plan_id: str, payload: Check, session=Depends(current)):
    plans(session, catalog(session))
    state = hr_runtime.state(session)
    with hr_runtime.LOCK:
        item = state["plans"].get(plan_id)
        if not item:
            raise HTTPException(404, "본인의 준비 목록을 찾을 수 없어요.")
        if item["stale"] or payload.index >= len(item["checklist"]):
            raise HTTPException(409, "최신 조건과 규정으로 준비 목록을 다시 만들어 주세요.")
        selected = set(item["checked"])
        selected.add(payload.index) if payload.checked else selected.discard(payload.index)
        item["checked"] = sorted(selected)
        return deepcopy(item)


@router.delete("/preparations/{plan_id}", status_code=204)
def remove(plan_id: str, session=Depends(current)):
    with hr_runtime.LOCK:
        if not hr_runtime.state(session)["plans"].pop(plan_id, None):
            raise HTTPException(404, "본인의 준비 목록을 찾을 수 없어요.")


@router.post("/preparations/{plan_id}/submit")
def submit(plan_id: str, session=Depends(current)):
    if not any(p["id"] == plan_id for p in plans(session, catalog(session))):
        raise HTTPException(404, "본인의 준비 목록을 찾을 수 없어요.")
    raise HTTPException(409, "실제 신청·결재 연결과 최종 권한 검증이 완료되지 않았어요. 제출된 내용은 없습니다.")


class Preference(StrictModel):
    enabled: bool = Field(strict=True)


@router.put("/reminders")
def reminder_preference(payload: Preference, session=Depends(current)):
    with hr_runtime.LOCK:
        state = hr_runtime.state(session)
        state["reminders"] = payload.enabled
        if not payload.enabled:
            state["snapshot"] = None
    hr_runtime.record("reminders_changed")
    return dict(enabled=payload.enabled, delivery="in_app_only", external_notifications_sent=False)


@router.get("/updates")
def updates(session=Depends(current)):
    cards, state, day = catalog(session), hr_runtime.state(session), hr_policy.today()
    plans(session, cards)
    with hr_runtime.LOCK:
        if not state["reminders"]:
            return dict(enabled=False, updates=[], external_notifications_sent=False)
        previous, current_state, items = state["snapshot"] or {}, {}, []
        for c in cards:
            value = dict(status=c["status"], policy_sha256=c["policy_sha256"], deadline=c["deadline"])
            current_state[c["id"]] = value
            if c["id"] in previous and previous[c["id"]] != value:
                items.append(dict(benefit_id=c["id"], kind="conditions_or_policy_changed", message="규정 또는 내 조건이 변경돼 다시 확인이 필요해요."))
            if c["deadline"] and c["status"] != "ineligible" and 0 <= (date.fromisoformat(c["deadline"])-day).days <= 14:
                items.append(dict(benefit_id=c["id"], kind="deadline", message="신청 마감이 가까워요. 최신 조건과 일정을 확인해 주세요."))
        for removed in previous.keys()-current_state.keys():
            items.append(dict(benefit_id=removed, kind="policy_removed", message="이전에 안내한 규정을 현재 목록에서 확인할 수 없어요."))
        state["snapshot"] = current_state
    return dict(enabled=True, updates=items, synthetic=session["mode"] == "demo", external_notifications_sent=False)


@router.get("/readiness")
def readiness(session=Depends(current)):
    try:
        policies, approvals = hr_policy.registry()
        approved = sum(not hr_policy.approval_gates(p, approvals, "KTCS", hr_policy.today()) for p in policies)
        registry_valid = True
    except (OSError, ValueError):
        approved, registry_valid = 0, False
    try:
        official = len(hr_forms.verified())
    except (OSError, ValueError):
        official = 0
    try:
        research = hr_evidence.summary()
    except (OSError, ValueError, KeyError):
        research = dict(source_count=0, company="KEPCO", ktcs_applicable=False)
    if os.getenv('KLINK_HR_REVIEW_DOMAINS')=='reclassified':
        try:
            from . import hr_review_domains
            research['domain_review']=hr_review_domains.counts()
        except (OSError,ValueError):
            research['domain_review']=dict(available=False,classification_human_approved=False)
    gates = [dict(priority=1, ready=approved>0 and registry_valid, code="APPROVED_KTCS_RULES", message="승인된 현행 KTcs 규정과 조건·예외 검토가 필요해요."),
        dict(priority=2, ready=False, code="LIVE_EMPLOYEE_AUTH_RLS", message="실제 직원 계정·본인 저장·사용자 간 RLS 검증이 필요해요."),
        dict(priority=3, ready=False, code="KTCS_APPROVED_KNOWLEDGE", message="한국전력 참고 원문과 실제 KTcs 승인 원문을 구분해야 해요."),
        dict(priority=4, ready=False, code="OFFICIAL_FORMS_AND_SUBMISSION", message="회사 공식 양식과 실제 신청·결재 연결이 필요해요."),
        dict(priority=5, ready=False, code="APPROVED_CHANGE_AND_DELIVERY", message="승인된 규정·HR 변경 연동 및 운영 알림 검증이 필요해요."),
        dict(priority=6, ready=False, code="OPERATIONS_ACCEPTANCE", message="조직 인증·보존기간·감사·복구와 독립 검증이 필요해요.")]
    return dict(production_ready=all(g["ready"] for g in gates), gates=gates, approved_policy_count=approved,
        official_form_count=official, research=research, rule_registry_valid=registry_valid,
        session_access_ttl_seconds=3600, expired_session_purge_interval_seconds=60, profile_question_or_key_logged=False, aggregate_events=hr_runtime.aggregate(),
        actual_submission_enabled=False, note="기술적 구현과 조직의 운영 승인·실연결 검증은 별도입니다.")
