"""Supabase routing/search tests: no DB credentials, model download or paid API."""
import asyncio

import pytest

from server import supabase_rag as rag


def row(cid: str, section: str, content: str, score: float):
    return {
        "id": cid, "document_id": "SRC-0007", "name": "인사관리규정",
        "section": section, "content": content, "page": None,
        "score": score, "kind": "kb", "domain": "hr",
    }


def test_supabase_is_opt_in(monkeypatch):
    monkeypatch.delenv("KLINK_RAG_BACKEND", raising=False)
    assert not rag.enabled()
    monkeypatch.setenv("KLINK_RAG_BACKEND", "supabase")
    assert rag.enabled()


def test_no_db_query_without_explicit_credentials(monkeypatch):
    monkeypatch.delenv("KLINK_PG_DSN", raising=False)
    with pytest.raises(RuntimeError, match="KLINK_PG_DSN"):
        rag._dsn()


def test_anchored_payday_only_uses_real_clauses(monkeypatch):
    legitimate = row(
        "SRC-0007-c0315", "제5조(보수)",
        "⑤보수는매월25일에근로자명의예금통장에입금하되,"
        "지급일이휴일또는토요일인경우에는그전일로한다.", 0.41,
    )
    misleading = row(
        "SRC-0001-c0010", "제18조(성과연봉 지급일)",
        "성과연봉은 지급월의 급여지급일에 지급함을 원칙으로 한다.", 0.93,
    )
    monkeypatch.setattr(rag, "encode_queries", lambda phrases: [[1.0] * 1024] * len(phrases))
    monkeypatch.setattr(
        rag, "_run_db_query",
        lambda vectors, payday: [[misleading], [misleading], [legitimate]] if payday else [],
    )
    result = asyncio.run(rag.search_supabase("급여일이 언제야?"))
    assert len(result) == 1
    assert result[0]["row"]["id"] == "SRC-0007-c0315"
    assert "25일" in result[0]["row"]["content"]


def test_non_payday_synonyms_use_dense_and_no_fixed_answers(monkeypatch):
    seen = {}
    evidence = row("SRC-0004-c0001", "제3조(출장)", "출장비는 별도 증빙으로 정산한다.", 0.8)

    def fake_query(vectors, payday):
        seen["vectors"] = len(vectors)
        seen["payday"] = payday
        return [[evidence], [evidence]]

    monkeypatch.setattr(rag, "encode_queries", lambda phrases: [[1.0] * 1024] * len(phrases))
    monkeypatch.setattr(rag, "_run_db_query", fake_query)
    result = asyncio.run(rag.search_supabase("출장 경비 정산 방법 알려줘"))
    assert seen == {"vectors": 2, "payday": False}
    assert len(result) == 1
    assert "출장비" in result[0]["row"]["content"]


def test_no_payday_evidence_means_no_results(monkeypatch):
    misleading = row(
        "bonus", "성과연봉", "성과연봉은 급여지급일에 준하여 지급한다.", 0.91,
    )
    monkeypatch.setattr(rag, "encode_queries", lambda phrases: [[1.0] * 1024] * len(phrases))
    monkeypatch.setattr(rag, "_run_db_query", lambda vectors, payday: [
        [misleading], [misleading], [],
    ])
    assert asyncio.run(rag.search_supabase("월급은 매달 며칠 들어와?")) == []
