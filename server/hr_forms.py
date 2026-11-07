"""Official company forms can be served only after external provenance and blank-form review."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field

try:
    from .hr_policy import StrictModel, read_records
except ImportError:
    from hr_policy import StrictModel, read_records


FORM_TYPES = {
    "leave": ("휴가신청서", ["희망 휴가 종류와 기간 정리", "대상 규정과 증빙 확인", "회사 공식 양식·신청 경로 확인"]),
    "travel": ("출장신청·사전품의서", ["목적·방문지·일정 정리", "예상 비용과 사전 승인 기준 확인", "회사 공식 출장 양식 확인"]),
    "expense": ("출장비 정산서", ["출장 내역과 증빙 정리", "인정 비용·한도·정산 기한 확인", "회사 공식 정산 경로 확인"]),
    "resignation": ("사직원", ["퇴직 의사와 희망일 정리", "회사 규정의 통보·승인 절차 확인", "회사 공식 양식·담당 부서 확인"]),
    "handover": ("업무인수인계서", ["담당 업무·진행 상태 정리", "인계 대상·자료 접근권한 확인", "회사 공식 인계 양식 확인"]),
    "retirement": ("퇴직업무 확인서", ["인수인계 진행 상태 확인", "회사 자산·접근권한 반납 대상 확인", "회사 공식 퇴직 확인 절차 확인"]),
}


class VerifiedForm(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,80}$")
    company: str = Field(pattern=r"^KTCS$")
    version: str = Field(min_length=1, max_length=80)
    source_url: str = Field(min_length=10, max_length=1000)
    approval_ref: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")
    blank_template_verified: bool
    filename: str = Field(min_length=1, max_length=150)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def verified() -> dict[str, tuple[VerifiedForm, Path]]:
    records = read_records("KLINK_HR_FORMS_FILE", VerifiedForm)
    configured = os.getenv("KLINK_HR_FORMS_DIR")
    if not configured:
        return {}
    root = Path(configured).resolve()
    result = {}
    for item in records:
        url = urlsplit(item.source_url)
        file = (root/item.filename).resolve()
        if item.id not in FORM_TYPES or item.id in result or Path(item.filename).name != item.filename or not file.is_relative_to(root):
            raise ValueError("invalid form registry")
        if not item.blank_template_verified or url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("form review incomplete")
        if not file.is_file() or file.suffix.lower() not in {".pdf", ".docx", ".hwp", ".hwpx"} or file.stat().st_size > 20_000_000:
            raise ValueError("form file unavailable")
        if hashlib.sha256(file.read_bytes()).hexdigest() != item.sha256:
            raise ValueError("form integrity failed")
        result[item.id] = item, file
    return result


def listing() -> list[dict]:
    available = verified()
    return [dict(id=key, title=value[0], preparation_items=value[1], official_available=key in available,
        status="verified_ktcs_blank_template" if key in available else "official_form_required",
        download_path=f"/api/benefits/hr/forms/{key}/download" if key in available else None,
        version=available[key][0].version if key in available else None,
        notice="일반적인 준비 항목이며 회사의 최종 증빙·결재 요건은 확인이 필요해요.") for key, value in FORM_TYPES.items()]
