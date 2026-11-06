"""Regression smoke tests for the actual FastAPI/SSE contract (no paid API calls)."""
import importlib
import io
import json
import time

import fitz
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def demo(tmp_path, monkeypatch):
    monkeypatch.setenv("KLINK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("KLINK_DEMO_PASSWORD", "test-password-do-not-use")
    monkeypatch.setenv("KLINK_DEMO_USER", "klink")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    server = importlib.reload(importlib.import_module("server.app"))

    async def fake_dense(texts):
        # Deterministic test vectors; production uses real embeddings.
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(server, "embed", fake_dense)
    with TestClient(server.app) as client:
        yield client, server


def login(client):
    result = client.post("/api/auth/login", json={
        "username": "klink", "password": "test-password-do-not-use",
    })
    assert result.status_code == 200
    assert "httponly" in result.headers["set-cookie"].lower()


def sample_pdf():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((64, 80), "Article 3 Annual Leave Procedures. Submit a request.")
    content = doc.tobytes()
    doc.close()
    return io.BytesIO(content)


def sse_events(response):
    assert response.headers["content-type"].startswith("text/event-stream")
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_auth_and_live_chat_without_sources(demo):
    client, _ = demo
    assert client.get("/api/conversations").status_code == 401
    assert client.post("/api/auth/login", json={"username": "bad", "password": "bad"}).status_code == 401
    login(client)
    assert client.get("/api/auth/me").json()["role"] == "admin"
    conv = client.post("/api/conversations", json={"title": "첫 질문"}).json()
    res = client.post(f"/api/conversations/{conv['id']}/messages", json={
        "content": "휴가 신청 방법 알려줘", "attachment_ids": [],
    })
    events = sse_events(res)
    assert events[0]["type"] == "meta"
    assert events[0]["citations"] == []
    assert any(e["type"] == "delta" and "근거를 찾지 못" in e["text"] for e in events)
    assert events[-1]["type"] == "done"
    saved = client.get(f"/api/conversations/{conv['id']}/messages").json()
    assert [m["role"] for m in saved] == ["user", "assistant"]
    assert client.get("/api/admin/stats").json()["questions"] == 1


def test_pdf_upload_real_dense_search_and_citations(demo):
    client, _ = demo
    login(client)
    response = client.post(
        "/api/admin/documents",
        data={"collection_id": "hr"},
        files={"file": ("annual_leave.pdf", sample_pdf(), "application/pdf")},
    )
    assert response.status_code == 200
    doc_id = response.json()["id"]
    for _ in range(50):
        rows = client.get("/api/admin/documents").json()
        if rows[0]["status"] != "processing":
            break
        time.sleep(0.04)
    assert rows[0]["status"] == "ready", rows
    assert rows[0]["name"] == "annual_leave.pdf"
    conv = client.post("/api/conversations", json={"title": "leave"}).json()
    res = client.post(f"/api/conversations/{conv['id']}/messages", json={
        "content": "Annual Leave Procedures", "attachment_ids": [],
    })
    events = sse_events(res)
    assert events[0]["type"] == "meta"
    assert len(events[0]["citations"]) == 1
    assert events[0]["citations"][0]["docName"] == "annual_leave.pdf"
    assert events[0]["citations"][0]["source"] == "kb"
    assert "API 키가 없어" in "".join(e.get("text", "") for e in events if e["type"] == "delta")
    assert events[-1]["type"] == "done"
    assert client.get("/health").json()["indexedDocuments"] == 1


def test_attachments_are_not_global_knowledge(demo):
    client, _ = demo
    login(client)
    resp = client.post(
        "/api/attachments",
        files={"file": ("meeting.pdf", sample_pdf(), "application/pdf")},
    )
    assert resp.status_code == 200
    attachment_id = resp.json()["id"]
    assert client.get("/api/admin/documents").json() == []
    conv = client.post("/api/conversations", json={"title": "meeting"}).json()
    events = sse_events(client.post(f"/api/conversations/{conv['id']}/messages", json={
        "content": "annual leave", "attachment_ids": [attachment_id],
    }))
    assert events[0]["citations"][0]["source"] == "attachment"


def test_reject_non_pdf_and_unrecognized_collection(demo):
    client, _ = demo
    login(client)
    assert client.post(
        "/api/admin/documents", data={"collection_id": "invalid"},
        files={"file": ("a.pdf", io.BytesIO(b"%PDF-valid"), "application/pdf")},
    ).status_code == 400
    assert client.post(
        "/api/admin/documents", data={"collection_id": "hr"},
        files={"file": ("a.exe", io.BytesIO(b"bad"), "application/octet-stream")},
    ).status_code == 415
