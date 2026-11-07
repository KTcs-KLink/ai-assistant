"""Read-only comparison using existing real BGE vectors. No new embeddings or API calls.

Query vectors are evaluation fixtures ONLY. The application never reads the gold
question file or these question-ID vector maps.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
from collections import Counter

os.environ.setdefault("OPENBLAS_NUM_THREADS","2")
os.environ.setdefault("OMP_NUM_THREADS","2")
import numpy as np
from closeout_hr_quality import ROOT,REPO,CORPUS,readl,write,digest
import evaluate_hr_quality as shared


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    from server import hr_evidence
    current='--current' in sys.argv
    source=REPO/'server/hr_evidence.py' if current else ROOT/"baseline_code/hr_evidence.py"
    code=source.read_text(encoding="utf-8").replace("min(limit, 5)","min(limit, 449)")
    alias="server.closeout_lexical_probe"
    import types
    lexical=types.ModuleType(alias);lexical.__package__="server";sys.modules[alias]=lexical
    exec(compile(code,str(source),"exec"),lexical.__dict__)
    rows=hr_evidence.corpus()[0];allowed={r['id']:r for r in rows}
    index=shared.WORKSPACE/"outputs/kepco_hr_full_eval_960_20261102/indexes"
    windows_path=shared.WORKSPACE/"outputs/kepco_hr_full_20261102/indexes/windows.jsonl"
    meta=json.loads((index/"windows_vectors.json").read_text(encoding="utf-8"))
    query_meta=json.loads((index/"queries_vectors.json").read_text(encoding="utf-8"))
    assert digest(CORPUS)==meta["source_sha256"] and digest(windows_path)==meta["windows_sha256"]
    assert digest(index/"windows.npy")==meta["vectors_sha256"]
    assert digest(index/"queries.npy")==query_meta["vectors_sha256"]
    assert digest(shared.GOLD)==query_meta["golden_set_sha256"]
    windows=readl(windows_path)
    assert meta["ids"]==[w['id'] for w in windows]
    indices=[i for i,w in enumerate(windows) if w['unit_record_id'] in allowed]
    for i in indices:
        w=windows[i];r=allowed[w['unit_record_id']]
        assert r['source_file_sha256']==w['source_file_sha256']
        import hashlib
        assert hashlib.sha256(r['text'][w['start']:w['end']].encode()).hexdigest()==w['text_sha256']
    v=np.load(index/"windows.npy",mmap_mode='r',allow_pickle=False)[indices]
    q=np.load(index/"queries.npy",mmap_mode='r',allow_pickle=False)
    assert v.shape[1]==q.shape[1]==1024 and np.isfinite(v).all() and np.isfinite(q).all()
    gold=readl(shared.GOLD)
    assert query_meta['ids']==[g['case_id'] for g in gold]
    scores=q@v.T
    pools={rid:[j for j,i in enumerate(indices) if windows[i]['unit_record_id']==rid] for rid in allowed}
    ids=list(allowed)
    dense=np.stack([scores[:,pools[rid]].max(axis=1) for rid in ids],axis=1)
    mapping={m['case_id']:m for m in readl(shared.MAPPING)}
    target={c['case_id'] for c in readl(ROOT/'cohort.jsonl')}
    results=[]
    for i,g in enumerate(gold):
        m=mapping[g['case_id']]
        if not m['all_gold_answer_eligible'] or not set(m['mapped_unit_ids'])<=allowed.keys():continue
        lex=[r['id'] for r in (lexical.lexical_search(g['question'],449) if current else lexical.search(g['question'],449))]
        den=sorted(ids,key=lambda rid:(-float(dense[i,ids.index(rid)]),rid))
        rankings={'bm25':lex,'dense':den}
        for k in [10,60]:
            for weight in [0.5,1.,2.]:
                fused={rid:0. for rid in ids}
                for ranking,w in [(lex,weight),(den,1.)]:
                    for rank,rid in enumerate(ranking[:100],1):fused[rid]+=w/(k+rank)
                rankings[f'rrf_k{k}_lex{weight}']=sorted(fused,key=lambda rid:(-fused[rid],rid))
        if current:
            rankings['hybrid_facets']=hr_evidence.select_facets(g['question'],rankings['rrf_k10_lex1.0'],rows)
        results.append(dict(case_id=g['case_id'],target=g['case_id'] in target,required=m['mapped_unit_ids'],
            hits={name:ranking[:5] for name,ranking in rankings.items()},
            required_ranks={name:{rid:(ranking.index(rid)+1 if rid in ranking else None) for rid in m['mapped_unit_ids']} for name,ranking in rankings.items()},
            all5={name:set(m['mapped_unit_ids'])<=set(ranking[:5]) for name,ranking in rankings.items()}))
    names=list(results[0]['all5'])
    summary=dict(questions=len(results),target=sum(r['target'] for r in results),allowed_units=len(rows),allowed_windows=len(indices),
        methods={name:dict(all_at5=sum(r['all5'][name] for r in results),target_all5=sum(r['target'] and r['all5'][name] for r in results),
            target_missing=[r['case_id'] for r in results if r['target'] and not r['all5'][name]]) for name in names},
        new_embeddings=0,model_calls=0,old_files_changed=False,existing_vector_hashes_verified=True)
    shared.writel(ROOT/('embedding-probe/current-rankings.jsonl' if current else 'embedding-probe/rankings.jsonl'),results)
    write(ROOT/('embedding-probe/current-summary.json' if current else 'embedding-probe/summary.json'),summary)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
