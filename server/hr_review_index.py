"""Small, read-only local FTS index for held source excerpts. Never answer evidence."""
from functools import lru_cache
import sqlite3

from . import hr_source_scope as scope

DB = scope.OUT/'review-search.sqlite3'
DB_SHA256 = '2964e6aa79becf42ad0cf11342577d4d1fe1bd5762191addb7fc2974101fdbb1'
SCHEMA = '''
CREATE TABLE metadata (manifest_sha TEXT NOT NULL);
CREATE VIRTUAL TABLE excerpts USING fts5(terms, source_id UNINDEXED, title UNINDEXED,
 section UNINDEXED, text UNINDEXED, window_id UNINDEXED, start UNINDEXED, end UNINDEXED,
 layout_review UNINDEXED, decision UNINDEXED);
'''


@lru_cache(maxsize=2)
def checked(stamp, manifest_sha):
    if not DB_SHA256 or scope.file_sha(DB) != DB_SHA256:
        raise ValueError('추가 검토 검색 색인의 버전을 확인해야 해요.')
    with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute('SELECT manifest_sha FROM metadata').fetchone()
    if row != (manifest_sha,):raise ValueError('추가 검토 검색 색인이 원문 검증 기록과 다릅니다.')
    return True


def search(question, limit=5):
    from . import hr_evidence
    if not 2 <= len(question.strip()) <= 500 or hr_evidence.PRIVATE.search(question):
        raise ValueError('개인정보나 키 없이 일반 검색어를 입력해 주세요.')
    path=hr_evidence.local_evidence.corpus_path()
    manifest=scope.load(path) if path else None
    if manifest is None:return []
    checked(scope.fingerprint(DB),scope.MANIFEST_SHA256)
    allowed={e['id']:e for e in manifest['units'] if e['structural_verified'] and not e['answer_eligible']}
    words=sorted(set(hr_evidence.tokens(question))-hr_evidence.STOPWORDS)
    if not words:return []
    expression=' OR '.join('"'+w.replace('"','""')+'"' for w in words)
    result=[];seen=set()
    with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA cache_size=-4096')
        db.row_factory=sqlite3.Row
        for r in db.execute('SELECT *, bm25(excerpts) AS rank FROM excerpts WHERE excerpts MATCH ? ORDER BY rank, rowid LIMIT 100',(expression,)):
            if r['source_id'] not in allowed or r['source_id'] in seen:continue
            if hr_evidence.PRIVATE.search(r['text']):raise ValueError('추가 검토 구간의 공개 범위를 확인해야 해요.')
            seen.add(r['source_id'])
            result.append(dict(id=r['source_id'],title=r['title'],section=r['section'],text=r['text'],
                score=-r['rank'],window_id=r['window_id'],source_range=[int(r['start']),int(r['end'])],
                company='KEPCO',ktcs_applicable=False,human_approved=False,answer_eligible=False,review_only=True,
                source_mapping_verified=True,excerpt_only=True,hold_reasons=allowed[r['source_id']].get('hold_reasons',[]),
                needs_layout_review=bool(r['layout_review']),source_scope_decision=r['decision']))
            if len(result)>=max(1,min(limit,5)):break
    return result
