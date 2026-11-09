"""Scope regression: extra-domain sources cannot silently extend the user's taxonomy."""
from copy import deepcopy

import pytest

from server import five_domain_scope as five


@pytest.fixture
def tasks():
    return {code: dict(code=code, domain=code[:2], name=name) for code, name in
            [('01.05', '휴가'), ('01.08', '교육·평가'), ('02.07', '구매·계약')]}


def retained(primary='06.01', direct=('06.01',), relation='DIRECT', **patch):
    return dict(id='source', text='보존된 원문', status='CLASSIFIED', primary_path=primary,
                primary_domain=primary[:2], direct_paths=list(direct), privacy_hold=False,
                primary_has_local_support=True, service_answer_eligible=False,
                source_file_sha256='unchanged', assignments=[dict(code=code, supports=[
                    dict(relation=relation, quote='원문', source_range=[4, 6], support_in_target=False)])
                    for code in direct]) | patch


def test_only_original_34_codes_are_accepted_and_original_names_are_preserved():
    original = dict(version='original', tasks=[dict(code=f'{d}.{n:02d}', domain=d,
        name=f'기존 사용자 업무 {d}.{n:02d}', patterns=['discard'])
        for d, count in zip(('01', '02', '03', '04', '05'), (8, 7, 7, 6, 6)) for n in range(1, count+1)])
    tax = five.taxonomy(original)
    assert [t['name'] for t in tax['tasks']] == [t['name'] for t in original['tasks']]
    assert len(tax['domains']) == 5 and len(tax['tasks']) == 34 and not tax['extensions_allowed']
    assert all('patterns' not in t for t in tax['tasks'])
    changed = deepcopy(original); changed['tasks'][-1]['code'] = '05.07'
    with pytest.raises(ValueError, match='ORIGINAL_FIVE_DOMAIN'):
        five.taxonomy(changed)
    changed = deepcopy(original); changed['tasks'][0]['domain'] = '06'
    with pytest.raises(ValueError, match='ORIGINAL_FIVE_DOMAIN'):
        five.taxonomy(changed)


def test_original_direct_secondary_survives_extra_primary_without_changing_source(tasks):
    before = retained(direct=('06.01', '01.08'))
    frozen = deepcopy(before); result = five.project(before, tasks)
    assert result['scope_decision'] == 'IN_SCOPE' and result['primary_path'] == '01.08'
    assert result['direct_paths'] == ['01.08'] and result['primary_domain'] == '01'
    assert not result['primary_has_local_support']  # old primary's local-support flag must not leak
    assert result['text'] == before['text'] and result['source_file_sha256'] == 'unchanged'
    assert before == frozen and not result['classification_grants_answer_use']


def test_multiple_allowed_direct_links_survive_and_partial_review_is_not_cleared(tasks):
    result = five.project(retained('02.07', ('02.07', '01.05', '09.03'), status='PARTIAL_REVIEW'), tasks)
    assert result['primary_path'] == '02.07' and result['direct_paths'] == ['01.05', '02.07']
    assert result['multi_domain'] and result['status'] == 'PARTIAL_REVIEW'
    assert {a['code'] for a in result['assignments']} == {'01.05', '02.07'}


def test_related_and_reference_links_never_become_direct_workflows(tasks):
    related = retained(direct=('01.08',), relation='RELATED')
    related['direct_paths'] = []
    result = five.project(related, tasks)
    assert result['scope_decision'] == 'ADJACENT_SCOPE' and result['primary_domain'] == '01'
    assert result['primary_path'] is None and not result['direct_paths']
    reference = deepcopy(related); reference['assignments'][0]['supports'][0]['relation'] = 'REFERENCE_ONLY'
    result = five.project(reference, tasks)
    assert result['scope_decision'] == 'OUTSIDE_SCOPE' and result['primary_domain'] is None
    assert result['reference_paths'] == ['01.08'] and not result['direct_paths']


def test_unresolved_proposal_is_not_promoted_even_if_it_contains_a_direct_candidate(tasks):
    result = five.project(retained('01.05', ('01.05',), status='REVIEW_REQUIRED'), tasks)
    assert result['scope_decision'] == 'REVIEW_REQUIRED' and result['primary_path'] is None
    assert result['primary_domain'] is None and not result['direct_paths']


def test_within_domain_extension_stays_task_review_without_becoming_task_35(tasks):
    result = five.project(retained('01.09', ('01.09',)), tasks)
    assert result['scope_decision'] == 'ADJACENT_SCOPE' and result['primary_domain'] == '01'
    assert result['primary_path'] is None and not result['assignments']


def test_extra_domains_are_outside_and_privacy_body_is_never_exported(tasks):
    for code in ('06.01', '07.01', '08.01', '09.03', '10.01'):
        result = five.project(retained(code, (code,)), tasks)
        assert result['scope_decision'] == 'OUTSIDE_SCOPE' and result['primary_domain'] is None
        assert result['primary_path'] is None and not result['assignments']
    result = five.project(retained('01.05', ('01.05',), privacy_hold=True), tasks)
    assert result['scope_decision'] == 'PRIVACY_HOLD' and result['text'] is None
    assert not result['assignments'] and not result['direct_paths'] and not result['human_approved']
