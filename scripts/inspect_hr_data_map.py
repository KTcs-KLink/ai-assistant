"""Read-only inventory of the KEPCO gold, source units and real local embeddings."""
from collections import Counter
from datetime import datetime, timezone
import json
import sys

import numpy as np

import evaluate_hr_quality as shared
from closeout_hr_quality import ROOT
from server import hr_evidence, hr_vectors


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    gold=shared.readl(shared.GOLD)
    mapping=shared.readl(shared.MAPPING)
    allowed=hr_evidence.corpus()[0]
    allowed_ids={s['id'] for s in allowed}
    kinds=Counter();levels=Counter();total=searchable=eligible=0
    with shared.CORPUS.open(encoding='utf-8') as file:
        for line in file:
            unit=json.loads(line);total+=1;kinds[unit['kind']]+=1
            searchable+=unit.get('searchable') is True
            eligible+=unit.get('answer_eligible') is True
            if unit['id'] in allowed_ids:levels[unit.get('child_level')]+=1
    window_count=matched=0
    with (hr_vectors.SOURCE/'indexes/windows.jsonl').open(encoding='utf-8') as file:
        for line in file:
            window=json.loads(line);window_count+=1
            matched+=window['unit_record_id'] in allowed_ids
    meta=json.loads((hr_vectors.INDEX/'windows_vectors.json').read_text(encoding='utf-8'))
    values=np.load(hr_vectors.INDEX/'windows.npy',mmap_mode='r',allow_pickle=False)
    assert values.shape==(window_count,1024) and np.isfinite(values).all()
    assert shared.digest(shared.CORPUS)==meta['source_sha256']
    assert shared.digest(hr_vectors.INDEX/'windows.npy')==meta['vectors_sha256']
    assert shared.digest(hr_vectors.SOURCE/'indexes/windows.jsonl')==meta['windows_sha256']
    norms=np.linalg.norm(values,axis=1)
    assert float(np.max(np.abs(norms-1)))<1e-4
    result=dict(checked_at=datetime.now(timezone.utc).isoformat(),company='KEPCO',other_project_data_used=False,
        golden=dict(questions=len(gold),by_task=dict(Counter(g['task_name'] for g in gold)),
            path=str(shared.GOLD),sha256=shared.digest(shared.GOLD),human_independently_approved=False),
        full_source=dict(preserved_units=total,kinds=dict(kinds),
            searchable_units=searchable,
            automatically_answer_eligible_units=eligible,
            path=str(shared.CORPUS),sha256=shared.digest(shared.CORPUS)),
        app_scope=dict(source_units=len(allowed),documents=len({s['title'] for s in allowed}),
            source_unit_kind='ARTICLE',parent_child_levels=dict(levels),
            matched_vector_windows=matched,
            eligible_gold_questions=sum(m['all_gold_answer_eligible'] and set(m['mapped_unit_ids'])<=allowed_ids for m in mapping),
            human_approved_units=sum(s['human_approved'] for s in allowed),ktcs_applicable=False),
        chunking=dict(hierarchy='Chapter parent -> Section child where verified, otherwise Article fallback -> complete Article unit',
            retrieval_only_windows=True,maximum_bge_tokens=700,
            overlap='min(150 characters, one quarter of preceding window length)',
            embedding_text='document title and heading prefix + original body window',
            original_offsets_and_hashes_preserved=True,original_articles_truncated=False),
        embeddings=dict(model=meta['model'],revision=meta['revision'],dimension=meta['dimension'],
            shape=list(values.shape),dtype=str(values.dtype),normalization='L2',minimum_norm=float(norms.min()),maximum_norm=float(norms.max()),
            document_vector_path=str(hr_vectors.INDEX/'windows.npy'),sha256=meta['vectors_sha256'],
            storage='Local NumPy array; no Supabase ingestion in this task',document_embeddings_reused=True,
            new_document_embeddings_in_this_task=0,live_questions_encoded_locally=True,
            gold_query_vectors_used_at_runtime=False),
        supabase_ingestion='HOLD_USER_REQUESTED')
    shared.write(ROOT/'data-inventory.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
