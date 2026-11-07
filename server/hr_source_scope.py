"""Versioned, local-only expanded source audit. Baseline remains available.

A verified text mapping is not semantic, layout, current-policy or human approval.
Review-only candidates never authorize generated answers.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE/'outputs/kepco_hr_full_20261102'
NORMALIZED_ROOT = WORKSPACE/'outputs/kepco_parsed_normalized_20261025'
NORMALIZED = NORMALIZED_ROOT/'normalized_text'
INDEX = WORKSPACE/'outputs/kepco_hr_full_eval_960_20261102/indexes'
OUT = WORKSPACE/'outputs/klink_hr_source_expansion_20261107'
MANIFEST = OUT/'source-manifest-v2.json'
MANIFEST_SHA256 = '12855f512460820948318914271662dbb453b24afb6ce57e81bf5427d0d440ab'
MODEL_REVISION = '5617a9f61b028005a4858fdac845db406aefb181'
MODEL_WEIGHTS = '993b2248881724788dcab8c644a91dfd63584b6e5604ff2037cb5541e1e38e7e'
INPUTS = dict(reviewed_units=SOURCE/'data/reviewed_units.jsonl', units=SOURCE/'data/units.jsonl',
    documents=SOURCE/'data/documents.jsonl', parents=SOURCE/'data/parents.jsonl',
    normalized_documents=NORMALIZED_ROOT/'data/documents.jsonl', windows=SOURCE/'indexes/windows.jsonl',
    vectors=INDEX/'windows.npy', vector_metadata=INDEX/'windows_vectors.json')
UNIT_FIELDS = ('id', 'child_id', 'parent_id', 'unit_id', 'document_title', 'heading_path', 'article_label',
    'parent_range', 'text_sha256', 'parent_text_sha256', 'source_parts', 'kind', 'source_file_sha256',
    'source_url', 'file_version_key', 'child_level', 'sequence', 'source_mapping_uncovered_ranges')


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576), b''):digest.update(block)
    return digest.hexdigest()


def unit_signature(row):
    return text_sha(json.dumps({k:row.get(k) for k in UNIT_FIELDS}, sort_keys=True, ensure_ascii=False))


def expanded():
    return os.getenv('KLINK_HR_SOURCE_SCOPE', 'baseline') == 'expanded'


def fingerprint(path):
    stat = path.stat()
    return (str(path), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=2)
def _checked_inputs(stamps):
    if file_sha(MANIFEST) != MANIFEST_SHA256:
        raise ValueError('검증이 완료된 검색 범위 기록이 변경됐어요.')
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if (manifest.get('schema') != 'klink-hr-verified-source-scope-v1' or manifest.get('company') != 'KEPCO'
            or manifest.get('human_approved') is not False or manifest.get('ktcs_applicable') is not False
            or manifest.get('supabase_ingestion') != 'HOLD' or manifest.get('inputs') != {name:file_sha(p) for name,p in INPUTS.items()}):
        raise ValueError('한전 원문 검증 기록과 현재 파일이 일치하지 않아요.')
    with INPUTS['documents'].open(encoding='utf-8') as f:
        manifest['_document_titles']={r['unit_id']:r['document_title'] for line in f if (r:=json.loads(line))}
    originals = {}
    with INPUTS['normalized_documents'].open(encoding='utf-8') as f:
        for line in f:
            row=json.loads(line); originals[row['unit_id']]=row
    paths = []
    for uid, doc in manifest['documents'].items():
        origin = originals[uid]
        raw, norm = Path(origin['original_local_path']), NORMALIZED/f'{uid}.txt'
        if (doc.get('errors') or doc['source_sha256'] != origin['unit_file_sha256']
                or doc['normalized_sha256'] != origin['normalized_text_sha256']):
            raise ValueError('원본 문서의 검증 상태를 확인해야 해요.')
        paths.extend([(raw,doc['source_sha256']), (norm,doc['normalized_sha256'])])
    return manifest, tuple(paths)


@lru_cache(maxsize=2)
def _checked_originals(stamps, expected):
    if any(file_sha(Path(path)) != sha for path,sha in expected):
        raise ValueError('원본 파일 또는 정규화 원문의 내용이 달라졌어요.')
    return True


def load(corpus_path):
    if not expanded():return None
    if Path(corpus_path).resolve() != INPUTS['reviewed_units'].resolve():
        raise ValueError('확장 검색은 검증된 한전 원문에서만 실행해요.')
    stamps = tuple(fingerprint(p) for p in [MANIFEST, *INPUTS.values()])
    manifest, paths = _checked_inputs(stamps)
    _checked_originals(tuple(fingerprint(path) for path,_ in paths), tuple((str(path),sha) for path,sha in paths))
    return manifest


def signature(entries):
    return frozenset((e['id'], e['text_sha256'], e['source_file_sha256'], e['file_version_key']) for e in entries)


def held_named_documents(question, corpus_path):
    """Do not answer a held specialist document with a different general rule."""
    if not expanded() or corpus_path is None:return []
    from .hr_evidence import title_key
    manifest=load(corpus_path)
    titles=manifest.get('_document_titles',{})
    compact=title_key(question)
    matched={title_key(title):title for title in titles.values() if title_key(title) in compact}
    names={name for name in matched if not any(name!=other and name in other for other in matched)}
    available={title_key(titles[e['unit_id']]) for e in manifest['units'] if e['answer_eligible'] and e['structural_verified']}
    return sorted(matched[name] for name in names if name not in available)
