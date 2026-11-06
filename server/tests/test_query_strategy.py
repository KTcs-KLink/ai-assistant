"""Regression tests for synonym resolution and source-only factual rescue.

These tests use a deterministic fake embedding encoder so the retrieval
contract is tested without a secret key or external model service.
"""
import asyncio
from array import array

import pytest

from server.query_strategy import plan_query, supports_regular_payday
from test_api import demo, login


@pytest.mark.parametrize("question", [
    "급여일이 언제야?",
    "급여일",
    "월급날은?",
    "월급은 매달 며칠 들어와?",
    "월급 입금되는 날짜 좀 알려줘",
    "월급 언제 받는 날이야?",
    "보수 지급일 알려 줘",
    "임금은 언제 입금돼?",
    "급료를 주말에 지급하면?",
    "월급날이 토요일이면 어떻게 해?",
])
def test_payday_synonyms_map_to_same_intent(question):
    plan = plan_query(question)
    assert plan.intent == "regular_payday"
    assert len(plan.variants) == 2
    assert plan.variants[0] == " ".join(question.split())


@pytest.mark.parametrize("question", [
    "퇴직금 지급일은 언제야?",
    "성과연봉 언제 지급해?",
    "급여 계산기간은 언제부터 언제까지야?",
    "급여 명세서 발급 방법 알려줘",
    "퇴직급여 지급일 알려줘",
    "성과급 지급일은?",
    "월급 계산기간 알려줘",
])
def test_different_pay_questions_are_not_forced_to_payday(question):
    assert plan_query(question).intent != "regular_payday"


@pytest.mark.parametrize("question, expected", [
    ("출장 경비는 어떻게 정산해?", "semantic:출장비"),
    ("여비 신청은?", "semantic:출장비"),
    ("남은 연차는?", "semantic:연차휴가"),
    ("사직원 양식이 필요해", "semantic:사직"),
    ("시업종업시각 알려줘", "semantic:근무시간"),
    ("신규채용 절차가 뭐야", "semantic:채용"),
    ("개인정보 침해 신고 절차", "general"),
])
def test_other_synonymous_terms_keep_original_and_add_conservative_variant(question, expected):
    plan = plan_query(question)
    assert plan.intent == expected
    assert plan.variants[0] == question


def test_direct_evidence_requires_payday_date_and_scope():
    assert supports_regular_payday(
        "제17조(지급일)",
        "제17조(지급일) 보수의 지급일은 매월 25일로 한다. "
        "다만 지급일이 토요일 또는 휴일인 경우에는 그 전일로 한다.",
    )
    assert supports_regular_payday(
        "인사관리규정 > 근로계약서 표준 양식 > 제5조(보수)",
        "⑤보수는매월25일에근로자명의예금통장에입금하되, "
        "지급일이휴일또는토요일인경우에는그전일로한다.",
    )
    assert not supports_regular_payday(
        "성과연봉 제18조(지급일)",
        "성과연봉은 지급월의 급여지급일에 지급함을 원칙으로 한다.",
    )
    assert not supports_regular_payday(
        "성과연봉",
        "성과연봉은 매월 25일 지급한다.",
    )
    assert not supports_regular_payday(
        "제5조(업무계획)",
        "매월 25일에 회의를 개최한다.",
    )
    from server.query_strategy import extract_regular_payday
    assert extract_regular_payday(
        "제17조(보수 지급)",
        "보수는 매월 25일에 지급한다. 특별수당은 매월 20일에 지급한다.",
    ) is None


def _inject_indexed_text(server, doc_id, name, section, content, vector):
    with server.database() as db:
        db.execute(
            "INSERT INTO documents(id,name,collection_id,kind,path,size,uploaded_at,status,error) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (doc_id, name, "hr", "kb", "/demo/never-open.pdf", 1, server.now(), "ready", None),
        )
        db.execute(
            "INSERT INTO chunks VALUES(?,?,?,?,?,?)",
            ("chunk-"+doc_id, doc_id, 3, section, content, array("f", vector).tobytes()),
        )


def test_grounded_payday_rescue_and_debug(demo):
    client, server = demo
    login(client)
    # Both vectors intentionally point away from the query. The anchored
    # recovery must be based on actual document text, not a hardcoded date.
    _inject_indexed_text(
        server, "pay", "연봉 및 복리후생관리규정",
        "제17조(지급일)",
        "제17조(지급일) 보수의 지급일은 매월 25일로 한다. "
        "다만 지급일이 휴일 또는 토요일인 경우에는 그 전일로 한다.",
        [0.0, 1.0],
    )
    _inject_indexed_text(
        server, "bonus", "성과연봉 시행세칙",
        "제18조(성과연봉 지급일)",
        "성과연봉은 지급월의 급여지급일에 지급함을 원칙으로 한다.",
        [0.0, 1.0],
    )

    questions = [
        "급여일이 언제야?", "월급날은?", "월급 매달 며칠 들어와?",
        "보수 지급일 알려줘", "월급날이 휴일이면?",
    ]
    for question in questions:
        audit = client.get("/api/admin/retrieval-debug", params={"question": question})
        assert audit.status_code == 200
        body = audit.json()
        assert body["readyDocuments"] == 2
        assert body["indexedChunks"] == 2
        assert body["intent"] == "regular_payday"
        assert len(body["matches"]) == 1, body
        assert body["matches"][0]["document"] == "연봉 및 복리후생관리규정"
        assert "매월 25일" in body["matches"][0]["excerpt"]

        conv = client.post("/api/conversations", json={"title": question}).json()
        response = client.post(
            f"/api/conversations/{conv['id']}/messages",
            json={"content": question, "attachment_ids": []},
        )
        assert response.status_code == 200
        assert "연봉 및 복리후생관리규정" in response.text
        assert "매월 25일" in response.text
        assert "전일에 지급" in response.text
        assert "[[c1]]" in response.text
        assert "KTcs 실제 급여일을 확정한 것은 아닙니다" in response.text

    # Unrelated query cannot be turned into a payroll-day answer.
    audit = client.get("/api/admin/retrieval-debug", params={"question": "성과연봉 언제 지급해?"})
    assert audit.json()["intent"] != "regular_payday"


def test_no_payday_in_eligible_index_means_no_fabricated_answer(demo):
    client, server = demo
    from test_api import login
    login(client)
    _inject_indexed_text(
        server, "bonus-only", "성과연봉 시행세칙",
        "제18조(성과연봉 지급일)",
        "성과연봉은 지급월의 급여지급일에 지급함을 원칙으로 한다.",
        [1.0, 0.0],
    )
    audit = client.get("/api/admin/retrieval-debug", params={"question": "급여일이 언제야?"})
    assert audit.status_code == 200
    assert audit.json()["matches"] == []
    assert audit.json()["indexedChunks"] == 1



def test_conflicting_approved_paydays_refuse_single_day(demo):
    client, server = demo
    login(client)
    _inject_indexed_text(
        server, "a", "회사 규정 A", "제17조(보수 지급일)",
        "보수는 매월 25일에 지급한다.", [1.0, 0.0],
    )
    _inject_indexed_text(
        server, "b", "회사 규정 B", "제3조(보수 지급일)",
        "보수는 매월 26일에 지급한다.", [1.0, 0.0],
    )
    conv = client.post("/api/conversations", json={"title": "급여일"}).json()
    response = client.post(
        f"/api/conversations/{conv['id']}/messages",
        json={"content": "월급날은 언제야?", "attachment_ids": []},
    )
    assert "서로 다른 급여 지급일" in response.text
    assert "매월 25일 지급합니다" not in response.text
    assert "매월 26일 지급합니다" not in response.text
