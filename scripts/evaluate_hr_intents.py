"""Separate, source-grounded paraphrase check. No source/index/gold/database writes."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

# Keep this isolated evaluator small even on machines with a large CPU count.
os.environ['OPENBLAS_NUM_THREADS']='2'
os.environ['OMP_NUM_THREADS']='2'
os.environ['MKL_NUM_THREADS']='2'

import evaluate_hr_quality as shared

ROOT=shared.WORKSPACE/'outputs/klink_hr_semantic_intents_20261107'
write,readl,digest=shared.write,shared.readl,shared.digest
os.environ['KLINK_HR_RETRIEVAL']='hybrid'

GROUPS=[
 ('payday','regular_payday','연봉및복리후생관리규정',(17,0),[
  '월급은 매달 며칠 들어오나요?','급여 입금일이 궁금해요.','회사에서 주는 돈이 통장에 들어오는 날은 언제예요?']),
 ('annual_period','annual_leave_period','취업규칙',(29,0),[
  '연차휴가 계산기간은 언제부터 언제까지인가요?','연차를 세는 한 해의 시작과 끝이 궁금해요.','유급으로 쉬는 연차의 산정기간은 입사일을 기준으로 잡나요?']),
 ('sick_leave','sick_leave','취업규칙',(30,2),[
  '병가를 쓸 수 있는 사유와 기간은 어떻게 되나요?','아파서 일을 못 하거나 전염 우려가 있으면 며칠까지 쉴 수 있나요?','질병 때문에 일하기 어려울 때 쓸 수 있는 휴가의 조건과 한도는?']),
 ('resignation','resignation_procedure','취업규칙',(59,0),[
  '자진 퇴사하려면 사직원만 내면 되나요?','회사를 그만두겠다고 말하면 절차가 끝나나요?','사표를 제출한 다음에 별도 수속이나 승인이 필요한가요?']),
 ('work_break','work_break','취업규칙',(20,0),[
  '통상근무자의 휴게시간을 업무 사정으로 바꿀 수 있나요?','일 때문에 점심 쉬는 시간을 다른 때로 옮겨도 되나요?','일반 직원의 점심시간을 회사 사정에 맞춰 조정해도 되나요?']),
 ('vacancy','vacancy_fill','인사관리규정',(20,0),[
  '장기 교육이나 육아휴직으로 자리가 비면 정원과 별도로 결원을 보충할 수 있나요?',
  '긴 교육을 가거나 육아휴직으로 오래 비울 때 같은 직급 사람을 추가로 둘 수 있나요?',
  '장기간 교육·육아휴직자의 빈자리에 사람을 채워도 되는 기준을 알려주세요.']),
 ('renewal','contract_renewal','비정규직관리규정',(11,0),[
  '비정규직 계약이 끝난 뒤 4개월 후 재계약하면 재고용 판단에서 공백을 어떻게 보나요?',
  '기간제 직원이 계약 만료 후 네 달 쉬었다가 다시 계약하면 재고용 판단에서 그 공백은 어떻게 계산하나요?',
  '계약직이 종료 후 4개월 뒤 재계약할 때 재계약 판단에서 그 사이도 계속근무로 보나요?']),
 ('retirement','retirement_benefit','취업규칙',(64,0),[
  '공사 직원이 만 1년을 채우기 전에 그만두면 퇴직금을 지급하나요?',
  '공사에 입사하고 12개월을 못 채운 채 퇴사하면 퇴직금 대상인가요?',
  '공사 직원이 1년 미만 일하고 퇴직하면 퇴직금을 받을 수 있나요?']),
]
COUNTERS=[
 ('salary_period','salary_period','급여 계산기간은 언제부터 언제까지인가요?','ready'),
 ('retirement_date','retirement_benefit','퇴직금은 언제 지급받나요?','ready'),
 ('annual_days','annual_leave_entitlement','연차는 며칠 생기나요?','ready'),
 ('leave_permission','leave_permission','연차를 사용한 다음에 허가받아도 되나요?','ready'),
 ('contract_sick','sick_leave','계약직 직원의 업무상 부상 병가는 며칠까지 가능한가요?','ready'),
 ('regular_sick','sick_leave','정규직 직원의 일반 질병 병가는 며칠까지 가능한가요?','ready'),
 ('childcare','childcare_leave','육아휴직을 쓸 수 있는 자녀 나이와 휴직기간은?','ready'),
 ('retirement_over','retirement_benefit','공사 직원이 1년 이상 근무하고 퇴직하면 퇴직금을 지급하나요?','ready'),
 ('ambiguous',None,'그거 언제 돼요?','needs_clarification'),
 ('outside',None,'파이썬으로 게임을 만들어줘','out_of_scope'),
]
HELDOUT_QUESTIONS={
 'payday':'달마다 회사에서 받는 봉급, 받는 날짜가 언제야?',
 'annual_period':'연차를 집계하는 1년은 어느 날 시작해서 어느 날 끝나?',
 'sick_leave':'몸이 아파 출근이 어렵거나 남한테 옮길 염려가 있으면 쉴 수 있는 제도랑 최대 기간은?',
 'resignation':'사표 한 장 써서 내면 퇴사가 다 처리되는 거야?',
 'work_break':'근무표상 점심때 일이 몰려서 쉬는 시간대를 늦추고 싶어. 규정상 돼?',
 'vacancy':'긴 연수와 육아휴직 때문에 비어 있는 직위를 별도 정원으로 메울 수 있는 요건은?',
 'renewal':'기간제 재계약 심사에서 앞 계약이 끝난 뒤 넉 달의 공백을 근무기간으로 칠 수 있어?',
 'retirement':'입사한 지 열한 달밖에 안 된 공사 직원이 퇴사하면 퇴직금 조건을 충족하나요?',
}


def holdout():
    if (ROOT/'heldout.jsonl').exists():raise SystemExit('Held-out wording already frozen.')
    original={c['group']:c for c in readl(ROOT/'cohort.jsonl') if c['kind']=='equivalent'}
    cases=[]
    for group,q in HELDOUT_QUESTIONS.items():
        base=original[group]
        cases.append(base|dict(id=group+'-heldout',question=q,kind='heldout_equivalent'))
    shared.writel(ROOT/'heldout.jsonl',cases)
    write(ROOT/'heldout-protocol.json',dict(questions=len(cases),created_after_development=True,
        wording_not_in_model_prompt=True,source_documents_shared_with_development=True,
        cohort_sha256=digest(ROOT/'heldout.jsonl'),implementation_sha256=digest(shared.REPO/'server/hr_intent.py'),
        independent_human_approval=False))
    print(json.dumps(dict(heldout_questions=len(cases))))


def contrasts():
    from server import hr_evidence
    path=ROOT/'contrasts.jsonl'
    if path.exists():raise SystemExit('Condition contrasts already frozen.')
    rows=hr_evidence.corpus()[0]
    definitions=[
        ('regular_injury','sick_leave','취업규칙',(30,2),'정규직 직원의 업무상 부상 병가는 며칠까지 가능한가요?'),
        ('vacancy_without_maternity','vacancy_fill','인사관리규정',(20,0),'출산휴가에 이어 사용하지 않는 일반 육아휴직을 3개월 쓰는 경우, 정원 밖 결원을 보충할 수 있나요?'),
        ('vacancy_after_maternity','vacancy_fill','인사관리규정',(20,0),'출산전후휴가에 이어 취업규칙 제51조 제7호의 육아휴직을 3개월 쓰면 정원 외 결원 보충이 가능한가요?'),
    ]
    result=[]
    for cid,intent,title,key,q in definitions:
        matches=[r for r in rows if hr_evidence.title_key(r['title'])==title and hr_evidence.article_key(hr_evidence.section_heading(r['section']))==key]
        assert len(matches)==1
        result.append(dict(id=cid,group=cid,question=q,expected_intent=intent,expected_status='ready',
            expected_sources=[matches[0]['id']],kind='condition_contrast',source_comparison_human_approved=False))
    shared.writel(path,result)
    write(ROOT/'contrasts-protocol.json',dict(questions=len(result),cohort_sha256=digest(path),
        implementation_sha256=digest(shared.REPO/'server/hr_intent.py'),independently_human_approved=False))
    print(json.dumps(dict(condition_contrasts=len(result))))


def prepare():
    from server import hr_evidence,benefit_explanation
    if (ROOT/'protocol.json').exists():raise SystemExit('Frozen protocol already exists.')
    rows=hr_evidence.corpus()[0]
    cases=[]
    for group,intent,title,key,questions in GROUPS:
        matches=[r for r in rows if hr_evidence.title_key(r['title'])==title and hr_evidence.article_key(hr_evidence.section_heading(r['section']))==key]
        assert len(matches)==1,(title,key)
        for i,q in enumerate(questions,1):
            cases.append(dict(id=f'{group}-{i}',group=group,question=q,expected_intent=intent,expected_status='ready',
                expected_sources=[matches[0]['id']],kind='equivalent',source_comparison_human_approved=False))
    cases += [dict(id=name,group=name,question=q,expected_intent=intent,expected_status=status,
        expected_sources=[],kind='different_or_ambiguous',source_comparison_human_approved=False) for name,intent,q,status in COUNTERS]
    shared.writel(ROOT/'cohort.jsonl',cases)
    for name in ['hr_evidence','hr_answer']:
        folder=ROOT/'baseline_code';folder.mkdir(exist_ok=True)
        shutil.copy2(shared.REPO/'server'/f'{name}.py',folder/f'{name}.py')
    key,model=benefit_explanation.settings()
    write(ROOT/'protocol.json',dict(branch=subprocess.check_output(['git','branch','--show-current'],cwd=shared.REPO,text=True).strip(),
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=shared.REPO,text=True).strip(),
        source_sha256=digest(shared.CORPUS),gold_960_sha256=digest(shared.GOLD),
        vector_sha256=digest(shared.WORKSPACE/'outputs/kepco_hr_full_eval_960_20261102/indexes/windows.npy'),
        cohort_sha256=digest(ROOT/'cohort.jsonl'),model=model,credential_configured=bool(key),
        equivalent_questions=24,groups=8,counter_questions=10,source_units=len(rows),
        official_gold_modified=False,independently_human_approved=False,supabase_ingestion='HOLD_USER_REQUESTED',
        acceptance='Meaning group and source/conclusion consistency, not identical generated wording. Do not merge changed employee kind, number, negation, or business purpose.'))
    print(json.dumps(dict(cases=len(cases),equivalent=24,counters=10,model=model,source_units=len(rows))))


def baseline(heldout=False):
    name='heldout-summary' if heldout else 'summary'
    if (ROOT/f'baseline/{name}.json').exists():raise SystemExit('Baseline is frozen; do not overwrite.')
    from server import hr_evidence
    rows=readl(ROOT/('heldout.jsonl' if heldout else 'cohort.jsonl'));results=[]
    for c in rows:
        if not c['expected_sources']:continue
        hits=hr_evidence.search(c['question'],5)
        results.append(dict(id=c['id'],question=c['question'],source_ids=[s['id'] for s in hits],
            primary_source=hits[0]['id'] if hits else None,expected_at5=set(c['expected_sources'])<=set(s['id'] for s in hits)))
    shared.writel(ROOT/('baseline/heldout-retrieval.jsonl' if heldout else 'baseline/retrieval.jsonl'),results)
    result=dict(questions=len(results),all_at5=sum(r['expected_at5'] for r in results),
        missing=[r['id'] for r in results if not r['expected_at5']],llm_calls=0,document_embeddings=0)
    write(ROOT/f'baseline/{name}.json',result);print(json.dumps(result))


def snapshot(stage):
    names=['hr_intent','hr_evidence','hr_answer','hr_vectors','hr_conditions','benefit_explanation']
    files={name:digest(shared.REPO/'server'/f'{name}.py') for name in names}
    path=ROOT/stage/'implementation.json'
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8'))['files']!=files:
            raise SystemExit('Implementation changed; use a new --stage instead of mixing results.')
        return
    folder=ROOT/stage/'implementation';folder.mkdir(parents=True,exist_ok=True)
    for name in names:shutil.copy2(shared.REPO/'server'/f'{name}.py',folder/f'{name}.py')
    write(path,dict(files=files,model=json.loads((ROOT/'protocol.json').read_text(encoding='utf-8'))['model'],
        source_sha256=digest(shared.CORPUS),cohort_sha256=digest(ROOT/'cohort.jsonl')))


def analyze(workers,stage,heldout=False,contrast=False):
    from server import hr_intent,hr_evidence
    snapshot(stage)
    def one(case):
        path=ROOT/stage/'analysis'/f"{case['id']}.json"
        if path.exists():return
        start=time.monotonic()
        try:
            plan=hr_intent.understand(case['question'])
            hits=hr_evidence.search(case['question'],5,semantic_plan=plan) if plan.proposal.status=='ready' else []
            result=dict(id=case['id'],question=case['question'],understanding=plan.metadata(),
                proposal=plan.proposal.model_dump(),canonical_query=plan.canonical_query,provider_call=plan.call,
                expected_intent=case['expected_intent'],status_correct=plan.proposal.status==case['expected_status'],
                intent_correct=case['expected_intent'] is None or case['expected_intent'] in plan.proposal.intents,
                source_ids=[s['id'] for s in hits],primary_source=hits[0]['id'] if hits else None,
                expected_at5=not case['expected_sources'] or set(case['expected_sources'])<=set(s['id'] for s in hits),error=None)
        except hr_intent.IntentUnavailable as error:
            result=dict(id=case['id'],question=case['question'],error=dict(code=error.code,safe_message=str(error)))
        result['seconds']=round(time.monotonic()-start,2)
        write(path,result)
        return {k:result.get(k) for k in ['id','status_correct','intent_correct','expected_at5','error','seconds']}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for f in as_completed([pool.submit(one,c) for c in readl(ROOT/('contrasts.jsonl' if contrast else 'heldout.jsonl' if heldout else 'cohort.jsonl'))]):
            if result:=f.result():print(json.dumps(result,ensure_ascii=False),flush=True)


def answers(workers,ids,stage,heldout=False,contrast=False):
    from server import hr_answer
    snapshot(stage)
    os.environ['KLINK_HR_INTENT_MODE']='llm'
    cohort=[c for c in readl(ROOT/('contrasts.jsonl' if contrast else 'heldout.jsonl' if heldout else 'cohort.jsonl')) if c['id'] in ids]
    def one(c):
        path=ROOT/stage/'answers'/f"{c['id']}.json"
        if path.exists():return
        started=time.monotonic()
        try:response,error=hr_answer.generate(c['question']),None
        except hr_answer.AnswerUnavailable as e:response,error=None,dict(code=e.code,safe_message=str(e))
        record=dict(id=c['id'],question=c['question'],response=response,error=error,seconds=round(time.monotonic()-started,2),
            actual_configured_model_response=True,independent_human_approval=False)
        write(path,record)
        return dict(id=c['id'],status=(response or {}).get('status'),paragraphs=len((response or {}).get('paragraphs',[])),error=error,seconds=record['seconds'])
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for f in as_completed([pool.submit(one,c) for c in cohort]):
            if result:=f.result():print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','baseline','analyze','answers','snapshot','holdout','contrasts'])
    p.add_argument('--workers',type=int,default=3,choices=[1,2,3]);p.add_argument('--cases',nargs='*',default=[])
    p.add_argument('--stage',default='after')
    p.add_argument('--heldout',action='store_true')
    p.add_argument('--contrast',action='store_true')
    args=p.parse_args()
    if args.command=='prepare':prepare()
    elif args.command=='holdout':holdout()
    elif args.command=='contrasts':contrasts()
    elif args.command=='baseline':baseline(args.heldout)
    elif args.command=='analyze':analyze(args.workers,args.stage,args.heldout,args.contrast)
    elif args.command=='snapshot':snapshot(args.stage)
    else:answers(args.workers,args.cases,args.stage,args.heldout,args.contrast)
