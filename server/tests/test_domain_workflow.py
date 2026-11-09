"""Meaningful boundaries for organizing source chunks without granting answer use."""
import re

import pytest

from server import domain_workflow as domain

PRIVATE = re.compile(r'private@example|sk-secret', re.I)


@pytest.fixture
def tasks():
    return {t['code']: t for t in domain.taxonomy(dict(version='fixture', tasks=[
        dict(code='01.05', domain='01', name='휴가', patterns=['discard detector rules']),
        dict(code='02.07', domain='02', name='구매·계약'),
    ]))['tasks']}


def piece(text, pid='p1', start=0):
    return dict(id=pid, text=text, text_sha256=domain.digest(text), source_range=[start, start+len(text)])


def proposal(p, **patch):
    value = dict(id=p['id'], status='CLASSIFIED', reason='공사 직원의 휴가 제도를 직접 규정하는 본문이다.',
                 assignments=[dict(code='01.05', relation='DIRECT', actor='internal_employee', quote='공사 직원의 연차유급휴가')])
    return domain.Finding(**(value | patch))


def test_user_codes_and_names_survive_extension_without_inheriting_detector_patterns():
    previous = dict(version='original', tasks=[dict(code='02.07', domain='02', name='사용자 지정 구매업무', patterns=['입찰'])])
    result = domain.taxonomy(previous)
    assert next(t for t in result['tasks'] if t['code'] == '02.07')['name'] == '사용자 지정 구매업무'
    assert 'patterns' not in result['tasks'][0]
    assert result['original_task_count'] == 1 and len(result['domains']) == 10
    assert len({t['code'] for t in result['tasks']}) == len(result['tasks'])
    assert all(t['domain'] in domain.DOMAINS for t in result['tasks'])


def test_exact_source_and_known_workflow_are_required(tasks):
    p = piece('공사 직원의 연차유급휴가는 별도 규정에 따른다.')
    result = domain.validate(proposal(p), p, tasks, PRIVATE)
    assert result['assignments'][0]['support']['text'] in p['text']
    assert not result['classification_grants_answer_use'] and not result['human_approved']
    with pytest.raises(ValueError, match='UNKNOWN_OR_CHANGED_SOURCE'):
        domain.validate(proposal(p, id='invented'), p, tasks, PRIVATE)
    with pytest.raises(ValueError):
        domain.validate(proposal(p), p | dict(text_sha256='wrong'), tasks, PRIVATE)
    bad = proposal(p).model_dump(); bad['assignments'][0]['code'] = '99.99'
    with pytest.raises(ValueError, match='UNKNOWN_OR_DUPLICATE'):
        domain.validate(domain.Finding(**bad), p, tasks, PRIVATE)


def test_vendor_qualification_cannot_become_internal_hr(tasks):
    p = piece('입찰자 소속 임직원은 재직기간에 따라 평가한다.')
    wrong = proposal(p, assignments=[dict(code='01.05', relation='DIRECT', actor='external_worker_or_customer', quote='입찰자 소속 임직원은 재직기간')])
    with pytest.raises(ValueError, match='HR_INTERNAL_ACTOR_REQUIRED'):
        domain.validate(wrong, p, tasks, PRIVATE)
    wrong.assignments[0].actor = 'internal_employee'
    with pytest.raises(ValueError, match='HR_EXTERNAL_WORKFORCE_SUPPORT'):
        domain.validate(wrong, p, tasks, PRIVATE)
    wrong.assignments[0].code = '02.07'; wrong.assignments[0].actor = 'external_worker_or_customer'
    assert domain.validate(wrong, p, tasks, PRIVATE)['status'] == 'CLASSIFIED'


def test_explicit_internal_hr_record_procedure_can_have_an_organizational_actor(tasks):
    p = piece('제79조 상벌사실은 전산매체로 관리하고 영구보존하여야 한다.')
    finding = proposal(p, assignments=[dict(code='01.09', relation='DIRECT', actor='organization_process', quote='상벌사실은 전산매체로 관리')])
    assert domain.validate(finding, p, tasks, PRIVATE)['status'] == 'CLASSIFIED'
    external = piece('포상담당부서는 외부단체에 감사패를 수여할 수 있다.')
    bad = proposal(external, assignments=[dict(code='01.09', relation='DIRECT', actor='organization_process', quote='포상담당부서는 외부단체에')])
    with pytest.raises(ValueError, match='HR_INTERNAL_ACTOR_REQUIRED'):
        domain.validate(bad, external, tasks, PRIVATE)


def test_reference_or_adjacent_mention_is_not_a_primary_workflow(tasks):
    p = piece('공사 직원의 연차유급휴가는 별도 규정에 따른다.')
    for relation in ('RELATED', 'REFERENCE_ONLY'):
        finding = proposal(p); finding.assignments[0].relation = relation
        with pytest.raises(ValueError, match='PRIMARY_DIRECT'):
            domain.validate(finding, p, tasks, PRIVATE)
        finding.status = 'REVIEW_REQUIRED'
        result = domain.validate(finding, p, tasks, PRIVATE)
        aggregate = domain.aggregate([p], {p['id']: result})
        assert aggregate['primary_path'] is None and aggregate['assignments']


def test_multiple_direct_workflows_need_distinct_valid_source_links(tasks):
    p = piece('공사 직원의 연차유급휴가는 별도 규정에 따른다. 입찰자 소속 임직원은 재직기간에 따라 평가한다.')
    finding = proposal(p)
    finding.assignments.append(domain.Assignment(code='02.07', relation='DIRECT', actor='external_worker_or_customer', quote='입찰자 소속 임직원은 재직기간'))
    result = domain.validate(finding, p, tasks, PRIVATE)
    assert result['status'] == 'MIXED'
    aggregate = domain.aggregate([p], {p['id']: result})
    assert aggregate['multi_domain'] and aggregate['direct_paths'] == ['01.05', '02.07']
    assert aggregate['primary_path'] == '01.05'
    finding.assignments.append(finding.assignments[0])
    with pytest.raises(ValueError, match='UNKNOWN_OR_DUPLICATE'):
        domain.validate(finding, p, tasks, PRIVATE)


def test_pending_piece_keeps_known_tags_and_explicit_partial_status(tasks):
    p = piece('공사 직원의 연차유급휴가는 별도 규정에 따른다.')
    q = piece('구조가 불명확한 표', 'p2', len(p['text']))
    finding = domain.validate(proposal(p), p, tasks, PRIVATE)
    unknown = domain.validate(proposal(q, status='REVIEW_REQUIRED', assignments=[], reason='표의 구조와 업무를 판단하기 어려워 보류한다.'), q, tasks, PRIVATE)
    result = domain.aggregate([p, q], {p['id']: finding, q['id']: unknown})
    assert result['status'] == 'PARTIAL_REVIEW' and result['primary_path'] == '01.05'
    assert result['contains_review_required_piece']


def test_parent_context_is_not_reported_as_quote_inside_every_window(tasks):
    p = piece('공사 직원의 연차유급휴가는 별도 규정에 따른다. ' + '이후 지급 및 확인 절차를 따른다. '*20)
    finding = domain.validate(proposal(p), p, tasks, PRIVATE)
    window = domain.aggregate([p], {p['id']: finding}, [100, 150])
    assert window['primary_path'] == '01.05' and not window['primary_has_local_support']
    assert window['classification_basis'] == 'overlapping_source_piece_context'
    assert not window['assignments'][0]['supports'][0]['support_in_target']


def test_source_quotes_cannot_be_reconstructed_and_private_output_is_rejected(tasks):
    p = piece('공사 직원의 연차유급휴가는 별도 규정에 따른다.')
    bad = proposal(p); bad.assignments[0].quote = '공사 직원의 연차유급휴가는 법률에 따른다'
    with pytest.raises(ValueError):
        domain.validate(bad, p, tasks, PRIVATE)
    with pytest.raises(ValueError, match='PRIVATE_OUTPUT'):
        domain.validate(proposal(p, reason='private@example.invalid 개인 주소를 노출한다.'), p, tasks, PRIVATE)


def test_schema_constrains_ids_and_workflow_codes_at_their_actual_nesting(tasks):
    schema = domain.schema(['source:0:10'], tasks)
    assert schema['properties']['items']['items']['properties']['id']['enum'] == ['source:0:10']
    assert schema['$defs']['Assignment']['properties']['code']['enum'] == sorted(tasks)
    assert schema['additionalProperties'] is False


def test_folder_names_are_readable_and_do_not_admit_unknown_paths(tasks):
    parent, child = domain.folder_components('01.05', 'CLASSIFIED', tasks)
    assert parent == '01_인사·근태' and child == '01.05_휴가'
    assert domain.folder_components(None, 'PRIVACY_HOLD', tasks) == ('HOLD', 'PRIVACY_HOLD')
    with pytest.raises(ValueError):
        domain.folder_components('../../outside', 'CLASSIFIED', tasks)
    with pytest.raises(ValueError):
        domain.folder_components(None, '../outside', tasks)


def test_persisted_computed_supports_can_be_revalidated_without_entering_the_api_schema(tasks):
    p = piece('공사 직원의 연차유급휴가는 별도 규정에 따른다.')
    checked = domain.validate(proposal(p), p, tasks, PRIVATE)
    saved = checked | dict(model='configured-model', call_record='safe-call.json')
    restored = domain.validate(domain.finding_from_saved(saved), p, tasks, PRIVATE)
    assert restored['assignments'] == checked['assignments'] and restored['status'] == checked['status']


def test_offline_report_encodes_untrusted_script_closers_as_data():
    import json
    from scripts.report_domain_workflows import safe_payload
    value = dict(preview='</script><script>alert("untrusted")</script> & 원문')
    encoded = safe_payload(value)
    assert '</script>' not in encoded and json.loads(encoded) == value


def test_a_temporary_file_lock_retries_the_same_local_payload(monkeypatch, tmp_path):
    from scripts import classify_domain_workflows as runner
    attempts = []; delays = []
    payload = dict(source_id='source-fixture', classification_grants_answer_use=False)
    def locked_write(path, value):
        attempts.append(value)
        if len(attempts) < 3:
            raise PermissionError('temporary fixture lock')
        path.write_text('saved', encoding='utf-8')
    monkeypatch.setattr(runner, 'atomic_write', locked_write)
    monkeypatch.setattr(runner.time, 'sleep', delays.append)
    target = tmp_path/'proposal.json'
    runner.write(target, payload)
    assert target.read_text(encoding='utf-8') == 'saved'
    assert len(attempts) == 3 and all(value is payload for value in attempts)
    assert delays and sum(delays) < 1
