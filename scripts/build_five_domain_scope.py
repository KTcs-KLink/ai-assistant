"""Correct domain scope locally using retained evidence; no API calls or re-embedding."""
from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server import five_domain_scope as five, domain_workflow, hr_source_scope as source
from scripts.classify_domain_workflows import write
from scripts.reclassify_hr_review import readl, writel
from scripts.report_domain_workflows import safe_payload

PREVIOUS = source.WORKSPACE/'outputs/klink_domain_workflow_20261109'
ORIGINAL = source.WORKSPACE/'outputs/kepco_domains_20261026/data/taxonomy.json'
OUT = source.WORKSPACE/'outputs/klink_five_domain_scope_20261109'


def destination(record):
    scope = record['scope_decision']
    if scope == 'IN_SCOPE':
        parent, child = domain_workflow.folder_components(record['primary_path'], record['status'], TASKS)
        return OUT/'by-domain'/parent/child
    if scope == 'ADJACENT_SCOPE':
        name = five.DOMAINS[record['primary_domain']].replace('/', '·')
        return OUT/'by-domain'/(record['primary_domain']+'_'+name)/'세부업무검토'
    return OUT/{'OUTSIDE_SCOPE': 'outside-five-domains', 'REVIEW_REQUIRED': 'review-required', 'PRIVACY_HOLD': 'privacy-hold'}[scope]


def main():
    global TASKS
    if (OUT/'summary.json').exists() or (OUT/'by-domain').exists():
        raise SystemExit('Preserve the completed five-domain version before rebuilding.')
    original = json.loads(ORIGINAL.read_text(encoding='utf-8-sig'))
    tax = five.taxonomy(original); TASKS = {t['code']: t for t in tax['tasks']}
    baseline = json.loads((PREVIOUS/'protocol.json').read_text(encoding='utf-8'))
    previous_summary = json.loads((PREVIOUS/'summary.json').read_text(encoding='utf-8'))
    for name, key in [('unit-classification.jsonl', 'unit_classification_sha256'), ('window-classification.jsonl', 'window_classification_sha256')]:
        if source.file_sha(PREVIOUS/name) != previous_summary[key]:
            raise ValueError('RETAINED_SOURCE_CLASSIFICATION_CHANGED')
    for path, sha in baseline['baseline_sha256'].items():
        if source.file_sha(source.WORKSPACE/path) != sha:
            raise ValueError('ORIGINAL_BASELINE_CHANGED')
    units = []
    for path in sorted((PREVIOUS/'by-domain').glob('*/*/units.jsonl')):
        units.extend(five.project(r, TASKS) for r in readl(path))
    windows = [five.project(r, TASKS) for r in readl(PREVIOUS/'window-classification.jsonl')]
    if len(units) != 10205 or len({r['id'] for r in units}) != 10205 or len(windows) != 8511:
        raise ValueError('ALL_SOURCE_IDS_REQUIRED')
    if sum(r['service_answer_eligible'] for r in units) != 528 or sum(r['service_answer_eligible'] for r in windows) != 536:
        raise ValueError('ANSWER_SCOPE_CHANGED')
    memberships = []; view = []
    with ExitStack() as stack:
        handles = {}
        def emit(record, kind):
            folder = destination(record); key = (str(folder), kind)
            if key not in handles:
                folder.mkdir(parents=True, exist_ok=True)
                handles[key] = stack.enter_context((folder/f'{kind}.jsonl').open('w', encoding='utf-8'))
            handles[key].write(json.dumps(record, ensure_ascii=False)+'\n')
        for record in units:
            emit(record, 'units')
            links = []
            for assignment in record['assignments']:
                memberships.append(dict(id=record['id'], workflow=assignment['code'], supports=assignment['supports'], scope_decision=record['scope_decision']))
                for support in assignment['supports'][:2]:
                    links.append(dict(code=assignment['code'], relation=support['relation'], quote=support['quote'], source_range=support['source_range']))
            view.append(dict(id=record['id'], title=record['document_title'], heading=record['heading_path'],
                primary_path=record['primary_path'], primary_domain=record['primary_domain'], direct_paths=record['direct_paths'],
                related_paths=record['related_paths'], scope_decision=record['scope_decision'], status=record['status'],
                privacy_hold=record['privacy_hold'], preview=(record['text'] or '')[:240],
                existing_search_windows=record['existing_search_windows'], service_answer_eligible=record['service_answer_eligible'],
                links=links[:12], source_file_sha256=record['source_file_sha256'], text_sha256=record['text_sha256'],
                original_download_url=record['original_download_url'], source_format=record['source_format'], posted_date=record['posted_date'],
                export=(destination(record)/'units.jsonl').relative_to(OUT).as_posix()))
        for record in windows:
            emit(record, 'windows')
    writel(OUT/'unit-classification.jsonl', ({k: v for k, v in r.items() if k != 'text'} for r in units))
    writel(OUT/'window-classification.jsonl', windows); writel(OUT/'workflow-memberships.jsonl', memberships)
    summary = dict(source_units=10205, existing_search_windows=8511, domains=5, workflows=34,
        **five.counts(units), window_scope_counts=five.counts(windows)['scope_counts'],
        window_primary_domain_counts=five.counts(windows)['primary_domain_counts'],
        units_without_existing_vectors=6335, model_calls=0, new_document_embeddings=0,
        source_proposals_reused=True, prior_expanded_results_preserved=True, answer_eligibility_changed=False,
        independent_human_approval=False, supabase_ingestion='HOLD', external_database_writes=0,
        original_taxonomy_sha256=source.file_sha(ORIGINAL),
        unit_classification_sha256=source.file_sha(OUT/'unit-classification.jsonl'),
        window_classification_sha256=source.file_sha(OUT/'window-classification.jsonl'))
    write(OUT/'taxonomy.json', tax); write(OUT/'summary.json', summary)
    write(OUT/'protocol.json', dict(original_baseline_sha256=baseline['baseline_sha256'],
        previous_result_sha256={name: source.file_sha(PREVIOUS/name) for name in ['summary.json', 'taxonomy.json', 'unit-classification.jsonl', 'window-classification.jsonl']},
        source_result_directory=PREVIOUS.name, method='SCOPE_CORRECTION_USING_RETAINED_EVIDENCE', model_calls=0,
        base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()))
    payload = dict(summary=summary, taxonomy=tax, records=sorted(view, key=lambda r: (r['primary_path'] or '99', r['title'], r['id'])))
    template = (REPO/'server/five_domain_report.html').read_text(encoding='utf-8')
    style = (REPO/'server/domain_workflow_report.html').read_text(encoding='utf-8').split('<style>')[1].split('</style>')[0]
    (OUT/'index.html').write_text(template.replace('__STYLE__', style).replace('__PAYLOAD__', safe_payload(payload)), encoding='utf-8')
    write(OUT/'view-manifest.json', dict(app_id='klink-five-domain-scope-20261109', source_units=10205,
        domain_count=5, workflow_count=34, report_sha256=source.file_sha(OUT/'index.html'), supabase_ingestion='HOLD'))
    lines = ['# 기존 5개 도메인·34개 업무 기준으로 정정', '',
        '인사/근태, 총무/행정, 재무/회계, IT/보안, 경영기획/성과관리의 기존 분류만 사용한다. 추가 도메인과 추가 업무 코드는 현재 분류에서 제거했다. 이전 결과는 별도 폴더에 보존했다.', '',
        '기존 모델 제안과 원문 근거를 재사용하고 코드로 허용 업무 목록을 대조했다. 새 모델 호출·청킹·임베딩·답변 근거 추가·Supabase 적재는 수행하지 않았다.', '',
        '| 자료 구분 | 원문 청크 |', '|---|---:|']
    for key, label in five.SCOPES.items():
        lines.append(f"| {label} | {summary['scope_counts'].get(key,0):,} |")
    lines += ['| 합계 | 10,205 |', '', '## 5개 도메인', '', '| 도메인 | 직접 업무 | 인접·세부업무 검토 |', '|---|---:|---:|']
    for code, name in five.DOMAINS.items():
        lines.append(f"| {name} | {summary['primary_domain_counts'].get(code,0):,} | {summary['adjacent_domain_counts'].get(code,0):,} |")
    lines += ['', '직접 근거가 있는 기존 34개 업무는 해당 경로에 연결했다. 관련·참조만으로 직접 업무를 승인하지 않는다. 기존 도메인에 인접하지만 34개 업무에 바로 대응하지 않는 자료는 세부업무 검토로, 그 외 자료는 5개 도메인 범위 밖으로 구분했다. 범위 밖과 보류는 새 도메인이 아니다.', '',
        '단순히 10개 분류의 앞 5개만 남긴 것이 아니다. 다른 대표 분류에 있더라도 기존 34개 업무의 직접 연결이 확인된 자료는 해당 업무에 보존했다. 복수 업무 연결도 유지했다.', '',
        '자동 분류 제안의 범위 정정이며 독립적인 사람의 의미 승인·현행성·실제 KTcs 적용 확인은 아니다. 기존 답변 근거 528개 원문·536개 검색 조각은 유지했다. 개인정보 패턴 보류 본문은 표시하거나 새로 모델에 보내지 않았다.', '',
        '## 업무별 파일', '', '| 도메인 → 업무 | 대표 원문 청크 |', '|---|---:|']
    for task in tax['tasks']:
        parent, child = domain_workflow.folder_components(task['code'], 'CLASSIFIED', TASKS)
        file = OUT/'by-domain'/parent/child/'units.jsonl'; label = task['code']+' '+task['name']
        if file.is_file(): label = f'[{label}]({file.as_posix()})'
        lines.append(f"| {five.DOMAINS[task['domain']]} → {label} | {summary['primary_workflow_counts'].get(task['code'],0):,} |")
    lines += ['', f"[5개 도메인 조회 화면]({(OUT/'index.html').as_posix()})", '',
        '원문 ID·해시·위치·기존 벡터 행 번호와 답변 사용 범위를 유지했다. 원본·청크·임베딩·골든셋을 삭제하거나 옮기지 않았다. PR과 외부 DB 쓰기는 수행하지 않는다.', '']
    (OUT/'README.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == '__main__':
    main()
