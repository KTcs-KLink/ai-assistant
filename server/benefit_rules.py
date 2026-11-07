"""Deterministic eligibility. The shipped catalog is SYNTHETIC, never KTcs policy."""
from __future__ import annotations

import hashlib
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BenefitProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employment_consent: bool = False
    family_consent: bool = False
    hire_date: date | None = None
    employment_type: Literal["regular", "fixed_term", "part_time"] | None = None
    children_ages: list[int] | None = Field(default=None, max_length=10)
    household_size: int | None = Field(default=None, ge=1, le=20)

    @field_validator("children_ages", mode="before")
    @classmethod
    def valid_ages(cls, values):
        if values is not None and (not isinstance(values, list) or any(type(age) is not int or not 0 <= age <= 30 for age in values)):
            raise ValueError("자녀 나이는 0~30세 정수로 입력하세요.")
        return values

    @field_validator("hire_date")
    @classmethod
    def valid_date(cls, value):
        if value and not date(1960, 1, 1) <= value <= date.today():
            raise ValueError("입사일을 확인하세요.")
        return value

    def consented(self) -> "BenefitProfile":
        data = self.model_dump()
        if not self.employment_consent:
            data.update(hire_date=None, employment_type=None)
        if not self.family_consent:
            data.update(children_ages=None, household_size=None)
        return BenefitProfile(**data)


DEMO_PROFILE = BenefitProfile(
    employment_consent=True, family_consent=True, hire_date=date(2019, 3, 11),
    employment_type="regular", children_ages=[5, 9], household_size=4,
)

# All amounts, thresholds, dates and text below are invented UI fixtures.
# This catalog has no authority to grant, deny or calculate a real employee benefit.
CATALOG = [
    dict(id="childcare", title="자녀 돌봄 지원금", category="가족·육아", icon="family",
         description="아이를 돌보는 일상에, 작은 여유를 더해요.", value="월 10만 원", value_note="자녀 1명당 · 예시 금액",
         employment_types=["regular", "fixed_term"], min_years=1, child_max_age=7,
         deadline="2026-11-30", period="매월 신청 · 예시 일정", section="제3조 자녀 돌봄",
         quote="[가상 규정] 정규직·기간제 직원으로 1년 이상 근속하고 만 7세 이하 자녀가 있으면 자녀 1명당 월 10만 원을 지원한다. 예시 접수 마감은 2026년 11월 30일이다.",
         checklist=["자녀 연령 확인", "회사에서 인정하는 가족관계 증빙 확인", "승인된 회사 양식과 담당 부서 확인"]),
    dict(id="family-leave", title="가족 돌봄 휴가", category="휴가·휴직", icon="leave",
         description="가족에게 필요한 시간, 미리 챙겨두세요.", value="연 5일", value_note="예시 일수 · 유급 여부 확인 필요",
         employment_types=["regular", "fixed_term", "part_time"], min_years=0, household_min=2,
         deadline=None, period="상시 확인", section="제4조 가족 돌봄",
         quote="[가상 규정] 고용형태와 관계없이 가구원이 2명 이상이면 연 5일의 가족 돌봄 휴가 신청을 준비할 수 있다. 유급 여부와 증빙은 별도 확인한다.",
         checklist=["돌봄 사유와 희망 기간 정리", "유급·무급 여부 및 증빙 확인", "실제 회사 휴가신청서 확인"]),
    dict(id="learning", title="나를 위한 배움 지원", category="성장·자기계발", icon="learning",
         description="배우고 싶었던 것, 올해 시작해볼까요?", value="연 30만 원", value_note="예시 한도 · 실비 정산",
         employment_types=["regular", "fixed_term"], min_years=0,
         deadline="2026-11-20", period="연간 신청 · 예시 일정", section="제5조 자기계발",
         quote="[가상 규정] 정규직·기간제 직원에게 자기계발 비용을 연 30만 원 한도로 실비 지원한다. 예시 접수 마감은 2026년 11월 20일이다.",
         checklist=["지원 가능한 교육인지 확인", "사전 승인과 영수증 요건 확인", "실제 신청·정산 경로 확인"]),
    dict(id="long-service", title="오래 함께한 당신에게", category="수당·지원", icon="award",
         description="함께 쌓은 시간에 보내는 고마움이에요.", value="50만 원", value_note="예시 포상금 · 10년 근속",
         employment_types=["regular"], min_years=10,
         deadline=None, period="근속 도래 시 확인", section="제6조 장기근속",
         quote="[가상 규정] 정규직 직원으로 만 10년 이상 근속하면 50만 원의 장기근속 포상금 신청을 준비할 수 있다.",
         checklist=["인정 근속기간 확인", "포상 기준일과 중복 수급 확인", "담당 부서의 확정 판정 확인"]),
    dict(id="school", title="자녀 교육비 지원", category="가족·육아", icon="school",
         description="자녀의 새로운 시작을 함께 응원해요.", value="학기당 20만 원", value_note="예시 금액 · 만 8~18세",
         employment_types=["regular", "fixed_term"], min_years=1, child_min_age=8, child_max_age=18, unresolved=True,
         unresolved_reason="자녀 재학 여부와 증빙을 추가로 확인해야 해요.",
         deadline=None, period="학기별 일정 확인", section="제7조 교육비",
         quote="[가상 규정] 정규직·기간제 직원으로 1년 이상 근속하고 만 8세 이상 18세 이하 자녀가 있으면 학기당 20만 원을 지원한다. 재학 증빙과 접수 일정은 별도 확인한다.",
         checklist=["자녀 연령 및 재학 여부 확인", "지원 제외·중복 조건 확인", "학기별 접수 일정과 실제 양식 확인"]),
    dict(id="housing", title="주거 안심 지원", category="수당·지원", icon="home",
         description="생활의 기반을 다지는 데 도움이 되도록.", value="조건 확인 후 안내", value_note="금액·요건 미확정",
         employment_types=["regular", "fixed_term"], min_years=1, unresolved=True,
         deadline=None, period="담당 부서 확인", section="제8조 주거 지원",
         quote="[가상 규정] 주거 지원의 소득·주택 보유·중복 지원 조건과 금액은 미확정이다. 추가 조건이 확인되기 전에는 자격을 확정하지 않는다.",
         checklist=["실제 회사 제도 존재 여부 확인", "소득·주택·중복 조건 확인", "금액·기한·공식 신청 경로 확인"]),
]


def catalog_item(benefit_id: str) -> dict | None:
    return next((p for p in CATALOG if p["id"] == benefit_id), None)


def evaluate(policy: dict, profile: BenefitProfile, *, as_of: date | None = None,
             company: str = "DEMO", approved: bool = False) -> dict:
    """False wins over unknown in an AND rule; company/source gates always fail closed."""
    today = as_of or date.today()
    p = profile.consented()
    checks = []

    def add(label, result, reason):
        checks.append(dict(label=label, result=result, reason=reason))

    employment = {"regular": "정규직", "fixed_term": "기간제", "part_time": "시간제"}
    if p.employment_type is None:
        add("고용형태", "unknown", "근무 정보 활용 동의와 고용형태 확인이 필요해요.")
    else:
        passed = p.employment_type in policy["employment_types"]
        add("고용형태", "pass" if passed else "fail", f"{employment[p.employment_type]} · " + ("예시 고용 조건에 맞아요." if passed else "예시 지원 대상 고용형태에 포함되지 않아요."))

    if policy["min_years"]:
        if not p.hire_date:
            add("근속기간", "unknown", "입사일 확인이 필요해요.")
        elif p.hire_date > today:
            add("근속기간", "unknown", "평가 기준일보다 입사일이 늦어요.")
        else:
            years = today.year - p.hire_date.year - ((today.month, today.day) < (p.hire_date.month, p.hire_date.day))
            passed = years >= policy["min_years"]
            add("근속기간", "pass" if passed else "fail", f"만 {years}년 근속 · {policy['min_years']}년 이상 필요해요.")

    if "child_max_age" in policy:
        if p.children_ages is None:
            add("자녀 연령", "unknown", "가족 정보 활용 동의와 자녀 연령 확인이 필요해요.")
        else:
            low, high = policy.get("child_min_age", 0), policy["child_max_age"]
            matching = [age for age in p.children_ages if low <= age <= high]
            passed = bool(matching)
            add("자녀 연령", "pass" if passed else "fail", (f"만 {min(matching)}세 자녀 · " if matching else "") + f"만 {low}~{high}세 자녀 " + ("조건에 맞아요." if passed else "조건에 해당하지 않아요."))
    if "household_min" in policy:
        add("가구 구성", "unknown" if p.household_size is None else "pass" if p.household_size >= policy["household_min"] else "fail",
            "가족 정보 확인이 필요해요." if p.household_size is None else f"가구원 {p.household_size}명 · 2명 이상 필요해요.")
    if policy.get("unresolved"):
        add("추가 조건", "unknown", policy.get("unresolved_reason", "필수 조건이 확정되지 않아 담당 부서 확인이 필요해요."))
    if policy["deadline"] and today > date.fromisoformat(policy["deadline"]):
        add("접수기간", "fail", "예시 접수기간이 지났어요. 다음 일정을 확인해 주세요.")

    simulated = "ineligible" if any(c["result"] == "fail" for c in checks) else "needs_review" if any(c["result"] == "unknown" for c in checks) else "eligible"
    # Even a true predicate cannot turn another company's or unapproved policy into a grant/denial.
    production_verified = company == "KTCS" and approved and policy.get("company") == "KTCS" and policy.get("human_approved") is True
    status = simulated if company == "DEMO" or production_verified else "needs_review"
    priority = {"자녀 연령": 0, "가구 구성": 1, "근속기간": 2, "고용형태": 3}
    reasons = [c["reason"] for c in checks if c["result"] != "pass"] or [c["reason"] for c in sorted(checks, key=lambda c: priority.get(c["label"], 4))[:2]]
    if company != "DEMO" and not production_verified:
        reasons = ["KTcs의 승인된 현행 규정과 자격 검증이 연결되지 않았어요."] + reasons
    source = dict(id=f"DEMO-{policy['id']}", title="화면 검증용 가상 복지 규정", company="DEMO", version="demo-2026.11.07",
                  section=policy["section"], quote=policy["quote"], sha256=hashlib.sha256(policy["quote"].encode()).hexdigest(),
                  review_status="SYNTHETIC_NOT_COMPANY_POLICY", human_approved=False)
    return {**{k: policy[k] for k in ("id", "title", "category", "icon", "description", "value", "value_note", "deadline", "period", "checklist")},
            "status": status, "reasons": reasons, "checks": checks, "source": source,
            "production_verified": production_verified, "application_enabled": False,
            "form_status": "승인된 회사 양식 미연결", "as_of": today.isoformat()}
