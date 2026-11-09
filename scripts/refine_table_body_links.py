"""Recheck only failed/incomplete duplicate claims, reusing frozen source packets."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import base64
import json
from pathlib import Path
import re
import sys
import threading
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import review_table_body_links as runner
from server import table_body_review as review, hr_source_scope as source

INSTRUCTIONS = review.INSTRUCTIONS+'''
이번 입력은 1차 중복 제안에서 누락 또는 적용 범위 문제를 발견한 구간의 집중 재검토다. initial_check는 실패 이유이지 정답이 아니다.
본문이 '표N에 따른다/표 참조'라고 적었다고 표 셀의 상세 항목까지 본문에 포함된 것이 아니다. 일부 큰 분류만 같고 세부 종류·서류 목록·조건별 대응이 빠져 있으면 그 추가 정보를 명시한다. 같은 값이어도 (구) 기준/새 기준 또는 서로 다른 대상이면 바로 중복 처리하지 않는다.
표의 모든 금액·단위·목록·조건을 본문에서 실제 확인한 경우에만 DUPLICATE다. 순번/번호가 실제 정보인지 단순 표기인지도 구분한다. 제공된 본문 범위를 넘어 추정하지 않는다. 인용은 짧고 원문 그대로 복사한다. 성명/서명 같은 짧은 보조 필드는 2~3자도 가능하나, 적어도 하나는 4자 이상의 표 원문 구절을 함께 인용한다.
확인되지 않은 정보는 구체적인 이유로 HOLD 처리한다. 원문 불일치와 단순 추출 오류를 구분하고 정답 수식을 만들어내지 않는다.'''


def run(stage, workers, dry_run=False):
    protocol, records = runner.context(); key, model = runner.configured()
    if model != protocol['model']:
        raise ValueError('FROZEN_MODEL_CHANGED')
    page_reviewed = {r['id'] for r in runner.readl(runner.OUT/'source-page-reviews.jsonl')} if (runner.OUT/'source-page-reviews.jsonl').exists() else set()
    candidates = []
    for record in records:
        if record['stage'] != stage or record['id'] in page_reviewed or not runner.result_path(record['id']).is_file():
            continue
        first = runner.load(runner.result_path(record['id']))
        gated = review.apply_context_gate(first, record)
        if (first.get('proposed_label') == 'DUPLICATE' and gated['label'] == 'HOLD') or first['method'] == 'CODE_REJECTED_PROPOSALS_HOLD':
            candidates.append((record, first, gated))
    frozen = dict(stage=stage, ids=[r['id'] for r, _, _ in candidates], instructions_sha256=review.digest(INSTRUCTIONS),
        source_cohort_sha256=protocol['cohort_sha256']['occurrences.jsonl'],
        initial_result_sha256={r['id']: source.file_sha(runner.result_path(r['id'])) for r, _, _ in candidates},
        model=model, independent_human_approval=False, supabase_ingestion='HOLD')
    frozen_path = runner.OUT/f'refinement-protocol-{stage}.json'
    if frozen_path.exists():
        saved = runner.load(frozen_path)
        if any(saved[k] != frozen[k] for k in ['stage', 'instructions_sha256', 'source_cohort_sha256', 'model']):
            raise ValueError('REFINEMENT_PROTOCOL_CHANGED')
        if any(source.file_sha(runner.result_path(i)) != sha for i, sha in saved['initial_result_sha256'].items()):
            raise ValueError('INITIAL_COMPARISON_CHANGED')
        # Later source-page corrections resolve cases without invalidating the original frozen cohort.
        byid = {r['id']: r for r in records}; candidates = []
        for ident in saved['ids']:
            if ident not in page_reviewed:
                first = runner.load(runner.result_path(ident))
                candidates.append((byid[ident], first, review.apply_context_gate(first, byid[ident])))
        frozen = saved
    else:
        runner.write(frozen_path, frozen)
    output = runner.OUT/'refinement-results'
    candidates = [r for r in candidates if not (output/(review.digest(r[0]['id'])+'.json')).exists()]
    batches = [candidates[i:i+4] for i in range(0, len(candidates), 4)]
    if dry_run:
        print(json.dumps(dict(stage=stage, frozen_candidates=len(frozen['ids']), unresolved_quote_checks=len(candidates),
                              source_page_reviews_preserved=True, new_model_calls=0)))
        return
    from openai import OpenAI
    local = threading.local(); clients = []; lock = threading.Lock(); stopped = threading.Event(); run_id = uuid.uuid4().hex[:10]
    def process(batch):
        if not hasattr(local, 'client'):
            local.client = OpenAI(api_key=key, timeout=180, max_retries=0)
            with lock:
                clients.append(local.client)
        remaining = batch
        for attempt in range(3):
            if not remaining or stopped.is_set():
                return
            ids = [r['id'] for r, _, _ in remaining]; content = []
            for r, first, gated in remaining:
                payload = {k: r[k] for k in ['id', 'title', 'unit_id', 'page', 'posted_date', 'table_lines', 'comparison_scope', 'privacy_context_omitted']}
                payload['body'] = [{k: b[k] for k in ['id', 'page', 'text']} for b in r['body']]
                payload['initial_check'] = {k: gated.get(k) for k in ['reason', 'code_hold_reasons', 'context_gate', 'missing_table_terms']}
                content.append(dict(type='input_text', text=json.dumps(payload, ensure_ascii=False)))
                content.append(dict(type='input_image', image_url='data:image/png;base64,'+base64.b64encode((runner.OUT/r['image_path']).read_bytes()).decode(), detail='high'))
            request = dict(model=model, instructions=INSTRUCTIONS, input=[dict(role='user', content=content)],
                text={'format': dict(type='json_schema', name='table_body_refinement', strict=True, schema=review.schema(ids))}, truncation='disabled')
            name = f'refine.{run_id}.{review.digest("|".join(ids))[:16]}.{attempt}.json'
            call = dict(ids=ids, stage='refinement_'+stage, model=model, attempt=attempt, request_attempted=False,
                        input_tokens=None, usage=None, status='STARTED', errors=[], instructions_sha256=frozen['instructions_sha256'])
            started = time.monotonic()
            try:
                call['input_tokens'] = local.client.responses.input_tokens.count(**request).input_tokens
                if call['input_tokens'] > protocol['input_token_limit']:
                    call['status'] = 'SPLIT_INPUT_LIMIT'; runner.write(runner.OUT/'calls'/name, call)
                    if len(remaining) > 1:
                        middle = len(remaining)//2; process(remaining[:middle]); process(remaining[middle:])
                    return
                call['request_attempted'] = True; runner.write(runner.OUT/'calls'/name, call)
                response = local.client.responses.create(**request, store=False, max_output_tokens=7000, reasoning={'effort':'low'})
                call['usage'] = response.usage.model_dump() if response.usage else None
                if response.status != 'completed' or runner.private(response.output_text):
                    raise ValueError('INCOMPLETE_OR_PRIVATE_OUTPUT')
                values = json.loads(response.output_text)['items']
                if len(values) != len(ids) or {r['id'] for r in values} != set(ids):
                    raise ValueError('OUTPUT_ID_COVERAGE')
                byid = {r['id']: r for r in values}; failed = []
                for r, first, gated in remaining:
                    try:
                        checked = review.validate(review.Comparison.model_validate(byid[r['id']]), r, runner.PRIVATE)
                        checked.update(model=model, call_record=name, refinement=True,
                            expected_initial_result_sha256=frozen['initial_result_sha256'][r['id']])
                        runner.write(output/(review.digest(r['id'])+'.json'), checked)
                    except (ValueError, KeyError, TypeError) as error:
                        code = str(error) if type(error) is ValueError and re.fullmatch('[A-Z_]+',str(error)) else 'SCHEMA_REJECTED'
                        call['errors'].append(dict(id=r['id'],code=code)); failed.append((r,first,gated))
                call['proposals'] = values; remaining = failed; call['status'] = 'PARTIAL_RETRY' if failed else 'VALIDATED'
            except Exception as error:
                status = getattr(error,'status_code',None)
                call['status'] = 'FAILED'; call['errors'].append(dict(code=type(error).__name__,http_status=status))
                if status in {401,402,403} or (status==429 and getattr(error,'code',None)=='insufficient_quota'):
                    stopped.set()
            call['seconds'] = round(time.monotonic()-started,2); runner.write(runner.OUT/'calls'/name,call)
            if remaining and not stopped.is_set():
                time.sleep(2*(attempt+1))
        # Retain the initial conservative hold when the refinement itself cannot be checked.
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for future in as_completed([pool.submit(process,b) for b in batches]):
                future.result()
                print(json.dumps(dict(refinement_stage=stage,selected=len(frozen['ids']),
                    checked=sum((output/(review.digest(i)+'.json')).exists() for i in frozen['ids']))),flush=True)
    finally:
        for client in clients:
            client.close()
    if stopped.is_set():
        raise SystemExit('MODEL_ACCESS_OR_QUOTA_BLOCKED; initial evidence preserved.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['priority_172','remaining_745'],required=True)
    parser.add_argument('--workers',type=int,default=2);parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args();run(args.stage,args.workers,args.dry_run)
