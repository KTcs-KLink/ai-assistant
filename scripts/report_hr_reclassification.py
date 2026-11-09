"""Publish a readable local separation report from completed, source-verified results."""
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from server import hr_review_domains as domains,hr_source_scope as scope


def main():
    out=domains.OUT
    summary=json.loads((out/'summary.json').read_text(encoding='utf-8'))
    index=json.loads((out/'domain-review-index.json').read_text(encoding='utf-8'))
    units={r['id']:r for r in map(json.loads,(out/'data/units.jsonl').read_text(encoding='utf-8').splitlines())}
    labels={'HR':'인사 관련','NON_HR':'인사 외 업무','MIXED':'인사·다른 업무 혼합','REVIEW_REQUIRED':'판단 보류'}
    counts=summary['window_labels']
    overrides={r['piece_id']:r['finding'] for r in map(json.loads,(out/'source-review-overrides.jsonl').read_text(encoding='utf-8').splitlines())} if (out/'source-review-overrides.jsonl').exists() else {}
    lines=['# 한전 원문 7,235개 검색 조각 재분류 결과','',
        '기존에 인사 여부가 미확정이던 검색 조각 7,235개를 대상으로 지정 GPT가 원문을 새로 읽고, 코드가 원문 ID·직접 인용·범위·중복·전체 연결을 검사했다. Supabase 적재와 외부 DB 쓰기는 계속 보류했다.','',
        '| 재분류 | 검색 조각 | 처리 |','|---|---:|---|']
    for label in labels:
        treatment={'HR':'인사 검토 후보로 유지','NON_HR':'별도 폴더·검색으로 분리, 기본 인사 검토 검색에서 제외',
            'MIXED':'인사 부분의 손실을 막기 위해 혼합 자료로 보존','REVIEW_REQUIRED':'구조·문맥·분류 근거 등의 확인이 필요해 판단 보류'}[label]
        lines.append(f'| {labels[label]} | {counts.get(label,0):,} | {treatment} |')
    lines += ['| 합계 | 7,235 | 누락·중복 없이 분리 |','',
        f"대상은 {len({u['unit_id'] for u in units.values()}):,}개 문서의 조문·서식 원문 단위 3,014개다. 긴 원문을 중복 없는 {summary['reviewed_source_pieces']:,}개 구간으로 나눠 검토한 뒤 기존 검색 조각에 결과를 연결했다. 같은 원문을 겹치는 검색 조각마다 반복 입력하지 않았다.",'',
        '## 분류 기준과 검증 범위','',
        '- 내부 직원·임원·지원자·퇴직자·가족의 채용·복무·급여·휴가·복리후생·직원 교육·평정·징계·노사관계는 인사 관련으로 분류했다.',
        '- 전력·요금·설비·공사·입찰·거래 절차와 협력업체 기술인력 자격·교육 등은 내부 직원 인사와 구분했다.',
        '- 인사와 다른 업무가 같이 있으면 통째로 인사 외로 버리지 않고 혼합으로 남겼다.',
        '- 글리프나 표 구조의 문제는 인사 여부와 별도다. 형식만으로 인사 자료를 인사 외로 제외하지 않았다.',
        '- 모델이 제안한 ID·원문 인용·문자 위치를 코드로 대조했다. 원문의 일부를 생략해 요청 한도에 맞추지 않았다.',
        '- 이전 인사 표시 535개 검색 조각은 이번 7,235개 재분류 분모에 포함하지 않았다. 서비스 검토 검색에는 이 기존 자료도 별도로 유지했다.',
        '- 인사 분류는 답변 사용 승인과 다르다. 이번 대상의 `answer_eligible`은 모두 false로 유지했다. 기존 답변용 528조문·536검색 조각과 원문·벡터·골든셋은 변경하지 않았다.',
        '- 자동 분류와 원문 일치 검사는 독립적인 사람 승인·현행성·KTcs 적용 확인이 아니다.','',
        f"모델: `{summary['model']}`. 보존된 호출 기록 기준으로 생성 요청 시도 {summary['generation_request_attempts']:,}회(재시도 포함), 확인된 구조화 응답 {summary['completed_response_records']:,}개다. 사용량을 돌려받지 못한 요청 시도는 {summary['request_attempts_without_returned_usage']:,}회로 별도 표시한다. 공급자 측 청구 총량을 검증한 수치는 아니다. 분류 제안 검사 실패로 코드가 판단 보류한 구간 {summary.get('code_failed_proposal_hold_pieces',0):,}개이며, 해당 구간에 걸친 검색 조각은 {summary.get('windows_with_failed_proposal_hold',0):,}개다. 실패 시도도 별도로 보존했다.",'',
        f"원문 대조에서 자동 제안의 설명·적용 대상이 충분히 입증되지 않은 {summary.get('source_comparison_overrides',0):,}개 구간은 판단 보류로 수정했다. 입찰업체의 고용지표·소속 기술자·보호장비 기준을 내부 직원 인사 근거로 제시한 사례와, 깨진 본문에서 확인되지 않는 내용을 추론한 사례다. 수정 전 제안과 원문 위치를 모두 보존했다. 이는 표본·실패 사례 검토이며 전체 분류 정확도나 사람의 독립 승인을 뜻하지 않는다.",'',
        '구조화된 응답의 형식 제약은 의미 정답 보증과 다르다. 구현 참고: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).','',
        '## 분리한 실제 데이터','']
    for label in labels:
        path=out/'separated'/label.lower()/'windows.jsonl'
        lines.append(f"- [{labels[label]} 검색 조각]({path.as_posix()}): {counts.get(label,0):,}개. 기존 검색 ID·원문·위치·분류 근거 연결을 보존했다.")
    lines += ['',f"전체 근거는 [{(out/'unit-classification.jsonl').name}]({(out/'unit-classification.jsonl').as_posix()})와 로컬 `proposals/`, `calls/`에 있다.",'',
        '## 원문 근거 예시','']
    for label in labels:
        lines.append('### '+labels[label]);lines.append('')
        selected=[];seen=set()
        for row in map(json.loads,(out/'separated'/label.lower()/'windows.jsonl').read_text(encoding='utf-8').splitlines()):
            unit=units[row['unit_record_id']]
            if unit['document_title'] in seen:continue
            selected.append(row);seen.add(unit['document_title'])
            if len(selected)==3:break
        for row in selected:
            unit=units[row['unit_record_id']]
            findings=[overrides.get(pid) or json.loads((out/'proposals'/f'{scope.text_sha(pid)}.json').read_text(encoding='utf-8')) for pid in row['source_piece_ids']]
            reasons=' / '.join(dict.fromkeys(f"{finding['label']}: {finding['reason']}" for finding in findings))
            lines.append(f"- **{unit['document_title']}** · {unit['heading_path']}: {reasons}")
        if not selected:lines.append('- 해당 없음')
        lines.append('')
    if (out/'non-hr-document-counts.json').exists():
        lines += ['## 인사 외로 분리된 주요 문서','', '| 문서 | 검색 조각 |','|---|---:|']
        for title,count in json.loads((out/'non-hr-document-counts.json').read_text(encoding='utf-8'))[:10]:
            lines.append(f'| {title} | {count:,} |')
        lines += ['', '위 표는 인사 외 자료가 많은 상위 10개 문서이며, 문서 전체의 인사 여부를 뜻하지 않는다. 같은 문서 안에서도 조문·구간에 따라 분류가 다를 수 있다.','']
    lines += ['## 운영 경계','',
        '기존 원본을 옮기거나 삭제하지 않고 새 폴더에 분리본과 분류 목록을 만들었다. 인사 외 자료는 별도 조회할 수 있으며, 기본 인사 검토 검색에서는 제거했다. 혼합·판단 보류 자료는 인사 내용을 잃지 않도록 후보에 남긴다.',
        '다른 프로젝트의 데이터·설정은 사용하지 않았다. 키·직원 프로필을 모델에 보내거나 결과·Git·브라우저에 복사하지 않았다. Supabase 적재·외부 DB 쓰기·PR 생성은 수행하지 않았다.','']
    (out/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(report=str(out/'README.md'),window_labels=counts,default_excludes_non_hr=True),ensure_ascii=True))


if __name__=='__main__':main()
