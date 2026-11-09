"""Versioned local organization of all 10,205 source chunks; no re-embedding or DB writes."""
from __future__ import annotations

import os
for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '2'
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import uuid

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server import domain_workflow as domain, hr_evidence, hr_source_scope as scope
from scripts.reclassify_hr_review import configured, readl, write as atomic_write, writel

OUT = scope.WORKSPACE/'outputs/klink_domain_workflow_20261109'
PREVIOUS_TAXONOMY = scope.WORKSPACE/'outputs/kepco_domains_20261026/data/taxonomy.json'
CACHE = {}


def write(path, value):
    # Windows readers/sync clients can briefly hold a file open during replace.
    # Retry the local write, never regenerate a model answer for a file lock.
    for attempt in range(8):
        try:
            return atomic_write(path, value)
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(.1*(attempt+1))


def result_path(pid):
    return OUT/'proposals'/f'{domain.digest(pid)}.json'


def hold(piece, method, reason):
    return dict(id=piece['id'], status='REVIEW_REQUIRED', proposed_status='REVIEW_REQUIRED',
                assignments=[], reason=reason, source_text_sha256=piece['text_sha256'],
                method=method, human_approved=False, classification_grants_answer_use=False,
                ktcs_applicable=False, unit_record_id=piece['unit_record_id'], source_range=piece['source_range'])


def prepare():
    if (OUT/'protocol.json').exists():
        raise SystemExit('Frozen cohort exists; resume without overwriting it.')
    os.environ['KLINK_HR_SOURCE_SCOPE'] = 'expanded'
    manifest = scope.load(scope.INPUTS['reviewed_units'])
    documents = {d['unit_id']: d for d in readl(scope.INPUTS['documents'])}
    origins = {d['unit_id']: d for d in readl(scope.INPUTS['normalized_documents'])}
    if len(documents) != 203:
        raise ValueError('SOURCE_DOCUMENT_COUNT')
    for uid, doc in documents.items():
        origin = origins[uid]
        if (scope.file_sha(Path(origin['original_local_path'])) != doc['source_file_sha256']
                or doc['source_file_sha256'] != origin['unit_file_sha256']
                or scope.file_sha(scope.NORMALIZED/f'{uid}.txt') != doc['normalized_source_sha256']
                or doc['normalized_source_sha256'] != origin['normalized_text_sha256']):
            raise ValueError('ORIGINAL_DOCUMENT_HASH')
    tax = domain.taxonomy(json.loads(PREVIOUS_TAXONOMY.read_text(encoding='utf-8-sig')))
    entries = {r['id']: r for r in manifest['units']}
    windows = []
    for i, w in enumerate(readl(scope.INPUTS['windows'])):
        windows.append({k: w[k] for k in ['id', 'unit_record_id', 'unit_id', 'start', 'end', 'text_sha256', 'source_file_sha256']} | {'vector_row': i})
    window_counts = Counter(w['unit_record_id'] for w in windows)
    units = []; pieces = []; seen = set(); privacy = 0; short = 0
    for row in readl(scope.INPUTS['reviewed_units']):
        if row['id'] in seen or domain.digest(row['text']) != row['text_sha256']:
            raise ValueError('DUPLICATE_OR_CHANGED_SOURCE_UNIT')
        seen.add(row['id'])
        if row['source_file_sha256'] != documents[row['unit_id']]['source_file_sha256']:
            raise ValueError('UNIT_DOCUMENT_PROVENANCE')
        blocked = bool(hr_evidence.PRIVATE.search(unicodedata.normalize('NFKC', row['text'] + row['document_title'] + row['heading_path'])))
        meta = {k: row[k] for k in ['id', 'unit_id', 'document_title', 'heading_path', 'parent_id', 'parent_range', 'kind', 'text_sha256', 'source_file_sha256', 'file_version_key']}
        meta.update(text=None if blocked else row['text'], privacy_hold=blocked,
                    source_characters=len(row['text']), existing_search_windows=window_counts[row['id']],
                    previous_searchable=row['searchable'], service_answer_eligible=entries.get(row['id'], {}).get('answer_eligible', False))
        if blocked:
            privacy += 1
            for field in ('document_title', 'heading_path'):
                if hr_evidence.PRIVATE.search(unicodedata.normalize('NFKC', meta[field])):
                    meta[field] = '개인정보 패턴 검토 보류'
        units.append(meta)
        if blocked:
            continue
        for a, b in domain.split_ranges(row['text']):
            text = row['text'][a:b]
            piece = dict(id=f"{row['id']}:{a}:{b}", unit_record_id=row['id'], document_title=row['document_title'],
                         heading_path=row['heading_path'], source_range=[a, b], text=text, text_sha256=domain.digest(text),
                         before=row['text'][max(0, a-180):a], after=row['text'][b:b+180])
            pieces.append(piece)
            if len(''.join(text.split())) < 8:
                write(result_path(piece['id']), hold(piece, 'CODE_SHORT_STRUCTURE_HOLD', '짧은 표제·구조 단편은 업무를 확정하지 않고 원문 위치와 함께 보존한다.'))
                short += 1
    if len(units) != 10205 or len(windows) != 8511 or not {w['unit_record_id'] for w in windows} <= seen:
        raise ValueError('FROZEN_FULL_CORPUS_COVERAGE')
    batches = []; batch = []; chars = 0
    for piece in pieces:
        if result_path(piece['id']).exists():
            continue
        if batch and (chars+len(piece['text']) > 24000 or len(batch) >= 32):
            batches.append(batch); batch = []; chars = 0
        batch.append(piece['id']); chars += len(piece['text'])
    if batch:
        batches.append(batch)
    writel(OUT/'data/units.jsonl', units); writel(OUT/'data/pieces.jsonl', pieces); writel(OUT/'data/windows.jsonl', windows)
    write(OUT/'taxonomy.json', tax); write(OUT/'batches.json', batches)
    _, model = configured()
    baseline_files = dict(scope.INPUTS) | dict(previous_manifest=scope.MANIFEST,
        previous_domain_summary=scope.WORKSPACE/'outputs/klink_hr_reclassification_20261108/summary.json',
        previous_domain_index=scope.WORKSPACE/'outputs/klink_hr_reclassification_20261108/domain-review-search.sqlite3',
        gold=scope.WORKSPACE/'outputs/kepco_hr_gold_960_20261102/data/golden_set.jsonl', previous_taxonomy=PREVIOUS_TAXONOMY)
    protocol = dict(schema='klink-domain-workflow-20261109-v1', model=model, company='KEPCO',
        source_units=len(units), existing_search_windows=len(windows), source_documents=len(documents),
        pieces=len(pieces), short_structure_holds=short, privacy_pattern_hold_units=privacy,
        original_user_domains=5, original_user_workflows=34, domains=len(tax['domains']), workflows=len(tax['tasks']), batches=len(batches),
        instructions_sha256=domain.digest(domain.INSTRUCTIONS), taxonomy_sha256=scope.file_sha(OUT/'taxonomy.json'),
        cohort_sha256={name: scope.file_sha(OUT/'data'/f'{name}.jsonl') for name in ['units', 'pieces', 'windows']},
        baseline_sha256={str(path.relative_to(scope.WORKSPACE)): scope.file_sha(path) for path in baseline_files.values()},
        base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
        source_versions_and_originals_preserved=True, document_embeddings_changed=False,
        employee_profiles_sent=False, gold_used_for_classification=False, answer_eligibility_changed=False,
        supabase_ingestion='HOLD', external_database_writes=0, human_approved=False, ktcs_applicable=False)
    write(OUT/'protocol.json', protocol)
    implementation = OUT/'implementation'; implementation.mkdir(exist_ok=True)
    for path in (Path(__file__), REPO/'server/domain_workflow.py'):
        shutil.copy2(path, implementation/path.name)
    print(json.dumps({k: protocol[k] for k in ['source_units', 'existing_search_windows', 'source_documents', 'pieces', 'short_structure_holds', 'privacy_pattern_hold_units', 'domains', 'workflows', 'batches', 'model']}))


def context():
    protocol = json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
    if (protocol['instructions_sha256'] != domain.digest(domain.INSTRUCTIONS)
            or scope.file_sha(OUT/'taxonomy.json') != protocol['taxonomy_sha256']):
        raise ValueError('FROZEN_PROTOCOL_CHANGED')
    for name, expected in protocol['cohort_sha256'].items():
        if scope.file_sha(OUT/'data'/f'{name}.jsonl') != expected:
            raise ValueError('COHORT_CHANGED')
    pieces = {p['id']: p for p in readl(OUT/'data/pieces.jsonl')}
    tax = json.loads((OUT/'taxonomy.json').read_text(encoding='utf-8'))
    return protocol, pieces, tax, {t['code']: t for t in tax['tasks']}


def status():
    protocol = json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
    for path in (OUT/'proposals').glob('*.json'):
        if path.name not in CACHE:
            CACHE[path.name] = json.loads(path.read_text(encoding='utf-8'))['status']
    result = dict(completed_pieces=len(CACHE), total_pieces=protocol['pieces'],
                  piece_proposal_statuses=dict(Counter(CACHE.values())), complete=len(CACHE) == protocol['pieces'])
    write(OUT/'progress.json', result)
    return result


def run(workers, limit):
    protocol, pieces, tax, tasks = context(); key, model = configured()
    if model != protocol['model']:
        raise ValueError('FROZEN_MODEL_CHANGED')
    pending = [[pieces[pid] for pid in ids if not result_path(pid).exists()]
               for ids in json.loads((OUT/'batches.json').read_text(encoding='utf-8'))]
    pending = [b for b in pending if b]
    if limit:
        pending = pending[:limit]
    run_id = uuid.uuid4().hex[:12]; stop = threading.Event(); local = threading.local(); clients = []; lock = threading.Lock()
    from openai import OpenAI

    def process(batch):
        remaining = list(batch)
        if not hasattr(local, 'client'):
            local.client = OpenAI(api_key=key, timeout=150, max_retries=0)
            with lock:
                clients.append(local.client)
        client = local.client
        for attempt in range(3):
            if not remaining or stop.is_set():
                return
            ids = [p['id'] for p in remaining]
            request = dict(model=model, instructions=domain.INSTRUCTIONS,
                input=json.dumps(dict(taxonomy=[dict(code=t['code'], name=t['name']) for t in tax['tasks']],
                    pieces=[{k: p[k] for k in ['id', 'document_title', 'heading_path', 'text', 'before', 'after']} for p in remaining],
                    validation_notice='인용은 text에서 짧은 연속 구간을 그대로 복사하고 내부 인사와 외부 업체 인력을 구분한다.' if attempt else ''), ensure_ascii=False),
                text={'format': dict(type='json_schema', name='domain_workflow_classification', strict=True, schema=domain.schema(ids, tasks))},
                truncation='disabled')
            fingerprint = domain.digest(json.dumps(request, ensure_ascii=False, sort_keys=True))
            record_name = f'{fingerprint}.{run_id}.{attempt}.json'; path = OUT/'calls'/record_name
            call = dict(ids=ids, model=model, run_id=run_id, attempt=attempt, input_tokens=None,
                        request_attempted=False, usage=None, status='STARTED', errors=[])
            started = time.monotonic()
            try:
                call['input_tokens'] = client.responses.input_tokens.count(**request).input_tokens
                if call['input_tokens'] > 20000:
                    if len(remaining) == 1:
                        raise ValueError('SINGLE_PIECE_INPUT_LIMIT')
                    call['status'] = 'SPLIT_INPUT_LIMIT'; write(path, call)
                    middle = len(remaining)//2; process(remaining[:middle]); process(remaining[middle:]); return
                call['request_attempted'] = True; write(path, call)
                response = client.responses.create(**request, store=False, max_output_tokens=9000, reasoning={'effort': 'low'})
                call['usage'] = response.usage.model_dump() if response.usage else None
                if response.status != 'completed':
                    raise ValueError('INCOMPLETE_OUTPUT')
                if hr_evidence.PRIVATE.search(unicodedata.normalize('NFKC', response.output_text)):
                    raise ValueError('PRIVATE_OUTPUT')
                items = json.loads(response.output_text)['items']
                if len(items) != len(ids) or {r['id'] for r in items} != set(ids):
                    raise ValueError('OUTPUT_ID_COVERAGE')
                byid = {r['id']: r for r in items}; failed = []
                for piece in remaining:
                    try:
                        checked = domain.validate(domain.Finding.model_validate(byid[piece['id']]), piece, tasks, hr_evidence.PRIVATE)
                        checked.update(unit_record_id=piece['unit_record_id'], source_range=piece['source_range'],
                                       model=model, call_record=record_name, attempt=attempt)
                        write(result_path(piece['id']), checked)
                    except (ValueError, KeyError, TypeError) as error:
                        code = str(error) if type(error) is ValueError and str(error).replace('_', '').isupper() else 'SCHEMA_REJECTED'
                        call['errors'].append(dict(id=piece['id'], code=code)); failed.append(piece)
                call['proposals'] = items; remaining = failed
                call['status'] = 'PARTIAL_RETRY' if failed else 'VALIDATED'
            except Exception as error:
                http_status = getattr(error, 'status_code', None)
                code = str(error) if type(error) is ValueError and str(error).replace('_', '').isupper() else type(error).__name__
                call['status'] = 'FAILED'; call['errors'].append(dict(code=code, http_status=http_status))
                if http_status in {401, 402, 403} or (http_status == 429 and getattr(error, 'code', None) == 'insufficient_quota'):
                    stop.set()
            call['seconds'] = round(time.monotonic()-started, 2); write(path, call)
            if call['errors'] and call['errors'][-1]['code'] == 'INCOMPLETE_OUTPUT' and len(remaining) > 1:
                middle = len(remaining)//2; process(remaining[:middle]); process(remaining[middle:]); return
            if remaining and not stop.is_set():
                time.sleep(min(2*(attempt+1), 6))
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(process, b) for b in pending]
            for future in as_completed(futures):
                future.result()
                try:
                    progress = status()
                except (OSError, ValueError) as error:
                    progress = dict(progress_refresh_pending=True, error_type=type(error).__name__)
                print(json.dumps(progress), flush=True)
    finally:
        for client in clients:
            client.close()
    if stop.is_set():
        raise SystemExit('MODEL_ACCESS_OR_QUOTA_BLOCKED; safe records retained, no credentials printed.')


def quarantine():
    protocol, pieces, _, _ = context()
    calls = [(p, json.loads(p.read_text(encoding='utf-8'))) for p in (OUT/'calls').glob('*.json')]
    records = []
    for piece in pieces.values():
        if result_path(piece['id']).exists():
            continue
        attempted = [(p, c) for p, c in calls if piece['id'] in c['ids']]
        proposals = [(p, c) for p, c in attempted if any(r.get('id') == piece['id'] for r in c.get('proposals', []))]
        if len(proposals) < 3:
            raise ValueError('UNREVIEWED_PIECE_REQUIRES_RESUME')
        if any(e.get('http_status') in {401, 402, 403, 429} for _, c in attempted for e in c.get('errors', [])):
            raise ValueError('ACCESS_OR_RATE_FAILURE_REQUIRES_RESUME')
        result = hold(piece, 'CODE_HOLD_AFTER_REJECTED_GPT_PROPOSALS', '지정 모델의 재검토 제안이 인용·업무·적용 대상 검사를 통과하지 못해 판단 보류한다.')
        result.update(model=protocol['model'], failed_proposal_calls=[p.name for p, _ in proposals])
        write(result_path(piece['id']), result); records.append(piece['id'])
    write(OUT/'failed-proposal-holds.json', dict(pieces=records, new_model_calls=0, human_approved=False))
    print(json.dumps(dict(held=len(records))))


def finalize():
    if (OUT/'summary.json').exists() or (OUT/'by-domain').exists():
        raise SystemExit('Preserve the published or interrupted version before rebuilding.')
    protocol, pieces, tax, tasks = context()
    missing = [pid for pid in pieces if not result_path(pid).exists()]
    if missing:
        raise SystemExit(f'No final publication: {len(missing)} source pieces pending.')
    findings = {}; parts = defaultdict(list)
    for pid, piece in pieces.items():
        saved = json.loads(result_path(pid).read_text(encoding='utf-8'))
        if saved['source_text_sha256'] != piece['text_sha256']:
            raise ValueError('PROPOSAL_SOURCE_HASH')
        if saved['method'].startswith('CODE_'):
            if saved['status'] != 'REVIEW_REQUIRED' or saved['assignments']:
                raise ValueError('CODE_HOLD_CANNOT_PROMOTE')
        else:
            checked = domain.validate(domain.finding_from_saved(saved), piece, tasks, hr_evidence.PRIVATE)
            if checked['status'] != saved['status'] or checked['assignments'] != saved['assignments']:
                raise ValueError('PROPOSAL_REVALIDATION')
        findings[pid] = saved; parts[piece['unit_record_id']].append(piece)
    overrides = []
    if (OUT/'source-review-overrides.jsonl').is_file():
        for override in readl(OUT/'source-review-overrides.jsonl'):
            pid = override['piece_id']; piece = pieces[pid]; saved = findings[pid]
            if (scope.file_sha(result_path(pid)) != override['expected_original_proposal_sha256']
                    or piece['text_sha256'] != override['source_text_sha256']):
                raise ValueError('SOURCE_COMPARISON_VERSION_MISMATCH')
            checked = domain.validate(domain.finding_from_saved(override['reviewed_finding']), piece, tasks, hr_evidence.PRIVATE)
            findings[pid] = saved | checked | dict(method='TARGETED_GPT_SOURCE_COMPARISON_WITH_CODE_CHECKS_NOT_HUMAN_APPROVAL')
            overrides.append(dict(piece_id=pid, original_paths=[a['code'] for a in saved['assignments']],
                                  revised_paths=[a['code'] for a in checked['assignments']], human_approved=False))
    writel(OUT/'applied-source-review-overrides.jsonl', overrides)
    units = list(readl(OUT/'data/units.jsonl')); records = []; units_by_id = {}; memberships = []
    documents = {r['unit_id']: r for r in readl(scope.INPUTS['documents'])}
    mappings = {r['id']: r for r in readl(OUT/'source-mapping-checks.jsonl')}
    if set(mappings) != {u['id'] for u in units} or any(
            not mappings[u['id']]['mapping_verified'] or mappings[u['id']]['text_sha256'] != u['text_sha256'] for u in units):
        raise ValueError('FULL_ORIGINAL_MAPPING_NOT_VERIFIED')
    for unit in units:
        uid = unit['id']; group = sorted(parts[uid], key=lambda p: p['source_range'][0])
        if unit['privacy_hold']:
            result = dict(status='PRIVACY_HOLD', primary_path=None, primary_domain=None, direct_paths=[], assignments=[], multi_domain=False)
        else:
            end = 0
            for piece in group:
                a, b = piece['source_range']
                if a != end or unit['text'][a:b] != piece['text']:
                    raise ValueError('UNIT_PARTITION_COVERAGE')
                end = b
            if end != len(unit['text']) or domain.digest(unit['text']) != unit['text_sha256']:
                raise ValueError('UNIT_SOURCE_COVERAGE')
            result = domain.aggregate(group, findings)
        record = unit | result | dict(company='KEPCO', source_mapping_verified=True, human_approved=False, ktcs_applicable=False,
                    classification_grants_answer_use=False, source_piece_ids=[p['id'] for p in group])
        document = documents[unit['unit_id']]
        record.update(source_url=document['source_url'], original_download_url=document['original_download_url'],
                      source_format=document['format'], effective_status=document['effective_status'], posted_date=document['posted_date'])
        records.append(record); units_by_id[uid] = record
        for link in record['assignments']:
            memberships.append(dict(unit_record_id=uid, domain=link['code'].split('.')[0], workflow=link['code'],
                                    primary=link['code'] == record['primary_path'], supports=link['supports']))
    window_records = []
    for window in readl(OUT/'data/windows.jsonl'):
        unit = units_by_id[window['unit_record_id']]
        if unit['privacy_hold']:
            result = dict(status='PRIVACY_HOLD', primary_path=None, primary_domain=None, direct_paths=[], assignments=[], multi_domain=False)
        else:
            if domain.digest(unit['text'][window['start']:window['end']]) != window['text_sha256']:
                raise ValueError('WINDOW_SOURCE_HASH')
            result = domain.aggregate(parts[unit['id']], findings, [window['start'], window['end']])
        window_records.append(window | result | dict(company='KEPCO', classification_grants_answer_use=False,
            file_version_key=unit['file_version_key'], source_mapping_verified=True, ktcs_applicable=False,
            service_answer_eligible=unit['service_answer_eligible'], privacy_hold=unit['privacy_hold'], human_approved=False))
    if len(records) != 10205 or len({r['id'] for r in records}) != 10205 or len(window_records) != 8511:
        raise ValueError('FINAL_COVERAGE')
    writel(OUT/'unit-classification.jsonl', ({k: v for k, v in r.items() if k != 'text'} for r in records))
    writel(OUT/'window-classification.jsonl', window_records); writel(OUT/'workflow-memberships.jsonl', memberships)
    with ExitStack() as stack:
        handles = {}
        def emit(record, kind):
            code = record['primary_path']
            parent, child = domain.folder_components(code, record['status'], tasks)
            folder = OUT/'by-domain'/parent/child
            key = (str(folder), kind)
            if key not in handles:
                folder.mkdir(parents=True, exist_ok=True)
                handles[key] = stack.enter_context((folder/f'{kind}.jsonl').open('w', encoding='utf-8'))
            handles[key].write(json.dumps(record, ensure_ascii=False)+'\n')
        for record in records:
            emit(record, 'units')
        for record in window_records:
            emit(record, 'windows')
    source_hashes_unchanged = all(scope.file_sha(scope.WORKSPACE/relative) == sha for relative, sha in protocol['baseline_sha256'].items())
    if not source_hashes_unchanged:
        raise ValueError('BASELINE_CHANGED')
    calls = [json.loads(p.read_text(encoding='utf-8')) for p in (OUT/'calls').glob('*.json')]
    if (OUT/'source-review-call.json').is_file():
        calls.append(json.loads((OUT/'source-review-call.json').read_text(encoding='utf-8')))
    summary = dict(source_units=len(records), source_documents=protocol['source_documents'], existing_search_windows=len(window_records),
        primary_domain_counts=dict(Counter(r['primary_domain'] or r['status'] for r in records)),
        primary_workflow_counts=dict(Counter(r['primary_path'] or r['status'] for r in records)),
        source_status_counts=dict(Counter(r['status'] for r in records)),
        window_primary_domain_counts=dict(Counter(r['primary_domain'] or r['status'] for r in window_records)),
        window_status_counts=dict(Counter(r['status'] for r in window_records)),
        workflow_memberships=len(memberships), multi_domain_units=sum(r['multi_domain'] for r in records),
        piece_count=len(pieces), piece_method_counts=dict(Counter(r['method'] for r in findings.values())),
        source_comparison_corrections=len(overrides),
        original_user_domains=5, original_user_workflows=34, classification_domains=len(tax['domains']), workflows=len(tasks),
        previous_searchable_units=sum(r['previous_searchable'] for r in records),
        units_without_existing_vectors=sum(r['existing_search_windows'] == 0 for r in records),
        service_answer_eligible_units=sum(r['service_answer_eligible'] for r in records),
        source_hashes_unchanged=source_hashes_unchanged, full_source_coverage_verified=True,
        model=protocol['model'], retained_generation_request_attempts=sum(c['request_attempted'] for c in calls),
        completed_response_records=sum(c['status'] in {'VALIDATED', 'PARTIAL_RETRY'} for c in calls),
        request_attempts_without_usage=sum(c['request_attempted'] and c.get('usage') is None for c in calls),
        returned_usage={key: sum((c.get('usage') or {}).get(key, 0) or 0 for c in calls) for key in ['input_tokens', 'output_tokens', 'total_tokens']},
        answer_eligibility_changed=False, new_document_embeddings=0, supabase_ingestion='HOLD', external_database_writes=0,
        independent_human_approval=False, ktcs_applicable=False,
        unit_classification_sha256=scope.file_sha(OUT/'unit-classification.jsonl'),
        window_classification_sha256=scope.file_sha(OUT/'window-classification.jsonl'))
    write(OUT/'summary.json', summary)
    for path in (Path(__file__), REPO/'server/domain_workflow.py'):
        target = OUT/'final_implementation'/path.name; target.parent.mkdir(exist_ok=True)
        shutil.copy2(path, target)
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(); parser.add_argument('command', choices=['prepare', 'run', 'status', 'quarantine', 'finalize'])
    parser.add_argument('--workers', type=int, choices=[1, 2, 3, 4], default=3); parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    if args.command == 'prepare': prepare()
    elif args.command == 'run': run(args.workers, args.limit)
    elif args.command == 'status': print(json.dumps(status()))
    elif args.command == 'quarantine': quarantine()
    else: finalize()
