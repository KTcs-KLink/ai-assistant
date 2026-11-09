"""Workflow contracts in isolated SQLite and fixture files, not a RAG quality evaluation."""
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from operations import automation as flow, meter, service, store
from operations.test_operations import client, login, mock_upstream, sample_receipt, ask

DOC = "K-170-A01"


def config(client, **changes):
    value = client.get("/api/control/admin/automation").json()["config"]
    return client.put("/api/control/admin/automation", json={**value, **changes})


def request_approval(client, **changes):
    return client.post("/api/control/approvals", json={**dict(document_id=DOC, job_kind="verify", reason="원문의 보관 무결성을 확인해 주세요."), **changes})


def case(client, category="규정 문의"):
    return client.post("/api/control/cases", json=dict(title="자동화 기능 확인 문의", category=category, body="개인정보 없는 기능 확인용 문의입니다."))


def agent(client, name="검증용 운영 별칭", capacity=1):
    return client.post("/api/control/admin/agents", json=dict(name=name, team="인사 운영", active=True, capacity=capacity)).json()["id"]


def decision(client, uid, revision=1, state="approved"):
    return client.post(f"/api/control/admin/approvals/{uid}/decide", json=dict(state=state, revision=revision, note="원문과 요청 범위를 확인했습니다."))


def observed_download(job_id, content, baseline=None):
    """A local changed-byte fixture. Never writes an actual policy source."""
    folder = store.DATA / "artifacts" / job_id
    folder.mkdir(parents=True)
    (folder / (DOC + ".source")).write_bytes(content)
    sha = hashlib.sha256(content).hexdigest()
    report = dict(documents=[dict(id=DOC, title="변경 감지 검증 문서", downloaded_sha256=sha, original_sha256=baseline or "0"*64)])
    with store.connect() as c:
        c.execute("INSERT INTO jobs(id,kind,state,documents,created_at,updated_at,message,report) VALUES(?,'recollect','succeeded',?,?,?,'fixture',?)",
                  (job_id, json.dumps([DOC]), store.now(), store.now(), json.dumps(report)))
    flow.observe_job(job_id)
    return sha


def test_additive_schema_preserves_rows(client):
    login(client, "employee")
    uid = case(client).json()["id"]
    flow.init()
    assert store.rows("SELECT id,team FROM cases WHERE id=?", (uid,))[0]["team"] == "인사 운영"
    assert store.setting("automation")["revision"] == 1


def test_approval_owner_revision_and_exactly_once_job(client):
    login(client, "employee")
    uid = request_approval(client).json()["id"]
    assert request_approval(client).status_code == 409
    login(client, "owner")
    assert decision(client, uid).status_code == 200
    assert decision(client, uid).status_code == 409
    assert len(store.rows("SELECT * FROM jobs")) == 1
    row = client.get("/api/control/inbox").json()["approvals"][0]
    assert row["state"] == "approved" and row["job_id"]
    assert "owner" not in row
    assert len(row["events"]) == 2
    login(client, "employee")
    assert client.get("/api/control/inbox").json()["approvals"] == []
    assert client.patch(f"/api/control/approvals/{uid}", json=dict(action="cancel", revision=2)).status_code == 404


def test_no_self_approval_even_when_session_role_changes(client):
    login(client, "employee")
    uid = request_approval(client).json()["id"]
    owner_id = store.rows("SELECT owner FROM approvals WHERE id=?", (uid,))[0]["owner"]
    with store.connect() as c:
        c.execute("UPDATE sessions SET role='owner' WHERE id=?", (owner_id,))
    token = client.cookies.get("klink_ops_employee")
    client.cookies.set("klink_ops_admin", token, domain="testserver.local", path="/api/control")
    assert decision(client, uid).status_code == 403
    assert not store.rows("SELECT * FROM jobs")


def test_needs_info_resubmit_cancel_and_stale(client):
    login(client, "employee")
    uid = request_approval(client).json()["id"]
    login(client)
    assert decision(client, uid, state="needs_info").status_code == 200
    assert client.patch(f"/api/control/approvals/{uid}", json=dict(action="resubmit", revision=1, reason="추가 설명을 제출합니다.")).status_code == 409
    assert client.patch(f"/api/control/approvals/{uid}", json=dict(action="resubmit", revision=2, reason="추가 설명을 제출합니다.")).status_code == 200
    assert client.patch(f"/api/control/approvals/{uid}", json=dict(action="cancel", revision=3)).status_code == 200
    assert decision(client, uid, revision=4).status_code == 409


def test_change_detection_unchanged_dedup_supersedes_and_hash_check(client):
    login(client)
    baseline = hashlib.sha256(b"baseline").hexdigest()
    observed_download("JOB-fixture0", b"baseline", baseline)
    assert not store.rows("SELECT * FROM approvals")
    changed = observed_download("JOB-fixture1", b"changed bytes", baseline)
    observed_download("JOB-fixture2", b"changed bytes", baseline)
    rows = store.rows("SELECT * FROM approvals")
    assert len(rows) == 1 and rows[0]["state"] == "pending"
    first = rows[0]["id"]
    observed_download("JOB-fixture3", b"newer bytes", baseline)
    assert decision(client, first).status_code == 409
    current = store.rows("SELECT * FROM approvals WHERE state='pending'")[0]
    folder = store.DATA / "artifacts/JOB-fixture3"
    (folder / (DOC + ".source")).write_bytes(b"tampered")
    assert decision(client, current["id"]).status_code == 409
    (folder / (DOC + ".source")).write_bytes(b"newer bytes")
    assert decision(client, current["id"]).status_code == 200
    assert store.rows("SELECT state FROM source_versions WHERE sha256=?", (changed,))[0]["state"] == "superseded"
    assert store.rows("SELECT state FROM source_versions WHERE id=?", (current["version_id"],))[0]["state"] == "accepted"
    assert not store.rows("SELECT * FROM jobs WHERE state='queued'")
    assert store.rows("SELECT last_sha FROM source_checks")[0]["last_sha"] != baseline


def test_return_to_baseline_retires_pending_change(client):
    baseline = hashlib.sha256(b"baseline").hexdigest()
    observed_download("JOB-fixture1", b"candidate", baseline)
    observed_download("JOB-fixture2", b"baseline", baseline)
    assert store.rows("SELECT state FROM approvals")[0]["state"] == "superseded"
    assert store.rows("SELECT state FROM alerts")[0]["state"] == "resolved"


def test_watcher_bounded_and_no_overlapping_restart_burst(client):
    login(client)
    assert config(client, watch_enabled=True).status_code == 422
    assert config(client, watch_documents=[DOC, DOC]).status_code == 422
    assert config(client, watch_documents=[DOC], watch_enabled=True, watch_interval_minutes=1).status_code == 422
    assert config(client, watch_documents=[DOC], watch_enabled=True).status_code == 200
    submitted = []
    with store.connect() as c:
        c.execute("UPDATE watch_runtime SET next_due=0")
    flow.tick(lambda *a: submitted.append(a))
    assert len(submitted) == 1
    with store.connect() as c:
        c.execute("UPDATE watch_runtime SET next_due=0")
    flow.tick(lambda *a: submitted.append(a))
    assert len(submitted) == 1
    assert len(store.rows("SELECT * FROM jobs")) == 1
    assert store.setting("automation")["watch_documents"] == [DOC]


def test_routing_capacity_and_reassignment_are_transactional(client):
    login(client)
    a, b = agent(client, "검증 별칭 하나"), agent(client, "검증 별칭 둘")
    login(client, "employee")
    ids = [case(client).json()["id"] for _ in range(3)]
    rows = store.rows("SELECT id,agent_id FROM cases")
    assert sorted(r["agent_id"] for r in rows if r["agent_id"]) == sorted([a, b])
    assert sum(r["agent_id"] is None for r in rows) == 1
    assert len(client.get("/api/control/inbox").json()["notifications"]) == 3
    login(client)
    pending = store.rows("SELECT * FROM cases WHERE agent_id IS NULL")[0]
    body = dict(mode="manual", agent_id=a, reason="담당 범위를 확인해 재배정합니다.", revision=pending["revision"])
    assert client.patch(f"/api/control/admin/cases/{pending['id']}/assignment", json=body).status_code == 409
    occupied = store.rows("SELECT * FROM cases WHERE agent_id=?", (a,))[0]
    assert client.patch(f"/api/control/admin/cases/{occupied['id']}", json=dict(state="resolved", reply="기능 확인을 완료했습니다.", revision=occupied["revision"])).status_code == 200
    assert client.patch(f"/api/control/admin/cases/{pending['id']}/assignment", json={**body, "mode": "auto"}).status_code == 200
    assert store.rows("SELECT agent_id FROM cases WHERE id=?", (pending["id"],))[0]["agent_id"] == a
    assert client.patch(f"/api/control/admin/cases/{pending['id']}/assignment", json=body).status_code == 409


def test_manual_assignment_lock_and_inactive_agent_alert(client):
    login(client)
    uid = agent(client, capacity=5)
    login(client, "employee")
    cid = case(client).json()["id"]
    login(client)
    row = store.rows("SELECT * FROM cases WHERE id=?", (cid,))[0]
    assert client.patch(f"/api/control/admin/cases/{cid}/assignment", json=dict(mode="manual", agent_id=uid, reason="수동 담당 지정을 기록합니다.", revision=row["revision"])).status_code == 200
    with store.connect() as c:
        flow.route_case(c, cid)
    assert store.rows("SELECT routing_locked FROM cases")[0]["routing_locked"] == 1
    a = client.get("/api/control/admin/agents").json()["items"][0]
    assert client.patch(f"/api/control/admin/agents/{uid}", json=dict(name=a["name"], team=a["team"], active=False, capacity=5, revision=a["revision"])).status_code == 200
    alerts = client.get("/api/control/admin/alerts").json()["items"]
    assert any(r["fingerprint"] == "inactive-agent:" + cid and r["state"] == "open" for r in alerts)


def test_parallel_routing_never_exceeds_capacity(client):
    login(client)
    aid = agent(client, capacity=1)
    def insert(i):
        with store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            cid = f"HR-test-{i}"
            c.execute("INSERT INTO cases(id,owner,title,category,body,state,created_at,updated_at) VALUES(?,'test','test','규정 문의','test','received',?,?)", (cid, store.now(), store.now()))
            flow.route_case(c, cid)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(insert, range(4)))
    assert len(store.rows("SELECT id FROM cases WHERE agent_id=?", (aid,))) == 1


def test_budget_unknown_pending_and_alert_ack_dedup(client):
    login(client)
    rid, _ = meter.start_request()
    assert not client.get("/api/control/admin/alerts").json()["items"]
    meter.finish(rid, 200, 100)
    alerts = client.get("/api/control/admin/alerts").json()["items"]
    unknown = next(r for r in alerts if r["category"] == "cost")
    assert client.patch(f"/api/control/admin/alerts/{unknown['id']}", json=dict(state="acknowledged", revision=unknown["revision"])).status_code == 200
    assert client.patch(f"/api/control/admin/alerts/{unknown['id']}", json=dict(state="open", revision=unknown["revision"])).status_code == 409
    again = client.get("/api/control/admin/alerts").json()["items"]
    assert len(again) == 1 and again[0]["state"] == "acknowledged"
    assert again[0]["occurrences"] == 1
    with store.connect() as c:
        c.execute("UPDATE requests SET cost_usd='19.00' WHERE id=?", (rid,))
    rows = client.get("/api/control/admin/alerts").json()["items"]
    assert next(a for a in rows if a["fingerprint"].startswith("unknown-cost"))["state"] == "resolved"
    assert next(a for a in rows if a["fingerprint"].startswith("budget"))["severity"] == "warning"
    with store.connect() as c:
        c.execute("UPDATE requests SET cost_usd='21.00' WHERE id=?", (rid,))
    rows = client.get("/api/control/admin/alerts").json()["items"]
    assert next(a for a in rows if a["fingerprint"].startswith("budget"))["severity"] == "critical"


def test_feedback_owned_receipt_no_content_storage_and_review(client, monkeypatch):
    receipt = sample_receipt()
    mock_upstream(monkeypatch, receipt)
    login(client, "employee")
    response = ask(client)
    assert response.json() == receipt
    rid = response.headers["X-Klink-Meter-Id"]
    first_cookie = client.cookies.get("klink_ops_employee")
    login(client, "employee")
    assert client.post(f"/api/control/feedback/{rid}", json=dict(reason="根拠不一致")).status_code == 422
    payload = dict(reason="조건·예외 확인")
    assert client.post(f"/api/control/feedback/{rid}", json=payload).status_code == 404
    client.cookies.set("klink_ops_employee", first_cookie, domain="testserver.local", path="/api")
    feedback = client.post(f"/api/control/feedback/{rid}", json=payload)
    assert feedback.status_code == 201
    assert client.post(f"/api/control/feedback/{rid}", json=payload).status_code == 409
    login(client)
    body = client.get("/api/control/admin/alerts").json()
    assert body["feedback"][0]["request_id"] == rid
    assert "owner_session" not in str(client.get("/api/control/admin/usage").json())
    assert "owner_session" not in client.get(f"/api/control/admin/usage/requests/{rid}").text
    uid = feedback.json()["id"]
    reviewed = client.patch(f"/api/control/admin/feedback/{uid}", json=dict(state="resolved", resolution="해당 조문을 확인할 절차를 안내합니다.", revision=1))
    assert reviewed.json()["semantic_accuracy_certified"] is False
    notifications = client.get("/api/control/inbox").json()["notifications"]
    assert notifications[-1]["title"] == "답변 검토 처리 안내"
    assert "NEVER_STORE_ANSWER" not in str(store.rows("SELECT * FROM requests"))


def test_refusal_not_quality_failure_and_alert_role_boundaries(client):
    login(client)
    rid, _ = meter.start_request()
    meter.finish(rid, 200, 1000, dict(status="insufficient_evidence", provider_calls=[]))
    assert not client.get("/api/control/admin/alerts").json()["items"]
    rid, _ = meter.start_request()
    meter.finish(rid, 502, 70000)
    rows = client.get("/api/control/admin/alerts").json()["items"]
    cost = next(a for a in rows if a["category"] == "cost")
    login(client, "data_admin")
    assert client.get("/api/control/admin/alerts").json()["items"] == []
    assert client.patch(f"/api/control/admin/alerts/{cost['id']}", json=dict(state="acknowledged", revision=cost["revision"])).status_code == 404
    assert client.post("/api/control/admin/agents", json=dict(name="권한 확인", team="인사 운영")).status_code == 403
    assert client.put("/api/control/admin/automation", json=store.setting("automation")).status_code == 403
    login(client, "hr_admin")
    assert all(a["category"] != "cost" for a in client.get("/api/control/admin/alerts").json()["items"])


def test_notification_ownership_and_revision_config(client):
    login(client, "employee")
    case(client)
    notification = client.get("/api/control/inbox").json()["notifications"][0]
    assert client.get("/api/control/workflow-counts").json()["todo"] == 1
    login(client, "employee")
    assert client.get("/api/control/workflow-counts").json()["todo"] == 0
    assert client.post(f"/api/control/notifications/{notification['id']}/read", json={}).status_code == 404
    login(client)
    cfg = store.setting("automation")
    assert config(client, slow_seconds=120).status_code == 200
    assert client.put("/api/control/admin/automation", json=cfg).status_code == 409
    assert request_approval(client, reason="     ").status_code == 422


def test_config_can_be_edited_again_without_server_metadata_rejection(client):
    login(client)
    assert config(client, slow_seconds=120).status_code == 200
    assert config(client, cost_warning_percent=90).status_code == 200
    assert store.setting("automation")["slow_seconds"] == 120
    assert store.setting("automation")["cost_warning_percent"] == 90


def test_candidate_download_hash_and_permission(client):
    observed_download("JOB-fixture-download", b"candidate download")
    row = store.rows("SELECT * FROM source_versions")[0]
    login(client, "analyst")
    path = f"/api/control/admin/versions/{row['id']}/download"
    assert client.get(path).status_code == 403
    login(client, "data_admin")
    response = client.get(path)
    assert response.status_code == 200 and response.content == b"candidate download"
    assert row["sha256"][:12] in response.headers["content-disposition"]
    (store.DATA / "artifacts/JOB-fixture-download" / (DOC + ".source")).write_bytes(b"changed after review")
    assert client.get(path).status_code == 409


def test_alert_bookkeeping_error_never_replaces_original_answer(client, monkeypatch):
    login(client, "employee")
    receipt = sample_receipt()
    mock_upstream(monkeypatch, receipt)
    def unavailable():
        raise RuntimeError("local alert bookkeeping unavailable")
    monkeypatch.setattr(flow, "reconcile", unavailable)
    response = ask(client)
    assert response.status_code == 200 and response.json() == receipt
    assert store.rows("SELECT status FROM requests")[0]["status"] == 200


def test_legacy_cookie_is_migrated_without_extending_server_expiry(client, monkeypatch):
    login(client, "employee")
    token = client.cookies.get("klink_ops_employee")
    expiry = store.rows("SELECT expires FROM sessions WHERE id=?", (store.hash_token(token),))[0]["expires"]
    client.cookies.clear()
    client.cookies.set("klink_ops_employee", token, domain="testserver.local", path="/api/control")
    assert client.get("/api/control/session").status_code == 200
    assert store.rows("SELECT expires FROM sessions WHERE id=?", (store.hash_token(token),))[0]["expires"] == expiry
    mock_upstream(monkeypatch, sample_receipt())
    response = ask(client)
    row = store.rows("SELECT owner_session FROM requests WHERE id=?", (response.headers["X-Klink-Meter-Id"],))[0]
    assert row["owner_session"] == store.hash_token(token)
