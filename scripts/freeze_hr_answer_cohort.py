"""Final prospective QA audit. No answers have been generated for this cohort."""
from collections import Counter
import json
import shutil
import sys

from hr_source_audit import OUT,BASE,incomplete_clause_issues,sha
from expand_hr_sources import write,writel,readl


def main():
    path=OUT/'original-proofs.jsonl';snapshot=OUT/'pre-completeness-original-proofs.jsonl'
    if snapshot.exists():raise SystemExit('This prospective source/cohort audit is already frozen.')
    shutil.copy2(path,snapshot)
    proofs={p['id']:p for p in readl(path)};changed=[]
    for line in (BASE/'data/reviewed_units.jsonl').open(encoding='utf-8'):
        row=json.loads(line)
        if not row.get('searchable'):continue
        issues=incomplete_clause_issues(row['text'])
        if issues:
            p=proofs[row['id']];p['issues']=sorted(set(p['issues']+issues));p['source_structure_verified']=False
            changed.append(dict(id=row['id'],title=row['document_title'],section=row['heading_path'],prior_answer_eligible=row['answer_eligible']))
    temp=path.with_suffix('.complete.tmp');writel(temp,list(proofs.values()));temp.replace(path)
    write(OUT/'incomplete-clause-holds.json',changed)
    for name in ['review-overlay.json','review-summary.json','review-final-ledger.jsonl']:
        shutil.copy2(OUT/name,OUT/('pre-completeness-'+name))
    cohort=OUT/'evaluation/combined-cohort.jsonl'
    cases=readl(cohort)
    if (OUT/'evaluation/expanded/answers').exists():raise SystemExit('Do not revise a cohort after seeing its answers.')
    shutil.copy2(cohort,OUT/'evaluation/pre-prospective-review-cohort.jsonl')
    # The draft refers to an unseen excerpt and cannot be evaluated as a
    # stand-alone chat question. Reject it before any candidate generation.
    rejected=[c for c in cases if '이 조문 발췌만' in c['question']]
    cases=[c for c in cases if c not in rejected]
    writel(cohort,cases)
    write(OUT/'evaluation/prospective-cohort-review.json',dict(
        candidate_answers_seen=False,remaining_cases=len(cases),rejected_cases=[dict(case_id=c['case_id'],question=c['question'],reason='Question refers to an excerpt not included in the chat input; source fragment also failed completeness audit.') for c in rejected],
        original_questions_and_rubrics_otherwise_unchanged=True,cohort_sha256=sha(cohort),human_approved=False))
    print(json.dumps(dict(incomplete_source_holds=len(changed),previously_eligible=sum(c['prior_answer_eligible'] for c in changed),rejected_draft_questions=len(rejected),remaining_cases=len(cases)),ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
