"""Versioned KEPCO expansion evaluation. Original gold/index files stay read-only.

Precomputed gold-query vectors are used ONLY here, for offline evaluation. They
are never connected to live retrieval, source classification or answer prompts.
"""
from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time

import numpy as np

REPO=Path(__file__).resolve().parents[1]
WORKSPACE=REPO.parent
ROOT=WORKSPACE/'outputs/klink_hr_corpus_expansion_20261107'
EVAL=ROOT/'evaluation'
GOLD=WORKSPACE/'outputs/kepco_hr_gold_960_20261102/data/golden_set.jsonl'
MAPPING=WORKSPACE/'outputs/kepco_hr_full_eval_960_20261102/data/gold_map.jsonl'
INDEX=WORKSPACE/'outputs/kepco_hr_full_eval_960_20261102/indexes'
CORPUS=WORKSPACE/'outputs/kepco_hr_full_20261102/data/reviewed_units.jsonl'
sys.path.insert(0,str(REPO))
os.environ['KLINK_ENV_FILE']=str(WORKSPACE/'.env')
os.environ['KLINK_LOCAL_REVIEWED_UNITS']=str(CORPUS)
os.environ['KLINK_HR_RETRIEVAL']='hybrid'
from server import hr_answer,hr_evidence,hr_vectors,benefit_explanation
from hr_source_audit import sha
from expand_hr_sources import write,writel,readl


def frozen(name):
    alias='server.expansion_frozen_'+name
    spec=importlib.util.spec_from_file_location(alias,ROOT/'baseline_code'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);sys.modules[alias]=module;spec.loader.exec_module(module)
    return module


def retrieve(stage):
    if stage=='core':evidence=frozen('hr_evidence')
    elif stage=='eligible':
        evidence=hr_evidence
        stat=CORPUS.stat()
        corpus=evidence._load(str(CORPUS),stat.st_mtime_ns,stat.st_size,'expanded',('',0,0))
        evidence.corpus=lambda:corpus
    elif stage.startswith('expanded'):evidence=hr_evidence
    else:raise ValueError('Unknown stage')
    gold=readl(GOLD);mapping={m['case_id']:m for m in readl(MAPPING)}
    meta=json.loads((INDEX/'queries_vectors.json').read_text(encoding='utf-8'))
    # Exact question ordering/text, model identity and frozen array hashes are
    # checked before the evaluator can bypass live query encoding.
    if (meta.get('model')!=hr_vectors.MODEL or meta.get('revision')!=hr_vectors.REVISION or
        meta.get('weights_sha256')!=hr_vectors.WEIGHTS or meta.get('ids')!=[g['case_id'] for g in gold] or
        meta.get('questions')!=[g['question'] for g in gold] or meta.get('golden_set_sha256')!=sha(GOLD) or
        meta.get('question_sha256')!=[hashlib.sha256(g['question'].encode()).hexdigest() for g in gold] or
        meta.get('truncation') is not False or meta.get('normalized') is not True or
        meta.get('vectors_sha256')!=sha(INDEX/'queries.npy')):raise ValueError('EVAL_QUERY_VECTOR_IDENTITY')
    protocol=json.loads((ROOT/'baseline-protocol.json').read_text(encoding='utf-8'))
    if sha(GOLD)!=protocol['gold_sha256'] or sha(CORPUS)!=protocol['source_sha256']:raise ValueError('EVAL_SOURCE_IDENTITY')
    queries=np.load(INDEX/'queries.npy',allow_pickle=False)
    if (queries.shape!=(960,1024) or queries.dtype!=np.float32 or not np.isfinite(queries).all()
        or np.max(np.abs(np.linalg.norm(queries,axis=1)-1))>1e-4):raise ValueError('EVAL_QUERY_SHAPE')
    rows=evidence.corpus()[0];allowed={r['id'] for r in rows}
    index=hr_vectors.VectorIndex(rows,CORPUS)
    out=[];started=time.monotonic()
    for g,query in zip(gold,queries):
        required=set(mapping[g['case_id']]['mapped_unit_ids'])
        eligible=bool(required) and mapping[g['case_id']]['all_gold_source_present'] and required<=allowed
        lexical=evidence.lexical_search(g['question'])
        is_hr=evidence.is_hr_question(g['question']) if hasattr(evidence,'is_hr_question') else bool(evidence.HR_TERMS.search(g['question']))
        if evidence.PRIVATE.search(g['question']) or not is_hr:ids=[]
        else:
            dense=index.score(query)
            query_rows=[r for r in rows if not hasattr(evidence,'query_source_allowed') or evidence.query_source_allowed(g['question'],r)]
            allowed_for_query={r['id'] for r in query_rows}
            dense={rid:value for rid,value in dense.items() if rid in allowed_for_query}
            fused=hr_vectors.fuse([r['id'] for r in lexical],dense)
            ids=evidence.select_facets(g['question'],sorted(fused,key=lambda rid:(-fused[rid],rid)),query_rows)[:5]
        out.append(dict(case_id=g['case_id'],task_code=g['task_code'],fully_inside_runtime=bool(eligible),
            designated_ids=sorted(required),retrieved_ids=ids,all_at_3=bool(required) and required<=set(ids[:3]),
            all_at_5=bool(required) and required<=set(ids),any_at_5=bool(required&set(ids))))
        if len(out)%160==0:print(json.dumps(dict(stage=stage,queries=len(out),total=960)),flush=True)
    inside=[r for r in out if r['fully_inside_runtime']]
    summary=dict(total=960,fully_inside_runtime=len(inside),out_of_runtime=960-len(inside),
        source_units=len(rows),document_versions=len({r['version'] for r in rows}),document_titles=len({r['title'] for r in rows}),
        reused_document_vectors=len(index.ids),new_document_embeddings=0,
        metrics={k:dict(numerator=sum(r[k] for r in inside),denominator=len(inside)) for k in ['all_at_3','all_at_5','any_at_5']},
        seconds=round(time.monotonic()-started,2),gold_sha256=sha(GOLD),source_sha256=sha(CORPUS),
        query_vectors_sha256=sha(INDEX/'queries.npy'),code_sha256=sha(ROOT/'baseline_code/hr_evidence.py' if stage=='core' else REPO/'server/hr_evidence.py'),
        query_vectors_evaluation_only=True,answer_semantic_accuracy=False,human_approved=False)
    writel(EVAL/stage/'retrieval.jsonl',out);write(EVAL/stage/'retrieval-summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


def prepare_regression():
    path=EVAL/'regression-cohort.jsonl'
    if path.exists():raise SystemExit('The regression cohort is already frozen.')
    old=WORKSPACE/'outputs/klink_hr_quality_closeout_20261107'
    cases={c['case_id']:c for p in ['previous_40_cohort.jsonl','cohort.jsonl'] for c in readl(old/p)}
    core={r['id'] for r in frozen('hr_evidence').corpus()[0]}
    gold={r['case_id']:r for r in readl(GOLD)}
    mapping={r['case_id']:r for r in readl(MAPPING)}
    stat=CORPUS.stat()
    existing={r['id']:r for r in hr_evidence._load(str(CORPUS),stat.st_mtime_ns,stat.st_size,'expanded',('',0,0))[0]}
    for cid,m in mapping.items():
        ids=set(m['mapped_unit_ids'])
        if ids and m['all_gold_source_present'] and ids<=existing.keys() and ids-core:
            g=gold[cid]
            cases[cid]=dict(case_id=cid,question=g['question'],task_code=g['task_code'],task_name=g['task_name'],
                designated_ids=m['mapped_unit_ids'],designated_full_sources=[existing[i] for i in m['mapped_unit_ids']],
                required_points=['질문에 필요한 조건·예외·적용대상·의무와 재량·참조 조문을 원문 전체와 대조한다.'],
                original_evidence=g['evidence'],purpose='previously_missing_153',human_approved=False)
    # Checklist wording is an evaluation aid, never an answer or retrieval input.
    for c in cases.values():
        if c.get('purpose')!='previously_missing_153':c['purpose']='preserved_regression'
    writel(path,sorted(cases.values(),key=lambda c:c['case_id']))
    write(EVAL/'regression-protocol.json',dict(created_at=datetime.now(timezone.utc).isoformat(),
        cohort_sha256=sha(path),cases=len(cases),by_purpose=dict(Counter(c['purpose'] for c in cases.values())),
        frozen_before_new_generation=True,source_sha256=sha(CORPUS),gold_sha256=sha(GOLD),human_approved=False))
    print(json.dumps(dict(cases=len(cases),cohort=str(path)),ensure_ascii=False))


def generate(stage,cohort,workers):
    cases=readl(cohort)
    current=threading.local()
    original_validate=hr_answer.validate
    def capture(draft,sources,*args,**kwargs):
        try:return original_validate(draft,sources,*args,**kwargs)
        except hr_answer.AnswerUnavailable as error:
            safe=draft.model_dump()
            if not hr_evidence.PRIVATE.search(json.dumps(safe,ensure_ascii=False)):
                current.validation_errors.append(dict(code=error.code,safe_reason=str(error),
                    details=getattr(error,'repair_details',None),draft=safe,source_ids=[s['id'] for s in sources]))
            raise
    hr_answer.validate=capture
    if stage=='eligible':
        stat=CORPUS.stat();corpus=hr_evidence._load(str(CORPUS),stat.st_mtime_ns,stat.st_size,'expanded',('',0,0))
        hr_evidence.corpus=lambda:corpus
    # Warm and verify the exact allowed source/vector connection before workers.
    index=hr_vectors.get_index(hr_evidence.corpus()[0],CORPUS)
    run_protocol=dict(model=benefit_explanation.settings()[1],
        cohort_sha256=sha(cohort),cases=len(cases),source_units=index.source_count,vector_windows=len(index.ids),
        answer_code_sha256=sha(REPO/'server/hr_answer.py'),evidence_code_sha256=sha(REPO/'server/hr_evidence.py'),
        overlay_sha256=sha(ROOT/'review-overlay.json') if (ROOT/'review-overlay.json').exists() else None,
        actual_fresh_generation=True,provider_store=False,no_employee_data=True,supabase_ingestion='HOLD')
    run_path=EVAL/stage/'generation-runs'/(run_protocol['cohort_sha256'][:16]+'-'+run_protocol['answer_code_sha256'][:12]+'.json')
    write(run_path,run_protocol)
    if not (EVAL/stage/'generation-protocol.json').exists():write(EVAL/stage/'generation-protocol.json',run_protocol)
    def one(case):
        path=EVAL/stage/'answers'/(case['case_id']+'.json')
        if path.exists():return None
        start=time.monotonic()
        current.validation_errors=[]
        try:
            response=hr_answer.generate(case['question'])
            record=dict(case_id=case['case_id'],question=case['question'],purpose=case['purpose'],response=response,error=None)
        except hr_answer.AnswerUnavailable as error:
            record=dict(case_id=case['case_id'],question=case['question'],purpose=case['purpose'],response=None,
                error=dict(code=error.code,safe_message=str(error)))
        record['seconds']=round(time.monotonic()-start,2)
        record.update(run_protocol_sha256=sha(run_path),answer_code_sha256=run_protocol['answer_code_sha256'],cohort_sha256=run_protocol['cohort_sha256'])
        write(path,record)
        if current.validation_errors:write(EVAL/stage/'validation-errors-local-only'/(case['case_id']+'.json'),
            dict(case_id=case['case_id'],not_user_visible=True,errors=current.validation_errors))
        return dict(case_id=case['case_id'],paragraphs=len((record['response'] or {}).get('paragraphs',[])),error=bool(record['error']),seconds=record['seconds'])
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(one,c) for c in cases]):
            result=future.result()
            if result:print(json.dumps(result),flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['retrieve','prepare-regression','generate','judge'])
    parser.add_argument('--stage',default='expanded',choices=['core','eligible','expanded','expanded-v2','expanded-v3'])
    parser.add_argument('--cohort',type=Path,default=EVAL/'regression-cohort.jsonl')
    parser.add_argument('--workers',type=int,default=3,choices=[1,2,3,4])
    parser.add_argument('--follow',action='store_true')
    args=parser.parse_args()
    if args.command=='retrieve':retrieve(args.stage)
    elif args.command=='prepare-regression':prepare_regression()
    elif args.command=='generate':generate(args.stage,args.cohort,args.workers)
    else:
        import judge_hr_quality as judge
        judge.ROOT=EVAL
        judge.INSTRUCTIONS+=' 원문과 대조하되 질문 밖 항목을 강제하지 마라. omissions의 인용은 원문의 연속 문자열만 써라. missing_information의 잘못된 주장도 대조하라. unsupported_claims.answer_claim은 후보에 실제 있는 연속 문자열을 그대로 복사하고 말줄임표나 의역을 쓰지 마라. source_role/source_context/section은 실제 원문 대조로 확인한 메타데이터다. 첨부 계약서 견본이라는 메타데이터가 있으면 계약서 출처임을 인정하되 실제 모든 직원의 계약조건으로 확대하지 마라.'
        expected={c['case_id'] for c in readl(args.cohort)}
        deadline=time.monotonic()+7200
        while True:
            judge.review(args.stage,args.workers,'source-prose-review',args.cohort,check_all_visible_fields=True)
            done={p.stem for p in (EVAL/args.stage/'source-prose-review').glob('*.json')}
            if not args.follow or expected<=done:break
            if time.monotonic()>deadline:raise SystemExit('Answer-review deadline; checkpoints preserved.')
            time.sleep(5)
