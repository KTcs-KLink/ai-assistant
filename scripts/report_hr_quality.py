"""Build a local, self-contained inspection report from preserved QA checkpoints."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import statistics
import sys

from evaluate_hr_quality import ROOT, CORPUS, REPO, readl, write, digest


def read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def assemble(stage):
    cohort=readl(ROOT / "cohort.jsonl")
    adjudications=read(ROOT / "codex-source-review.json", {})
    cases=[]
    for c in cohort:
        cid=c["case_id"]
        entries={}
        for s in dict.fromkeys(("baseline","candidate-3",stage)):
            answer=read(ROOT / s / "answers" / (cid+".json"))
            judgment=read(ROOT / s / "source-review-v2" / (cid+".json"))
            entries[s]=dict(answer=answer,automatic_review=judgment,
                codex_source_review=adjudications.get(s,{}).get(cid))
        cases.append(dict(**c,results=entries))
    def aggregate(split,s):
        selected=[c for c in cases if split=="all" or c["split"]==split]
        present=[c for c in selected if c["results"][s]["answer"]]
        verdicts=Counter((c["results"][s]["automatic_review"] or {}).get("verdict","pending") for c in present)
        semantic=Counter((c["results"][s]["codex_source_review"] or c["results"][s]["automatic_review"] or {}).get("verdict","pending") for c in present)
        latency=[c["results"][s]["answer"]["seconds"] for c in present]
        return dict(expected=len(selected),attempted=len(present),automatic_verdicts=dict(verdicts),
            codex_adjudicated_verdicts=dict(semantic),human_approved=False,
            strict_automatic_complete=dict(numerator=verdicts["complete"],denominator=len(present)),
            strict_codex_display_complete=dict(numerator=semantic["complete"],denominator=len(present)),
            median_seconds=round(statistics.median(latency),2) if latency else None,
            maximum_seconds=max(latency) if latency else None)
    baseret=read(ROOT / "baseline/retrieval-summary.json")
    newret=read(ROOT / stage / "retrieval-summary.json") or read(ROOT / "candidate-2/retrieval-summary.json")
    attempts=[]
    for folder in sorted(ROOT.iterdir()):
        answers=list((folder / "answers").glob("KEPCO-HR-*.json")) if folder.is_dir() else []
        if not answers:continue
        provider_calls=0
        usage=Counter()
        errors=0
        for path in answers:
            record=read(path)
            response=record.get("response") or {}
            calls=response.get("provider_calls")
            if calls is None:calls=[dict(usage=response["usage"])] if response.get("usage") else []
            provider_calls+=len(calls)
            errors+=bool(record.get("error"))
            for call in calls:
                for field in ("input_tokens","output_tokens","total_tokens"):
                    usage[field]+=(call.get("usage") or {}).get(field,0)
        attempts.append(dict(stage=folder.name,cases=len(answers),completed_provider_calls_recorded=provider_calls,
            provider_errors=errors,recorded_usage=dict(usage)))
    summary=dict(created_at=datetime.now(timezone.utc).isoformat(),final_stage=stage,
        supabase_ingestion="HOLD_USER_REQUESTED",supabase_calls_this_task=0,
        source_verification= {k:v for k,v in read(ROOT / "source-verification.json",{}).items() if k not in ("files","excerpts")},
        protocol=read(ROOT / "protocol.json"),retrieval=dict(baseline=baseret,after=newret),
        baseline=aggregate("development","baseline"),
        after_development=aggregate("development",stage),after_held_out=aggregate("held_out_from_fix_selection",stage),
        after_all=aggregate("all",stage),attempt_history=attempts,
        first_full_live_pass=aggregate("all","candidate-3"),
        first_full_live_development=aggregate("development","candidate-3"),
        first_full_live_held_out=aggregate("held_out_from_fix_selection","candidate-3"),
        display_replay_proof=read(ROOT / "final-display-replay/replay-proof.json"),
        quality_gate=read(ROOT / "quality-gate.json"),
        current_source_sha256=digest(CORPUS),
        current_code={n:digest(REPO / "server" / (n+".py")) for n in ("hr_answer","hr_evidence")},
        limitations=["한국전력 공개 대체자료이며 KTcs 실제 규정이나 실직원 자격을 검증한 것이 아닙니다.",
            "원본 해시·정규화 본문·위치 매핑을 재검사했습니다. 원본을 이번에 새로 파싱하거나 모든 서식·표를 눈으로 재검수하지는 않았습니다.",
            "543문항은 검색 평가 범위이며 전체 답변 의미 평가 분모가 아닙니다. 실제 답변 검증은 고정한 40문항입니다.",
            "자동 의미 검토는 같은 설정 모델을 사용합니다. Codex 원문 대조도 AI 검토이며 사람의 독립 승인이나 완벽한 품질 보증이 아닙니다.",
            "수정 개발 24문항과 별도 검증 16문항은 지정 원문 구간이 겹치지 않지만 같은 문서를 공유합니다.",
            "실패·중간 수정·재시도는 별도 폴더에 보존하며 최종 결과와 섞어 최고 성공만 집계하지 않습니다."])
    write(ROOT / "summary.json",summary)
    write(ROOT / "report-data.json",dict(summary=summary,cases=cases))
    return summary,cases


PAGE='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>K:LINK 인사 답변 원문 대조</title><link rel="icon" href="data:,"><style>
:root{font-family:system-ui,"Malgun Gothic",sans-serif;color:#192b45;background:#f4f6fa;line-height:1.65}*{box-sizing:border-box}body{margin:0}main{max-width:1260px;margin:auto;padding:36px 24px 80px}h1{font-size:32px;line-height:1.25;margin:10px 0 16px}h2{font-size:20px}h3{font-size:17px;margin:12px 0}p{margin:8px 0}.eyebrow{font-size:12px;font-weight:750;letter-spacing:2px;color:#536682}.notice{background:#fff1db;border:1px solid #e8c184;border-radius:14px;padding:18px 22px;margin:24px 0}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.metric{padding:20px;background:white;border:1px solid #dce3ed;border-radius:14px}.big{font-size:28px;line-height:1.3;font-weight:750;margin:8px 0}.muted,small{color:#52657d}small{font-size:12px}.controls{position:sticky;top:0;z-index:1;background:#f4f6faee;backdrop-filter:blur(8px);padding:18px 0;display:flex;gap:10px;flex-wrap:wrap}select,input,button{font:inherit;background:white;color:#192b45;border:1px solid #bcc8d7;border-radius:8px;padding:9px 12px}input{flex:1;min-width:180px}button{cursor:pointer}button:focus-visible,summary:focus-visible{outline:3px solid #3674cb;outline-offset:3px}.case{padding:24px;margin:16px 0;border:1px solid #d5dfea;border-radius:16px;background:white}.case header{display:flex;gap:12px;align-items:center;justify-content:space-between}.pill{background:#e8edf5;border-radius:20px;padding:4px 12px;font-size:12px;font-weight:700;white-space:nowrap}.complete{background:#e5f3ee;color:#12604b}.incorrect,.judge_error,.provider_error{background:#fde8e8;color:#943b38}.incomplete,.withheld,.pending{background:#fff0d6;color:#875311}.cols{display:grid;grid-template-columns:1fr 1fr;gap:22px}.col{border:1px solid #e2e8f0;border-radius:10px;padding:18px;min-width:0}.col.before{background:#f7f8fa}.question{font-size:18px;font-weight:650}.answer p{white-space:pre-wrap}.review{font-size:13px;border-top:1px solid #dce3ed;margin-top:16px;padding-top:12px}.review ul{padding-left:20px}details{border-top:1px solid #dce3ed;margin-top:18px;padding-top:12px}summary{cursor:pointer;font-weight:650}.original{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;padding:14px;background:#f1f4f8;border-radius:8px;max-height:420px;overflow:auto}.hash{font-family:ui-monospace,monospace;font-size:11px;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;border-bottom:1px solid #dce3ed;text-align:left}footer{margin-top:32px}.empty{padding:40px;text-align:center}a{color:#255da3}@media(max-width:800px){.metrics{grid-template-columns:1fr 1fr}.cols{grid-template-columns:1fr}main{padding:22px 14px}.case{padding:18px}h1{font-size:27px}}@media print{.controls{display:none}.case{break-inside:avoid}.original{max-height:none}.notice{background:white}}
</style><main><div class="eyebrow">K:LINK / LOCAL ANSWER QUALITY</div><h1>인사 답변을 원문과 대조했습니다</h1><p class="muted">조건 · 예외 · 적용 대상 · 의무와 재량 · 수치 · 인용 근거를 구분해 확인하는 로컬 검증 기록</p>
<div class="notice"><strong>Supabase 적재 보류 유지</strong><p>한국전력 공개 대체자료의 연구용 답변입니다. KTcs 실제 규정, 직원 자격, 최신 법령 또는 사람의 승인을 확인한 결과가 아닙니다. 자동 검사 통과를 완벽한 정확도로 해석하지 마세요.</p></div>
<section class="metrics" id="metrics"></section><section><h2>검색과 답변을 따로 평가했습니다</h2><div id="scope"></div></section>
<div class="controls"><select id="split" aria-label="질문 묶음"><option value="">전체 질문</option value="development">수정 개발 질문</option><option value="held_out_from_fix_selection">별도 검증 질문</option></select><select id="verdict" aria-label="검토 결과"><option value="">모든 결과</option><option value="complete">완전 답변</option><option value="incomplete">조건 누락</option><option value="incorrect">의미 오류</option><option value="withheld">답변 표시 보류</option><option value="judge_error">자동 검토 오류</option></select><input id="search" aria-label="질문 검색" placeholder="업무 · 질문 · 원문 검색"><button id="all-sources">원문 모두 펼치기</button><span id="count" aria-live="polite"></span></div><section id="cases"></section><footer><h2>해석할 때의 한계</h2><ul id="limits"></ul><p class="hash" id="fingerprint"></p></footer></main>
<script id="data" type="application/json">__DATA__</script><script>
const D=JSON.parse(document.getElementById('data').textContent),S=D.summary,stage=S.final_stage,replay=stage==='final-display-replay';
const $=id=>document.getElementById(id),e=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels={complete:'완전 답변',incomplete:'조건 누락',incorrect:'의미 오류',withheld:'표시 보류',judge_error:'자동 검토 오류',provider_error:'호출 실패',pending:'검토 대기'};
function metric(label,a){const v=a.strict_automatic_complete;return `<article class="metric"><small>${e(label)}</small><div class="big">${v.numerator} / ${v.denominator}</div><small>자동 본문 채점 · 사람 승인 아님</small></article>`}
const br=S.retrieval.baseline.metrics.all_at_3,ar=S.retrieval.after.metrics.all_at_5;
$('metrics').innerHTML=metric('수정 전 · 같은 개발 질문',S.baseline)+metric('최종 보완 전 실제 생성 · 같은 질문',S.first_full_live_development)+metric('최종 보완 전 실제 생성 · 별도 질문',S.first_full_live_held_out)+`<article class="metric"><small>원문 연결 재검사</small><div class="big">${S.source_verification.runtime_units}개 구간</div><small>${S.source_verification.documents}개 파일 · ${S.source_verification.source_parts_checked}개 위치</small></article>`;
$('scope').innerHTML=`<p>기존 960문항 중 현재 허용된 원문에 필요한 근거가 모두 있는 질문은 <strong>${ar.denominator}개</strong>입니다. 상위 검색 결과에 필요한 지정 근거가 모두 포함된 문항은 기존 3개 검색에서 <strong>${br.numerator}/${br.denominator}</strong>, 수정 후 5개 검색에서 <strong>${ar.numerator}/${ar.denominator}</strong>입니다. 이는 답변 의미 정확도와 다른 지표입니다.</p><p>실제 답변 검증 목표는 8개 업무의 고정 질문 40개이며, 현재 ${S.after_all.attempted}개 실행했습니다. 답변 전 자동 원문 재검토도 같은 설정 모델을 쓰며 독립적인 사람 평가가 아닙니다. 모델: <strong>${e(S.protocol.model)}</strong>.</p>`+(replay?`<div class="notice"><strong>최종 화면의 40/40은 AI 정확도 100%가 아닙니다.</strong><p>실제 생성 40문항의 첫 자동 채점은 ${S.first_full_live_pass.strict_automatic_complete.numerator}/40이었습니다. 이 자동 채점도 조건 연결 오류를 놓쳤습니다. 그 뒤 4문항을 새로 생성하고 실제 응답 40개를 수정한 코드로 재생·대조했습니다. 위 최종 수치는 본문과 바로 보이는 원문 조건을 합친 표시 결과이며, 본문만으로는 1문항에 원칙 범위 설명 보완이 필요합니다. 21문항의 지정 근거 검색 및 현행성·KTcs 적용·사람 승인은 미완료이므로 적재를 보류합니다.</p></div>`:'');
function entry(c,s){const r=c.results[s],a=r.answer?.response,j=r.automatic_review,ver=r.codex_source_review?.verdict||j?.verdict||'pending';if(!r.answer)return '<p class="muted">수정 개발에 사용하지 않은 별도 검증 질문입니다.</p>';let out=`<span class="pill ${e(ver)}">${e(labels[ver])}</span>`;out+=a?.paragraphs?.length?a.paragraphs.map(p=>`<p>${e(p.text)}</p>`).join(''):`<p class="muted">${e(r.answer.error?.safe_message||a?.missing_information?.join(' / ')||'검증된 답변을 표시하지 않았습니다.')}</p>`;if(a?.source_conditions?.length){out+='<div class="review"><strong>함께 확인할 조건·예외 원문 · 코드가 원문 그대로 표시</strong>'+a.source_conditions.map(c=>`<p><small>${e(c.section)}</small></p><div class="original">${e(c.quote)}</div>`).join('')+'</div>'}if(j?.judgment){out+=`<div class="review"><strong>자동 원문 대조</strong><p>${e(j.judgment.rationale)}</p>`;if(j.judgment.omissions?.length)out+='<ul>'+j.judgment.omissions.map(o=>`<li>${e(o.explanation)}<br><small>근거: ${e(o.original_quote)}</small></li>`).join('')+'</ul>';if(j.judgment.unsupported_claims?.length)out+='<ul>'+j.judgment.unsupported_claims.map(u=>`<li>${e(u.answer_claim)} — ${e(u.explanation)}</li>`).join('')+'</ul>';out+='</div>'}if(r.codex_source_review)out+=`<div class="review"><strong>Codex의 추가 원문 대조 · 사람 승인 아님</strong><p>${e(r.codex_source_review.note)}</p></div>`;return out}
function render(){const query=$('search').value.trim().toLowerCase(),split=$('split').value,v=$('verdict').value;const list=D.cases.filter(c=>(!split||c.split===split)&&(!v||(c.results[stage].codex_source_review?.verdict||c.results[stage].automatic_review?.verdict||'pending')===v)&&(!query||JSON.stringify([c.question,c.task_name,c.designated_full_sources]).toLowerCase().includes(query)));$('count').textContent=`${list.length}개 질문`;$('cases').innerHTML=list.map(c=>`<article class="case"><header><small>${e(c.task_name)} · ${e(c.case_id)}</small><span class="pill">${c.split==='development'?'같은 질문 재검증':'별도 검증'}</span></header><p class="question">${e(c.question)}</p><div class="cols"><section class="col before"><h3>수정 전</h3><div class="answer">${entry(c,'baseline')}</div></section><section class="col"><h3>수정 후</h3><div class="answer">${entry(c,stage)}</div></section></div><details class="source"><summary>원문과 점검 기준 확인 · ${c.designated_full_sources.length}개 구간</summary><p><strong>질문별 필수 조건 초안 · Codex 원문 대조 · 사람 승인 아님</strong></p><ul>${c.required_points.map(p=>`<li>${e(p)}</li>`).join('')}</ul>${c.designated_full_sources.map(s=>`<h3>${e(s.section)}</h3><p><small>${e(s.company)} · 현행성 ${e(s.effective_status)} · 사람 미승인</small></p><div class="original">${e(s.text)}</div><p class="hash">${e(s.id)}<br>원본 파일 SHA256 ${e(s.source_file_sha256)}<br>본문 SHA256 ${e(s.sha256)}</p>`).join('')}</details></article>`).join('')||'<div class="empty">선택한 조건의 질문이 없습니다.</div>'}
for(const id of ['split','verdict','search'])$(id).addEventListener('input',render);$('all-sources').addEventListener('click',()=>{const nodes=[...document.querySelectorAll('details.source')],open=nodes.some(n=>!n.open);nodes.forEach(n=>n.open=open);$('all-sources').textContent=open?'원문 모두 접기':'원문 모두 펼치기'});$('limits').innerHTML=S.limitations.map(l=>`<li>${e(l)}</li>`).join('');$('fingerprint').textContent='검증 입력 SHA256 '+S.current_source_sha256;render();
</script></html>'''


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser()
    parser.add_argument("--stage",default="candidate-3")
    args=parser.parse_args()
    summary,cases=assemble(args.stage)
    data=json.dumps(dict(summary=summary,cases=cases),ensure_ascii=False).replace("<","\\u003c")
    (ROOT / "report.html").write_text(PAGE.replace("__DATA__",data),encoding="utf-8")
    print(json.dumps({k:summary[k] for k in ("final_stage","baseline","after_development","after_held_out","after_all")},ensure_ascii=False))


if __name__=="__main__":main()
