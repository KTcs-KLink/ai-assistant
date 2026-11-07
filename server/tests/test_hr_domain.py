"""HR rules, membership, source provenance, workflow staleness and reminder boundaries."""
from copy import deepcopy
from datetime import date
import hashlib
import importlib
import json

from fastapi.testclient import TestClient
import pytest

from server import benefits_api, hr_policy, hr_evidence, hr_answer, hr_forms, hr_runtime, supabase_bridge
from server.benefit_rules import BenefitProfile, DEMO_PROFILE

DAY = date(2026, 11, 7)


@pytest.fixture
def hr(tmp_path, monkeypatch):
    monkeypatch.setenv("KLINK_DATA_DIR", str(tmp_path/"app"))
    monkeypatch.setenv("KLINK_BENEFITS_DEMO", "true")
    for name in ["KLINK_ENV_FILE", "KLINK_LOCAL_REVIEWED_UNITS", "KLINK_HR_POLICIES_FILE", "KLINK_HR_APPROVALS_FILE", "KLINK_HR_FORMS_FILE", "KLINK_HR_FORMS_DIR"]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(supabase_bridge, "settings", lambda: ("", ""))
    monkeypatch.setattr(hr_policy, "today", lambda: DAY)
    benefits_api.SESSIONS.clear()
    hr_runtime.WINDOWS.clear()
    hr_runtime.COUNTS.clear()
    app = importlib.reload(importlib.import_module("server.app")).app
    with TestClient(app) as client:
        assert client.post("/api/benefits/session/demo").status_code == 200
        assert client.post("/api/benefits/profile/example").status_code == 200
        yield client, app
    benefits_api.SESSIONS.clear()


def company_policy():
    data = hr_policy.demo_policies()[0].model_dump(mode="json")
    data["company"] = data["source"]["company"] = "KTCS"
    data["version"] = data["source"]["version"] = "test-only-1"
    data["source"]["id"] = "TEST-POLICY-1"
    return hr_policy.Policy.model_validate(data)


def approval(policy):
    return hr_policy.Approval(policy_id=policy.id, company="KTCS", version=policy.version,
        policy_sha256=policy.digest(), source_sha256=policy.source.sha256, approval_ref="TEST-APPROVAL-NOT-REAL", approved_on=DAY)


def test_independent_approval_and_exact_version_are_required():
    policy = company_policy()
    result = hr_policy.evaluate(policy, DEMO_PROFILE, [], company="KTCS", as_of=DAY)
    assert result["status"] == "needs_review" and not result["production_verified"]
    approved = approval(policy)
    assert hr_policy.evaluate(policy, DEMO_PROFILE, [approved], company="KTCS", as_of=DAY)["production_verified"]
    changed = policy.model_copy(update={"value": "변경된 금액"})
    assert hr_policy.evaluate(changed, DEMO_PROFILE, [approved], company="KTCS", as_of=DAY)["status"] == "needs_review"


@pytest.mark.parametrize("change", [dict(company="DEMO"), dict(version="wrong"), dict(policy_sha256="0"*64), dict(source_sha256="0"*64), dict(approved_on=date(2026, 12, 1)), dict(expires_on=date(2026, 11, 6))])
def test_wrong_company_version_hash_future_or_expired_approval_cannot_grant(change):
    policy = company_policy()
    original = approval(policy).model_dump()
    # The intentionally wrong company is an object with no authority, not a valid approval artifact.
    if "company" in change:
        assert hr_policy.evaluate(policy, DEMO_PROFILE, [], company="DEMO", as_of=DAY)["status"] == "needs_review"
    else:
        bad = hr_policy.Approval(**(original|change))
        assert not hr_policy.evaluate(policy, DEMO_PROFILE, [bad], company="KTCS", as_of=DAY)["production_verified"]


def test_regulation_expiry_and_incomplete_dependencies_override_true_conditions():
    policy = company_policy()
    for patch in [dict(effective_to=date(2026, 11, 6)), dict(conditions_complete=False), dict(unresolved=["필수 예외 조문 미확인"])]:
        changed = policy.model_copy(update=patch)
        result = hr_policy.evaluate(changed, DEMO_PROFILE, [approval(changed)], company="KTCS", as_of=DAY)
        assert result["status"] == "needs_review"


def test_missing_family_is_not_no_children_and_known_fail_explains_first():
    policy = hr_policy.demo_policies()[0]
    missing = DEMO_PROFILE.model_copy(update={"family_consent": False})
    assert hr_policy.evaluate(policy, missing, [], company="DEMO", as_of=DAY)["status"] == "needs_review"
    empty = DEMO_PROFILE.model_copy(update={"children_ages": []})
    assert hr_policy.evaluate(policy, empty, [], company="DEMO", as_of=DAY)["status"] == "ineligible"
    long_service = hr_policy.demo_policies()[3]
    incomplete = DEMO_PROFILE.model_copy(update={"employment_type": None})
    result = hr_policy.evaluate(long_service, incomplete, [], company="DEMO", as_of=DAY)
    assert result["status"] == "ineligible" and "10년" in result["reasons"][0]


@pytest.mark.parametrize("types,status", [(["regular"], "ineligible"), (["part_time"], "eligible")])
def test_structured_exclusions_are_evaluated_instead_of_only_displayed(types, status):
    policy = company_policy().model_copy(update={"exceptions": ["가상 테스트 제외 대상"],
        "exclusions": [[hr_policy.Condition(id="excluded", label="지원 제외 고용형태", kind="employment", employment_types=types)]]})
    assert hr_policy.evaluate(policy, DEMO_PROFILE, [approval(policy)], company="KTCS", as_of=DAY)["status"] == status
    unmapped = policy.model_copy(update={"exclusions": []})
    assert hr_policy.evaluate(unmapped, DEMO_PROFILE, [approval(unmapped)], company="KTCS", as_of=DAY)["status"] == "needs_review"


def test_negated_condition_preserves_unknown_when_consent_is_missing():
    condition = hr_policy.Condition(id="not-regular", label="정규직 이외", kind="employment", employment_types=["regular"], negate=True)
    assert hr_policy.condition_check(condition, DEMO_PROFILE, DAY)["state"] == "fail"
    assert hr_policy.condition_check(condition, BenefitProfile(), DAY)["state"] == "unknown"


def test_rule_file_rejects_tampering_self_approval_and_duplicate_ids(tmp_path, monkeypatch):
    policy = company_policy().model_dump(mode="json")
    path = tmp_path/"policies.json"
    monkeypatch.setenv("KLINK_HR_POLICIES_FILE", str(path))
    for data in [[policy|{"human_approved": True}], [policy, policy], [policy|{"source": policy["source"]|{"quote": "변경된 원문으로 바꾼 테스트"}}]]:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(ValueError):
            hr_policy.registry()


def test_rule_condition_ranges_and_unknown_fields_are_rejected():
    for payload in [dict(id="x", label="x", kind="children", minimum=8, maximum=7), dict(id="x", label="x", kind="employment"), dict(id="x", label="x", kind="tenure", minimum=True), dict(id="x", label="x", kind="household", minimum=0)]:
        with pytest.raises(ValueError):
            hr_policy.Condition(**payload)


def prepare(client):
    data = client.get("/api/benefits/hr/catalog").json()
    card = next(c for c in data["cards"] if c["id"] == "childcare")
    payload = dict(conditions_revision=data["conditions_revision"], policy_sha256=card["policy_sha256"])
    result = client.post("/api/benefits/hr/preparations/childcare", json=payload)
    assert result.status_code == 200
    return result.json(), payload


def test_preparation_idempotence_stale_profile_recheck_and_no_submission(hr):
    client, _ = hr
    plan, payload = prepare(client)
    assert client.post("/api/benefits/hr/preparations/childcare", json=payload).json()["id"] == plan["id"]
    assert client.patch("/api/benefits/hr/preparations/"+plan["id"], json={"index": 0, "checked": True}).json()["checked"] == [0]
    assert client.post("/api/benefits/hr/preparations/"+plan["id"]+"/submit").status_code == 409
    changed = DEMO_PROFILE.model_dump(mode="json")|{"children_ages": [6]}
    assert client.put("/api/benefits/profile", json=changed).status_code == 200
    stale = client.get("/api/benefits/hr/preparations").json()["plans"][0]
    assert stale["stale"] and stale["checked"] == []
    assert client.post("/api/benefits/hr/preparations/childcare", json=payload).status_code == 409
    assert client.patch("/api/benefits/hr/preparations/"+plan["id"], json={"index": 0, "checked": True}).status_code == 409
    refreshed, _ = prepare(client)
    assert refreshed["id"] != plan["id"] and not refreshed["stale"]


def test_policy_change_invalidates_preparation(hr, monkeypatch):
    client, _ = hr
    plan, _ = prepare(client)
    original = hr_policy.demo_policies()
    original[0] = original[0].model_copy(update={"checklist": ["변경된 준비 항목"]})
    monkeypatch.setattr(hr_policy, "demo_policies", lambda: original)
    stale = client.get("/api/benefits/hr/preparations").json()["plans"][0]
    assert stale["id"] == plan["id"] and stale["stale"]


def test_preparation_ids_are_session_owned(hr):
    client, app = hr
    plan, _ = prepare(client)
    with TestClient(app) as other:
        other.post("/api/benefits/session/demo")
        assert other.get("/api/benefits/hr/preparations").json()["plans"] == []
        assert other.delete("/api/benefits/hr/preparations/"+plan["id"]).status_code == 404
        assert other.patch("/api/benefits/hr/preparations/"+plan["id"], json={"index": 0, "checked": True}).status_code == 404


def test_reminders_require_consent_detect_changes_and_are_cleared_on_revocation(hr):
    client, _ = hr
    assert not client.get("/api/benefits/hr/updates").json()["enabled"]
    assert client.put("/api/benefits/hr/reminders", json={"enabled": True}).json()["external_notifications_sent"] is False
    first = client.get("/api/benefits/hr/updates").json()
    assert any(u["kind"] == "deadline" for u in first["updates"])
    client.put("/api/benefits/profile", json=DEMO_PROFILE.model_dump(mode="json")|{"family_consent": False})
    changed = client.get("/api/benefits/hr/updates").json()
    assert any(u["kind"] == "conditions_or_policy_changed" for u in changed["updates"])
    client.delete("/api/benefits/profile")
    assert not client.get("/api/benefits/hr/updates").json()["enabled"]
    assert client.get("/api/benefits/hr/preparations").json()["plans"] == []


def test_unapproved_company_rules_are_not_silently_replaced_with_demo(hr, monkeypatch):
    client, _ = hr
    session = next(iter(benefits_api.SESSIONS.values()))
    session.update(mode="supabase", uid="00000000-0000-0000-0000-000000000001", access_token="test-jwt")
    monkeypatch.setattr(supabase_bridge, "identity", lambda token: session["uid"])
    monkeypatch.setattr(supabase_bridge, "employee_authorized", lambda token, uid: True)
    result = client.get("/api/benefits/hr/catalog").json()
    assert result["cards"] == [] and result["configuration_required"] and not result["production_eligibility_verified"]
    assert client.get("/api/benefits/hr/evidence").status_code == 403
    assert client.post("/api/benefits/hr/answer", json={"question": "병가는 언제 쓰나요?"}).status_code == 409


def test_non_employee_and_membership_revocation_are_rejected(hr, monkeypatch):
    client, _ = hr
    monkeypatch.setattr(supabase_bridge, "login", lambda *a: {"access_token": "test-only"})
    monkeypatch.setattr(supabase_bridge, "identity", lambda *a: "00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(supabase_bridge, "employee_authorized", lambda *a: False)
    assert client.post("/api/benefits/session/login", json={"email": "synthetic@example.invalid", "password": "test-only"}).status_code == 503
    session = next(iter(benefits_api.SESSIONS.values()))
    session.update(mode="supabase", uid="00000000-0000-0000-0000-000000000001", access_token="test-only")
    assert client.get("/api/benefits/hr/catalog").status_code == 401
    assert not benefits_api.SESSIONS


def test_rate_limit_csrf_request_size_and_no_input_echo(hr, monkeypatch):
    client, _ = hr
    monkeypatch.setattr(supabase_bridge, "login", lambda *a: (_ for _ in ()).throw(supabase_bridge.IntegrationUnavailable()))
    for _ in range(6):
        assert client.post("/api/benefits/session/login", json={"email": "synthetic@example.invalid", "password": "test-only"}).status_code == 503
    assert client.post("/api/benefits/session/login", json={"email": "synthetic@example.invalid", "password": "test-only"}).status_code == 429
    assert client.put("/api/benefits/hr/reminders", json={"enabled": True}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/api/benefits/hr/answer", content="x"*17000).status_code == 413
    marker = "private@example.invalid"
    response = client.post("/api/benefits/hr/answer", json={"question": "병가 문의 "+marker})
    assert response.status_code == 422 and marker not in response.text


def test_expired_sessions_are_removed_and_operational_readiness_is_honest(hr):
    client, _ = hr
    ready = client.get("/api/benefits/hr/readiness").json()
    assert not ready["production_ready"] and ready["approved_policy_count"] == 0
    assert len(ready["gates"]) == 6 and not ready["profile_question_or_key_logged"]
    next(iter(benefits_api.SESSIONS.values()))["expires"] = 0
    assert client.get("/api/benefits/hr/catalog").status_code == 401
    assert not benefits_api.SESSIONS


def test_official_form_registry_fails_closed(hr, tmp_path, monkeypatch):
    client, _ = hr
    forms = client.get("/api/benefits/hr/forms").json()["forms"]
    assert len(forms) == 6 and not any(f["official_available"] for f in forms)
    assert client.get("/api/benefits/hr/forms/leave/download").status_code == 403
    path = tmp_path/"forms.json"
    monkeypatch.setenv("KLINK_HR_FORMS_FILE", str(path))
    monkeypatch.setenv("KLINK_HR_FORMS_DIR", str(tmp_path/"blank"))
    form = dict(id="leave", company="KTCS", version="test", source_url="https://example.invalid/form", approval_ref="TEST-ONLY",
        blank_template_verified=True, filename="../private.pdf", sha256="0"*64)
    path.write_text(json.dumps([form]), encoding="utf-8")
    with pytest.raises(ValueError):
        hr_forms.verified()


def source_row(text="병가는 질병으로 근무할 수 없을 때 확인하는 가상 테스트 문구입니다.", **patch):
    return dict(id="TEST-HR-1", document_title="취업규칙", heading_path="가상 테스트 제1조", text=text,
        text_sha256=hashlib.sha256(text.encode()).hexdigest(), searchable=True, answer_eligible=True, source_scope_reviewed=True,
        human_approved=False, employee_scope="가상 테스트 직원", file_version_key="test-only") | patch


def test_hr_reader_filters_other_domains_unreviewed_and_changed_text(tmp_path, monkeypatch):
    good = source_row()
    rows = [good, good|dict(id="OTHER", document_title="회계규정"), good|dict(id="UNREVIEWED", source_scope_reviewed=False), good|dict(id="CHANGED", text="본문 변경"), source_row("개인 연락처 private@example.invalid", id="PRIVATE")]
    path = tmp_path/"units.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    monkeypatch.setenv("KLINK_LOCAL_REVIEWED_UNITS", str(path))
    assert hr_evidence.summary()["source_count"] == 1
    assert [r["id"] for r in hr_evidence.search("병가")] == ["TEST-HR-1"]
    assert not hr_evidence.source("CHANGED")
    assert not hr_evidence.search("오늘 날씨")


def test_answers_require_verbatim_allowed_id_and_numbers_in_the_cited_quote():
    row = source_row("가상 테스트에서 병가 확인 기간은 3일이며 실제 회사 규정은 아닙니다.")
    draft = dict(status="answered", paragraphs=[dict(text="가상 테스트의 확인 기간은 3일입니다.", citations=[dict(source_id=row["id"], quote=row["text"])])], missing_information=[])
    assert hr_answer.validate(hr_answer.Draft(**draft), [row])
    for text, source_id, quote in [("10일입니다.", row["id"], row["text"]), ("기간 안내", "UNKNOWN", row["text"]), ("기간 안내", row["id"], "없는 문장을 만든 테스트 인용")]:
        changed = deepcopy(draft)
        changed["paragraphs"] = [dict(text=text, citations=[dict(source_id=source_id, quote=quote)])]
        with pytest.raises(hr_answer.AnswerUnavailable):
            hr_answer.validate(hr_answer.Draft(**changed), [row])


def test_article_numbers_use_exact_source_context_while_factual_numbers_still_need_quotes():
    text = "가상 예시에서 자녀 1인에 대하여 3년 이내로 정한 문구입니다."
    source = dict(id="TEST", section="가상 규정 제52조 휴직기간", text=text)
    def draft(summary):
        return hr_answer.Draft(status="answered", paragraphs=[hr_answer.Paragraph(text=summary,
            citations=[hr_answer.Citation(source_id="TEST", quote=text)])], missing_information=[])
    assert hr_answer.validate(draft("제52조에서 자녀 1인에 대하여 3년 이내로 정해요."), [source])
    for summary in ["제999조에서 3년 이내로 정해요.", "제52조에서 10년 이내로 정해요."]:
        with pytest.raises(hr_answer.AnswerUnavailable):
            hr_answer.validate(draft(summary), [source])
    with pytest.raises(hr_answer.AnswerUnavailable):
        hr_answer.validate(draft("제52조에서 3년 이내로 정해요."), [source|dict(section="가상 규정 제52조의2")])


def test_oversized_complete_evidence_is_not_truncated_or_sent_for_generation(monkeypatch):
    from openai import OpenAI
    from types import SimpleNamespace
    monkeypatch.setattr(hr_evidence, "search", lambda q: [source_row()|dict(company="KEPCO", title="취업규칙", section="가상 테스트")])
    monkeypatch.setattr(hr_evidence, "summary", lambda: {"source_count": 1})
    monkeypatch.setattr(hr_answer.benefit_explanation, "settings", lambda: ("test-key", "test-model"))
    class Fake:
        def __init__(self, **kw):
            self.responses = SimpleNamespace(input_tokens=SimpleNamespace(count=self.count))
        def count(self, **payload):
            assert "source_id" in str(payload) or "TEST-HR-1" in str(payload)
            assert "hire_date" not in str(payload) and payload["truncation"] == "disabled"
            assert all(k in json.loads(payload["input"])["sources"][0] for k in ("version", "effective_status", "human_approved", "company"))
            return SimpleNamespace(input_tokens=8193)
        def __enter__(self): return self
        def __exit__(self, *a): pass
    monkeypatch.setattr("openai.OpenAI", Fake)
    result = hr_answer.generate("병가는 언제 쓰나요?")
    assert result["status"] == "needs_review" and result["token_count"] == 8193


def test_invalid_generated_text_is_withheld_but_verified_sources_remain_available(monkeypatch):
    from types import SimpleNamespace
    row = source_row("가상 테스트에서 확인 기간은 3일입니다.")|dict(company="KEPCO", title="가상 테스트", section="제1조")
    monkeypatch.setattr(hr_evidence, "search", lambda q: [row])
    monkeypatch.setattr(hr_evidence, "summary", lambda: {"source_count": 1})
    monkeypatch.setattr(hr_answer.benefit_explanation, "settings", lambda: ("test-key", "test-model"))
    class Fake:
        def __init__(self, **kw):
            self.responses=SimpleNamespace(input_tokens=SimpleNamespace(count=lambda **kw: SimpleNamespace(input_tokens=100)), create=self.create)
        def create(self, **payload):
            assert payload["store"] is False
            invalid=dict(status="answered", paragraphs=[dict(text="가상 테스트의 기간은 999일입니다.", citations=[dict(source_id=row["id"], quote=row["text"])])],missing_information=[])
            return SimpleNamespace(status="completed", output_text=json.dumps(invalid), usage=None)
        def __enter__(self): return self
        def __exit__(self,*a): pass
    monkeypatch.setattr("openai.OpenAI", Fake)
    result=hr_answer.generate("병가는 언제 쓰나요?")
    assert result["status"] == "needs_review" and result["paragraphs"] == []
    assert result["generated_text_withheld"] and "999" not in json.dumps(result)
    assert result["sources"][0]["text"] == row["text"]


def test_provider_rate_limit_diagnostic_never_exposes_provider_body(monkeypatch):
    import httpx
    import openai
    from types import SimpleNamespace
    row=source_row()|dict(company="KEPCO",title="가상 테스트",section="제1조")
    monkeypatch.setattr(hr_evidence,"search",lambda q:[row])
    monkeypatch.setattr(hr_evidence,"summary",lambda:{"source_count":1})
    monkeypatch.setattr(hr_answer.benefit_explanation,"settings",lambda:("test-key","test-model"))
    class Fake:
        def __init__(self, **kw): self.responses=SimpleNamespace(input_tokens=SimpleNamespace(count=self.count))
        def count(self, **kw):
            raise openai.RateLimitError("PRIVATE_PROVIDER_VALUE", response=httpx.Response(429, request=httpx.Request("POST","https://example.invalid")), body={"private":"PRIVATE_PROVIDER_VALUE"})
        def __enter__(self): return self
        def __exit__(self,*a): pass
    monkeypatch.setattr("openai.OpenAI",Fake)
    with pytest.raises(hr_answer.AnswerUnavailable) as error:
        hr_answer.generate("병가는 언제 쓰나요?")
    assert error.value.code == "PROVIDER_RATE_LIMITED" and "PRIVATE_PROVIDER_VALUE" not in str(error.value)
