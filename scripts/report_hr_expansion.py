"""Local audit report: source coverage, retrieval and generated answers separately."""
from collections import Counter
from datetime import datetime,timezone
import argparse
import html
import json
from pathlib import Path
import sys

from evaluate_hr_expansion import ROOT,EVAL,CORPUS,GOLD,INDEX,hr_evidence,hr_vectors,benefit_explanation
from expand_hr_sources import write,readl
from hr_source_audit import sha


def main(stage):
    rows=hr_evidence.corpus()[0];allowed={r['id'] for r in rows};index=hr_vectors.get_index(rows,CORPUS)
    raw=[]
    for line in CORPUS.open(encoding='utf-8'):
        r=json.loads(line)
        if r['answer_eligible']:raw.append({k:r[k] for k in ['id','document_title','heading_path']})
    missing={r['id'] for r in raw if hr_evidence.title_key(r['document_title']) not in hr_evidence.HR_TITLES}
    review=json.loads((ROOT/'review-summary.json').read_text(encoding='utf-8'))
    original=json.loads((ROOT/'final-original-audit-summary.json').read_text(encoding='utf-8'))
    ledger=readl(ROOT/'review-final-ledger.jsonl')
    cohort=readl(EVAL/'combined-cohort.jsonl')
    cohort_ids={c['case_id'] for c in cohort}
    stages={}
    supplemental=[]
    for name in ['eligible','expanded','expanded-v2','expanded-v3']:
        path=EVAL/name
        answers={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (path/'answers').glob('*.json')}
        judgments={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (path/'source-prose-review').glob('KEPCO-*.json')}
        if not answers:continue
        stages[name]=dict(actual_requests=len(answers),automatic_reviews=len(judgments),
            main_cohort_cases=len(set(answers)&cohort_ids),supplemental_cases=len(set(answers)-cohort_ids),
            verdicts=dict(Counter(r['verdict'] for r in judgments.values())),
            actual_generation_calls=sum(len((r.get('response') or {}).get('provider_calls',[])) for r in answers.values()),
            provider_errors=sum(bool(r.get('error')) for r in answers.values()),
            cohort_sha256=json.loads((path/'generation-protocol.json').read_text(encoding='utf-8'))['cohort_sha256'])
        for cid in sorted(set(answers)-cohort_ids):
            supplemental.append(dict(case_id=cid,stage=name,verdict=judgments.get(cid,{}).get('verdict','pending'),
                actual_provider_calls=len((answers[cid].get('response') or {}).get('provider_calls',[])),
                included_in_main_133=False,human_approved=False))
    selected_answers={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (EVAL/stage/'answers').glob('*.json')}
    selected_judgments={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (EVAL/stage/'source-prose-review').glob('KEPCO-*.json')}
    cases=[]
    final_selection={r['case_id']:r for r in readl(EVAL/'final-selection.jsonl')} if (EVAL/'final-selection.jsonl').exists() else {}
    for c in cohort:
        selected=final_selection.get(c['case_id'])
        if selected:
            selected_stage=selected['stage']
            a=json.loads((EVAL/selected_stage/'answers'/(c['case_id']+'.json')).read_text(encoding='utf-8'))
            j=json.loads((EVAL/selected_stage/'source-prose-review'/(c['case_id']+'.json')).read_text(encoding='utf-8'))
        else:
            selected_stage=stage;a=selected_answers.get(c['case_id'],{});j=selected_judgments.get(c['case_id'],{})
        response=a.get('response') or {}
        sources={s['id']:s for s in response.get('sources',[])}
        evidence=[]
        seen=set()
        for paragraph in response.get('paragraphs',[]):
            for cite in paragraph.get('citations',[]):
                key=(cite['source_id'],cite['quote'])
                if key in seen:continue
                seen.add(key)
                source=sources[cite['source_id']]
                start=source['text'].find(cite['quote'])
                if start<0:raise ValueError('REPORT_CITATION_NOT_IN_ORIGINAL')
                evidence.append(dict(source_id=source['id'],title=source['title'],section=source.get('section',''),
                    quote=cite['quote'],start=start,end=start+len(cite['quote']),
                    original_text_layer_verified=source.get('original_text_layer_verified',False)))
        cases.append(dict(case_id=c['case_id'],question=c['question'],purpose=c['purpose'],
            verdict=j.get('verdict','pending'),paragraphs=[p['text'] for p in response.get('paragraphs',[])],
            missing_information=response.get('missing_information',[]),validation=response.get('validation'),
            judgment=j.get('judgment'),all_designated_currently_allowed=set(c['designated_ids'])<=allowed,
            actual_provider_calls=len(response.get('provider_calls',[])),selected_stage=selected_stage,
            source_evidence=evidence,source_conditions=response.get('source_conditions',[]),human_approved=False))
    retrieval={}
    for name in ['core','eligible','expanded','expanded-v2','expanded-v3']:
        path=EVAL/name/'retrieval-summary.json'
        if path.exists():retrieval[name]=json.loads(path.read_text(encoding='utf-8'))
    comparability={}
    base_path=EVAL/'core/retrieval.jsonl';selected_path=EVAL/stage/'retrieval.jsonl'
    if base_path.exists() and selected_path.exists():
        before={r['case_id']:r for r in readl(base_path)};after={r['case_id']:r for r in readl(selected_path)}
        old={cid for cid,r in before.items() if r['fully_inside_runtime']};new={cid for cid,r in after.items() if r['fully_inside_runtime']};common=old&new
        comparability=dict(shared_denominator=len(common),before_all_at_5=sum(before[c]['all_at_5'] for c in common),
            after_all_at_5=sum(after[c]['all_at_5'] for c in common),newly_in_scope=len(new-old),
            old_cases_now_quarantined=len(old-new),regressed_cases=[c for c in sorted(common) if before[c]['all_at_5'] and not after[c]['all_at_5']],
            improved_cases=[c for c in sorted(common) if not before[c]['all_at_5'] and after[c]['all_at_5']])
    preservation=dict(source_sha256=sha(CORPUS),gold_sha256=sha(GOLD),document_vectors_sha256=sha(INDEX/'windows.npy'))
    baseline=json.loads((ROOT/'baseline-protocol.json').read_text(encoding='utf-8'))
    preservation['all_baselines_unchanged']=all(preservation[k]==baseline[k] for k in ['source_sha256','gold_sha256']) and preservation['document_vectors_sha256']==baseline['vector_sha256']
    if not preservation['all_baselines_unchanged']:raise ValueError('BASELINE_CHANGED')
    result=dict(created_at=datetime.now(timezone.utc).isoformat(),stage=stage,source_summary=hr_evidence.summary(),
        connected_source_units=len(rows),reused_vector_windows=len(index.ids),new_document_embeddings=0,
        missing_153_connected=len(missing&allowed),missing_153_held=len(missing-allowed),
        original_core_connected=sum(r['id'] in allowed for r in raw if r['id'] not in missing),
        original_source_holds=[r for r in raw if r['id'] not in allowed],review=review,original=original,
        frozen_answer_cases=len(cohort),stages=stages,retrieval=retrieval,shared_retrieval=comparability,
        final_validation=json.loads((EVAL/'final-validation.json').read_text(encoding='utf-8')),
        supplemental_answer_checks=supplemental,
        answer_cases=cases,preservation=preservation,generation_model=benefit_explanation.settings()[1],
        selected_final_verdicts=dict(Counter(r['verdict'] for r in cases)),
        human_approved=False,independent_human_semantic_review=False,ktcs_applicable=False,supabase_ingestion='HOLD',pr_created=False)
    write(ROOT/'result-summary.json',result)
    esc=lambda value:html.escape(str(value))
    source_table=''.join(f'<tr><td>{esc(label)}</td><td>{count:,}</td></tr>' for label,count in [
        ('기존 449개 중 유지',result['original_core_connected']),('기존 449개 중 원문 문제로 보류',449-result['original_core_connected']),
        ('누락 153개 중 현재 사용',result['missing_153_connected']),
        ('누락 153개 중 원문 문제로 보류',result['missing_153_held']),('대기 3,268개 중 새로 사용',review['new_answer_source_units']),
        ('대기 중 인사 범위 밖으로 분류',review['status_counts']['RESOLVED_NON_HR']),
        ('대기 중 미해결·보류',3268-review['new_answer_source_units']-review['status_counts']['RESOLVED_NON_HR']),
        ('기존 602개 중 재점검 후 보류',review['previously_eligible_quarantined']),('현재 사용 원문 구간',len(rows)),('연결한 기존 벡터',len(index.ids))])
    retrieval_table=''.join(f"<tr><td>{esc(name)}</td><td>{r['source_units']}</td><td>{r['fully_inside_runtime']}/960</td><td>{r['metrics']['all_at_5']['numerator']}/{r['metrics']['all_at_5']['denominator']}</td></tr>" for name,r in retrieval.items())
    answer_table=''.join(f"<tr><td>{esc(name)}</td><td>{s['actual_requests']}</td><td>{s['verdicts'].get('complete',0)}</td><td>{s['verdicts'].get('incomplete',0)}</td><td>{s['verdicts'].get('incorrect',0)}</td><td>{s['verdicts'].get('withheld',0)}</td><td>{s['verdicts'].get('judge_error',0)+s['verdicts'].get('provider_error',0)}</td></tr>" for name,s in stages.items())
    final_counts=result['selected_final_verdicts']
    answer_table+=f"<tr><th>최신 재검증 결과 조합</th><th>{len(cases)}</th><th>{final_counts.get('complete',0)}</th><th>{final_counts.get('incomplete',0)}</th><th>{final_counts.get('incorrect',0)}</th><th>{final_counts.get('withheld',0)}</th><th>{final_counts.get('judge_error',0)}</th></tr>"
    case_cards=[]
    for c in cases:
        detail=''.join('<p>'+esc(p)+'</p>' for p in c['paragraphs'])
        detail+=''.join('<p class="muted">확인 필요: '+esc(p)+'</p>' for p in c['missing_information'])
        j=c.get('judgment') or {}
        if j:detail+='<p class="muted">자동 대조 이유: '+esc(j.get('rationale',''))+'</p>'
        for source in c['source_evidence']:
            detail+=f"<p><b>대조 원문: {esc(source['title'])}</b><br>{esc(source['section'])}<br><small>{esc(source['source_id'])} · 문자 위치 {source['start']}–{source['end']}</small></p><blockquote>{esc(source['quote'])}</blockquote>"
        case_cards.append(f"<details data-verdict='{esc(c['verdict'])}'><summary><b>{esc(c['case_id'])}</b> · {esc(c['verdict'])} · {esc(c['question'])}</summary>{detail}</details>")
    ledger_rows=''.join(f"<tr data-ledger='{esc(r['status'])}'><td>{esc(r['document_id'])}</td><td>{esc(r['title'])}</td><td>{esc(r['section'])}</td><td>{esc(r['status'])}</td><td>{esc(', '.join(r['reasons']))}</td></tr>" for r in ledger)
    page=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>K:LINK 한전 인사 자료 연결·답변 검증</title>
<style>body{{font:16px/1.65 system-ui,sans-serif;color:#152238;background:#f5f7fb;margin:0}}main{{max-width:1180px;margin:40px auto;padding:0 24px}}h1{{font-size:30px}}h2{{margin-top:36px}}section,.notice{{background:white;border:1px solid #dce3ec;border-radius:14px;padding:24px;margin:20px 0}}.notice{{border-left:5px solid #7159c1}}.muted{{color:#526176}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #e5eaf0;vertical-align:top}}.scroll{{overflow:auto}}details{{padding:14px;border-bottom:1px solid #dce3ec}}summary{{cursor:pointer}}blockquote{{white-space:pre-wrap;border-left:3px solid #b8c5da;margin:12px 0;padding:8px 16px;background:#f5f7fb}}select,input{{font:inherit;padding:8px;margin:4px 8px 14px 0}}code,small{{overflow-wrap:anywhere}}[hidden]{{display:none!important}}.ledger{{max-height:650px;overflow:auto}}@media(max-width:600px){{main{{padding:0 12px}}section{{padding:15px}}h1{{font-size:24px}}}}</style>
<main><h1>K:LINK 인사 자료 연결·답변 검증</h1><p class="muted">대상: 한국전력 공개 대체자료 · 단계: {esc(stage)} · 생성 시각: {esc(result['created_at'])}</p>
<div class="notice"><b>Supabase 적재 보류 · PR 없음 · KTcs 적용 확인 전 · 사람 승인 0</b><p>자동 원문 대조와 같은 GPT 모델의 의미 검토 결과입니다. 독립적인 정답 평가나 조직의 최종 승인이 아닙니다. 인용 일치, 검색 성공과 답변의 의미·완전성은 별개입니다.</p></div>
<section><h2>얼마나 연결했나</h2><table><tbody>{source_table}</tbody></table><p>숫자는 원문 파일 수가 아닌 조문·보존 구간 수입니다. 문서 벡터는 기존 BAAI/bge-m3 배열을 그대로 골라 연결했습니다. 신규 문서 임베딩은 0개입니다.</p></section>
<section><h2>원문은 어떻게 확인했나</h2><p>검토 대기 3,268개를 포함해 검색 후보 3,870개의 구조·범위·해시를 점검했습니다. 원본 파일 {original['verified_original_files']}개의 해시가 일치했습니다. 문자층 대조 통과는 {original['actual_original_text_layer_passed']:,}개 구간이며, 이것만으로 표·읽기 순서·의미가 검증되지는 않습니다.</p><p>현재 연결된 {len(rows)}개는 원본 파일·문자층·위치 대조와 구조 검사를 통과했습니다. 불완전한 문장, 열이 섞인 PDF, 표·깨진 문자·불확실한 대상은 보류했습니다. 구조 미확정 큰 덩어리에 원문 전체를 대조했다고 표시하지 않았습니다.</p></section>
<section><h2>검색 검증과 답변 검증</h2><p>기존 골든셋 960문항은 변경하지 않았습니다. 질문 벡터는 아래 오프라인 검색 평가에서만 재사용하며 서비스에 골든 질문·정답을 넣지 않습니다.</p><div class="scroll"><table><tr><th>단계</th><th>원문 구간</th><th>모든 지정 근거가 허용된 문항</th><th>필수 근거 모두 찾음 @5</th></tr>{retrieval_table}</table></div><p>공통 범위 비교: {esc(json.dumps(comparability,ensure_ascii=False))}</p>
<p>실제 답변 검증은 기존 회귀·누락 자료 83문항과 새 자료 시험 질문 50문항을 합친 133문항입니다. 새 질문은 원문 기반 초안이며 독립 골든셋이 아닙니다. 응답을 보기 전, 입력에 없는 발췌문을 가리키던 초안 1문항을 제외했습니다.</p><div class="scroll"><table><tr><th>실행 단계</th><th>실제 실행</th><th>자동 완전</th><th>설명 미흡</th><th>오류 판정</th><th>답변 보류</th><th>채점·제공자 오류</th></tr>{answer_table}</table></div><p>expanded・expanded-v2는 133문항 전체 실행입니다. expanded-v3의 26문항은 이 중 필수 재실행 25문항과 별도 회귀 확인 1문항입니다. 최신 결과 조합은 필수 재실행 결과를 우선하고 나머지 문항에 v2 결과를 사용하며, 가장 좋은 점수를 골라 합치지 않습니다. 선택된 133개 응답 모두 현재 코드로 인용·수치·범위 검사를 다시 통과했습니다.</p><p>133문항 밖 추가 확인: {esc(json.dumps(supplemental,ensure_ascii=False))}</p><p>보류·빈 답변·채점 실패를 완전 답변으로 세지 않습니다. 판정 모델의 오류 가능성도 있어 원시 판정과 원문을 보존했습니다.</p></section>
<section><h2>문항별 실제 결과</h2><select id="verdict"><option value="">전체</option><option>complete</option><option>incomplete</option><option>incorrect</option><option>withheld</option><option>judge_error</option></select><div id="cases">{''.join(case_cards)}</div></section>
<section><h2>3,268개 검토 기록</h2><p>상태는 서로 겹치지 않으며 세부 보류 사유는 한 구간에 여러 개일 수 있습니다.</p><input id="query" placeholder="문서명·구간·사유 검색"><div class="ledger"><table><thead><tr><th>원문 파일 ID</th><th>문서</th><th>구간</th><th>상태</th><th>사유</th></tr></thead><tbody id="ledger">{ledger_rows}</tbody></table></div></section>
<section><h2>보존과 한계</h2><p>원문·골든셋·문서 벡터 해시는 기준과 모두 일치: <b>{preservation['all_baselines_unchanged']}</b>. 사용 모델은 {esc(result['generation_model'])}로 유지했습니다. 직원 개인정보는 입력하지 않았으며 API 키는 서버의 기존 설정에서만 읽었습니다.</p><p>실제 KTcs 규정 현행성, 직원 인증·권한, 개인별 자격 및 조직 승인, Supabase 적재, 실제 신청·결재는 이번 검증의 완료 항목이 아닙니다.</p></section></main>
<script>document.querySelector('#verdict').onchange=e=>document.querySelectorAll('#cases details').forEach(d=>d.hidden=!!e.target.value&&d.dataset.verdict!==e.target.value);document.querySelector('#query').oninput=e=>{{const q=e.target.value.toLowerCase();document.querySelectorAll('#ledger tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))}};</script></html>'''
    (ROOT/'validation-report.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(stage=stage,sources=len(rows),vectors=len(index.ids),answer_results=stages.get(stage),report=str(ROOT/'validation-report.html')),ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('--stage',default='expanded-v2');main(p.parse_args().stage)
