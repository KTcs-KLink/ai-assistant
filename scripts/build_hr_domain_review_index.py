"""Separate reclassified and previous-HR review windows in a new local FTS index."""
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from server import hr_review_domains as domains,hr_review_index,hr_source_scope as scope


def main():
    if domains.DB.exists():raise SystemExit('Preserve the completed versioned domain index.')
    summary=json.loads((domains.OUT/'summary.json').read_text(encoding='utf-8'))
    if summary.get('classification_coverage_complete') is not True:raise ValueError('CLASSIFICATION_INCOMPLETE')
    classification_sha=scope.file_sha(domains.CLASSIFICATIONS)
    if classification_sha!=summary['classification_sha256']:raise ValueError('CLASSIFICATION_CHANGED')
    labels={}
    with domains.CLASSIFICATIONS.open(encoding='utf-8') as f:
        for line in f:
            row=json.loads(line);labels[row['id']]=row['domain_label']
    if len(labels)!=7235:raise ValueError('TARGET_COVERAGE')
    if scope.file_sha(hr_review_index.DB)!=hr_review_index.DB_SHA256:raise ValueError('BASE_REVIEW_INDEX_CHANGED')
    counts=Counter();previous=0;ids=set()
    temporary=domains.DB.with_name(f'.{domains.DB.name}.building')
    if temporary.exists():raise SystemExit('An interrupted build remains. Inspect it before retrying.')
    with closing(sqlite3.connect(hr_review_index.DB.as_uri()+'?mode=ro',uri=True)) as source,closing(sqlite3.connect(temporary)) as target:
        with target:
            target.execute('PRAGMA cache_size=-4096');target.executescript(domains.SCHEMA)
            target.execute('INSERT INTO metadata VALUES (?,?)',(scope.MANIFEST_SHA256,classification_sha))
            for row in source.execute('SELECT terms,source_id,title,section,text,window_id,start,end,layout_review,decision FROM excerpts ORDER BY rowid'):
                window_id=row[5]
                if window_id in labels:
                    label=labels[window_id];method='FRESH_SOURCE_PIECE_DOMAIN_REVIEW_PROJECTED_TO_WINDOW'
                else:
                    if row[9]!='HR':raise ValueError('UNCLASSIFIED_REVIEW_WINDOW')
                    label='HR';method='PREVIOUS_HR_LABEL_NOT_RECLASSIFIED';previous+=1
                if window_id in ids:raise ValueError('DUPLICATE_WINDOW')
                ids.add(window_id);counts[label]+=1
                target.execute('INSERT INTO excerpts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(*row,label,method))
            if len(ids)!=7770 or previous!=535 or not set(labels)<=ids:raise ValueError('ALL_REVIEW_COVERAGE')
            target.execute("INSERT INTO excerpts(excerpts) VALUES ('optimize')")
    temporary.replace(domains.DB)
    record=dict(index_sha256=scope.file_sha(domains.DB),classification_sha256=classification_sha,
        source_manifest_sha256=scope.MANIFEST_SHA256,total_review_windows=7770,previous_hr_windows=535,
        fresh_reclassified_windows=7235,all_review_domain_counts=dict(counts),
        default_search='hr_candidates',excluded_from_default='NON_HR',
        answer_sources_unchanged=True,answer_eligible=False,human_approved=False,supabase_ingestion='HOLD',external_database_writes=0)
    (domains.OUT/'domain-review-index.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record))


if __name__=='__main__':main()
