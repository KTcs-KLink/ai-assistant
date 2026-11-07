"""Select measured failures and changed evidence; never select best-of retries."""
from collections import Counter
import json
import sys
from copy import deepcopy

from evaluate_hr_expansion import ROOT,EVAL,CORPUS,hr_evidence,hr_vectors
from expand_hr_sources import write,writel,readl
from hr_source_audit import sha


def main():
    path=EVAL/'followup-cohort.jsonl'
    if path.exists():raise SystemExit('The follow-up cohort is already frozen.')
    cases=readl(EVAL/'combined-cohort.jsonl');rows=hr_evidence.corpus()[0];lookup={r['id']:r for r in rows}
    index=hr_vectors.get_index(rows,CORPUS);selection=[];selected=[];replays=[]
    for number,c in enumerate(cases,1):
        cid=c['case_id'];a=json.loads((EVAL/'expanded-v2/answers'/(cid+'.json')).read_text(encoding='utf-8'))
        j=json.loads((EVAL/'expanded-v2/source-prose-review'/(cid+'.json')).read_text(encoding='utf-8'))
        r=a.get('response') or {};old_ids=[s['id'] for s in r.get('sources',[])]
        latest=hr_evidence.search(c['question'],5)
        ambiguous=set(hr_evidence.ambiguous_versions(c['question'],latest))
        primary_boundary=bool(latest) and (latest[0]['id'] in ambiguous or any(hr_evidence.title_key(s['title']) in hr_evidence.title_key(c['question']) for s in latest if s['id'] in ambiguous))
        effective=latest if primary_boundary else [s for s in latest if s['id'] not in ambiguous]
        new_ids=[s['id'] for s in effective];reasons=[]
        if j['verdict']!='complete':reasons.append('prior_automatic_review_not_complete')
        if old_ids!=new_ids:reasons.append('retrieved_evidence_changed')
        valid=True;message=None
        if r.get('paragraphs'):
            try:
                from server import hr_answer
                draft=hr_answer.Draft(**{k:r[k] for k in ['status','paragraphs','missing_information']})
                hr_answer.validate(deepcopy(draft),r['sources'],c['question'])
            except hr_answer.AnswerUnavailable as error:
                valid=False;message=error.code;reasons.append('new_source_validation_rejects_prior_text')
        replays.append(dict(case_id=cid,old_verdict=j['verdict'],prior_text_passes_current_code=valid,
            code=message,evidence_unchanged=old_ids==new_ids,primary_version_boundary=primary_boundary))
        if reasons:selected.append(c)
        selection.append(dict(case_id=cid,reasons=reasons,previous_source_ids=old_ids,current_source_ids=new_ids,
            regenerate=bool(reasons),prior_answer_sha256=sha(EVAL/'expanded-v2/answers'/(cid+'.json'))))
        if number%20==0:print(json.dumps(dict(checked=number,total=len(cases))),flush=True)
    writel(path,selected);writel(EVAL/'followup-selection.jsonl',selection);writel(EVAL/'validation-replay-v3.jsonl',replays)
    write(EVAL/'followup-protocol.json',dict(cases=len(selected),full_replay_cases=len(cases),
        reasons=dict(Counter(reason for s in selection for reason in s['reasons'])),
        source_sha256=sha(CORPUS),cohort_sha256=sha(path),evidence_code_sha256=sha(__import__('pathlib').Path(hr_evidence.__file__)),
        actual_gpt_generation=False,previous_outputs_preserved=True,selection_uses_evaluation_outcomes_only_offline=True))
    print(json.dumps(dict(followup_cases=len(selected),full_code_replay=len(cases)),ensure_ascii=False),flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
