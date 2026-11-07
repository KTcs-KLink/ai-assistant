"""Bounded expansion checks, separate from the preserved 960 benchmark.

Reuses saved genuine intent proposals only for a before/after retrieval check.
New-source entry checks use source-derived queries, not independent gold labels.
Never writes source files, vectors, secrets or a database.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='2'
os.environ['OMP_NUM_THREADS']='2'
os.environ['MKL_NUM_THREADS']='2'
from collections import Counter
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from server import hr_evidence,hr_intent,hr_source_scope as scope,hr_vectors


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def lines(path):return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def main():
    path=scope.OUT/'retrieval-verification-v3.json'
    if path.exists():raise SystemExit('Preserve the completed check; choose a new artifact version to rerun.')
    os.environ['KLINK_LOCAL_REVIEWED_UNITS']=str(scope.INPUTS['reviewed_units'])
    os.environ['KLINK_HR_RETRIEVAL']='hybrid'
    old=scope.WORKSPACE/'outputs/klink_hr_semantic_intents_20261107'
    cases=lines(old/'cohort.jsonl')+lines(old/'heldout.jsonl')
    # Fresh verified encoder results are shared only within this paired scope check.
    # No stored gold embeddings, answer vectors or source IDs enter retrieval.
    cache={};query=hr_vectors.VectorIndex.query
    def paired_query(self,text):
        if text not in cache:cache[text]=query(self,text)
        return cache[text]
    hr_vectors.VectorIndex.query=paired_query
    results={};baseline_ids=set()
    for selected in ['baseline','expanded']:
        os.environ['KLINK_HR_SOURCE_SCOPE']=selected
        rows=hr_evidence.corpus()[0]
        if selected=='baseline':baseline_ids={r['id'] for r in rows}
        records=[]
        for case in cases:
            folder='after-v2' if case['kind']=='heldout_equivalent' else 'after'
            analysis=read(old/folder/'analysis'/f"{case['id']}.json")
            plan=hr_intent.accept(hr_intent.Proposal.model_validate(analysis['proposal']),case['question'],'gpt-6-luna')
            hits=hr_evidence.search(case['question'],5,semantic_plan=plan) if plan.proposal.status=='ready' else []
            records.append(dict(id=case['id'],kind=case['kind'],sources=[r['id'] for r in hits],
                expected_at5=not case['expected_sources'] or set(case['expected_sources'])<={r['id'] for r in hits},
                verified_answer_sources_only=all(r['answer_eligible'] and not r['review_only'] for r in hits)))
        results[selected]=dict(source_units=len(rows),cases=records,missing=[r['id'] for r in records if not r['expected_at5']])
        print(json.dumps(dict(scope=selected,source_units=len(rows),checked=len(records),missing=results[selected]['missing'])),flush=True)
    new=[r for r in hr_evidence.corpus()[0] if r['id'] not in baseline_ids]
    entries=[]
    for row in new:
        question=row['title']+' '+hr_evidence.section_heading(row['section'])+' 내용'
        hits=hr_evidence.search(question,5)
        entries.append(dict(id=row['id'],question=question,at5=row['id'] in {r['id'] for r in hits},sources=[r['id'] for r in hits]))
    review=hr_evidence.review_search('인사 근무')
    results.update(new_source_entry_checks=entries,new_source_count=len(new),new_source_entry_at5=sum(r['at5'] for r in entries),
        source_derived_queries_not_independent_gold=True,saved_intent_proposals_reused=True,new_intent_model_calls=0,
        distinct_encoder_queries=len(cache),review_results=len(review),
        review_sources_excluded_from_answer_allowlist=all(hr_evidence.source(r['id']) is None for r in review),
        document_embeddings_changed=False,supabase_ingestion='HOLD',human_approved=False)
    path.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in results.items() if k not in ['baseline','expanded','new_source_entry_checks']},ensure_ascii=True))


if __name__=='__main__':main()
