"""Source expansion cannot bypass identity, scope or original-structure gates."""
from copy import deepcopy
import hashlib
import json

import pytest

from server import hr_answer, hr_evidence, hr_source_review


def fixture_source():
    text='제1조(가상 시험) 근로자의 시험용 휴가는 별도 확인한다.'
    row=dict(id='TEST-UNIT',text=text,text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        source_file_sha256='a'*64,file_version_key='test-v1',kind='ARTICLE',decision='REVIEW',
        needs_layout_review=True,answer_eligible=False,human_approved=False)
    proposal=dict(id=row['id'],source_text_sha256=row['text_sha256'],source_file_sha256=row['source_file_sha256'],
        version=row['file_version_key'],decision='HR',human_approved=False,employee_scope='가상 시험의 근로자',
        original_text_layer_verified=True,source_structure_verified=True,task_codes=['01.05'],
        support_ranges=[dict(start=0,end=len(text),sha256=row['text_sha256'])],recovered_structure=None)
    return row,proposal


def test_expansion_includes_verified_hr_clauses_outside_core_document_titles(tmp_path,monkeypatch):
    row,_=fixture_source()
    row.update(document_title='가상 법률지원규정',heading_path='가상 법률지원규정 > 제1조',
        searchable=True,answer_eligible=True,source_scope_reviewed=True,decision='HR',employee_scope='가상 직원')
    path=tmp_path/'units.jsonl';path.write_text(json.dumps(row,ensure_ascii=False),encoding='utf-8')
    monkeypatch.setenv('KLINK_LOCAL_REVIEWED_UNITS',str(path));monkeypatch.delenv('KLINK_HR_SOURCE_REVIEW',raising=False)
    monkeypatch.setattr(hr_evidence,'CANONICAL_CORPUS',path)
    monkeypatch.setenv('KLINK_HR_SCOPE_PROFILE','core');assert not hr_evidence.corpus()[0]
    monkeypatch.setenv('KLINK_HR_SCOPE_PROFILE','expanded');assert hr_evidence.corpus()[0][0]['id']==row['id']


def test_overlay_preserves_original_text_and_prior_hold_without_claiming_human_approval():
    row,proposal=fixture_source()
    original=deepcopy(row)
    updated=hr_source_review.apply(row,proposal,hr_evidence.PRIVATE)
    assert row==original and updated['text']==row['text'] and updated['id']==row['id']
    assert updated['answer_eligible'] and updated['source_scope_reviewed']
    assert updated['prior_layout_review'] and updated['prior_review_decision']=='REVIEW'
    assert not updated['human_approved'] and not updated['needs_layout_review']


@pytest.mark.parametrize('patch',[
    dict(id='OTHER'),dict(source_text_sha256='0'*64),dict(source_file_sha256='0'*64),
    dict(version='foreign-version'),dict(human_approved=True),dict(decision='NON_HR'),
    dict(original_text_layer_verified=False),dict(source_structure_verified=False),
    dict(employee_scope=''),dict(task_codes=[]),dict(task_codes=['02.01']),
    dict(support_ranges=[]),dict(support_ranges=[dict(start=0,end=999,sha256='0'*64)]),
    dict(review_reason='test-private@example.invalid'),
])
def test_overlay_rejects_changed_identity_unverified_scope_and_private_content(patch):
    row,proposal=fixture_source()
    with pytest.raises(ValueError):hr_source_review.apply(row,proposal|patch,hr_evidence.PRIVATE)


def test_unsplit_fragment_requires_a_verified_complete_article_boundary():
    row,proposal=fixture_source();row['kind']='UNSTRUCTURED'
    with pytest.raises(ValueError):hr_source_review.apply(row,proposal,hr_evidence.PRIVATE)
    recovered=dict(article_label='제2조',section='가상 시험 > 제2조')
    with pytest.raises(ValueError):hr_source_review.apply(row,proposal|dict(recovered_structure=recovered),hr_evidence.PRIVATE)


def test_foreign_project_review_path_is_rejected_before_loading(tmp_path,monkeypatch):
    monkeypatch.setenv('KLINK_HR_SOURCE_REVIEW',str(tmp_path/'review-overlay.json'))
    with pytest.raises(ValueError):hr_source_review.fingerprint(hr_source_review.CORPUS)


def test_a_foreign_corpus_is_rejected_in_bm25_as_well_as_vector_mode(tmp_path,monkeypatch):
    row,_=fixture_source();path=tmp_path/'other-project.jsonl'
    path.write_text(json.dumps(row,ensure_ascii=False),encoding='utf-8')
    monkeypatch.setenv('KLINK_LOCAL_REVIEWED_UNITS',str(path));monkeypatch.setenv('KLINK_HR_RETRIEVAL','bm25')
    with pytest.raises(ValueError,match='한전'):hr_evidence.corpus()


def test_runtime_view_requires_exact_ids_columns_and_unchanged_bytes(tmp_path,monkeypatch):
    monkeypatch.setattr(hr_source_review,'REVIEW_DIR',tmp_path)
    view=tmp_path/hr_source_review.VIEW_NAME
    row={key:None for key in hr_source_review.VIEW_FIELDS};row['id']='A'
    view.write_text(json.dumps(row)+'\n',encoding='utf-8')
    manifest=tmp_path/'review-overlay.json'
    data=dict(runtime_view_file=hr_source_review.VIEW_NAME,runtime_view_count=1,runtime_view_sha256=hr_source_review.file_sha(view))
    manifest.write_text(json.dumps(data),encoding='utf-8');fp=(str(manifest),0,0)
    assert hr_source_review.source_view('unused',fp,{'A':{}})==view
    with pytest.raises(ValueError):hr_source_review.source_view('unused',fp,{'B':{}})
    view.write_text(json.dumps(row|dict(text='changed'))+'\n',encoding='utf-8')
    with pytest.raises(ValueError):hr_source_review.source_view('unused',fp,{'A':{}})


def test_missing_canonical_review_manifest_cannot_fall_back_to_old_gates(tmp_path,monkeypatch):
    monkeypatch.setattr(hr_source_review,'REVIEW_DIR',tmp_path)
    monkeypatch.delenv('KLINK_HR_SOURCE_REVIEW',raising=False)
    with pytest.raises(ValueError):hr_source_review.fingerprint(hr_source_review.CORPUS)


def test_revision_suffixes_group_versions_without_merging_the_source_ids():
    assert hr_evidence.title_key('가상규정 제1차 개정')==hr_evidence.title_key('가상규정_261022')
    options=[dict(title='가상규정 제1차 개정',version='old'),dict(title='가상규정_261022',version='new')]
    rows=[dict(id='NEW',title=options[1]['title'],version='new',version_options=options)]
    assert hr_evidence.ambiguous_versions('가상규정의 근무 기준은?',rows)==['NEW']
    assert not hr_evidence.ambiguous_versions('가상규정_261022의 근무 기준은?',rows)


def test_contract_payday_is_not_a_universal_employee_payday():
    row=dict(section='첨부 근로계약서 > 제6조',source_role='contract_template')
    assert not hr_evidence.query_source_allowed('직원의 임금은 언제 지급하나요?',row)
    assert hr_evidence.query_source_allowed('첨부 계약서의 임금 지급일은 언제인가요?',row)


def test_employee_rights_and_surety_questions_are_in_scope_but_weather_is_not():
    for question in ['직원이 부조리 신고 후 불이익을 받으면 구제를 신청할 수 있나요?',
        '직원 제안의 인정 범위는 무엇인가요?','회계관계직원의 재정보증은 어디에 따르나요?']:
        assert hr_evidence.is_hr_question(question)
    assert not hr_evidence.is_hr_question('오늘 직원들이 점심에 보는 날씨는?')


def test_output_schema_limits_each_source_to_its_actual_original_span_ids():
    sources=[dict(id='A',text='첫 본문\n①첫 항\n②둘째 항'),dict(id='B',text='하나의 본문')]
    variants=hr_answer.span_schema(sources)['$defs']['SpanCitation']['anyOf']
    assert variants[0]['properties']['source_id']['enum']==['A']
    assert variants[0]['properties']['span_ids']['items']['enum']==['S0','S1','S2']
    assert variants[1]['properties']['span_ids']['items']['enum']==['S0']
    invalid=hr_answer.SpanDraft(status='answered',missing_information=[],paragraphs=[dict(text='시험',citations=[dict(source_id='B',span_ids=['S1'])])])
    with pytest.raises(hr_answer.AnswerUnavailable):hr_answer.resolve_spans(invalid,sources)


def test_a_primary_unknown_version_withholds_before_gpt_but_an_unrelated_candidate_does_not(monkeypatch):
    options=[dict(title='가상규정_261001',version='old'),dict(title='가상규정_261022',version='new')]
    versioned=dict(id='V',title='가상규정_261022',text='가상 휴가',section='제1조',version='new',version_options=options)
    plain=dict(id='P',title='다른 가상규정',text='휴가 참고 본문',section='제1조',version='one',version_options=[])
    monkeypatch.setattr(hr_evidence,'summary',lambda:dict(company='KEPCO',source_count=2))
    monkeypatch.setattr(hr_evidence,'search',lambda *args,**kwargs:[versioned,plain])
    def forbidden():pytest.fail('A primary ambiguous version must not call GPT.')
    monkeypatch.setattr(hr_answer.benefit_explanation,'settings',forbidden)
    assert hr_answer.generate('휴가 기준은 무엇인가요?')['validation']=='AMBIGUOUS_SOURCE_VERSION_NO_GENERATION'
    monkeypatch.setattr(hr_evidence,'search',lambda *args,**kwargs:[plain,versioned])
    class ReachedConfiguration(Exception):pass
    def observed():raise ReachedConfiguration()
    monkeypatch.setattr(hr_answer.benefit_explanation,'settings',observed)
    with pytest.raises(ReachedConfiguration):hr_answer.generate('휴가 기준은 무엇인가요?')


def test_incomplete_wrong_company_or_modified_corpus_cannot_activate_an_overlay(tmp_path):
    corpus=tmp_path/'corpus.jsonl';corpus.write_text('fixed',encoding='utf-8')
    path=tmp_path/'review-overlay.json'
    valid=dict(schema=hr_source_review.SCHEMA,company='KEPCO',human_approved=False,
        all_target_units_audited=3268,source_corpus_sha256=hr_source_review.file_sha(corpus),promotions=[])
    for patch in [dict(company='FOREIGN'),dict(all_target_units_audited=10),dict(human_approved=True),dict(source_corpus_sha256='0'*64)]:
        path.write_text(json.dumps(valid|patch),encoding='utf-8');hr_source_review.load.cache_clear()
        with pytest.raises(ValueError):hr_source_review.load(str(path),path.stat().st_mtime_ns,path.stat().st_size,str(corpus),0,0)


def test_invalid_review_manifest_withholds_before_reading_credentials_or_calling_gpt(monkeypatch):
    def invalid():raise ValueError('test invalid source manifest')
    monkeypatch.setattr(hr_evidence,'summary',invalid)
    def forbidden():pytest.fail('A rejected source manifest must not trigger GPT configuration or calls.')
    monkeypatch.setattr(hr_answer.benefit_explanation,'settings',forbidden)
    result=hr_answer.generate('시험용 휴가 조건을 알려주세요')
    assert result['status']=='needs_review' and not result['paragraphs']
    assert result['validation']=='KEPCO_RETRIEVAL_UNAVAILABLE_NO_GENERATION'


def test_an_existing_source_can_be_quarantined_without_editing_its_text():
    row,_=fixture_source();row['answer_eligible']=True
    hold=dict(id=row['id'],source_text_sha256=row['text_sha256'],source_file_sha256=row['source_file_sha256'],
        version=row['file_version_key'],action='hold',issues=['PDF_RAW_TEXT_MISMATCH'],human_approved=False)
    result=hr_source_review.apply(row,hold,hr_evidence.PRIVATE)
    assert not result['answer_eligible'] and row['answer_eligible']
    assert result['text']==row['text'] and result['original_review_issues']==hold['issues']
    with pytest.raises(ValueError):hr_source_review.apply(row,hold|dict(issues=[]),hr_evidence.PRIVATE)


def test_contract_scope_context_requires_an_original_verified_header():
    row,proposal=fixture_source();title='가상 근로계약서'
    context=dict(title=title,source_text=title,source_text_sha256=hashlib.sha256(title.encode()).hexdigest(),
        source_file_sha256=row['source_file_sha256'],original_text_layer_verified=True)
    correct=proposal|dict(source_role='contract_template',source_context=context)
    assert hr_source_review.apply(row,correct,hr_evidence.PRIVATE)['source_role']=='contract_template'
    for patch in [dict(original_text_layer_verified=False),dict(source_file_sha256='0'*64),dict(title='임의 계약서')]:
        with pytest.raises(ValueError):hr_source_review.apply(row,correct|dict(source_context=context|patch),hr_evidence.PRIVATE)


@pytest.mark.parametrize('source_text,wrong,correct',[
    ('제1조 휴게시간은 실정에 따라 일괄 또는 분할하여 부여한다.',
     '휴게시간은 일괄 또는 분할하여 부여할 수 있습니다.',
     '휴게시간은 부여해야 합니다. 실정에 따라 일괄 또는 분할 방식을 정합니다.'),
    ('제1조 정부의 지시가 있을 때에는 이에 따르며, 상호 필요에 의하여 시간을 달리 정할 수 있다.',
     '정부의 지시가 있거나 상호 필요이면 시간을 달리 정할 수 있습니다.',
     '정부의 지시가 있으면 그 지시에 따릅니다. 상호 필요에 의해서는 시간을 달리 정할 수 있습니다.'),
])
def test_method_choice_cannot_weaken_a_source_obligation(source_text,wrong,correct):
    source=dict(id='SOURCE',text=source_text,title='가상 시험',section='제1조')
    def draft(text):return hr_answer.Draft(status='answered',missing_information=[],paragraphs=[
        hr_answer.Paragraph(text=text,citations=[hr_answer.Citation(source_id=source['id'],quote=source_text)])])
    with pytest.raises(hr_answer.AnswerUnavailable) as caught:hr_answer.validate(draft(wrong),[source])
    assert caught.value.code=='SOURCE_MODALITY_CHANGED'
    assert hr_answer.validate(draft(correct),[source]).paragraphs


def test_explicit_question_scenario_numbers_do_not_become_policy_amounts():
    source=dict(id='SOURCE',title='가상 시험',section='휴게',text='휴게시간은 30분을 부여한다.')
    def draft(text):return hr_answer.Draft(status='answered',missing_information=[],paragraphs=[
        hr_answer.Paragraph(text=text,citations=[hr_answer.Citation(source_id='SOURCE',quote=source['text'])])])
    question='하루 3시간을 근무할 때 휴게는?'
    assert hr_answer.validate(draft('질문처럼 하루 근무시간을 3시간으로 정한 경우에도 휴게시간은 30분을 부여해야 합니다.'),[source],question)
    for text in ['하루 3시간 근무에는 휴게시간 30분을 부여합니다.','질문처럼 하루 근무시간을 5시간으로 정한 경우 휴게시간 30분을 부여합니다.']:
        with pytest.raises(hr_answer.AnswerUnavailable):hr_answer.validate(draft(text),[source],question)


def test_rank_scope_guard_checks_both_word_orders_without_inventing_a_hierarchy():
    text='4직급 이상 직원은 전환할 수 없다. 다만, 불가피한 경우 2직급 이하 직원에 대하여 전환할 수 있다.'
    source=dict(id='S',title='가상 시험',section='전환',text=text)
    def draft(prose):return hr_answer.Draft(status='answered',missing_information=[],paragraphs=[
        hr_answer.Paragraph(text=prose,citations=[hr_answer.Citation(source_id='S',quote=text)])])
    for prose in ['4직급 직원도 그 예외 요건에 해당하면 전환이 가능합니다.','이 예외는 4직급에게 적용되지 않습니다.']:
        with pytest.raises(hr_answer.AnswerUnavailable) as caught:hr_answer.validate(draft(prose),[source])
        assert caught.value.code=='UNVERIFIED_RANK_SCOPE'
    assert hr_answer.validate(draft('4직급 직원의 예외 포함 여부는 직급 체계를 추가 확인해야 합니다.'),[source])


def test_scope_completeness_is_whole_answer_and_does_not_borrow_unused_qualifications():
    family=dict(id='F',title='가상 시험',section='채용',text='채용권자는 가족 또는 사적관계에 의한 지인 등을 채용하여서는 안 된다.')
    def paragraph(text,source):return hr_answer.Paragraph(text=text,citations=[hr_answer.Citation(source_id=source['id'],quote=source['text'])])
    question='가족 채용 금지 범위는 어떻게 구분하나요?'
    full=hr_answer.Draft(status='answered',missing_information=[],paragraphs=[paragraph('가족을 채용해서는 안 됩니다.',family),paragraph('사적 관계의 지인도 금지 대상입니다.',family)])
    assert hr_answer.validate(full,[family],question)
    first=hr_answer.Draft(status='answered',missing_information=[],paragraphs=full.paragraphs[:1])
    assert hr_answer.validate(deepcopy(first),[family],question,check_completeness=False)
    with pytest.raises(hr_answer.AnswerUnavailable):hr_answer.validate(deepcopy(first),[family],question)
    unused=dict(id='U',title='다른 가상 시험',section='다른 채용',text='서류전형에 외부 관련 전문가를 참여시킨다.')
    actual=dict(id='A',title='가상 위원회',section='위원',text='외부위원은 이사회가 선임한다.')
    draft=hr_answer.Draft(status='answered',missing_information=[],paragraphs=[paragraph('외부위원은 이사회가 선임합니다.',actual)])
    assert hr_answer.validate(draft,[unused,actual],'위원회 외부위원은 누가 선임하나요?')


def test_an_unwritten_external_authority_is_not_added_to_a_complete_clause():
    source=dict(id='S',title='가상 시험',section='교육',text='학비지원형 교육은 공사에서 교육비만 부담한다.')
    def draft(text):return hr_answer.Draft(status='answered',missing_information=[],paragraphs=[
        hr_answer.Paragraph(text=text,citations=[hr_answer.Citation(source_id='S',quote=source['text'])])])
    with pytest.raises(hr_answer.AnswerUnavailable) as caught:hr_answer.validate(draft('학비지원형은 별도 기준에 따라 교육비만 부담합니다.'),[source])
    assert caught.value.code=='UNSUPPORTED_EXTERNAL_AUTHORITY'
    assert hr_answer.validate(draft('학비지원형은 공사에서 교육비만 부담합니다.'),[source])
