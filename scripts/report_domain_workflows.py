"""Publish an offline, searchable hierarchy and separated data from completed proposals."""
from collections import Counter
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server import hr_source_scope as scope, domain_workflow as domain
from scripts.classify_domain_workflows import OUT
from scripts.reclassify_hr_review import readl, write


def safe_payload(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('&', '\\u0026')


def main():
    summary = json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    tax = json.loads((OUT/'taxonomy.json').read_text(encoding='utf-8'))
    if (scope.file_sha(OUT/'unit-classification.jsonl') != summary['unit_classification_sha256']
            or scope.file_sha(OUT/'window-classification.jsonl') != summary['window_classification_sha256']):
        raise ValueError('CLASSIFICATION_CHANGED')
    tasks = {t['code']: t for t in tax['tasks']}; names = {d['code']: d['name'] for d in tax['domains']}
    records = []; ids = set(); folder_counts = Counter()
    for path in sorted((OUT/'by-domain').glob('*/*/units.jsonl')):
        for r in readl(path):
            if r['id'] in ids or r['classification_grants_answer_use'] or r['human_approved']:
                raise ValueError('INVALID_EXPORT_MEMBERSHIP')
            ids.add(r['id']); folder_counts[str(path.relative_to(OUT))] += 1
            if r['privacy_hold'] and (r['text'] is not None or r['assignments']):
                raise ValueError('PRIVACY_EXPORT_BOUNDARY')
            links = []
            for assignment in r['assignments']:
                for support in assignment['supports'][:2]:
                    links.append(dict(code=assignment['code'], relation=support['relation'], quote=support['quote'],
                                      source_range=support['source_range']))
            records.append(dict(id=r['id'], title=r['document_title'], heading=r['heading_path'],
                primary_path=r['primary_path'], primary_domain=r['primary_domain'], direct_paths=r['direct_paths'],
                status=r['status'], privacy_hold=r['privacy_hold'], preview=(r['text'] or '')[:240],
                existing_search_windows=r['existing_search_windows'], service_answer_eligible=r['service_answer_eligible'],
                text_sha256=r['text_sha256'], source_file_sha256=r['source_file_sha256'],
                original_download_url=r['original_download_url'], source_format=r['source_format'],
                effective_status=r['effective_status'], posted_date=r['posted_date'],
                file_version_key=r['file_version_key'], links=links[:12], export=str(path.relative_to(OUT)).replace('\\', '/')))
    if len(ids) != 10205 or ids != {r['id'] for r in readl(OUT/'unit-classification.jsonl')}:
        raise ValueError('EXPORT_COVERAGE')
    records.sort(key=lambda r: (r['primary_path'] or '99', r['title'], r['heading'], r['id']))
    payload = dict(summary=summary, taxonomy=tax, records=records)
    template = (REPO/'server/domain_workflow_report.html').read_text(encoding='utf-8')
    (OUT/'index.html').write_text(template.replace('__PAYLOAD__', safe_payload(payload)), encoding='utf-8')
    write(OUT/'view-manifest.json', dict(app_id='klink-domain-workflow-view-20261109', source_units=10205,
        existing_search_windows=8511, report_sha256=scope.file_sha(OUT/'index.html'),
        unit_classification_sha256=summary['unit_classification_sha256'], supabase_ingestion='HOLD'))
    lines = ['# 한전 원문 전체 도메인 → 업무 분류', '',
        '기존 원문 청크 10,205개 전체를 대상으로 분류 제안을 만들고 원문 ID·해시·위치·인용을 검사했다. 기존 청킹과 임베딩은 보존했고 새 분류표와 업무별 분리본을 추가했다.', '',
        f"[도메인·업무별로 조회하기]({(OUT/'index.html').as_posix()})", '',
        '## 기존 자료와 이번 작업', '',
        '- 한전 원문 파일 단위 203개 → 원문 청크 10,205개는 이미 보존되어 있었다.',
        '- 기존 임베딩 8,511개는 선별된 원문 청크 3,870개에서 만든 검색 조각이다. 검색에 없던 원문 6,335개도 이번 분류에 포함했다.',
        '- 이전 7,235개 재분류는 인사 미확정 검색 조각을 대상으로 했다. 이번 10,205개는 원문 청크 전체이며 서로 다른 집계 단위이므로 합산하지 않는다.',
        '- 사용자 기준 5개 도메인·34개 업무의 코드와 이름을 보존했다. 기존 인사 공통 업무와 원문 정리용 확장을 포함해 10개 도메인·82개 업무 경로로 구성했다. 확장은 공식 조직 분류나 사람의 승인으로 표현하지 않는다.',
        '- 한 본문에 여러 업무가 있으면 복수 연결했다. DIRECT(직접 업무), RELATED(관련), REFERENCE_ONLY(단순 참조)를 구분하고 관련·참조만으로 주 업무를 정하지 않았다.',
        '- 긴 원문은 기존 경계를 바꾸지 않고 연속 구간으로 나눠 검토했다. 기존 검색 조각에는 겹치는 원문 구간의 분류를 연결하고, 인용이 검색 조각 안에 직접 있는지도 따로 기록했다.', '',
        '## 도메인별 대표 분류', '',
        '| 도메인 | 원문 청크 | 기존 검색 조각 |', '|---|---:|---:|']
    for d in tax['domains']:
        code = d['code']
        lines.append(f"| {code} {d['name']} | {summary['primary_domain_counts'].get(code,0):,} | {summary['window_primary_domain_counts'].get(code,0):,} |")
    for code, label in [('REVIEW_REQUIRED', '업무 판단 보류'), ('PRIVACY_HOLD', '개인정보 패턴 보류')]:
        lines.append(f"| {label} | {summary['primary_domain_counts'].get(code,0):,} | {summary['window_primary_domain_counts'].get(code,0):,} |")
    lines += ['| 합계 | 10,205 | 8,511 |', '',
        f"대표 분류는 각 원문을 한 번만 세기 위한 폴더 위치다. 복수 도메인에 걸친 원문은 {summary['multi_domain_units']:,}개이며 별도 업무 연결 목록도 보존했다. 같은 도메인 안의 복수 업무도 유지한다. 복수 연결 수를 원문 청크 수와 합산하지 않는다.", '',
        '## 상태와 검증 경계', '',
        '| 상태 | 원문 청크 |', '|---|---:|']
    state_names = dict(CLASSIFIED='직접 업무 1개', MIXED='직접 업무 복수', PARTIAL_REVIEW='확인된 업무와 보류 구간 함께 존재', REVIEW_REQUIRED='직접 업무 판단 보류', PRIVACY_HOLD='개인정보 패턴으로 본문 비공개·모델 전송 제외')
    for state, count in summary['source_status_counts'].items():
        lines.append(f'| {state_names[state]} | {count:,} |')
    if (OUT/'held-source-types.json').is_file():
        held = json.loads((OUT/'held-source-types.json').read_text(encoding='utf-8'))
        lines += ['', f"업무 판단 보류 {held['unassigned_source_units']:,}개 중 공백을 제외한 본문이 30자 미만인 자료는 {held['under_30_nonwhitespace_characters']:,}개다. 보류의 구조 유형은 구조 미확정 구간 {held['source_kinds'].get('UNSTRUCTURED',0):,}개, 조문 {held['source_kinds'].get('ARTICLE',0):,}개, 기존 구조에서 빠져 별도로 보존한 본문 {held['source_kinds'].get('NORMALIZED_UNMAPPED',0):,}개다. 유형과 길이는 형식 통계이며, 이를 의미 정확도나 불필요한 자료라는 판정으로 바꾸지 않는다."]
    lines += ['',
        '- 분류는 지정된 GPT의 의미 제안과 코드의 원문 대조 결과다. 자동 검사나 같은 모델의 재시도는 사람의 독립 의미 평가가 아니다.',
        '- 짧은 표제·구조 단편, 깨진 문맥, 반복 검토에서도 인용·분류 검사를 통과하지 못한 구간은 보류로 남겼다. 연결 실패만으로 원문을 검토했다고 처리하지 않는다.',
        f"- 원문 대조 표본에서 발견한 업무 누락·직접/관련 연결 문제는 좁은 범위로 모델에 재검토하고 {summary.get('source_comparison_corrections',0):,}개 구간을 수정했다. 계약금액 변경과 계약문서 구성은 구매·계약을 직접 업무로, 감리 업무지침의 연결은 관련 업무로 구분한 사례다. 수정 전 제안과 재검토 기록을 보존했다. 이는 전체 정확도 측정이나 독립 평가가 아니다.",
        '- 개인정보 패턴에 걸린 원문은 본문을 모델·브라우저·분리본에 넣지 않고 ID·해시·보류 상태만 보존했다. 이는 개인정보 확정 판정과는 다르다.',
        f"- 기존 서비스 답변 근거 {summary['service_answer_eligible_units']:,}개 원문은 그대로다. 분류 결과가 새 답변 사용 승인을 부여하지 않는다. 새 문서 임베딩은 0개다.",
        '- 원본·정규화 원문·청크·기존 벡터·골든셋·이전 분류는 덮어쓰지 않았다. 한전 외 프로젝트 자료는 합치지 않았다.',
        '- Supabase 적재·외부 DB 쓰기는 HOLD이며 PR을 생성하지 않는다. 실제 KTcs 규정 적용이나 현행성은 별도 확인 대상이다.', '',
        '구조화 응답의 형식 제약에는 [OpenAI 공식 Structured Outputs 문서](https://developers.openai.com/api/docs/guides/structured-outputs)를 참고했다. 형식 제약이 의미 정확성을 보증하지는 않는다.', '',
        '## 업무별 분리 파일', '',
        '각 파일은 대표 분류를 기준으로 한 실제 원문 청크 분리본이다. 추가 연결은 `workflow-memberships.jsonl`에서 확인한다.', '',
        '| 도메인 → 업무 | 원문 청크 | 파일 |', '|---|---:|---|']
    for t in tax['tasks']:
        count = summary['primary_workflow_counts'].get(t['code'], 0)
        parent, child = domain.folder_components(t['code'], 'CLASSIFIED', tasks)
        p = OUT/'by-domain'/parent/child/'units.jsonl'
        link = f'[원문 분리본]({p.as_posix()})' if count else '대표 분류 자료 없음'
        lines.append(f"| {names[t['domain']]} → {t['code']} {t['name']} | {count:,} | {link} |")
    lines += ['', '## 재현·확인 기록', '',
        '- `protocol.json`, `taxonomy.json`: 대상·기준·원본 해시 고정 기록',
        '- `unit-classification.jsonl`: 원문 청크 10,205개의 대표·복수 업무 및 출처',
        '- `window-classification.jsonl`: 기존 8,511개 검색 조각과 벡터 행 번호 연결',
        '- `workflow-memberships.jsonl`: 직접·관련·참조별 복수 업무 연결',
        '- `source-mapping-audit.json`, `source-mapping-checks.jsonl`: 전체 부모 범위·정규화 원문 연결 검사',
        '- `proposals/`, `calls/`: 실제 분류 제안·인용·호출·검사 실패·재시도 기록',
        '- `summary.json`: 분모를 구분한 집계. 호출 수와 사용량은 보존된 응답 기록 기준이며 공급자 청구 총량 검증이 아니다.', '']
    (OUT/'README.md').write_text('\n'.join(lines), encoding='utf-8')
    write(OUT/'export-verification.json', dict(source_units=10205, disjoint_primary_folders=True,
        all_source_ids_present=True, folder_counts=dict(folder_counts), offline_report_records=len(records),
        privacy_text_exported=False, new_document_embeddings=0, supabase_ingestion='HOLD'))
    print(json.dumps(dict(report=str(OUT/'index.html'), source_units=len(records), primary_domain_counts=summary['primary_domain_counts']), ensure_ascii=True))


if __name__ == '__main__':
    main()
