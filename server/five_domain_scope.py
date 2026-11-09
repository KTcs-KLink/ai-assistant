"""Constrain retained source proposals to the user's five domains and 34 tasks."""
from collections import Counter
from copy import deepcopy

DOMAINS = {'01': '인사/근태', '02': '총무/행정', '03': '재무/회계',
           '04': 'IT/보안', '05': '경영기획/성과관리'}
SCOPES = {'IN_SCOPE': '34개 업무 직접 자료', 'ADJACENT_SCOPE': '도메인 인접·세부업무 검토',
          'OUTSIDE_SCOPE': '5개 도메인 범위 밖', 'REVIEW_REQUIRED': '업무 판단 보류',
          'PRIVACY_HOLD': '개인정보 패턴 보류'}


def taxonomy(original):
    tasks = [{key: task[key] for key in ('code', 'domain', 'name')} for task in original['tasks']]
    expected = {f'{domain}.{n:02d}' for domain, count in zip(DOMAINS, (8, 7, 7, 6, 6)) for n in range(1, count+1)}
    if (len(tasks) != 34 or {t['code'] for t in tasks} != expected
            or any(t['domain'] != t['code'].split('.')[0] for t in tasks)):
        raise ValueError('ORIGINAL_FIVE_DOMAIN_TAXONOMY_REQUIRED')
    return dict(version='klink-original-five-domains-20261109-v1', source_version=original['version'],
                domains=[dict(code=code, name=name) for code, name in DOMAINS.items()], tasks=tasks,
                domain_count=5, workflow_count=34, extensions_allowed=False, human_approved=False)


def project(record, tasks):
    """Apply an allowlist, preserving evidence and uncertainty without new model claims."""
    allowed = set(tasks)
    direct = sorted(set(record.get('direct_paths', [])) & allowed)
    links = [deepcopy(a) for a in record.get('assignments', []) if a['code'] in allowed]
    related = sorted({a['code'] for a in links if any(s['relation'] == 'RELATED' for s in a['supports'])})
    references = sorted({a['code'] for a in links if any(s['relation'] == 'REFERENCE_ONLY' for s in a['supports'])})
    previous_status = record['status']
    primary = None; domain = None
    if record.get('privacy_hold') or previous_status == 'PRIVACY_HOLD':
        scope = status = 'PRIVACY_HOLD'; links = []; direct = []; related = []; references = []
    elif previous_status == 'REVIEW_REQUIRED':
        scope = status = 'REVIEW_REQUIRED'; direct = []
    elif direct:
        scope = 'IN_SCOPE'
        primary = record.get('primary_path') if record.get('primary_path') in direct else direct[0]
        domain = tasks[primary]['domain']
        status = 'PARTIAL_REVIEW' if previous_status == 'PARTIAL_REVIEW' else ('MIXED' if len(direct) > 1 else 'CLASSIFIED')
    elif record.get('primary_domain') in DOMAINS or related:
        scope = status = 'ADJACENT_SCOPE'
        domain = record['primary_domain'] if record.get('primary_domain') in DOMAINS else tasks[related[0]]['domain']
    else:
        scope = status = 'OUTSIDE_SCOPE'
    result = deepcopy(record)
    result.update(scope_decision=scope, status=status, primary_domain=domain, primary_path=primary,
                  direct_paths=direct, related_paths=related, reference_paths=references, assignments=links,
                  multi_domain=len({tasks[code]['domain'] for code in direct}) > 1,
                  scope_correction_method='ORIGINAL_34_TASK_ALLOWLIST_APPLIED_TO_RETAINED_SOURCE_PROPOSALS',
                  source_proposal_status=previous_status, human_approved=False,
                  classification_grants_answer_use=False, ktcs_applicable=False)
    result['primary_has_local_support'] = bool(primary and any(
        a['code'] == primary and any(s['relation'] == 'DIRECT' and s['support_in_target'] for s in a['supports'])
        for a in links))
    if scope == 'PRIVACY_HOLD' and 'text' in result:
        result['text'] = None
    return result


def counts(records):
    return dict(scope_counts=dict(Counter(r['scope_decision'] for r in records)),
                primary_domain_counts=dict(Counter(r['primary_domain'] for r in records if r['scope_decision'] == 'IN_SCOPE')),
                adjacent_domain_counts=dict(Counter(r['primary_domain'] for r in records if r['scope_decision'] == 'ADJACENT_SCOPE')),
                primary_workflow_counts=dict(Counter(r['primary_path'] for r in records if r['primary_path'])))
