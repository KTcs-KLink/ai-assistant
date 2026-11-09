"""Checkpointed review of the retained 172+745 table assets. No source/DB mutations."""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import gc
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import uuid

for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '2'
for logger_name in ('openai', 'httpx', 'httpcore'):
    logging.getLogger(logger_name).setLevel(logging.WARNING)
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server import table_body_review as review, hr_evidence, hr_source_scope as source
from scripts.classify_domain_workflows import write
from scripts.reclassify_hr_review import readl, writel, configured

ROOT = REPO.parent
OUT = ROOT/'outputs/klink_table_body_review_20261109'
OLD = ROOT/'work/kepco_table_redundancy'
CLEAN = ROOT/'outputs/kepco_cleaned_20261025'
DOCS = ROOT/'outputs/kepco_complex_materials_20261025/data/documents.jsonl'
INPUTS = [CLEAN/'tables/inventory.json', CLEAN/'data/tables_context_linked.jsonl',
          CLEAN/'provenance/table_text_redundancy_reviews.jsonl', OLD/'analysis.json', OLD/'native_analysis.json', DOCS,
          ROOT/'outputs/klink_five_domain_scope_20261109/summary.json',
          ROOT/'outputs/klink_five_domain_scope_20261109/taxonomy.json',
          ROOT/'outputs/klink_five_domain_scope_20261109/unit-classification.jsonl',
          source.INPUTS['reviewed_units'], source.INPUTS['documents'], source.INPUTS['normalized_documents'],
          source.INPUTS['windows'], source.INPUTS['vectors'],
          ROOT/'outputs/kepco_hr_gold_960_20261102/data/golden_set.jsonl']
PRIVATE = hr_evidence.PRIVATE
STATUS_META = None
STATUS_RESULTS = {}


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def private(text):
    return bool(PRIVATE.search(unicodedata.normalize('NFKC', text)))


def private_payload(value):
    # Numeric geometry can contain 13-digit decimal fractions; those are not identity numbers.
    if isinstance(value, str):
        return private(value)
    if isinstance(value, dict):
        return any(private_payload(v) for v in value.values())
    if isinstance(value, list):
        return any(private_payload(v) for v in value)
    return False


def overlaps(a, b):
    area = max(0, min(a[2], b[2])-max(a[0], b[0]))*max(0, min(a[3], b[3])-max(a[1], b[1]))
    return area > max(1, (a[2]-a[0])*(a[3]-a[1]))*.02


def terms(text):
    result = Counter()
    for word in re.findall(r'[가-힣]{2,}|[A-Za-z]{2,}|\d+(?:[.,]\d+)*', text.lower()):
        if word in review.HEADERS:
            continue
        result[word] += 1
        if re.fullmatch(r'[가-힣]{4,}', word):
            for i in range(len(word)-2):
                result['~'+word[i:i+3]] += .2
    return result


def table_text(record):
    return record.get('evidence_text') or '\n'.join(' '.join(str(v or '') for v in row) for row in record.get('cells', []))


def source_paragraphs(pdf, uid, sha, boxes):
    """Keep native source lines together; never use any detected table's cell text as body."""
    paragraphs = []; blocked = []
    for page_index in range(len(pdf)):
        page = pdf[page_index]; page_number = page_index+1
        blocks = page.get_text('dict')['blocks']
        for block_index, block in enumerate(blocks):
            active = []; part = 0
            def flush():
                nonlocal active, part
                if not active:
                    return
                text = '\n'.join(x['text'] for x in active)
                ident = f'{uid}:P{page_number:04d}:B{block_index:04d}:S{part:02d}'
                bbox = [min(x['bbox'][0] for x in active), min(x['bbox'][1] for x in active),
                        max(x['bbox'][2] for x in active), max(x['bbox'][3] for x in active)]
                if private(text):
                    blocked.append(dict(id=ident, page=page_number, reason='PRIVATE_PATTERN_BODY_OMITTED'))
                elif len(text.strip()) >= 4 and not re.fullmatch(r'[\d\s./\-]+', text) and not re.match(
                        r'^\s*[\[【(<〈]?\s*(?:표\s*\d+|그림\s*\d+|Table\s*\d+)', text, re.I):
                    paragraphs.append(dict(id=ident, unit_id=uid, page=page_number, bbox=bbox, text=text,
                        text_sha256=review.digest(text), source_file_sha256=sha, inside_table=False,
                        source_method='ORIGINAL_PDF_NATIVE_LINES_OUTSIDE_ALL_DETECTED_TABLE_REGIONS', source_lines=active))
                active = []; part += 1
            for line_index, line in enumerate(block.get('lines', [])):
                spans = line.get('spans', [])
                if not spans or any(overlaps(span['bbox'], box) for span in spans for box in boxes.get(page_number, [])):
                    flush(); continue
                text = ''.join(span['text'] for span in spans).strip()
                if text:
                    active.append(dict(line_index=line_index, text=text, bbox=list(line['bbox'])))
            flush()
    return paragraphs, blocked


def prepare():
    if (OUT/'protocol.json').exists():
        raise SystemExit('Frozen table cohort exists; resume without overwriting it.')
    sys.path.insert(0, str(ROOT/'work/kepco_complex/pdf_runtime'))
    import pymupdf
    inventory = load(INPUTS[0]); old_reviews = {r['asset_id']: r for r in readl(INPUTS[2])}
    cached = {r['asset_id']: r for r in load(OLD/'analysis.json')}
    native_cached = {r['asset_id']: r['native_occurrences'] for r in load(OLD/'native_analysis.json')}
    assert len(inventory) == 917 and sum(len(r['source_records']) for r in inventory) == 1014
    assert all(r['image_sha256'] == old_reviews[r['asset_id']]['image_sha256'] for r in inventory)
    priority = {r['asset_id'] for r in inventory if old_reviews[r['asset_id']]['ranking_score_for_triage_only'] >= .3}
    assert len(priority) == 172
    documents = {r['unit_id']: r for r in readl(DOCS)}
    current_documents = {r['unit_id']: r for r in readl(source.INPUTS['documents'])}
    current_origins = {r['unit_id']: r for r in readl(source.INPUTS['normalized_documents'])}
    needed = {r['unit_id'] for t in inventory for r in t['source_records']}
    boxes = defaultdict(lambda: defaultdict(list))
    for path in (ROOT/'outputs/kepco_types_20261025/provenance/pdf_scans').glob('*.json'):
        scan = load(path)
        if scan['unit_id'] in needed:
            for item in scan['tables']:
                boxes[scan['unit_id']][item['physical_pdf_page']].append(item['bbox'])
    sources = {}; bodies = {}; blocked = {}; page_crop_private = set(); images = {}
    reusable_bodies = defaultdict(list); reusable_blocked = defaultdict(list)
    if (OUT/'source-body-paragraphs.jsonl').is_file() and (OUT/'private-body-omissions.json').is_file():
        # Resume this task's own completed native-extraction checkpoint after a preparation failure.
        for paragraph in readl(OUT/'source-body-paragraphs.jsonl'):
            if (paragraph['unit_id'] not in needed or paragraph['source_file_sha256'] != current_documents[paragraph['unit_id']]['source_file_sha256']
                    or review.digest(paragraph['text']) != paragraph['text_sha256'] or private_payload(paragraph)):
                raise ValueError('NATIVE_EXTRACTION_CHECKPOINT_CHANGED')
            reusable_bodies[paragraph['unit_id']].append(paragraph)
        for omitted in load(OUT/'private-body-omissions.json'):
            reusable_blocked[omitted['id'].split(':', 1)[0]].append(omitted)
    by_uid = defaultdict(list)
    for table in inventory:
        image = (CLEAN/table['source_image_path']).resolve()
        if not image.is_relative_to(ROOT) or source.file_sha(image) != table['image_sha256']:
            raise ValueError('ORIGINAL_TABLE_IMAGE_CHANGED')
        images[table['asset_id']] = image
        for item in table['source_records']:
            by_uid[item['unit_id']].append((table['asset_id'], item))
    OUT.mkdir(parents=True, exist_ok=True)
    for uid in sorted(needed):
        doc = documents[uid]; original = Path(current_origins[uid]['original_local_path']).resolve()
        sha = source.file_sha(original)
        if (sha != doc['unit_file_sha256'] or sha != current_documents[uid]['source_file_sha256']
                or any(item['source_sha256'] != sha for _, item in by_uid[uid])):
            raise ValueError('ORIGINAL_DOCUMENT_CHANGED')
        sources[uid] = dict(path=str(original), sha256=sha)
        with pymupdf.open(original) as pdf:
            if uid in reusable_bodies:
                bodies[uid], blocked[uid] = reusable_bodies[uid], reusable_blocked[uid]
            else:
                bodies[uid], blocked[uid] = source_paragraphs(pdf, uid, sha, boxes[uid])
            for asset, item in by_uid[uid]:
                crop_text = pdf[item['physical_pdf_page']-1].get_textbox(item.get('clip') or item['bbox'])
                if private(crop_text) or private(table_text(item)):
                    page_crop_private.add(asset)
        print(json.dumps(dict(prepared_documents=len(bodies), total_documents=len(needed))), flush=True)
    writel(OUT/'source-body-paragraphs.jsonl', (p for group in bodies.values() for p in group))
    write(OUT/'private-body-omissions.json', [r for group in blocked.values() for r in group])
    indices = {}; postings = {}
    for uid, paragraphs in bodies.items():
        posting = defaultdict(set)
        for index, p in enumerate(paragraphs):
            for term in terms(p['text']):
                posting[term].add(index)
        indices[uid] = {p['id']: i for i, p in enumerate(paragraphs)}; postings[uid] = posting
    occurrences = []; assets = []
    for table in sorted(inventory, key=lambda t: (t['asset_id'] not in priority,
            -old_reviews[t['asset_id']]['ranking_score_for_triage_only'], t['asset_id'])):
        asset = table['asset_id']; stage = 'priority_172' if asset in priority else 'remaining_745'
        private_asset = asset in page_crop_private or private(table['title']+' '+table.get('context_evidence_text', ''))
        saved_image = OUT/'images'/(asset+'.png')
        if not private_asset:
            saved_image.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(images[asset], saved_image)
        asset_record = dict(asset_id=asset, title=table['title'], stage=stage,
            prior_ranking_score=old_reviews[asset]['ranking_score_for_triage_only'],
            image_sha256=table['image_sha256'], image_path=None if private_asset else saved_image.relative_to(OUT).as_posix(),
            privacy_hold=private_asset, occurrence_ids=[r['item_id'] for r in table['source_records']],
            previous_native_comparison_available=asset in native_cached, classification_grants_answer_use=False)
        assets.append(asset_record)
        old_byid = {r['item_id']: r for r in cached[asset]['source_occurrences']}
        for item in table['source_records']:
            uid = item['unit_id']; page = item['physical_pdf_page']; text = '' if private_asset else table_text(item)
            paragraphs = bodies[uid]; posting = postings[uid]; scores = Counter()
            caption = table.get('context_evidence_text', '')
            query = terms(text+' '+('' if private(caption) else caption))
            for term, weight in query.items():
                hits = posting.get(term, set())
                for index in hits:
                    scores[index] += min(weight, 2)*math.log1p(len(paragraphs)/(1+len(hits)))
            chosen = {i for i, p in enumerate(paragraphs) if abs(p['page']-page) <= 1}
            prior_native = next((r for r in native_cached.get(asset, []) if r['item_id'] == item['item_id']), None)
            reused_native_ids = set()
            if prior_native:
                # Reuse retained source spans as retrieval anchors, after rechecking the current PDF.
                for span in prior_native['outside_table_pdf_spans']:
                    needle = ''.join(span['text'].split())
                    if len(needle) < 4 or private(span['text']):
                        continue
                    for i, paragraph in enumerate(paragraphs):
                        if paragraph['page'] == span['page'] and needle in ''.join(paragraph['text'].split()):
                            chosen.add(i); reused_native_ids.add(paragraph['id'])
            global_matches = [i for i, score in scores.most_common(5) if score > 0]
            for index in global_matches:
                chosen.add(index)
                # Keep the adjacent original paragraph to retain conditions and exceptions.
                for adjacent in (index-1, index+1):
                    if 0 <= adjacent < len(paragraphs) and paragraphs[adjacent]['page'] == paragraphs[index]['page']:
                        chosen.add(adjacent)
            selected = [paragraphs[i] for i in sorted(chosen)]
            previous = old_byid[item['item_id']]
            record = dict(id=item['item_id'], asset_id=asset, stage=stage, title=table['title'], unit_id=uid, page=page,
                posted_date=documents[uid].get('posted_date'), effective_status=documents[uid].get('effective_status'),
                source_file_sha256=documents[uid]['unit_file_sha256'], image_sha256=table['image_sha256'],
                image_path=asset_record['image_path'], table_bbox=item['bbox'], table_clip=item.get('clip') or item['bbox'],
                table_text=text, table_text_sha256=review.digest(text), table_lines=review.meaningful_lines(text),
                body=selected if not private_asset else [], privacy_hold=private_asset,
                privacy_context_omitted=any(abs(p['page']-page) <= 1 for p in blocked[uid]),
                prior_parent=previous.get('source_parent'), prior_nearby_body_text_sha256=review.digest(previous['body_text']),
                previous_native_comparison_available=prior_native is not None,
                reused_native_body_ids=sorted(reused_native_ids),
                same_document_global_retrieval_added=True, global_retrieval_body_ids=[paragraphs[i]['id'] for i in global_matches],
                comparison_scope='SELECTED_TABLE_EXCLUDED_BODY_FROM_SAME_DOCUMENT_VERSION',
                original_download_url=item['original_download_url'], body_source_count=len(selected),
                independent_human_approval=False, answer_eligible=False, source_action='PRESERVE')
            if private_asset:
                record['prior_parent'] = None
            if private_payload(record):
                raise ValueError('PRIVATE_FROZEN_PAYLOAD')
            occurrences.append(record)
    writel(OUT/'occurrences.jsonl', occurrences); writel(OUT/'assets.jsonl', assets)
    protocol = dict(schema='klink-table-body-comparison-20261109-v1', company='KEPCO', assets=917,
        occurrences=1014, stages=dict(priority_172=172, remaining_745=745),
        occurrence_stages=dict(Counter(r['stage'] for r in occurrences)),
        model=configured()[1], instructions_sha256=review.digest(review.INSTRUCTIONS),
        baseline_sha256={str(p.relative_to(ROOT)): source.file_sha(p) for p in INPUTS},
        source_file_sha256=sources, table_image_sha256={r['asset_id']: r['image_sha256'] for r in assets},
        cohort_sha256={name: source.file_sha(OUT/name) for name in ['occurrences.jsonl', 'assets.jsonl', 'source-body-paragraphs.jsonl']},
        body_extraction='NATIVE_PDF_ONLY_NO_OCR; ALL_DETECTED_TABLE_BOXES_EXCLUDED',
        previous_ranking_and_parent_context_reused=True, previous_native_records_available_for_current_assets=len(priority),
        input_token_limit=24000, new_embeddings=0, source_action='PRESERVE', answer_eligibility_changed=False,
        human_approved=False, supabase_ingestion='HOLD', external_database_writes=0,
        base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip())
    write(OUT/'protocol.json', protocol)
    for record in occurrences:
        if record['privacy_hold']:
            write(result_path(record['id']), review.hold(record, 'CODE_PRIVACY_HOLD', '표 영역에서 개인정보 패턴이 발견되어 이미지·본문을 보내지 않고 보류했다.'))
        elif not record['table_lines'] or not record['body']:
            write(result_path(record['id']), review.hold(record, 'CODE_MISSING_EVIDENCE_HOLD', '추출 가능한 표 텍스트 또는 표 바깥 연결 본문이 부족해 의미 비교를 보류했다.'))
    print(json.dumps(status()), flush=True)


def result_path(ident):
    return OUT/'results'/(review.digest(ident)+'.json')


def context():
    protocol = load(OUT/'protocol.json')
    if protocol['instructions_sha256'] != review.digest(review.INSTRUCTIONS):
        raise ValueError('FROZEN_INSTRUCTIONS_CHANGED')
    for name, sha in protocol['cohort_sha256'].items():
        if source.file_sha(OUT/name) != sha:
            raise ValueError('FROZEN_COHORT_CHANGED')
    records = []
    for record in readl(OUT/'occurrences.jsonl'):
        # Native line provenance remains in the frozen cohort/body registry, not duplicated in API memory.
        for body in record['body']:
            body.pop('source_lines', None)
        records.append(record)
    return protocol, records


def status():
    global STATUS_META
    if STATUS_META is None:
        STATUS_META = [{k: r[k] for k in ['id', 'asset_id', 'stage']} for r in readl(OUT/'occurrences.jsonl')]
    records = STATUS_META
    for path in (OUT/'results').glob('*.json'):
        stamp = path.stat().st_mtime_ns
        if path.name not in STATUS_RESULTS or STATUS_RESULTS[path.name][0] != stamp:
            r = load(path); STATUS_RESULTS[path.name] = (stamp, {k: r[k] for k in ['id', 'label']})
    results = {r['id']: r for _, r in STATUS_RESULTS.values()}
    perasset = defaultdict(list)
    for record in records:
        perasset[record['asset_id']].append(record['id'])
    stages = {}
    for stage in ['priority_172', 'remaining_745']:
        asset_ids = {r['asset_id'] for r in records if r['stage'] == stage}
        finished = {aid: review.aggregate([results[i] for i in perasset[aid]]) for aid in asset_ids if all(i in results for i in perasset[aid])}
        stages[stage] = dict(completed_assets=len(finished), total_assets=len(asset_ids), labels=dict(Counter(finished.values())))
    result = dict(completed_occurrences=len(results), total_occurrences=len(records),
                  complete=len(results) == len(records), stages=stages)
    write(OUT/'progress.json', result)
    return result


def run(stage, workers, limit):
    protocol, records = context(); key, model = configured()
    if model != protocol['model']:
        raise ValueError('CONFIGURED_MODEL_CHANGED')
    pending = [r for r in records if r['stage'] == stage and not result_path(r['id']).exists()]
    batches = [pending[i:i+4] for i in range(0, len(pending), 4)]
    if limit:
        batches = batches[:limit]
    from openai import OpenAI
    local = threading.local(); clients = []; lock = threading.Lock(); stop = threading.Event(); run_id = uuid.uuid4().hex[:10]
    def process(batch):
        if not hasattr(local, 'client'):
            local.client = OpenAI(api_key=key, timeout=180, max_retries=0)
            with lock:
                clients.append(local.client)
        client = local.client; remaining = batch
        for attempt in range(3):
            if not remaining or stop.is_set():
                return
            ids = [r['id'] for r in remaining]
            content = []
            for r in remaining:
                payload = {k: r[k] for k in ['id', 'title', 'unit_id', 'page', 'posted_date', 'table_lines', 'privacy_context_omitted', 'comparison_scope']}
                payload['body'] = [{k: b[k] for k in ['id', 'page', 'text']} for b in r['body']]
                payload['validation_notice'] = '원문 그대로 짧게 인용하고 모든 id를 한 번 반환한다.' if attempt else ''
                content.append(dict(type='input_text', text=json.dumps(payload, ensure_ascii=False)))
                content.append(dict(type='input_image', image_url='data:image/png;base64,'+base64.b64encode((OUT/r['image_path']).read_bytes()).decode('ascii'), detail='high'))
            request = dict(model=model, instructions=review.INSTRUCTIONS, input=[dict(role='user', content=content)],
                text={'format': dict(type='json_schema', name='table_body_comparison', strict=True, schema=review.schema(ids))}, truncation='disabled')
            call_name = f'{run_id}.{review.digest("|".join(ids))[:16]}.{attempt}.json'
            path = OUT/'calls'/call_name
            call = dict(ids=ids, stage=stage, model=model, attempt=attempt, request_attempted=False,
                        input_tokens=None, usage=None, status='STARTED', errors=[])
            started = time.monotonic()
            try:
                call['input_tokens'] = client.responses.input_tokens.count(**request).input_tokens
                if call['input_tokens'] > protocol['input_token_limit']:
                    call['status'] = 'SPLIT_INPUT_LIMIT'; write(path, call)
                    if len(remaining) > 1:
                        middle = len(remaining)//2; process(remaining[:middle]); process(remaining[middle:])
                    else:
                        write(result_path(remaining[0]['id']), review.hold(remaining[0], 'CODE_INPUT_LIMIT_HOLD', '필요 근거 묶음이 입력 한도를 넘어 조건·예외를 자르지 않고 보류했다.'))
                    return
                call['request_attempted'] = True; write(path, call)
                response = client.responses.create(**request, store=False, max_output_tokens=7000, reasoning={'effort': 'low'})
                call['usage'] = response.usage.model_dump() if response.usage else None
                if response.status != 'completed':
                    raise ValueError('INCOMPLETE_OUTPUT')
                if private(response.output_text):
                    raise ValueError('PRIVATE_OUTPUT')
                items = json.loads(response.output_text)['items']
                if len(items) != len(ids) or {r['id'] for r in items} != set(ids):
                    raise ValueError('OUTPUT_ID_COVERAGE')
                proposed = {r['id']: r for r in items}; failed = []
                for record in remaining:
                    try:
                        checked = review.validate(review.Comparison.model_validate(proposed[record['id']]), record, PRIVATE)
                        checked.update(model=model, call_record=call_name)
                        write(result_path(record['id']), checked)
                    except (ValueError, KeyError, TypeError) as error:
                        code = str(error) if type(error) is ValueError and re.fullmatch('[A-Z_]+', str(error)) else 'SCHEMA_REJECTED'
                        call['errors'].append(dict(id=record['id'], code=code)); failed.append(record)
                call['proposals'] = items; remaining = failed; call['status'] = 'PARTIAL_RETRY' if failed else 'VALIDATED'
            except Exception as error:
                http_status = getattr(error, 'status_code', None)
                code = str(error) if type(error) is ValueError and re.fullmatch('[A-Z_]+', str(error)) else type(error).__name__
                detail = dict(code=code, http_status=http_status)
                for name in ['code', 'param']:
                    value = getattr(error, name, None)
                    if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.\[\]-]{1,100}', value):
                        detail['api_'+name] = value
                call['status'] = 'FAILED'; call['errors'].append(detail)
                if http_status in {401, 402, 403} or (http_status == 429 and getattr(error, 'code', None) == 'insufficient_quota'):
                    stop.set()
            call['seconds'] = round(time.monotonic()-started, 2); write(path, call)
            if remaining and not stop.is_set():
                time.sleep(2*(attempt+1))
        for record in remaining:
            if not stop.is_set():
                method = 'CODE_REJECTED_PROPOSALS_HOLD' if call.get('proposals') else 'CODE_API_FAILURE_HOLD'
                write(result_path(record['id']), review.hold(record, method, '의미 비교 응답 또는 원문 인용·수치·형식 검사가 완료되지 않아 근거 확인 대상으로 보류했다.'))
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(process, batch) for batch in batches]
            for future in as_completed(futures):
                future.result()
                with lock:
                    print(json.dumps(status()), flush=True)
    finally:
        for client in clients:
            client.close()
    if stop.is_set():
        raise SystemExit('MODEL_ACCESS_OR_QUOTA_BLOCKED; safe checkpoints retained.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('command', choices=['prepare', 'run', 'status'])
    parser.add_argument('--stage', choices=['priority_172', 'remaining_745'], default='priority_172')
    parser.add_argument('--workers', type=int, default=4); parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    elif args.command == 'run':
        run(args.stage, args.workers, args.limit)
    else:
        print(json.dumps(status()))
