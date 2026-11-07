"""Synthetic vector-space controls, original-span gates, and the LLM handoff.

No local company corpus, GPU, network, provider credentials or paid calls.
"""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from server import hr_answer, hr_evidence, hr_vector


@pytest.fixture
def vector_data(tmp_path, monkeypatch):
    sources, windows, texts = [], [], {}
    vectors = np.eye(4, hr_vector.DIMENSION, dtype=np.float32)
    for number in range(4):
        text = f"테스트용 병가 원문 {number}입니다.\n후속 예외도 함께 보존합니다."
        source = dict(id=f"TEST-HR-{number}", company="KEPCO", title="취업규칙", section=f"제{number}조 테스트",
            text=text, sha256=hr_vector.digest(text), source_file_sha256=hr_vector.digest("TEST FILE"),
            version="TEST-ONLY", effective_status="UNVERIFIED", human_approved=False,
            ktcs_applicable=False, review_status="AUTOMATIC_TEST", employee_scope="TEST ONLY")
        if number < 3:
            sources.append(source)
        span = text.split("\n")[0]
        retrieval = source["title"] + " > " + source["section"] + "\n" + span
        texts[retrieval] = vectors[number]
        windows.append(dict(id=f"W-test-{number}", unit_record_id=source["id"], answer_bundle_id=source["id"],
            source_file_sha256=source["source_file_sha256"], start=0, end=len(span), text_sha256=hr_vector.digest(span),
            retrieval_text=retrieval, retrieval_text_sha256=hr_vector.digest(retrieval), retrieval_only=True, bge_tokens=50))
    np.save(tmp_path / "windows.npy", vectors, allow_pickle=False)
    windows_path = tmp_path / "windows.jsonl"
    windows_path.write_text("\n".join(json.dumps(w, ensure_ascii=False) for w in windows), encoding="utf-8")
    meta = dict(**hr_vector.IDENTITY, normalized=True, stored_vectors="FP32", rows=4,
        ids=[w["id"] for w in windows], vectors_sha256=hr_vector.sha(tmp_path / "windows.npy"),
        windows_sha256=hr_vector.sha(windows_path),
        encoder_runtime=dict(loader="CPU_WORD_GATHER_VERIFIED_OFFICIAL_ENCODER_LAYERS"))
    (tmp_path / "windows_vectors.json").write_text(json.dumps(meta), encoding="utf-8")
    monkeypatch.setenv("KLINK_HR_RETRIEVAL", "dense")
    monkeypatch.setenv("KLINK_HR_VECTOR_INDEX", str(tmp_path))
    monkeypatch.setenv("KLINK_HR_VECTOR_WINDOWS", str(windows_path))
    monkeypatch.setattr(hr_evidence, "corpus", lambda: (sources, [], Counter(), [], 0))
    monkeypatch.setattr(hr_vector, "health", lambda: dict(**hr_vector.IDENTITY, instance_id="TEST-ENCODER"))
    seen = []

    def fake_embed(text):
        seen.append(text)
        vector = texts[text] if text in texts else vectors[1]
        return vector, dict(model=hr_vector.MODEL, revision=hr_vector.REVISION, dimension=1024,
                            computed=True, cached=False, location="LOCAL_SERVER", elapsed_ms=0)

    monkeypatch.setattr(hr_vector, "embed", fake_embed)
    hr_vector._load.cache_clear()
    hr_vector._numeric_check.cache_clear()
    yield SimpleNamespace(folder=tmp_path, sources=sources, windows=windows, meta=meta, vectors=vectors, seen=seen)
    hr_vector._load.cache_clear()
    hr_vector._numeric_check.cache_clear()


def test_dense_uses_real_row_order_intersects_scope_and_keeps_complete_exception(vector_data):
    sources, trace = hr_vector.retrieve("테스트 병가 조건은 무엇인가요?")
    assert sources[0]["id"] == "TEST-HR-1" and trace["matches"][0]["chunk_id"] == "W-test-1"
    assert trace["matches"][0]["similarity"] == 1
    assert trace["index"]["window_count"] == 3 and trace["index"]["stored_window_count"] == 4
    assert "TEST-HR-3" not in trace["source_unit_ids"]
    assert "후속 예외" in sources[0]["text"] and "후속 예외" not in trace["matches"][0]["text"]
    assert trace["embedding"]["computed"] and not trace["embedding"]["cached"] and not trace["lexical_fallback"]


def test_questions_are_embedded_again_and_not_replayed_from_a_gold_cache(vector_data):
    question = "테스트 병가 조건은 무엇인가요?"
    hr_vector.retrieve(question)
    hr_vector.retrieve(question)
    assert vector_data.seen.count(question) == 2
    assert len(vector_data.seen) == 5  # Three original-window controls, two new queries.


def test_source_scope_metadata_change_invalidates_cached_source_views(vector_data):
    before, _ = hr_vector.retrieve("테스트 병가")
    assert before[0]["employee_scope"] == "TEST ONLY"
    vector_data.sources[1]["employee_scope"] = "CHANGED TEST SCOPE"
    after, _ = hr_vector.retrieve("테스트 병가")
    assert after[0]["employee_scope"] == "CHANGED TEST SCOPE"


def test_index_byte_tampering_blocks_before_query_embedding(vector_data):
    path = vector_data.folder / "windows.npy"
    with path.open("r+b") as file:
        file.seek(-1, 2)
        file.write(b"X")
    with pytest.raises(hr_vector.VectorUnavailable):
        hr_vector.retrieve("테스트 병가")
    assert vector_data.seen == []


def test_changed_window_cannot_be_authorized_by_only_updating_its_file_hash(vector_data):
    windows = deepcopy(vector_data.windows)
    windows[0]["start"] = 1
    path = vector_data.folder / "windows.jsonl"
    path.write_text("\n".join(json.dumps(w) for w in windows), encoding="utf-8")
    meta = vector_data.meta | dict(windows_sha256=hr_vector.sha(path))
    (vector_data.folder / "windows_vectors.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(hr_vector.VectorUnavailable):
        hr_vector.retrieve("테스트 병가")


def test_incompatible_vector_space_fails_even_when_model_names_and_hashes_match(vector_data, monkeypatch):
    monkeypatch.setattr(hr_vector, "embed", lambda text: (vector_data.vectors[3], {}))
    with pytest.raises(hr_vector.VectorUnavailable) as error:
        hr_vector.retrieve("테스트 병가")
    assert error.value.code == "LOCAL_VECTOR_SPACE_MISMATCH"
    assert not hr_vector.status()["ready"]


def test_out_of_scope_and_private_questions_do_not_reach_model(vector_data):
    sources, trace = hr_vector.retrieve("오늘 날씨는 어떻습니까?")
    assert not sources and trace["embedding"] is None
    with pytest.raises(hr_vector.VectorUnavailable):
        hr_vector.retrieve("test@example.invalid 직원 병가")
    assert vector_data.seen == []


def test_dense_failure_never_silently_calls_keyword_search_or_llm(vector_data, monkeypatch):
    def unavailable():
        raise hr_vector.VectorUnavailable("TEST UNAVAILABLE")
    monkeypatch.setattr(hr_vector, "index", unavailable)
    monkeypatch.setattr(hr_evidence, "search", lambda *a, **kw: pytest.fail("lexical fallback"))
    monkeypatch.setattr(hr_answer.benefit_explanation, "settings", lambda: pytest.fail("LLM configuration accessed"))
    with pytest.raises(hr_answer.AnswerUnavailable) as error:
        hr_answer.generate("테스트 병가")
    assert error.value.code == "LOCAL_VECTOR_INDEX_UNAVAILABLE"


@pytest.mark.parametrize("patch", [dict(model="wrong"), dict(cached=True), dict(computed=False), dict(vector=[0.0] * 1024)])
def test_query_vector_identity_cache_and_normalization_are_checked(monkeypatch, patch):
    original_embed = hr_vector.embed
    monkeypatch.setattr(hr_vector, "health", lambda: {})
    value = dict(**hr_vector.IDENTITY, computed=True, cached=False,
                 vector=np.eye(1, 1024, dtype=np.float32)[0].tolist()) | patch
    monkeypatch.setattr(hr_vector, "_json", lambda *a, **kw: value)
    with pytest.raises(hr_vector.VectorUnavailable) as error:
        original_embed("테스트 병가")
    assert error.value.code == "LOCAL_QUERY_EMBEDDING_FAILED"


def test_full_reviewed_source_units_from_dense_results_are_the_only_llm_evidence(vector_data, monkeypatch):
    monkeypatch.setattr(hr_answer.benefit_explanation, "settings", lambda: ("TEST-KEY-NOT-REAL", "configured-test-model"))
    received = []

    class FakeModel:
        def __init__(self, **kw):
            self.responses = SimpleNamespace(input_tokens=SimpleNamespace(count=self.count), create=self.create)
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def count(self, **payload):
            data = json.loads(payload["input"])
            assert [s["id"] for s in data["sources"]] == ["TEST-HR-1", "TEST-HR-0", "TEST-HR-2"]
            assert all("후속 예외" in s["text"] for s in data["sources"])
            assert "hire_date" not in payload["input"] and "TEST-KEY-NOT-REAL" not in str(payload)
            received.append(data)
            return SimpleNamespace(input_tokens=500)
        def create(self, **payload):
            assert payload["store"] is False and payload["model"] == "configured-test-model"
            source = vector_data.sources[1]
            draft = dict(status="answered", paragraphs=[dict(text="테스트용 원문이며 후속 예외도 함께 보존합니다.",
                         citations=[dict(source_id=source["id"], quote=source["text"])])], missing_information=[])
            return SimpleNamespace(status="completed", output_text=json.dumps(draft), usage=None)

    monkeypatch.setattr("openai.OpenAI", FakeModel)
    result = hr_answer.generate("테스트 병가")
    assert len(received) == 2 and result["retrieval"]["method"] == hr_vector.METHOD
    assert len(result["provider_calls"]) == 2 and result["paragraphs"]
    assert not result["employee_data_sent"] and not result["ktcs_applicable"] and not result["human_approved"]
