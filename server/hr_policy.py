"""Versioned HR rules. Approval is a separate, server-owned artifact, never a client flag."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

try:
    from .benefit_rules import BenefitProfile, CATALOG
except ImportError:
    from benefit_rules import BenefitProfile, CATALOG


def today() -> date:
    return datetime.now(timezone(timedelta(hours=9))).date()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,120}$")
    company: Literal["KTCS", "DEMO"]
    title: str = Field(min_length=1, max_length=200)
    section: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=80)
    quote: str = Field(min_length=8, max_length=60000)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def intact(self):
        if hashlib.sha256(self.quote.encode()).hexdigest() != self.sha256:
            raise ValueError("source integrity failed")
        return self


class Condition(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,60}$")
    label: str = Field(min_length=1, max_length=100)
    kind: Literal["employment", "tenure", "children", "household"]
    employment_types: list[Literal["regular", "fixed_term", "part_time"]] = Field(default_factory=list, max_length=3)
    minimum: int | None = Field(default=None, strict=True, ge=0, le=70)
    maximum: int | None = Field(default=None, strict=True, ge=0, le=70)
    negate: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def parameters(self):
        if self.kind == "employment":
            valid = bool(self.employment_types) and self.minimum is None and self.maximum is None
        elif self.kind == "children":
            valid = not self.employment_types and self.minimum is not None and self.maximum is not None and 0 <= self.minimum <= self.maximum <= 30
        else:
            valid = not self.employment_types and self.minimum is not None and self.maximum is None
            if self.kind == "household":
                valid = valid and 1 <= self.minimum <= 20
        if not valid:
            raise ValueError("invalid condition parameters")
        return self


class Policy(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,80}$")
    company: Literal["KTCS", "DEMO"]
    version: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=150)
    category: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=150)
    effective_from: date
    effective_to: date | None = None
    deadline: date | None = None
    source: Source
    conditions: list[Condition] = Field(min_length=1, max_length=25)
    exceptions: list[str] = Field(default_factory=list, max_length=25)
    exclusions: list[list[Condition]] = Field(default_factory=list, max_length=25)
    unresolved: list[str] = Field(default_factory=list, max_length=25)
    conditions_complete: bool = False
    checklist: list[str] = Field(min_length=1, max_length=25)
    form_id: str | None = Field(default=None, pattern=r"^[a-z0-9_-]{1,80}$")

    @model_validator(mode="after")
    def consistent(self):
        if self.company != self.source.company or self.version != self.source.version:
            raise ValueError("company or source version mismatch")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("invalid effective interval")
        if len({c.id for c in self.conditions}) != len(self.conditions):
            raise ValueError("duplicate condition")
        if any(not group or len(group) > 25 or len({c.id for c in group}) != len(group) for group in self.exclusions):
            raise ValueError("invalid exclusion group")
        return self

    def digest(self) -> str:
        body = json.dumps(self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(body.encode()).hexdigest()


class Approval(StrictModel):
    policy_id: str
    company: Literal["KTCS"]
    version: str
    policy_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    approval_ref: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")
    approved_on: date
    expires_on: date | None = None


def read_records(setting: str, model: type[BaseModel]) -> list:
    configured = os.getenv(setting)
    if not configured:
        return []
    path = Path(configured).expanduser().resolve()
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("registry unavailable")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) > 200:
        raise ValueError("invalid registry")
    return [model.model_validate(item) for item in data]


def registry() -> tuple[list[Policy], list[Approval]]:
    policies = read_records("KLINK_HR_POLICIES_FILE", Policy)
    approvals = read_records("KLINK_HR_APPROVALS_FILE", Approval)
    if len({p.id for p in policies}) != len(policies) or len({a.policy_id for a in approvals}) != len(approvals):
        raise ValueError("duplicate registry id")
    return policies, approvals


def demo_policies() -> list[Policy]:
    result = []
    for p in CATALOG:
        rules = [dict(id="employment", label="고용형태", kind="employment", employment_types=p["employment_types"])]
        if p["min_years"]:
            rules.append(dict(id="tenure", label="근속기간", kind="tenure", minimum=p["min_years"]))
        if "child_max_age" in p:
            rules.append(dict(id="children", label="자녀 연령", kind="children", minimum=p.get("child_min_age", 0), maximum=p["child_max_age"]))
        if "household_min" in p:
            rules.append(dict(id="household", label="가구 구성", kind="household", minimum=p["household_min"]))
        result.append(Policy(id=p["id"], company="DEMO", version="demo-2026.11.07", title=p["title"],
            category=p["category"], value=p["value"], effective_from=date(2026, 1, 1), deadline=p["deadline"],
            source=Source(id="DEMO-"+p["id"], company="DEMO", title="가상 복지 규정", section=p["section"],
                version="demo-2026.11.07", quote=p["quote"], sha256=hashlib.sha256(p["quote"].encode()).hexdigest()),
            conditions=rules, conditions_complete=True, checklist=p["checklist"],
            unresolved=[p.get("unresolved_reason", "필수 조건 추가 확인")] if p.get("unresolved") else [],
            form_id="leave" if p["id"] == "family-leave" else None))
    return result


def approval_gates(policy: Policy, approvals: list[Approval], company: str, as_of: date) -> list[str]:
    failures = []
    if policy.company != company:
        failures.append("회사 적용 범위가 일치하지 않아요.")
    if policy.effective_from > as_of or (policy.effective_to and policy.effective_to < as_of):
        failures.append("평가 기준일의 현행 규정으로 확인되지 않았어요.")
    if not policy.conditions_complete or policy.unresolved:
        failures.extend(policy.unresolved or ["필수 조건·예외 검토가 완료되지 않았어요."])
    if len(policy.exceptions) != len(policy.exclusions):
        failures.append("예외 조문과 지원 제외 조건의 연결이 완료되지 않았어요.")
    if company != "DEMO":
        match = next((a for a in approvals if a.policy_id == policy.id and a.company == company
            and a.version == policy.version and a.policy_sha256 == policy.digest() and a.source_sha256 == policy.source.sha256
            and a.approved_on <= as_of and (not a.expires_on or as_of <= a.expires_on)), None)
        if not match:
            failures.append("이 규정 버전과 본문에 대한 회사의 승인 기록이 없어요.")
    return failures


def condition_check(c: Condition, p: BenefitProfile, day: date) -> dict:
    state, reason = "unknown", "동의해 제공한 조건을 추가로 확인해 주세요."
    if c.kind == "employment" and p.employment_type is not None:
        state = "pass" if p.employment_type in c.employment_types else "fail"
        reason = "고용형태가 지원 대상에 포함돼요." if state == "pass" else "고용형태가 지원 대상에 포함되지 않아요."
    elif c.kind == "tenure" and p.hire_date is not None and p.hire_date <= day:
        years = day.year-p.hire_date.year-((day.month, day.day) < (p.hire_date.month, p.hire_date.day))
        state = "pass" if years >= c.minimum else "fail"
        reason = f"만 {years}년 근속 · {c.minimum}년 이상 조건이에요."
    elif c.kind == "children" and p.children_ages is not None:
        state = "pass" if any(c.minimum <= a <= c.maximum for a in p.children_ages) else "fail"
        reason = f"만 {c.minimum}~{c.maximum}세 자녀 조건" + ("에 맞아요." if state == "pass" else "에 해당하지 않아요.")
    elif c.kind == "household" and p.household_size is not None:
        state = "pass" if p.household_size >= c.minimum else "fail"
        reason = f"가구원 {c.minimum}명 이상 조건" + ("에 맞아요." if state == "pass" else "에 해당하지 않아요.")
    if c.negate and state != "unknown":
        state = "fail" if state == "pass" else "pass"
        reason = "이 조건을 만족하지 않아야 해요. " + reason
    return dict(id=c.id, label=c.label, state=state, reason=reason)


def evaluate(policy: Policy, profile: BenefitProfile, approvals: list[Approval], *, company: str, as_of: date | None = None) -> dict:
    day, p = as_of or today(), profile.consented()
    gates = approval_gates(policy, approvals, company, day)
    checks = [condition_check(c, p, day) for c in policy.conditions]
    for index, group in enumerate(policy.exclusions):
        details = [condition_check(c, p, day) for c in group]
        state = "pass" if any(c["state"] == "fail" for c in details) else "unknown" if any(c["state"] == "unknown" for c in details) else "fail"
        reasons = {"pass": "지원 제외 조건에 해당하지 않아요.", "unknown": "지원 제외 조건을 추가로 확인해야 해요.", "fail": "지원 제외 조건에 해당해요."}
        checks.append(dict(id=f"exclusion-{index}", label=policy.exceptions[index] if index < len(policy.exceptions) else "미연결 예외", state=state, reason=reasons[state], details=details))
    if policy.deadline and day > policy.deadline:
        checks.append(dict(id="deadline", label="접수기간", state="fail", reason="확인된 신청 기간이 지났어요."))
    status = "needs_review" if gates else "ineligible" if any(c["state"] == "fail" for c in checks) else "needs_review" if any(c["state"] == "unknown" for c in checks) else "eligible"
    reasons = gates or [c["reason"] for c in checks if c["state"] == "fail"] or [c["reason"] for c in checks if c["state"] == "unknown"] or ["동의해 제공한 조건이 규정의 필수 조건에 맞아요."]
    return dict(id=policy.id, title=policy.title, category=policy.category, value=policy.value, status=status,
        reasons=reasons, checks=checks, exceptions=policy.exceptions, checklist=policy.checklist, source=policy.source.model_dump(),
        policy_version=policy.version, policy_sha256=policy.digest(), as_of=day.isoformat(),
        deadline=policy.deadline.isoformat() if policy.deadline else None, form_id=policy.form_id,
        synthetic=company == "DEMO", production_verified=company == "KTCS" and not gates,
        application_enabled=False, policy_approval_verified=company == "KTCS" and not gates)
