"""Fresh domain separation must retain mixed HR, source text, and review boundaries."""
import re

import pytest

from server import hr_domain_reclassification as domain

PRIVATE=re.compile(r'sk-secret|private@example',re.I)


def piece(text):return dict(id='source:0:100',text=text,text_sha256=domain.digest(text))


def finding(**patch):
    values=dict(id='source:0:100',label='HR',actor='internal_employee',reason='공사 직원의 휴가 조건을 직접 규정하는 인사 본문이다.',hr_quote='직원의 연차유급휴가',non_hr_quote='')
    return domain.Finding(**(values|patch))


def test_piece_partition_preserves_every_character_without_overlap_or_truncation():
    text=('직원 조건과 예외를 보존한다.\n'*1000)+'마지막 예외'
    spans=list(domain.split_ranges(text,maximum=123))
    assert ''.join(text[a:b] for a,b in spans)==text
    assert spans[0][0]==0 and spans[-1][1]==len(text)
    assert all(a[1]==b[0] for a,b in zip(spans,spans[1:]))


def test_hr_and_non_hr_need_actual_source_support_and_do_not_grant_answer_use():
    text='제1조 직원의 연차유급휴가는 인사 규정에 따른다.'
    result=domain.validate(finding(),piece(text),PRIVATE)
    assert result['label']=='HR' and result['hr_support']['text'] in text
    assert result['answer_eligible'] is False and result['human_approved'] is False
    with pytest.raises(ValueError):domain.validate(finding(hr_quote='없는 원문을 만든 인용'),piece(text),PRIVATE)
    with pytest.raises(ValueError):domain.validate(finding(label='NON_HR'),piece(text),PRIVATE)


def test_external_workforce_does_not_become_internal_hr():
    text='협력회사 기술인력의 자격 기준은 계약 평가에 사용한다.'
    r=domain.validate(finding(label='NON_HR',actor='external_worker_or_customer',hr_quote='',non_hr_quote='협력회사 기술인력의 자격 기준',reason='외부 협력회사의 기술인력 자격과 거래 평가를 다룬다.'),piece(text),PRIVATE)
    assert r['label']=='NON_HR'
    wrong=domain.validate(finding(actor='external_worker_or_customer',hr_quote='협력회사 기술인력의 자격 기준'),piece(text),PRIVATE)
    assert wrong['label']=='REVIEW_REQUIRED'


def test_mixed_content_requires_both_kinds_of_source_quote():
    text='직원의 연차유급휴가는 인사 규정에 따른다. 전력 공급계약의 요금은 별표를 따른다.'
    r=domain.validate(finding(label='MIXED',actor='mixed',non_hr_quote='전력 공급계약의 요금은 별표'),piece(text),PRIVATE)
    assert r['label']=='MIXED' and r['hr_support'] and r['non_hr_support']
    with pytest.raises(ValueError):domain.validate(finding(label='MIXED'),piece(text),PRIVATE)


def test_non_hr_proposal_cannot_discard_a_clear_internal_hr_conflict():
    text='공사 직원의 연차유급휴가는 인사 규정에 따른다. 전력 공급계약의 요금은 별표를 따른다.'
    r=domain.validate(finding(label='NON_HR',actor='organization_process',hr_quote='',non_hr_quote='전력 공급계약의 요금은 별표'),piece(text),PRIVATE)
    assert r['label']=='REVIEW_REQUIRED' and r['proposed_label']=='NON_HR'


def test_only_whitespace_can_be_restored_in_a_support_quote():
    r=domain.original_span('직원의 연차유급휴가는 규정을 따른다','직원의\n연차유급휴가는 규정을 따른다.')
    assert r['text']=='직원의\n연차유급휴가는 규정을 따른다'
    with pytest.raises(ValueError):domain.original_span('직원의 연차유급휴가는 법률을 따른다','직원의 연차유급휴가는 규정을 따른다')


@pytest.mark.parametrize('labels,expected',[
    (['HR'],'HR'),(['NON_HR'],'NON_HR'),(['HR','NON_HR'],'MIXED'),
    (['MIXED','NON_HR'],'MIXED'),(['HR','REVIEW_REQUIRED'],'REVIEW_REQUIRED'),([], 'REVIEW_REQUIRED'),
])
def test_window_projection_keeps_mixed_and_unknown_parts(labels,expected):
    assert domain.aggregate(labels)==expected


def test_private_output_and_unknown_source_id_are_rejected():
    text='직원의 연차유급휴가는 인사 규정에 따른다.'
    with pytest.raises(ValueError):domain.validate(finding(id='invented'),piece(text),PRIVATE)
    with pytest.raises(ValueError):domain.validate(finding(reason='private@example.invalid 개인 연락처를 넣은 문장입니다.'),piece(text),PRIVATE)


def test_short_source_heading_can_remain_review_only_without_an_invented_long_quote():
    r=domain.validate(finding(label='REVIEW_REQUIRED',actor='unspecified',reason='부칙 제목만 있어 본문 내용과 업무 범위를 판단하기 어렵다.',hr_quote='부칙'),piece('부칙'),PRIVATE)
    assert r['label']=='REVIEW_REQUIRED' and r['hr_support']['text']=='부칙'
    assert not r['answer_eligible']
