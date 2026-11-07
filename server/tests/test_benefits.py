"""Eligibility boundaries, consent, isolation, source integrity, and safe integration failures."""
import hashlib
import importlib
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from server.benefit_rules import BenefitProfile, CATALOG, DEMO_PROFILE, evaluate
from server import local_evidence, supabase_bridge
from server import benefit_explanation

TODAY = date(2026, 11, 7)


def test_anniversary_and_child_age_are_inclusive():
    p = DEMO_PROFILE.model_copy(update={"hire_date": date(2025, 11, 7), "children_ages": [7]})
    assert evaluate(CATALOG[0], p, as_of=TODAY)["status"] == "eligible"
    assert evaluate(CATALOG[0], p, as_of=date(2026, 11, 6))["status"] == "ineligible"
    p.children_ages = [8]
    assert evaluate(CATALOG[0], p, as_of=TODAY)["status"] == "ineligible"


def test_unknown_is_not_no_children_and_revoked_consent_removes_information():
    p = DEMO_PROFILE.model_copy(update={"family_consent": False})
    clean = p.consented()
    assert clean.children_ages is None and clean.household_size is None
    assert evaluate(CATALOG[0], p, as_of=TODAY)["status"] == "needs_review"
    p = DEMO_PROFILE.model_copy(update={"children_ages": []})
    assert evaluate(CATALOG[0], p, as_of=TODAY)["status"] == "ineligible"


def test_deadline_last_day_and_expiry():
    assert evaluate(CATALOG[0], DEMO_PROFILE, as_of=date(2026, 11, 30))["status"] == "eligible"
    assert evaluate(CATALOG[0], DEMO_PROFILE, as_of=date(2026, 12, 1))["status"] == "ineligible"


@pytest.mark.parametrize("age", [True, -1, 31, "5", 5.5])
def test_invalid_child_age_is_rejected(age):
    with pytest.raises(ValueError):
        BenefitProfile(children_ages=[age])


def test_ai_draft_requires_allowed_id_verbatim_quote_and_source_numbers():
    p = CATALOG[0]
    valid = dict(summary="가상 규정입니다.", source_id="DEMO-childcare", quote=p["quote"])
    assert benefit_explanation.validate(benefit_explanation.Draft(**valid), p)
    for patch in [dict(source_id="unknown"), dict(quote="없는 근거를 만들어낸 인용"), dict(summary="100만 원 지급")]:
        with pytest.raises(benefit_explanation.ExplanationUnavailable):
            benefit_explanation.validate(benefit_explanation.Draft(**(valid | patch)), p)


def test_ai_draft_never_receives_profile_or_changes_eligibility(benefits, monkeypatch):
    c, _ = benefits
    start(c)
    received = []
    def fake(policy):
        received.append(policy)
        return dict(summary="가상 규정 초안", source_id="DEMO-childcare", quote=policy["quote"])
    monkeypatch.setattr(benefit_explanation, "generate", fake)
    before = c.get("/api/benefits/recommendations").json()
    assert c.post("/api/benefits/childcare/explanation").status_code == 200
    assert c.post("/api/benefits/childcare/explanation").status_code == 200
    assert len(received) == 1 and "hire_date" not in received[0] and "children_ages" not in received[0]
    assert c.get("/api/benefits/recommendations").json() == before


@pytest.mark.parametrize("index", [0, 3, 5])
def test_unapproved_or_other_company_rule_cannot_grant_or_deny(index):
    c = evaluate(CATALOG[index], DEMO_PROFILE, as_of=TODAY, company="KTCS", approved=True)
    assert c["status"] == "needs_review"
    assert not c["production_verified"] and not c["application_enabled"]
    assert c["source"]["company"] == "DEMO"
    assert "KTcs" in c["reasons"][0]


@pytest.fixture()
def benefits(tmp_path, monkeypatch):
    monkeypatch.setenv("KLINK_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("KLINK_BENEFITS_DEMO", "true")
    monkeypatch.delenv("KLINK_ENV_FILE", raising=False)
    monkeypatch.setattr(supabase_bridge, "settings", lambda: ("", ""))
    app = importlib.reload(importlib.import_module("server.app")).app
    with TestClient(app) as client:
        yield client, app


def start(client):
    r = client.post("/api/benefits/session/demo")
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower()
    assert "samesite=strict" in r.headers["set-cookie"].lower()
    assert client.post("/api/benefits/profile/example").status_code == 200


def test_profile_mutation_bookmark_prepare_and_consent_revocation(benefits):
    client, _ = benefits
    assert client.get("/api/benefits/recommendations").status_code == 401
    start(client)
    r = client.get("/api/benefits/recommendations")
    assert r.headers["cache-control"] == "no-store"
    assert len(r.json()["cards"]) == 6
    card = r.json()["cards"][0]
    assert card["status"] == "eligible"
    assert client.put("/api/benefits/childcare/bookmark", json={"saved": True}).json()["saved"]
    prepared = client.post("/api/benefits/childcare/prepare").json()
    assert prepared["status"] == "demo_preparation_only" and prepared["submitted"] is False
    # Stale UI status cannot be used after the profile changes.
    p = client.get("/api/benefits/profile").json()
    p["employment_type"] = "part_time"
    assert client.put("/api/benefits/profile", json=p).status_code == 200
    assert client.post("/api/benefits/childcare/prepare").status_code == 409
    assert client.delete("/api/benefits/profile").status_code == 204
    empty = client.get("/api/benefits/profile").json()
    assert empty["children_ages"] is None and empty["hire_date"] is None
    assert client.get("/api/benefits/recommendations").json()["counts"]["eligible"] == 0


def test_sessions_are_isolated_and_do_not_unlock_legacy_admin(benefits):
    first, app = benefits
    start(first)
    first.put("/api/benefits/childcare/bookmark", json={"saved": True})
    with TestClient(app) as second:
        assert second.get("/api/benefits/profile").status_code == 401
        second.post("/api/benefits/session/demo")
        assert second.get("/api/benefits/profile").json()["family_consent"] is False
        assert not second.get("/api/benefits/recommendations").json()["cards"][0]["saved"]
        assert second.get("/api/admin/documents").status_code == 401
        assert second.get("/api/conversations").status_code == 401
    first.delete("/api/benefits/session")
    assert first.get("/api/benefits/profile").status_code == 401


def test_errors_do_not_echo_personal_values_and_csrf_is_rejected(benefits):
    c, _ = benefits
    start(c)
    marker = "DO_NOT_ECHO_PRIVATE_VALUE"
    r = c.put("/api/benefits/profile", json={"children_ages": [marker]})
    assert r.status_code == 422 and marker not in r.text
    assert c.put("/api/benefits/profile", json={"name": marker}).status_code == 422
    assert c.post("/api/benefits/session/demo", headers={"Origin": "https://untrusted.invalid"}).status_code == 403
    assert c.get("/api/benefits/config").json()["supabase"]["status"] == "not_configured"


def test_local_evidence_rejects_changed_excerpt_and_unapproved_source(tmp_path, monkeypatch):
    path = tmp_path / "reviewed.jsonl"
    text = "가족 복지 안내"
    good = dict(id="source-1", document_title="참고자료", heading_path="제1조", text=text,
                searchable=True, answer_eligible=True, text_sha256=hashlib.sha256(text.encode()).hexdigest())
    changed = good | dict(id="source-2", text="변조된 금액")
    unapproved = good | dict(id="source-3", answer_eligible=False)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in [good, changed, unapproved]), encoding="utf-8")
    monkeypatch.setenv("KLINK_LOCAL_REVIEWED_UNITS", str(path))
    result = local_evidence.search("복지")
    assert [r["id"] for r in result["results"]] == ["source-1"]
    assert not result["ktcs_applicable"]
    assert local_evidence.source("source-2") is None


def test_supabase_failure_does_not_return_provider_body_or_create_session(benefits, monkeypatch):
    client, _ = benefits
    def unavailable(*a):
        raise supabase_bridge.IntegrationUnavailable("PRIVATE_PROVIDER_DIAGNOSTIC")
    monkeypatch.setattr(supabase_bridge, "login", unavailable)
    r = client.post("/api/benefits/session/login", json={"email": "synthetic@example.invalid", "password": "test-only"})
    assert r.status_code == 503 and "PRIVATE_PROVIDER_DIAGNOSTIC" not in r.text
    assert "set-cookie" not in r.headers


def test_live_identity_uses_own_jwt_and_cannot_confirm_synthetic_rules(benefits, monkeypatch):
    client, _ = benefits
    uid = "00000000-0000-0000-0000-000000000001"
    monkeypatch.setattr(supabase_bridge, "login", lambda *a: {"access_token": "test-jwt"})
    monkeypatch.setattr(supabase_bridge, "identity", lambda t: uid if t == "test-jwt" else None)
    monkeypatch.setattr(supabase_bridge, "get_profile", lambda t, u: DEMO_PROFILE.model_dump(mode="json") if (t, u) == ("test-jwt", uid) else None)
    r = client.post("/api/benefits/session/login", json={"email": "synthetic@example.invalid", "password": "test-only"})
    assert r.status_code == 200 and "test-jwt" not in r.text
    assert client.get("/api/benefits/recommendations").json()["counts"]["needs_review"] == 6
    assert client.post("/api/benefits/profile/example").status_code == 403
    assert client.post("/api/benefits/childcare/prepare").status_code == 409
    assert client.get("/api/benefits/evidence/search?q=복지").status_code == 403


def test_auth_success_is_distinct_from_database_schema_failure(monkeypatch):
    import httpx
    monkeypatch.setattr(supabase_bridge, "settings", lambda: ("https://synthetic.supabase.co", "sb_publishable_test_only"))
    monkeypatch.setattr(supabase_bridge, "call", lambda *a: {})
    class FakeClient:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def get(self, url, headers):
            assert "limit=0" in url and "SUPABASE_SECRET_KEY" not in headers
            return httpx.Response(503, json={"code": "PGRST002"})
    monkeypatch.setattr(supabase_bridge.httpx, "Client", FakeClient)
    result = supabase_bridge.connection_status()
    assert result["status"] == "database_unavailable"
    assert result["auth_reachable"] and not result["database_reachable"]
    assert result["error_code"] == "PGRST002"
