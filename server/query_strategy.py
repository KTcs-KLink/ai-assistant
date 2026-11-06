"""Grounded Korean semantic query expansion for Dense RAG.

Retrieval enhancements never create facts or return an answer on their own:
only text already in the allowed, indexed documents can support a claim.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryPlan:
    original: str
    intent: str
    variants: tuple[str, ...]


def _text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


def _compact(value: str) -> str:
    return re.sub(r"[\W_]+", "", _text(value).lower(), flags=re.UNICODE)


def _has(value: str, expressions: tuple[str, ...]) -> bool:
    return any(re.search(pattern, value) for pattern in expressions)


def plan_query(question: str) -> QueryPlan:
    """One source-neutral expansion, plus original question as the primary Dense query.

    Use narrow intent tests. An annual bonus, salary calculation period or a
    retirement allowance date is NOT the regular payroll payment date.
    """
    original = _text(question)
    q = _compact(original)
    if not q:
        raise ValueError("empty question")

    pay_subject = _has(q, ("급여", "월급", "월급날", "보수", "봉급", "임금", "급료"))
    pay_time = _has(
        q, ("언제", "몇일", "며칠", "몇월며칠", "날짜", "급여일", "월급일", "지급일", "입금일", "월급날",
            "월급날짜", "입금되", "들어오", "받는날", "언제받", "토요일", "주말", "공휴일", "휴일"),
    )
    different_pay = _has(
        q, ("퇴직금", "퇴직급여", "성과연봉", "성과급", "상여금", "휴직급여",
            "수당지급", "지급기준", "산정기간", "계산기간", "급여명세서", "연봉인상",
            "연봉계약", "기본급얼마", "시급", "연봉얼마"),
    )
    if pay_subject and pay_time and not different_pay:
        return QueryPlan(
            original=original,
            intent="regular_payday",
            variants=(
                original,
                "정기 보수 급여 월급 지급일 매월 며칠 지급 토요일 휴일이면 전일 입금 규정",
            ),
        )

    # Lightweight, conservative vocabulary bridges. Never drop constraints
    # such as employee category, conditions or dates from the original query.
    synonyms = (
        ("출장비", ("출장경비", "여비", "출장비정산")),
        ("연차휴가", ("연차", "연차휴가", "유급휴가")),
        ("사직", ("사직원", "사직서", "퇴사절차")),
        ("근무시간", ("출퇴근시간", "시업종업시각", "출근시간")),
        ("채용", ("신입입사", "신규채용", "신규입사")),
    )
    for canonical, variants in synonyms:
        if any(_compact(x) in q for x in variants):
            expanded = f"{original} 관련 규정 업무 절차: {canonical}"
            return QueryPlan(original=original, intent=f"semantic:{canonical}", variants=(original, expanded))
    return QueryPlan(original=original, intent="general", variants=(original,))


# An eligible chunk must directly state the regular monthly payment day.
# A clause saying only "paid on payday" does not prove the actual day.
_MONTHLY_DATE = re.compile(r"(?:매월|매달|매\s*월)\s*(?:\d{1,2}\s*일)")
_PAY_VOCAB = re.compile(r"급여|보수|임금|월급|봉급")
_PAY_VERB = re.compile(r"지급|입금")


def supports_regular_payday(section: str, content: str) -> bool:
    evidence = _compact(content)
    title = _compact(section)
    if not _MONTHLY_DATE.search(evidence):
        return False
    if not (_PAY_VOCAB.search(evidence) or _PAY_VOCAB.search(title)):
        return False
    if not (_PAY_VERB.search(evidence) or _PAY_VERB.search(title)):
        return False
    # Scope restrictions prevent incidental date matches from bonuses and
    # exceptional payment schedules being mistaken for the normal payday.
    if _has(title, ("퇴직급여", "성과연봉", "상여금")):
        return False
    return True


def evidence_priority(plan: QueryPlan, section: str, content: str) -> float:
    """Positive ordering bonus based exclusively on *actual source text*."""
    if plan.intent == "regular_payday" and supports_regular_payday(section, content):
        return 1.0
    return 0.0


def has_sufficient_direct_evidence(plan: QueryPlan, results: list[dict]) -> bool:
    if plan.intent != "regular_payday":
        return bool(results)
    return any(
        supports_regular_payday(item["row"]["section"], item["row"]["content"])
        for item in results
    )
