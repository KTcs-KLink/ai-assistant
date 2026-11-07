"""Combine latest preselected reruns with unchanged, revalidated actual answers.

Never choose a higher score from multiple attempts. A rerun always replaces the
earlier result, even if worse. All raw attempts and automated labels remain.
"""
from collections import Counter
from copy import deepcopy
import json
import sys

from evaluate_hr_expansion import EVAL,ROOT,CORPUS,hr_answer,hr_evidence
from expand_hr_sources import readl,write,writel
from hr_source_audit import sha


def main():
    cases=readl(EVAL/'combined-cohort.jsonl')
    expected_reruns={c['case_id'] for c in readl(EVAL/'followup-cohort.jsonl')}
    if (EVAL/'replay-rejected-cohort.jsonl').exists():expected_reruns.update(c['case_id'] for c in readl(EVAL/'replay-rejected-cohort.jsonl'))
    if (EVAL/'contract-workflow-followup.jsonl').exists():expected_reruns.update(c['case_id'] for c in readl(EVAL/'contract-workflow-followup.jsonl'))
    allowed={r['id']:r for r in hr_evidence.corpus()[0]};selection=[];rejected=[]
    for c in cases:
        cid=c['case_id'];stage='expanded-v3' if cid in expected_reruns else 'expanded-v2'
        ap=EVAL/stage/'answers'/(cid+'.json');jp=EVAL/stage/'source-prose-review'/(cid+'.json')
        if not ap.exists() or not jp.exists():raise SystemExit('Latest required rerun/review is incomplete.')
        a=json.loads(ap.read_text(encoding='utf-8'));j=json.loads(jp.read_text(encoding='utf-8'))
        response=a.get('response') or {};valid=True;issue=None
        try:
            if a.get('error'):raise ValueError('PROVIDER_ERROR')
            if a['question']!=c['question']:raise ValueError('QUESTION_CHANGED')
            if (response.get('company')!='KEPCO' or response.get('ktcs_applicable') is not False
                or response.get('human_approved') is not False or response.get('employee_data_sent') is not False):raise ValueError('SCOPE_CHANGED')
            for s in response.get('sources',[]):
                original=allowed[s['id']]
                if any(s.get(k)!=original.get(k) for k in ['text','sha256','source_file_sha256','version','company','source_role','source_context']):raise ValueError('SOURCE_CHANGED')
            if response.get('paragraphs'):
                draft=hr_answer.Draft(**{k:response[k] for k in ['status','paragraphs','missing_information']})
                hr_answer.validate(deepcopy(draft),response['sources'],c['question'])
                for condition in response.get('source_conditions',[]):
                    if allowed[condition['source_id']]['text'][condition['start']:condition['end']]!=condition['quote']:raise ValueError('CONDITION_RANGE_CHANGED')
            elif response.get('validation')!='AMBIGUOUS_SOURCE_VERSION_NO_GENERATION':raise ValueError('UNEXPECTED_WITHHOLD')
        except (hr_answer.AnswerUnavailable,ValueError,KeyError) as error:
            valid=False;issue=error.code if isinstance(error,hr_answer.AnswerUnavailable) else str(error);rejected.append(cid)
        selection.append(dict(case_id=cid,stage=stage,answer_sha256=sha(ap),judgment_sha256=sha(jp),
            verdict=j['verdict'],latest_code_validation_passed=valid,safe_issue=issue,
            actual_provider_calls=len(response.get('provider_calls',[])),human_approved=False))
    writel(EVAL/'final-selection.jsonl',selection)
    result=dict(cases=len(selection),verdicts=dict(Counter(r['verdict'] for r in selection)),
        full_actual_stages=['expanded','expanded-v2'],focused_actual_reruns=len(expected_reruns&{c['case_id'] for c in cases}),
        all_selected_responses_revalidated_with_current_code=not rejected,rejected_cases=rejected,
        selection_rule='latest required rerun; otherwise v2; never best-of',
        source_sha256=sha(CORPUS),answer_code_sha256=sha(__import__('pathlib').Path(hr_answer.__file__)),
        evidence_code_sha256=sha(__import__('pathlib').Path(hr_evidence.__file__)),
        overlay_sha256=sha(ROOT/'review-overlay.json'),human_approved=False,independent_semantic_approval=False)
    write(EVAL/'final-validation.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    if rejected:raise SystemExit('Do not publish the selected set until the rejected responses are repaired/rechecked.')


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
