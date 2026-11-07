"""Stream verified review windows into a new local SQLite FTS5 index. No external DB."""
import json
from pathlib import Path
import sqlite3
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from server import hr_source_scope as scope,hr_review_index,hr_evidence


def main():
    path=hr_review_index.DB
    if path.exists():raise SystemExit('The versioned review index already exists; preserve it.')
    manifest=json.loads(scope.MANIFEST.read_text(encoding='utf-8'))
    if scope.file_sha(scope.MANIFEST)!=scope.MANIFEST_SHA256:raise ValueError('MANIFEST_CHANGED')
    allowed={e['id'] for e in manifest['units'] if e['structural_verified'] and not e['answer_eligible']}
    windows={}
    with scope.INPUTS['windows'].open(encoding='utf-8') as f:
        for line in f:
            w=json.loads(line)
            if w['unit_record_id'] in allowed:windows.setdefault(w['unit_record_id'],[]).append(w)
    count=0
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA cache_size=-4096');db.executescript(hr_review_index.SCHEMA)
        db.execute('INSERT INTO metadata VALUES (?)',(scope.MANIFEST_SHA256,))
        with scope.INPUTS['reviewed_units'].open(encoding='utf-8') as f:
            for line in f:
                row=json.loads(line)
                if row['id'] not in allowed:continue
                for w in windows[row['id']]:
                    text=row['text'][w['start']:w['end']]
                    if scope.text_sha(text)!=w['text_sha256'] or hr_evidence.PRIVATE.search(text):raise ValueError('SOURCE_WINDOW_CHANGED')
                    terms=' '.join(hr_evidence.tokens(row['document_title']+' '+row['heading_path']+' '+text))
                    db.execute('INSERT INTO excerpts VALUES (?,?,?,?,?,?,?,?,?,?)',(terms,row['id'],row['document_title'],row['heading_path'],
                        text,w['id'],w['start'],w['end'],bool(row.get('needs_layout_review')),row['decision']))
                    count+=1
        db.execute("INSERT INTO excerpts(excerpts) VALUES ('optimize')")
    state=dict(method='local_fts5_bm25',review_units=len(allowed),review_windows=count,index_sha256=scope.file_sha(path),
        bytes=path.stat().st_size,manifest_sha256=scope.MANIFEST_SHA256,answer_eligible=False,
        source_excerpts_only=True,supabase_ingestion='HOLD',external_database_writes=0)
    (scope.OUT/'review-index.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(state))


if __name__=='__main__':main()
