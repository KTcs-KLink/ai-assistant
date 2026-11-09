"""Protect source identity, information coverage and reversible table decisions."""
from copy import deepcopy

import pytest

from server import hr_evidence, table_body_review as review


@pytest.fixture
def record():
    text = '지원 대상\n내부 직원\n지원 금액\n15만원'
    body = '내부 직원에게는 지원 금액으로 15만원을 지급한다.'
    return dict(id='table-occurrence', asset_id='table-asset', unit_id='doc-a', table_text=text,
        table_text_sha256=review.digest(text), table_lines=review.meaningful_lines(text), source_file_sha256='version-a',
        privacy_context_omitted=False, body=[dict(id='body-a', unit_id='doc-a', page=2, bbox=[0, 0, 10, 10],
            text=body, text_sha256=review.digest(body), source_file_sha256='version-a', inside_table=False)])


def proposal(record, **patch):
    return review.Comparison(**(dict(id=record['id'], label='DUPLICATE', reason='본문이 표의 대상과 지급 금액을 모두 설명한다.',
        table_readable=True, comparison_complete=True, function='DATA', table_quotes=['내부 직원'],
        body_quotes=[dict(id='body-a', quote=record['body'][0]['text'])],
        mapped_table_line_ids=[r['id'] for r in record['table_lines']], new_information='', conflict_detail='') | patch))


def test_complete_duplicate_is_only_a_proposal_and_never_deletes_source(record):
    before = deepcopy(record)
    checked = review.validate(proposal(record), record, hr_evidence.PRIVATE)
    assert checked['label'] == 'DUPLICATE' and checked['body_supports'][0]['page'] == 2
    assert checked['source_action'] == 'PRESERVE' and not checked['answer_eligible'] and not checked['human_approved']
    assert record == before


def test_self_text_and_other_document_or_version_cannot_be_body_evidence(record):
    for key, value, message in [('inside_table', True, 'SELF_COMPARISON'), ('unit_id', 'doc-b', 'CROSS_DOCUMENT'),
                                ('source_file_sha256', 'version-b', 'CROSS_DOCUMENT')]:
        changed = deepcopy(record); changed['body'][0][key] = value
        with pytest.raises(ValueError, match=message):
            review.validate(proposal(record), changed, hr_evidence.PRIVATE)
    bad = proposal(record); bad.body_quotes[0].id = 'invented'
    with pytest.raises(ValueError, match='UNKNOWN_BODY'):
        review.validate(bad, record, hr_evidence.PRIVATE)


def test_missing_row_or_numeric_value_prevents_duplicate(record):
    incomplete = proposal(record, mapped_table_line_ids=[0, 1])
    checked = review.validate(incomplete, record, hr_evidence.PRIVATE)
    assert checked['label'] == 'HOLD' and 'TABLE_LINE_COVERAGE_INCOMPLETE' in checked['code_hold_reasons']
    changed = deepcopy(record); changed['body'][0]['text'] = '내부 직원에게는 지원 금액으로 1만원을 지급한다.'
    changed['body'][0]['text_sha256'] = review.digest(changed['body'][0]['text'])
    checked = review.validate(proposal(changed), changed, hr_evidence.PRIVATE)
    assert checked['label'] == 'HOLD' and 'TABLE_NUMBERS_NOT_ALL_IN_CITED_BODY' in checked['code_hold_reasons']


def test_form_function_and_omitted_private_context_cannot_be_deduplicated(record):
    checked = review.validate(proposal(record, function='FORM'), record, hr_evidence.PRIVATE)
    assert checked['label'] == 'HOLD' and 'INDEPENDENT_FUNCTION_OR_INFORMATION' in checked['code_hold_reasons']
    checked = review.validate(proposal(record), record | dict(privacy_context_omitted=True), hr_evidence.PRIVATE)
    assert checked['label'] == 'HOLD' and 'PRIVATE_CONTEXT_OMITTED' in checked['code_hold_reasons']


def test_additional_information_needs_two_sources_and_no_invented_number(record):
    candidate = proposal(record, label='ADDITIONAL', mapped_table_line_ids=[], new_information='지원 대상과 금액이 표의 행에 연결되어 있다.')
    assert review.validate(candidate, record, hr_evidence.PRIVATE)['label'] == 'ADDITIONAL'
    candidate.body_quotes = []
    with pytest.raises(ValueError, match='BOTH_SOURCE'):
        review.validate(candidate, record, hr_evidence.PRIVATE)
    candidate = proposal(record, label='ADDITIONAL', new_information='지원금 99만원이 추가된다.')
    with pytest.raises(ValueError, match='UNSOURCED_FACT_NUMBER'):
        review.validate(candidate, record, hr_evidence.PRIVATE)


def test_conflict_and_unreadable_proposals_are_not_silently_approved(record):
    candidate = proposal(record, label='CONFLICT')
    with pytest.raises(ValueError, match='CONFLICT_DESCRIPTION'):
        review.validate(candidate, record, hr_evidence.PRIVATE)
    candidate = proposal(record, label='ADDITIONAL', new_information='지원 대상의 대응이 표에 제시되어 있다.', table_readable=False)
    assert review.validate(candidate, record, hr_evidence.PRIVATE)['label'] == 'HOLD'


def test_source_quotes_and_private_output_are_checked(record):
    bad = proposal(record); bad.table_quotes = ['본문에 없는 다른 규정 문장']
    with pytest.raises(ValueError, match='QUOTE_NOT_IN_SOURCE'):
        review.validate(bad, record, hr_evidence.PRIVATE)
    bad = proposal(record, reason='private@example.invalid 이 포함된 출력은 저장하지 않는다.')
    with pytest.raises(ValueError, match='PRIVATE_OUTPUT'):
        review.validate(bad, record, hr_evidence.PRIVATE)


def test_all_occurrences_count_and_conservative_aggregation():
    assert review.aggregate([dict(label='DUPLICATE'), dict(label='ADDITIONAL')]) == 'ADDITIONAL'
    assert review.aggregate([dict(label='DUPLICATE'), dict(label='HOLD')]) == 'HOLD'
    assert review.aggregate([dict(label='CONFLICT'), dict(label='HOLD')]) == 'CONFLICT'
    assert review.aggregate([]) == 'HOLD'


def test_geometry_fraction_is_not_misread_as_personal_identity_number():
    from scripts.review_table_body_links import private_payload
    assert not private_payload(dict(bbox=[281.5385437011719, 42.1234567890123]))
    assert private_payload(dict(text='연락처 private@example.invalid'))


def test_numeric_provenance_keeps_korean_attached_amounts_and_whole_numbers():
    assert review.numbers('월4,000원과15만원') == {'4000', '15'}
    assert '1' not in review.numbers('15만원')


def test_short_form_field_is_allowed_alongside_a_longer_exact_source_anchor(record):
    changed = deepcopy(record); changed['table_text'] = '법정대리인 동의\n성명\n서명'
    changed['table_text_sha256'] = review.digest(changed['table_text'])
    changed['table_lines'] = review.meaningful_lines(changed['table_text'])
    candidate = proposal(changed, label='ADDITIONAL', function='FORM', table_quotes=['법정대리인 동의', '성명', '서명'],
                         mapped_table_line_ids=[], new_information='작성과 서명을 위한 입력란이 있다.')
    assert review.validate(candidate, changed, hr_evidence.PRIVATE)['label'] == 'ADDITIONAL'
    candidate.table_quotes = ['성명', '서명']
    with pytest.raises(ValueError, match='TABLE_SUPPORT_ANCHOR'):
        review.validate(candidate, changed, hr_evidence.PRIVATE)


def test_distant_match_does_not_prove_same_applicability(record):
    checked = review.validate(proposal(record), record, hr_evidence.PRIVATE)
    record['page'] = 10
    gated = review.apply_context_gate(checked, record)
    assert gated['label'] == 'HOLD' and gated['model_checked_label'] == 'DUPLICATE'
    assert checked['label'] == 'DUPLICATE'


def test_source_page_correction_needs_same_version_and_new_context(record):
    checked = review.validate(proposal(record), record, hr_evidence.PRIVATE)
    decision = dict(id=record['id'], label='ADDITIONAL', reason='원문 화면에서 적용 대상이 서로 다름을 확인했다.',
                    new_information='별도의 적용 대상과 연결되는 정보가 있다.', images=[], extra_body_quotes=[])
    with pytest.raises(ValueError, match='CHANGED_LABEL'):
        review.apply_source_page_review(checked, record, decision, {}, hr_evidence.PRIVATE)
    decision['extra_body_quotes'] = [dict(id='body-a', quote=record['body'][0]['text'])]
    changed = review.apply_source_page_review(checked, record, decision, {'body-a': record['body'][0]}, hr_evidence.PRIVATE)
    assert changed['label'] == 'ADDITIONAL' and not changed['human_approved']


def test_reference_to_a_table_does_not_cover_its_detailed_item_list(record):
    changed = deepcopy(record)
    changed['table_text'] = '기본사양\n승강장치\n제동장치\n안전장치\n운반방법\n설치방법'
    result = dict(label='DUPLICATE', body_supports=[dict(page=2, text='운영실무 사항은 표에서 정한 내용을 숙지하여야 한다.')])
    checked = review.apply_context_gate(result, changed | dict(page=2))
    assert checked['label'] == 'HOLD' and checked['information_gate'] == 'TABLE_DETAILS_NOT_IN_CITED_BODY'
    assert '승강장치' in checked['missing_table_terms']
