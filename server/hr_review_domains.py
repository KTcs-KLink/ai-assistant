"""Read-only separated domain search. Reclassification never changes answer sources."""
from functools import lru_cache
from contextlib import closing
import sqlite3
import unicodedata

from . import hr_source_scope as scope

OUT=scope.WORKSPACE/'outputs/klink_hr_reclassification_20261108'
DB=OUT/'domain-review-search.sqlite3'
CLASSIFICATIONS=OUT/'window-classification.jsonl'
DB_SHA256='1c3f01791463cc7d0012c2a9fb7ddb35178ffc6e2868b253e2eea26bbac78258'
CLASSIFICATION_SHA256='b7d729a64417952cbe8bee8772bdda36c18a22dc5ee1b47754dd655f53918fb8'
CATEGORIES={
    'hr_candidates':('HR','MIXED','REVIEW_REQUIRED'),
    'hr':('HR',), 'non_hr':('NON_HR',), 'mixed':('MIXED',),
    'needs_review':('REVIEW_REQUIRED',), 'all':('HR','NON_HR','MIXED','REVIEW_REQUIRED'),
}
SCHEMA='''
CREATE TABLE metadata (source_manifest_sha TEXT, classification_sha TEXT);
CREATE VIRTUAL TABLE excerpts USING fts5(terms, source_id UNINDEXED, title UNINDEXED,
 section UNINDEXED, text UNINDEXED, window_id UNINDEXED, start UNINDEXED, end UNINDEXED,
 layout_review UNINDEXED, decision UNINDEXED, domain_label UNINDEXED, domain_method UNINDEXED);
'''


@lru_cache(maxsize=2)
def checked(db_stamp,classification_stamp):
    if (not DB_SHA256 or not CLASSIFICATION_SHA256 or scope.file_sha(DB)!=DB_SHA256
            or scope.file_sha(CLASSIFICATIONS)!=CLASSIFICATION_SHA256):
        raise ValueError('인사 재분류 검색 파일의 검증된 버전을 확인해야 해요.')
    with closing(sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)) as db:
        record=db.execute('SELECT source_manifest_sha,classification_sha FROM metadata').fetchone()
    if record!=(scope.MANIFEST_SHA256,CLASSIFICATION_SHA256):
        raise ValueError('인사 재분류 검색과 원문 버전이 다릅니다.')
    return True


def search(question,manifest,category='hr_candidates',limit=5):
    from . import hr_evidence
    if not 2<=len(question.strip())<=500 or hr_evidence.PRIVATE.search(unicodedata.normalize('NFKC',question)):
        raise ValueError('개인정보나 키 없이 일반 검색어를 입력해 주세요.')
    if category not in CATEGORIES:raise ValueError('알 수 없는 자료 분류입니다.')
    checked(scope.fingerprint(DB),scope.fingerprint(CLASSIFICATIONS))
    allowed={e['id']:e for e in manifest['units'] if e['structural_verified'] and not e['answer_eligible']}
    words=sorted(set(hr_evidence.tokens(question))-hr_evidence.STOPWORDS)
    if not words:return []
    expression=' OR '.join('"'+word.replace('"','""')+'"' for word in words)
    labels=CATEGORIES[category]
    slots=','.join('?' for _ in labels)
    query=f'SELECT *,bm25(excerpts) AS rank FROM excerpts WHERE excerpts MATCH ? AND domain_label IN ({slots}) ORDER BY rank,rowid LIMIT 100'
    records=[];seen=set()
    with closing(sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)) as db:
        db.execute('PRAGMA cache_size=-4096');db.row_factory=sqlite3.Row
        for r in db.execute(query,(expression,*labels)):
            if r['source_id'] not in allowed or r['source_id'] in seen:continue
            if hr_evidence.PRIVATE.search(r['text']):raise ValueError('공개 원문 범위를 확인해야 해요.')
            seen.add(r['source_id'])
            records.append(dict(id=r['source_id'],title=r['title'],section=r['section'],text=r['text'],
                score=-r['rank'],window_id=r['window_id'],source_range=[int(r['start']),int(r['end'])],
                domain_label=r['domain_label'],domain_method=r['domain_method'],
                company='KEPCO',human_approved=False,ktcs_applicable=False,answer_eligible=False,review_only=True,
                source_mapping_verified=True,excerpt_only=True,needs_layout_review=bool(r['layout_review']),
                source_scope_decision=r['decision'],hold_reasons=allowed[r['source_id']].get('hold_reasons',[])))
            if len(records)>=max(1,min(limit,5)):break
    return records


def counts():
    checked(scope.fingerprint(DB),scope.fingerprint(CLASSIFICATIONS))
    with closing(sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)) as db:
        db.execute('PRAGMA cache_size=-4096')
        values=dict(db.execute('SELECT domain_label,count(*) FROM excerpts GROUP BY domain_label'))
    return dict(available=True,window_counts=values,default_windows=sum(v for k,v in values.items() if k!='NON_HR'),
        non_hr_windows=values.get('NON_HR',0),classification_human_approved=False)
