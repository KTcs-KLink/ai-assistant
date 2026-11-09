"""Isolated operations contracts. Mock provider receipts are not real model calls."""
import json
import sqlite3
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from operations import corpus, meter, service, store


class NoWorker:
    def submit(self, *args):
        return None


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    monkeypatch.setattr(store, "DB", tmp_path / "operations.sqlite3")
    monkeypatch.setattr(service, "RUNNER", NoWorker())
    with TestClient(service.app, headers={"Origin": "http://testserver"}) as value:
        yield value


def login(client, role="owner"):
    response = client.post("/api/control/session/demo", json={"role": role})
    assert response.status_code == 200
    assert response.json()["production_authorized"] is False
    return response


def configure(client, **changes):
    row = client.get("/api/control/admin/settings").json()["policy"]
    body = {key: row[key] for key in ["monthly_budget_usd", "daily_request_limit", "budget_action", "maintenance", "revision"]}
    return client.put("/api/control/admin/settings", json={**body, **changes})


def mock_upstream(monkeypatch, receipt, status=200, authorized=True):
    calls = []
    def handler(request):
        if request.url.path.endswith("/session"):
            return httpx.Response(200 if authorized else 401, json={"mode": "demo"})
        calls.append(json.loads(request.content))
        return httpx.Response(status, json=receipt)
    original = httpx.AsyncClient
    monkeypatch.setattr(service.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    return calls


def sample_receipt():
    return dict(status="answered", model="gpt-6-luna", paragraphs=[{"text": "NEVER_STORE_ANSWER", "citations": []}],
                provider_calls=[dict(phase="draft", usage=dict(input_tokens=100, input_tokens_details=dict(cached_tokens=20), output_tokens=30, output_tokens_details=dict(reasoning_tokens=15)))])


def ask(client):
    return client.post("/api/benefits/hr/answer", json={"question": "개인정보 없는 일반 규정 문의입니다."})


def test_unauthenticated_and_csrf(client):
    assert client.get("/api/control/admin/overview").status_code == 401
    assert client.post("/api/control/session/demo", json={"role": "owner"}, headers={"Origin": "https://evil.invalid"}).status_code == 403
    assert client.post("/api/control/session/demo", json={"role": "owner", "company": "KTCS"}).status_code == 422


def test_cookie_and_employee_admin_separation(client):
    response = login(client, "employee")
    cookie = next(v for v in response.headers.get_list("set-cookie") if "HttpOnly" in v)
    assert "SameSite=strict" in cookie and "Path=/api;" in cookie
    assert client.get("/api/control/admin/cases").status_code == 401
    assert client.get("/api/control/cases").status_code == 200
    login(client, "owner")
    assert client.get("/api/control/cases").status_code == 200
    client.delete("/api/control/session?admin=true")
    assert client.get("/api/control/cases").status_code == 200
    assert client.get("/api/control/admin/usage").status_code == 401


@pytest.mark.parametrize("role,path,allowed", [
    ("analyst", "/api/control/admin/usage", True),
    ("analyst", "/api/control/admin/jobs", False),
    ("data_admin", "/api/control/admin/sources", True),
    ("data_admin", "/api/control/admin/cases", False),
    ("hr_admin", "/api/control/admin/cases", True),
    ("hr_admin", "/api/control/admin/usage", False),
])
def test_role_is_checked_by_server(client, role, path, allowed):
    login(client, role)
    assert client.get(path).status_code == (200 if allowed else 403)


def test_case_owner_isolation_and_admin_roundtrip(client):
    login(client, "employee")
    created = client.post("/api/control/cases", json=dict(title="양식 확인 절차 문의", category="양식 문의", body="공식 양식을 확인하는 절차를 안내해 주세요."))
    assert created.status_code == 201
    case_id = created.json()["id"]
    assert created.json()["actual_hr_submission"] is False
    saved_cookie = client.cookies.get("klink_ops_employee")
    login(client, "employee")
    assert not client.get("/api/control/cases").json()["items"]
    assert client.post(f"/api/control/cases/{case_id}/cancel", json={}).status_code == 404
    login(client, "owner")
    row = client.get("/api/control/admin/cases").json()["items"][0]
    body = dict(state="resolved", reply="규정·양식 화면에서 공식 연결 상태를 확인해 주세요.", revision=row["revision"])
    assert client.patch(f"/api/control/admin/cases/{case_id}", json=body).status_code == 200
    assert client.patch(f"/api/control/admin/cases/{case_id}", json=body).status_code == 409
    client.cookies.set("klink_ops_employee", saved_cookie, domain="testserver.local", path="/api")
    result = client.get("/api/control/cases").json()["items"][0]
    assert result["state"] == "resolved" and result["reply"] == body["reply"]
    assert "owner" not in result


def test_private_inputs_are_not_saved(client):
    login(client, "employee")
    for body in ["연락처 010-1234-5678로 보내 주세요", "password=DO_NOT_STORE_THIS", "이메일 test@example.com로 부탁합니다"]:
        assert client.post("/api/control/cases", json=dict(title="일반 문의", category="서비스 이용", body=body)).status_code == 422
    assert not client.get("/api/control/cases").json()["items"]


def test_pinned_real_catalog_and_exclusion(client):
    login(client)
    before = corpus.sha_file(corpus.MANIFEST)
    data = client.get("/api/control/admin/sources").json()
    assert data["answer_units"] == 528 and data["review_units"] == 3334 and data["excluded_units"] == 8
    assert data["total"] == 203 and data["production_approved"] is False
    doc = next(row for row in data["items"] if row["answer_count"])
    excerpt = client.get(f"/api/control/admin/sources/{doc['id']}/excerpts").json()
    assert excerpt["used_for_generation"] is False and excerpt["items"]
    assert all(row["human_approved"] is False and row["ktcs_applicable"] is False for row in excerpt["items"])
    assert corpus.sha_file(corpus.MANIFEST) == before


def test_source_urls_cannot_expand_network_scope():
    assert corpus.allowed_url("https://www.kepco.co.kr/c2r/FileDownload.do?fileNo=public")
    for value in ["http://www.kepco.co.kr/file", "https://127.0.0.1/file", "https://evil.invalid/file", "https://www.kepco.co.kr.evil.invalid/file", "https://name:secret@www.kepco.co.kr/file", "https://www.kepco.co.kr:9999/file"]:
        assert not corpus.allowed_url(value)


def test_job_duplicate_cancel_retry_and_scope(client):
    login(client)
    doc = next(row for row in corpus.load()["documents"] if row["answer_count"])
    body = dict(kind="verify", documents=[doc["id"]])
    response = client.post("/api/control/admin/jobs", json=body)
    assert response.status_code == 202
    job_id = response.json()["id"]
    assert response.json()["active_service_changed"] is False
    assert client.post("/api/control/admin/jobs", json=body).status_code == 409
    assert client.post(f"/api/control/admin/jobs/{job_id}/cancel", json={}).status_code == 200
    retried = client.post(f"/api/control/admin/jobs/{job_id}/retry", json={})
    assert retried.status_code == 202 and retried.json()["id"] != job_id
    assert client.post("/api/control/admin/jobs", json=dict(kind="reindex", documents=["../../.env"])).status_code == 422
    assert client.post("/api/control/admin/jobs", json={**body, "activate": True}).status_code == 422


def test_actual_staging_index_preserves_active_corpus(client):
    login(client)
    doc = next(row for row in corpus.load()["documents"] if row["answer_count"])
    before = corpus.sha_file(corpus.MANIFEST)
    response = client.post("/api/control/admin/jobs", json=dict(kind="reindex", documents=[doc["id"]]))
    job_id = response.json()["id"]
    corpus.run_job(job_id, "reindex", [doc["id"]])
    result = client.get("/api/control/admin/jobs").json()["items"][0]
    assert result["state"] == "succeeded", result["message"]
    path = store.DATA / "artifacts" / job_id / "staging.sqlite3"
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT count(*) FROM answer_fts").fetchone()[0] == doc["answer_count"]
        assert c.execute("SELECT count(*) FROM review_fts").fetchone()[0] == doc["review_count"]
    report = client.get(f"/api/control/admin/jobs/{job_id}/report").json()
    assert report["active_service_changed"] is False and report["new_embeddings"] == 0 and report["supabase_ingestion"] == "HOLD"
    assert corpus.sha_file(corpus.MANIFEST) == before


def test_empty_source_does_not_report_successful_ingestion(client):
    login(client)
    doc = next(row for row in corpus.load()["documents"] if not row["answer_count"] and not row["review_count"])
    assert client.post("/api/control/admin/jobs", json=dict(kind="reindex", documents=[doc["id"]])).status_code == 422
    assert not store.rows("SELECT id FROM jobs")


def test_review_record_cannot_approve_source(client):
    login(client)
    doc = next(row for row in corpus.load()["documents"] if row["review_count"])
    payload = dict(document_id=doc["id"], state="reviewed", note="표 구조와 조문 경계는 별도의 검토가 필요합니다.", revision=0)
    response = client.put("/api/control/admin/reviews", json=payload)
    assert response.status_code == 200
    assert response.json()["answer_eligibility_changed"] is False and response.json()["human_approval"] is False
    assert client.put("/api/control/admin/reviews", json=payload).status_code == 409
    assert client.put("/api/control/admin/reviews", json={**payload, "document_id": "UNKNOWN"}).status_code == 422


def test_usage_prices_cache_and_reasoning_without_double_count():
    rate = store.DEFAULT_RATE
    usage = sample_receipt()["provider_calls"][0]["usage"]
    assert Decimal(meter.price(usage, rate)) == (Decimal(80)*Decimal(".10")+Decimal(20)*Decimal(".01")+Decimal(30)*Decimal(".50"))/1000000
    assert meter.price({**usage, "input_tokens_details": {"cached_tokens": 101}}, rate) is None
    assert meter.price(usage, None) is None


def test_proxy_preserves_response_and_records_only_usage(client, monkeypatch):
    login(client)
    receipt = sample_receipt()
    calls = mock_upstream(monkeypatch, receipt)
    response = ask(client)
    assert response.status_code == 200 and response.json() == receipt
    assert list(calls[0]) == ["question"] and response.headers["x-klink-meter-id"]
    summary = client.get("/api/control/admin/usage?days=7").json()
    assert summary["totals"]["input_tokens"] == 100 and summary["totals"]["output_tokens"] == 30
    assert summary["totals"]["cached_tokens"] == 20 and summary["totals"]["provider_calls"] == 1
    assert summary["totals"]["unknown_usage"] == 0
    detail = client.get("/api/control/admin/usage/requests/"+response.headers["x-klink-meter-id"]).json()
    assert detail["questions_stored"] is False and detail["answers_stored"] is False
    with store.connect() as c:
        dump = "\n".join(c.iterdump())
    assert "NEVER_STORE_ANSWER" not in dump and calls[0]["question"] not in dump
    assert client.get("/api/control/admin/usage/export").headers["content-type"].startswith("text/csv")


def test_failed_receipt_is_unknown_cost_not_zero(client, monkeypatch):
    login(client)
    mock_upstream(monkeypatch, {"detail": "unavailable"}, status=503)
    assert ask(client).status_code == 503
    data = client.get("/api/control/admin/usage").json()
    assert data["totals"]["unknown_usage"] == 1 and data["totals"]["unpriced_requests"] == 1
    assert data["requests"][0]["cost_usd"] is None
    assert configure(client, budget_action="block").status_code == 200
    assert ask(client).status_code == 429


def test_held_zero_call_receipt_is_measured_zero(client, monkeypatch):
    login(client)
    mock_upstream(monkeypatch, dict(status="needs_review", provider_calls=[], validation="NAMED_SOURCE_HELD_NO_SUBSTITUTE_OR_GENERATION"))
    assert ask(client).status_code == 200
    totals = client.get("/api/control/admin/usage").json()["totals"]
    assert totals["provider_calls"] == 0 and totals["unknown_usage"] == 0 and Decimal(totals["known_cost_usd"]) == 0


def test_daily_limit_and_maintenance_apply_before_model(client, monkeypatch):
    login(client)
    calls = mock_upstream(monkeypatch, sample_receipt())
    assert configure(client, maintenance=True).status_code == 200
    assert ask(client).status_code == 503 and not calls
    assert configure(client, maintenance=False, daily_request_limit=1).status_code == 200
    assert ask(client).status_code == 200 and len(calls) == 1
    assert ask(client).status_code == 429 and len(calls) == 1


def test_price_version_changes_only_future_requests(client, monkeypatch):
    login(client)
    mock_upstream(monkeypatch, sample_receipt())
    first = ask(client).headers["x-klink-meter-id"]
    original = client.get("/api/control/admin/usage/requests/"+first).json()
    assert client.put("/api/control/admin/rates", json=dict(model="gpt-6-luna", input="1", cached=".1", write="1.25", output="5")).status_code == 200
    second = ask(client).headers["x-klink-meter-id"]
    updated = client.get("/api/control/admin/usage/requests/"+second).json()
    assert Decimal(updated["request"]["cost_usd"]) == Decimal(original["request"]["cost_usd"])*10
    assert client.get("/api/control/admin/usage/requests/"+first).json() == original


def test_invalid_policy_and_revision_are_rejected(client):
    login(client)
    assert configure(client, daily_request_limit=0).status_code == 422
    assert configure(client, monthly_budget_usd="NaN").status_code == 422
    assert configure(client, revision=999).status_code == 409
    assert client.get("/api/control/admin/usage?days=6").status_code == 422
    assert client.get("/api/control/admin/usage?days=30").status_code == 200


def test_upstream_authorization_is_required(client, monkeypatch):
    calls = mock_upstream(monkeypatch, sample_receipt(), authorized=False)
    assert ask(client).status_code == 401 and not calls
    assert not store.rows("SELECT id FROM requests")
