"""Render preserved actual before/after answers; do not turn rechecks into new calls."""
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone
import html
import json
import sys

from closeout_hr_quality import ROOT,readl,write,digest,REPO,CORPUS
from server import hr_answer,hr_evidence,hr_conditions


PICKS={'KEPCO-HR-03-003':'after-v5','KEPCO-HR-03-041':'after-v6','KEPCO-HR-04-049':'after-v4'}
NOTES={
 'KEPCO-HR-01-037':'공개채용의 가족 우대 금지와 특별채용 조문의 채용권자 금지는 구분했다. 특별채용 조문의 공개채용 적용 범위는 조직 해석을 확인해야 한다.',
 'KEPCO-HR-02-112':'질문은 재직 중 직무 수행 곤란의 해임·계약해지 비교다. 채용 전 고용결격 사유까지 설명하도록 한 자동 채점 요구는 질문 범위와 구분한다.',
 'KEPCO-HR-03-003':'실제 새 본문에서 교육·일반 휴직 및 일반 육아휴직 6개월 기준, 출산휴가 직후 육아휴직 3개월 별도 기준, 동일직급과 보충 가능을 확인했다.',
 'KEPCO-HR-03-041':'직급 상하관계의 허용 근거가 없어 예외의 포함·제외를 단정한 생성문은 차단했다. 일반 보직·전환 조문 원문은 제공하되 이 문항은 완료 판정하지 않는다.',
 'KEPCO-HR-04-049':'휴게시간 자유 이용과 질서·규율 한계, 근무시간 중 사적 이탈 금지 및 외출 목적을 함께 설명하고, 개인 용무의 외부 출입을 단정하지 않았다.',
}


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def esc(value):return html.escape(str(value))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    cohort=readl(ROOT/'cohort.jsonl')
    allowed={s['id']:s for s in hr_evidence.corpus()[0]}
    final=ROOT/'final';final.mkdir(exist_ok=True)
    entries=[];checks=[]
    for case in cohort:
        cid=case['case_id'];stage=PICKS.get(cid,'after-v3')
        before=load(ROOT/'baseline/answers'/f'{cid}.json')
        record=load(ROOT/stage/'answers'/f'{cid}.json');response=record.get('response') or {}
        recheck=dict(source_ids_allowed=all(s['id'] in allowed and s['sha256']==allowed[s['id']]['sha256'] for s in response.get('sources',[])),
            designated_sources_retrieved=set(case['designated_ids'])<=set(s['id'] for s in response.get('sources',[])),
            paragraphs=len(response.get('paragraphs',[])),quotes_exact=True,condition_offsets_exact=True,final_code_recheck=False)
        for paragraph in response.get('paragraphs',[]):
            for c in paragraph['citations']:
                recheck['quotes_exact'] &= c['source_id'] in allowed and c['quote'] in allowed[c['source_id']]['text']
        for c in response.get('source_conditions',[]):
            recheck['condition_offsets_exact'] &= c['source_id'] in allowed and allowed[c['source_id']]['text'][c['start']:c['end']]==c['quote']
        if response.get('paragraphs'):
            draft=hr_answer.Draft(**{k:deepcopy(response[k]) for k in ['status','paragraphs','missing_information']})
            try:
                hr_answer.validate(draft,response['sources'],case['question'])
                recheck['final_code_recheck']=True
            except hr_answer.AnswerUnavailable as error:
                recheck['safe_recheck_reason']=str(error)
        path=ROOT/stage/'source-prose-review'/f'{cid}.json'
        judgment=load(path) if path.exists() else None
        scope_review=cid in {'KEPCO-HR-01-037','KEPCO-HR-03-041'}
        entry=dict(case_id=cid,question=case['question'],selected_actual_generation_stage=stage,
            original_generation_sha256=digest(ROOT/stage/'answers'/f'{cid}.json'),
            same_model_raw_judgment=judgment.get('verdict') if judgment else 'not_reviewed',
            source_comparison_status='SOURCE_SCOPE_REVIEW_REQUIRED' if scope_review else 'QUESTION_RELEVANT_SOURCE_COMPARISON_PERFORMED',
            source_comparison_note=NOTES.get(cid,'질문에 필요한 대상·조건·예외·원문 근거를 본문 및 보존 원문과 대조했다.'),
            automatic_checks=recheck,human_approved=False)
        write(final/'answers'/f'{cid}.json',dict(**record,selected_actual_generation_stage=stage,final_recheck=entry))
        entries.append(entry);checks.append(recheck)
        def body(rec):
            result=rec.get('response') or {}
            paragraphs=''.join('<p>'+esc(p['text'])+'</p>' for p in result.get('paragraphs',[]))
            missing=''.join('<li>'+esc(t)+'</li>' for t in result.get('missing_information',[]))
            return (paragraphs or '<p>검증을 통과한 생성문이 없어 답변을 표시하지 않았습니다. 아래 원문을 확인하세요.</p>')+'<ul>'+missing+'</ul>'
        # Every displayed quotation is still linked to the real, preserved source.
        proofs=''.join('<details><summary>'+esc(s['title']+' / '+s['section'])+'</summary><pre>'+esc(s['text'])+'</pre></details>' for s in response.get('sources',[]))
        entry['_html']='<article id="'+cid+'"><h2>'+esc(cid+' '+case['question'])+'</h2><p>'+esc(entry['source_comparison_note'])+'</p><div class="comparison"><section><h3>수정 전 실제 답변</h3>'+body(before)+'</section><section><h3>수정 후 실제 답변 · '+esc(stage)+'</h3>'+body(record)+'</section></div><details><summary>대조한 원문</summary>'+proofs+'</details></article>'
    raw=Counter(e['same_model_raw_judgment'] for e in entries)
    baseline=Counter(load(p)['verdict'] for p in (ROOT/'baseline/source-prose-review').glob('KEPCO*.json'))
    regression=Counter(load(p)['verdict'] for p in (ROOT/'after-v4/regression-prose-review').glob('KEPCO*.json'))
    summary=dict(created_at=datetime.now(timezone.utc).isoformat(),target_cases=len(entries),
        actual_new_responses_with_prose=sum(c['paragraphs']>0 for c in checks),
        original_22_baseline_raw_auto_judgments=dict(baseline),final_selected_raw_auto_judgments=dict(raw),
        previous_40_regression_raw_auto_judgments=dict(regression),
        source_scope_review_required=[e['case_id'] for e in entries if e['source_comparison_status']=='SOURCE_SCOPE_REVIEW_REQUIRED'],
        live_target_all_designated_retrieved=sum(c['designated_sources_retrieved'] for c in checks),
        source_quote_checks_passed=all(c['source_ids_allowed'] and c['quotes_exact'] and c['condition_offsets_exact'] for c in checks),
        final_code_rechecked_prose=sum(c['final_code_recheck'] for c in checks),
        final_code_files={n:digest(REPO/'server'/n) for n in ['hr_answer.py','hr_evidence.py','hr_vectors.py','hr_conditions.py']},
        final_records_are_preserved_real_generation_plus_code_recheck=True,uniform_single_fresh_experiment=False,
        selection='Latest documented correction per case; all earlier attempts kept. No source-card replay counted as a new model response.',
        full_543_or_960_semantic_evaluation=False,independent_human_approval=False,
        source_currentness_verified=False,ktcs_applicable=False,supabase_ingestion='HOLD_USER_REQUESTED',production_ready=False)
    write(final/'summary.json',summary)
    write(final/'case-audit.json',[{k:v for k,v in e.items() if k!='_html'} for e in entries])
    markup='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>한전 인사 답변 22문항 수정 전후</title><style>body{max-width:1300px;margin:auto;padding:24px;font:16px/1.7 system-ui;color:#223544;background:#f5f7fa}article{background:white;border:1px solid #d9e0e7;padding:24px;margin:24px 0;border-radius:12px}h1{font-size:28px}h2{font-size:19px}.comparison{display:grid;grid-template-columns:1fr 1fr;gap:24px}section{min-width:0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.8 system-ui;background:#f0f3f6;padding:16px}summary{cursor:pointer}a{color:#15567e}@media(max-width:800px){.comparison{grid-template-columns:1fr}body{padding:12px}article{padding:16px}}</style><h1>한전 인사 답변 22문항 · 실제 응답 수정 전후</h1><p>KEPCO 공개 대체자료로 실제 생성한 답변을 보존했습니다. KTcs 사규 적용·직원 자격·사람 승인·완전 정확성 보증은 아닙니다. Supabase 적재는 보류합니다.</p><p>동일 설정 GPT의 자동 채점과 원문 대조 기록을 구분했습니다. 자동 채점이 질문 밖 설명을 요구하거나 규정 해석을 단정한 사례도 원시 결과 그대로 남겼습니다. 01-037과 03-041은 규정 적용 범위 확인을 남깁니다.</p>'''
    markup+='<nav>'+''.join('<a href="#'+e['case_id']+'">'+esc(e['case_id'][-6:])+'</a> · ' for e in entries)+'</nav>'
    markup+=''.join(e['_html'] for e in entries)+'</html>'
    (ROOT/'comparison.html').write_text(markup,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
