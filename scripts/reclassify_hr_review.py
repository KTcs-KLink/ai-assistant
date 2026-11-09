"""Fresh, checkpointed domain review of the frozen 7,235 windows. No external DB writes."""
from __future__ import annotations

import os
os.environ['OPENBLAS_NUM_THREADS']='2'
os.environ['OMP_NUM_THREADS']='2'
os.environ['MKL_NUM_THREADS']='2'
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import uuid

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from server import benefit_explanation,hr_evidence,hr_source_scope as scope,hr_domain_reclassification as domain

OUT=scope.WORKSPACE/'outputs/klink_hr_reclassification_20261108'
LOCK=threading.Lock()
PROGRESS_CACHE={}


def readl(path):
    with path.open(encoding='utf-8') as f:
        for line in f:
            if line.strip():yield json.loads(line)


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(f'.{path.name}.{os.getpid()}.{threading.get_ident()}.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)


def writel(path,records):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8') as f:
        for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')


def configured():
    os.environ['KLINK_ENV_FILE']=str(scope.WORKSPACE/'.env')
    key,model=benefit_explanation.settings()
    if not key or not model:raise RuntimeError('CONFIGURATION_REQUIRED')
    return key,model


def prepare():
    if (OUT/'protocol.json').exists():raise SystemExit('Frozen cohort exists; use run/finalize without overwriting it.')
    os.environ['KLINK_HR_SOURCE_SCOPE']='expanded'
    manifest=scope.load(scope.INPUTS['reviewed_units'])
    held={e['id'] for e in manifest['units'] if e['structural_verified'] and not e['answer_eligible']}
    units=[];pieces=[];target_ids=set()
    for row in readl(scope.INPUTS['reviewed_units']):
        if row['id'] not in held or row.get('decision')!='REVIEW_REQUIRED':continue
        if scope.text_sha(row['text'])!=row['text_sha256'] or hr_evidence.PRIVATE.search(unicodedata.normalize('NFKC',row['text'])):
            raise ValueError('SOURCE_OR_PRIVACY_CHECK')
        target_ids.add(row['id'])
        units.append({k:row[k] for k in ['id','unit_id','document_title','heading_path','text','text_sha256','source_file_sha256','file_version_key','kind']})
        for start,end in domain.split_ranges(row['text']):
            text=row['text'][start:end]
            pieces.append(dict(id=f"{row['id']}:{start}:{end}",unit_record_id=row['id'],document_title=row['document_title'],
                heading_path=row['heading_path'],source_range=[start,end],text=text,text_sha256=scope.text_sha(text),
                before=row['text'][max(0,start-180):start],after=row['text'][end:end+180]))
    windows=[w for w in readl(scope.INPUTS['windows']) if w['unit_record_id'] in target_ids]
    if len(units)!=3014 or len(windows)!=7235:raise ValueError('FROZEN_TARGET_CHANGED')
    batches=[];current=[];chars=0
    for p in pieces:
        if current and (chars+len(p['text'])>24000 or len(current)>=32):batches.append(current);current=[];chars=0
        current.append(p['id']);chars+=len(p['text'])
    if current:batches.append(current)
    OUT.mkdir(parents=True,exist_ok=True)
    writel(OUT/'data/units.jsonl',units);writel(OUT/'data/pieces.jsonl',pieces);writel(OUT/'data/windows.jsonl',windows)
    write(OUT/'batches.json',batches)
    _,model=configured()
    protocol=dict(version='klink-domain-reclassification-v1',company='KEPCO',target_windows=len(windows),target_units=len(units),
        pieces=len(pieces),batches=len(batches),model=model,instructions_sha256=domain.digest(domain.INSTRUCTIONS),
        source_inputs=manifest['inputs'],previous_manifest_sha256=scope.file_sha(scope.MANIFEST),
        cohort_sha256={name:scope.file_sha(OUT/'data'/f'{name}.jsonl') for name in ['units','pieces','windows']},
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        source_meaning_scope='fresh piece review projected to existing retrieval windows; complete source coverage without overlap',
        gold_used_for_classification=False,employee_profiles_sent=False,answer_eligibility_changed=False,
        document_embeddings_changed=False,supabase_ingestion='HOLD',human_approved=False,ktcs_applicable=False)
    write(OUT/'protocol.json',protocol)
    (OUT/'implementation').mkdir(exist_ok=True)
    shutil.copy2(Path(__file__),OUT/'implementation/reclassify_hr_review.py')
    shutil.copy2(REPO/'server/hr_domain_reclassification.py',OUT/'implementation/hr_domain_reclassification.py')
    print(json.dumps({k:protocol[k] for k in ['target_windows','target_units','pieces','batches','model']}))


def result_path(pid):return OUT/'proposals'/f'{domain.digest(pid)}.json'


def schema(ids):
    fields=domain.Finding.model_json_schema()
    fields['properties']['id']={'type':'string','enum':ids}
    return dict(type='object',properties={'items':dict(type='array',items=fields)},required=['items'],additionalProperties=False)


def status():
    counts=Counter();n=0
    for path in (OUT/'proposals').glob('*.json'):
        # Accepted proposal files are immutable in one run. Avoid reopening
        # thousands of small files for every batch's progress update.
        if path.name not in PROGRESS_CACHE:
            PROGRESS_CACHE[path.name]=json.loads(path.read_text(encoding='utf-8'))['label']
        counts[PROGRESS_CACHE[path.name]]+=1;n+=1
    protocol=json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
    result=dict(completed_pieces=n,total_pieces=protocol['pieces'],labels=dict(counts),complete=n==protocol['pieces'])
    write(OUT/'progress.json',result)
    return result


def run(workers,limit):
    key,model=configured();protocol=json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
    if model!=protocol['model'] or domain.digest(domain.INSTRUCTIONS)!=protocol['instructions_sha256']:raise ValueError('FROZEN_MODEL_OR_PROMPT_CHANGED')
    for name,expected in protocol['cohort_sha256'].items():
        if scope.file_sha(OUT/'data'/f'{name}.jsonl')!=expected:raise ValueError('COHORT_CHANGED')
    pieces={p['id']:p for p in readl(OUT/'data/pieces.jsonl')}
    batches=json.loads((OUT/'batches.json').read_text(encoding='utf-8'))
    pending=[[pieces[pid] for pid in ids if not result_path(pid).exists()] for ids in batches]
    pending=[p for p in pending if p]
    if limit:pending=pending[:limit]
    hard_stop=threading.Event()
    run_id=uuid.uuid4().hex[:12]
    from openai import OpenAI
    local=threading.local();clients=[]
    def client_for_thread():
        if not hasattr(local,'client'):
            local.client=OpenAI(api_key=key,timeout=150,max_retries=0)
            with LOCK:clients.append(local.client)
        return local.client
    def process(batch):
        remaining=list(batch)
        for attempt in range(3):
            if not remaining or hard_stop.is_set():return
            ids=[p['id'] for p in remaining]
            payload=dict(model=model,instructions=domain.INSTRUCTIONS,
                input=json.dumps(dict(pieces=[{k:p[k] for k in ['id','document_title','heading_path','text','before','after']} for p in remaining]),ensure_ascii=False),
                text={'format':dict(type='json_schema',name='hr_domain_reclassification',strict=True,schema=schema(ids))},truncation='disabled')
            if attempt:
                retry_input=json.loads(payload['input'])
                retry_input['code_validation_notice']='직전 원문 인용 또는 형식 검사를 통과하지 못한 id만 다시 검토한다. 인용은 text에서 연속된 짧은 구간을 문자 그대로 복사한다. 짧은 제목만으로 판단하기 어렵다면 REVIEW_REQUIRED로 보류하고 있는 원문만 인용한다.'
                payload['input']=json.dumps(retry_input,ensure_ascii=False)
            fingerprint=domain.digest(json.dumps(payload,sort_keys=True,ensure_ascii=False))
            call=dict(ids=ids,model=model,attempt=attempt,input_tokens=None,request_attempted=False,usage=None,
                status='STARTED',errors=[],human_approved=False)
            start=time.monotonic()
            try:
                client=client_for_thread()
                call['input_tokens']=client.responses.input_tokens.count(**payload).input_tokens
                if call['input_tokens']>20000:
                    if len(remaining)==1:raise ValueError('SINGLE_PIECE_INPUT_LIMIT')
                    call['status']='SPLIT_INPUT_LIMIT';write(OUT/'calls'/f'{fingerprint}.{run_id}.{attempt}.json',call)
                    middle=len(remaining)//2;process(remaining[:middle]);process(remaining[middle:]);return
                call['request_attempted']=True
                response=client.responses.create(**payload,store=False,max_output_tokens=9000,reasoning={'effort':'low'})
                call['usage']=response.usage.model_dump() if response.usage else None
                if response.status!='completed':raise ValueError('INCOMPLETE_OUTPUT')
                if hr_evidence.PRIVATE.search(unicodedata.normalize('NFKC',response.output_text)):raise ValueError('PRIVATE_OUTPUT')
                raw=json.loads(response.output_text)
                items=raw['items']
                if len(items)!=len(ids) or {i['id'] for i in items}!=set(ids):raise ValueError('OUTPUT_ID_COVERAGE')
                byid={i['id']:i for i in items};failed=[]
                for p in remaining:
                    try:
                        checked=domain.validate(domain.Finding.model_validate(byid[p['id']]),p,hr_evidence.PRIVATE)
                        checked.update(unit_record_id=p['unit_record_id'],source_range=p['source_range'],
                            model=model,call_fingerprint=fingerprint,call_record=f'{fingerprint}.{run_id}.{attempt}.json',attempt=attempt)
                        write(result_path(p['id']),checked)
                    except (ValueError,TypeError,KeyError) as error:
                        code=str(error) if type(error) is ValueError and str(error).replace('_','').isupper() else 'PROPOSAL_SCHEMA_REJECTED'
                        call['errors'].append(dict(id=p['id'],code=code));failed.append(p)
                remaining=failed;call['status']='VALIDATED' if not failed else 'PARTIAL_RETRY'
                call['proposals']=items
            except Exception as error:
                http_status=getattr(error,'status_code',None)
                code=str(error) if type(error) is ValueError and str(error).replace('_','').isupper() else type(error).__name__
                call['status']='FAILED';call['errors'].append(dict(code=code,http_status=http_status))
                if http_status in {401,403,402}:hard_stop.set()
                if http_status==429 and getattr(error,'code',None)=='insufficient_quota':hard_stop.set()
            call['seconds']=round(time.monotonic()-start,2)
            call['run_id']=run_id
            write(OUT/'calls'/f'{fingerprint}.{run_id}.{attempt}.json',call)
            if remaining and not hard_stop.is_set():time.sleep(min(2*(attempt+1),6))
        return
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(process,b) for b in pending]
        for future in as_completed(futures):
            future.result()
            with LOCK:progress=status()
            print(json.dumps(progress),flush=True)
    for client in clients:client.close()
    if hard_stop.is_set():raise SystemExit('MODEL_ACCESS_OR_QUOTA_BLOCKED; safe call records saved, no credentials printed.')


def quarantine_pending():
    """After genuine failed review attempts, retain uncertain text instead of discarding it."""
    protocol=json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
    calls=[(p,json.loads(p.read_text(encoding='utf-8'))) for p in (OUT/'calls').glob('*.json')]
    quarantined=[]
    for piece in readl(OUT/'data/pieces.jsonl'):
        if result_path(piece['id']).exists():continue
        attempts=[(p,c) for p,c in calls if c.get('request_attempted') and piece['id'] in c['ids']]
        completed_proposals=[(p,c) for p,c in attempts if any(r.get('id')==piece['id'] for r in c.get('proposals',[]))]
        if len(completed_proposals)<3:raise ValueError('UNREVIEWED_OR_CONNECTION_FAILED_PIECE_REQUIRES_RESUME')
        if any(e.get('http_status') in {401,402,403,429} for _,c in attempts for e in c.get('errors',[])):
            raise ValueError('ACCESS_OR_RATE_FAILURE_REQUIRES_RESUME')
        finding=domain.Finding(id=piece['id'],label='REVIEW_REQUIRED',actor='unspecified',
            reason='지정 모델의 재검토 결과가 원문 인용·형식 검사를 통과하지 못해 이 구간은 분리 제외하지 않고 판단 보류로 보존한다.',hr_quote='',non_hr_quote='')
        result=domain.validate(finding,piece,hr_evidence.PRIVATE)
        result.update(unit_record_id=piece['unit_record_id'],source_range=piece['source_range'],model=protocol['model'],
            method='CODE_REVIEW_HOLD_AFTER_FAILED_GPT_PROPOSALS',failed_proposal_calls=[p.name for p,_ in attempts],
            call_fingerprint=None,attempt=None)
        write(result_path(piece['id']),result);quarantined.append(piece['id'])
    write(OUT/'failed-proposal-holds.json',dict(pieces=quarantined,new_model_calls=0,human_approved=False))
    print(json.dumps(dict(quarantined_pieces=len(quarantined))))


def finalize():
    protocol=json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
    for name,expected in protocol['cohort_sha256'].items():
        if scope.file_sha(OUT/'data'/f'{name}.jsonl')!=expected:raise ValueError('COHORT_CHANGED')
    pieces={p['id']:p for p in readl(OUT/'data/pieces.jsonl')}
    proposals={pid:json.loads(result_path(pid).read_text(encoding='utf-8')) for pid in pieces if result_path(pid).exists()}
    missing=set(pieces)-set(proposals)
    if missing:raise SystemExit(f'Classification is incomplete: {len(missing)} source pieces pending. No final separation published.')
    byunit=defaultdict(list)
    for pid,p in pieces.items():
        saved=proposals[pid]
        raw={k:saved[k] for k in domain.Finding.model_fields}
        raw['label']=saved.get('proposed_label',saved['label'])
        checked=domain.validate(domain.Finding.model_validate(raw),p,hr_evidence.PRIVATE)
        if checked['label']!=saved['label'] or saved['source_text_sha256']!=p['text_sha256']:raise ValueError('PROPOSAL_REVALIDATION_FAILED')
        byunit[p['unit_record_id']].append(p)
    overrides=[]
    if (OUT/'source-review-overrides.jsonl').is_file():
        for override in readl(OUT/'source-review-overrides.jsonl'):
            pid=override['piece_id'];piece=pieces[pid];saved=proposals[pid]
            if (override['source_text_sha256']!=piece['text_sha256'] or saved['label']!=override['expected_original_label']
                    or override['finding']['label']!='REVIEW_REQUIRED'):
                raise ValueError('UNVERIFIED_OR_PROMOTING_REVIEW_OVERRIDE')
            checked=domain.validate(domain.Finding.model_validate(override['finding']),piece,hr_evidence.PRIVATE)
            proposals[pid]=saved|checked|dict(method='CODEX_SOURCE_COMPARISON_OVERRIDE_NOT_HUMAN_APPROVAL')
            overrides.append(dict(piece_id=pid,previous_label=saved['label'],label=checked['label'],reason=checked['reason'],human_approved=False))
    writel(OUT/'applied-source-review-overrides.jsonl',overrides)
    units={u['id']:u for u in readl(OUT/'data/units.jsonl')}
    unit_records=[]
    for uid,parts in byunit.items():
        parts.sort(key=lambda p:p['source_range'][0])
        expected=0
        for part in parts:
            a,b=part['source_range']
            if a!=expected or units[uid]['text'][a:b]!=part['text']:raise ValueError('SOURCE_PARTITION_COVERAGE')
            expected=b
        if expected!=len(units[uid]['text']):raise ValueError('SOURCE_PARTITION_INCOMPLETE')
        unit_records.append(dict(id=uid,document_title=units[uid]['document_title'],heading_path=units[uid]['heading_path'],
            label=domain.aggregate(proposals[p['id']]['label'] for p in parts),pieces=[p['id'] for p in parts],
            text_sha256=units[uid]['text_sha256'],human_approved=False,answer_eligible=False))
    records=[]
    for w in readl(OUT/'data/windows.jsonl'):
        uid=w['unit_record_id'];text=units[uid]['text'][w['start']:w['end']]
        if scope.text_sha(text)!=w['text_sha256']:raise ValueError('WINDOW_SOURCE_CHANGED')
        parts=[p for p in byunit[uid] if p['source_range'][0]<w['end'] and p['source_range'][1]>w['start']]
        coverage=sum(min(p['source_range'][1],w['end'])-max(p['source_range'][0],w['start']) for p in parts)
        if coverage!=w['end']-w['start']:raise ValueError('WINDOW_CLASSIFICATION_COVERAGE')
        label=domain.aggregate(proposals[p['id']]['label'] for p in parts)
        original_window=dict(w)
        previous=original_window.pop('decision',None)
        records.append(dict(**original_window,previous_domain_decision=previous,domain_label=label,source_text=text,source_piece_ids=[p['id'] for p in parts],
            source_classification_basis='complete_source_piece_review_projected_to_existing_window',
            contains_failed_proposal_hold=any(proposals[p['id']]['method']=='CODE_REVIEW_HOLD_AFTER_FAILED_GPT_PROPOSALS' for p in parts),
            company='KEPCO',human_approved=False,answer_eligible=False,ktcs_applicable=False))
    if len(records)!=7235 or len({r['id'] for r in records})!=7235:raise ValueError('WINDOW_PARTITION_TOTAL')
    for label in domain.LABELS:
        folder=OUT/'separated'/label.lower()
        writel(folder/'windows.jsonl',(r for r in records if r['domain_label']==label))
        writel(folder/'units.jsonl',(r for r in unit_records if r['label']==label))
    writel(OUT/'window-classification.jsonl',({k:v for k,v in r.items() if k!='source_text'} for r in records))
    writel(OUT/'unit-classification.jsonl',unit_records)
    calls=[json.loads(p.read_text(encoding='utf-8')) for p in (OUT/'calls').glob('*.json')]
    summary=dict(target_windows=7235,target_units=3014,reviewed_source_pieces=len(proposals),
        source_comparison_overrides=len(overrides),
        code_failed_proposal_hold_pieces=sum(r['method']=='CODE_REVIEW_HOLD_AFTER_FAILED_GPT_PROPOSALS' for r in proposals.values()),
        windows_with_failed_proposal_hold=sum(r['contains_failed_proposal_hold'] for r in records),
        window_labels=dict(Counter(r['domain_label'] for r in records)),unit_labels=dict(Counter(r['label'] for r in unit_records)),
        piece_labels=dict(Counter(r['label'] for r in proposals.values())),
        actual_generation_requests=sum(c['request_attempted'] for c in calls),
        generation_request_attempts=sum(c['request_attempted'] for c in calls),
        completed_response_records=sum(c['status'] in {'VALIDATED','PARTIAL_RETRY'} for c in calls),
        request_attempts_without_returned_usage=sum(c['request_attempted'] and c.get('usage') is None for c in calls),
        usage={key:sum((c.get('usage') or {}).get(key,0) or 0 for c in calls) for key in ['input_tokens','output_tokens','total_tokens']},
        model=protocol['model'],classification_coverage_complete=True,source_quotes_revalidated=True,
        independent_human_approval=False,answer_eligibility_changed=False,document_embeddings_changed=False,
        supabase_ingestion='HOLD',gold_used_for_classification=False,
        classification_sha256=scope.file_sha(OUT/'window-classification.jsonl'))
    write(OUT/'summary.json',summary)
    implementation=OUT/'final_implementation';implementation.mkdir(exist_ok=True)
    shutil.copy2(Path(__file__),implementation/'reclassify_hr_review.py')
    shutil.copy2(REPO/'server/hr_domain_reclassification.py',implementation/'hr_domain_reclassification.py')
    print(json.dumps(summary,ensure_ascii=True))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','status','finalize','quarantine']);p.add_argument('--workers',type=int,default=3,choices=[1,2,3,4]);p.add_argument('--limit',type=int,default=0)
    a=p.parse_args()
    if a.command=='prepare':prepare()
    elif a.command=='run':run(a.workers,a.limit)
    elif a.command=='finalize':finalize()
    elif a.command=='quarantine':quarantine_pending()
    else:print(json.dumps(status()))
