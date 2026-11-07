"""Read-only, source-wide provenance audit. Never promotes a held semantic/layout review.

Original binaries, normalized text, complete article units and vector windows are
compared separately. Outputs are a new local manifest and an explicit hold list;
no source, gold set, embedding, environment file or database is modified.
"""
from __future__ import annotations

import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
import sys
from urllib.parse import urlsplit

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from server import hr_source_scope as scope


def rows(path):
    with path.open(encoding='utf-8') as file:
        for line in file:
            if line.strip():
                yield json.loads(line)


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def mapping_errors(row, parent, normalized):
    errors = []
    text = row['text']
    if scope.text_sha(text) != row['text_sha256']:
        errors.append('UNIT_TEXT_HASH')
    a, b = row['parent_range']
    if (not parent or parent['text_sha256'] != row['parent_text_sha256'] or
            not 0 <= a < b <= len(parent['text']) or parent['text'][a:b] != text):
        return errors+['PARENT_RANGE_OR_HASH']
    if scope.text_sha(parent['text']) != parent['text_sha256']:
        errors.append('PARENT_TEXT_HASH')
    coverage = bytearray(len(text))
    previous = -1
    for part in row.get('source_parts', []):
        x, y = part['excerpt_text_range']
        u, v = part['source_normalized_range']
        pa, pb = part['parent_text_range']
        if (not 0 <= x < y <= len(text) or not 0 <= u < v <= len(normalized) or
                pa != a+x or pb != a+y or text[x:y] != normalized[u:v] or
                not part.get('source_location') or not part.get('source_method')):
            errors.append('NORMALIZED_SOURCE_SPAN')
            continue
        if u < previous:
            errors.append('SOURCE_ORDER')
        previous = v
        coverage[x:y] = b'\1'*(y-x)
    if not coverage or any(not covered and not char.isspace() for char, covered in zip(text, coverage)):
        errors.append('UNMAPPED_NON_WHITESPACE')
    return sorted(set(errors))


def additional_answer_holds(row, legacy_baseline):
    """An exact source mapping cannot repair a mixed table or missing body.

    Retain the previous 449-unit scope as a versioned baseline; do not interpret
    its inherited chapter-level flags as new layout approval. Newly added
    material must also pass these conservative article-quality checks.
    """
    body=re.sub(r'^\s*제\s*\d+\s*조(?:\s*의\s*\d+)?\s*\([^)]*\)\s*','',row['text'],count=1)
    holds=[]
    if len(body.strip())<8:holds.append('ARTICLE_BODY_MISSING_OR_TOO_SHORT')
    if not legacy_baseline:
        permitted={'PARENT_JOIN_WHITESPACE_NOT_SOURCE_MAPPED','NO_CHAPTER_STRUCTURE_IN_SOURCE',
            'ARTICLE_NUMBER_RESTART_REVIEW','CIRCLED_PARAGRAPH_SEQUENCE_REVIEW'}
        if set(row.get('quality_flags',[]))-permitted:
            holds.append('NEW_SOURCE_LAYOUT_OR_BOUNDARY_UNVERIFIED')
        markers=[ord(m[1])-0x245f for m in re.finditer(r'(?m)^\s*([①-⑳])',row['text'])]
        if markers and markers!=list(range(1,len(markers)+1)):
            holds.append('PARAGRAPH_SEQUENCE_INCOMPLETE')
    return holds


def main():
    if scope.MANIFEST.exists():
        raise SystemExit('A frozen audit already exists. Preserve it; use a new version for another audit.')
    scope.OUT.mkdir(parents=True, exist_ok=True)
    inputs = {name: scope.file_sha(path) for name, path in scope.INPUTS.items()}
    documents = {d['unit_id']: d for d in rows(scope.INPUTS['documents'])}
    originals = {d['unit_id']: d for d in rows(scope.INPUTS['normalized_documents'])}
    normalized, document_checks = {}, {}
    for uid, doc in documents.items():
        origin = originals[uid]
        raw_path = Path(origin['original_local_path'])
        norm_path = scope.NORMALIZED/f'{uid}.txt'
        errors = []
        raw_hash = scope.file_sha(raw_path) if raw_path.is_file() else None
        norm = norm_path.read_text(encoding='utf-8') if norm_path.is_file() else ''
        if raw_hash != doc['source_file_sha256'] or raw_hash != origin['unit_file_sha256']:
            errors.append('ORIGINAL_FILE_HASH')
        if scope.text_sha(norm) != doc['normalized_source_sha256'] or scope.text_sha(norm) != origin['normalized_text_sha256']:
            errors.append('NORMALIZED_FILE_HASH')
        if doc.get('source_organization') != 'KEPCO' or urlsplit(doc['source_url']).hostname not in {'www.kepco.co.kr', 'kepco.co.kr'}:
            errors.append('COMPANY_OR_ORIGIN')
        if doc['file_version_key'] != f'{uid}:{raw_hash}':
            errors.append('DOCUMENT_VERSION')
        normalized[uid] = norm
        document_checks[uid] = dict(source_sha256=raw_hash, normalized_sha256=scope.text_sha(norm), errors=errors)
    # Store just parent text, not hundreds of MB of duplicated source metadata.
    parents = {r['parent_id']: {k:r[k] for k in ['text', 'text_sha256']} for r in rows(scope.INPUTS['parents'])}
    unit_signatures = {r['id']: scope.unit_signature(r) for r in rows(scope.INPUTS['units'])}
    candidates, findings, baseline = {}, [], set()
    totals = Counter()
    from server.hr_evidence import HR_TITLES, title_key, PRIVATE
    for row in rows(scope.INPUTS['reviewed_units']):
        totals['preserved_units'] += 1
        if not row.get('searchable'):
            totals['non_searchable_units'] += 1
            continue
        uid = row['unit_id']
        errors = list(document_checks[uid]['errors'])
        if unit_signatures.get(row['id']) != scope.unit_signature(row):
            errors.append('UNREVIEWED_SOURCE_RECORD_CHANGED')
        errors += mapping_errors(row, parents.get(row['parent_id']), normalized[uid])
        if row['source_file_sha256'] != documents[uid]['source_file_sha256'] or row['file_version_key'] != documents[uid]['file_version_key']:
            errors.append('UNIT_VERSION')
        if PRIVATE.search(row['text']):
            errors.append('PRIVATE_DATA_PATTERN')
        is_baseline = title_key(row['document_title']) in HR_TITLES and all(row.get(k) is True for k in ['answer_eligible', 'source_scope_reviewed'])
        if is_baseline:
            baseline.add(row['id'])
        extra_holds=additional_answer_holds(row,is_baseline)
        eligible = (not errors and not extra_holds and row.get('answer_eligible') is True and row.get('decision') == 'HR'
                    and row.get('source_scope_reviewed') is True and row.get('kind') == 'ARTICLE'
                    and not row.get('needs_layout_review') and row.get('scope_gate') in {'HR_CORE', 'HR_SUPPORT_DIRECT_ACTOR_ACTION'}
                    and row.get('quote') and row['quote'] in row['text'])
        holds = list(extra_holds)
        if not eligible:
            if row.get('decision') != 'HR': holds.append('HR_SCOPE_REVIEW_REQUIRED')
            if row.get('kind') != 'ARTICLE': holds.append('INCOMPLETE_ARTICLE_OR_FORM')
            if row.get('needs_layout_review'): holds.append('LAYOUT_REVIEW_REQUIRED')
            if not row.get('answer_eligible'): holds.append('EXISTING_ANSWER_GATE_HELD')
            holds += row.get('local_gate_reasons', [])
        entry = dict(id=row['id'], text_sha256=row['text_sha256'], source_file_sha256=row['source_file_sha256'],
            file_version_key=row['file_version_key'], unit_id=uid, answer_eligible=bool(eligible),
            structural_verified=not errors, hold_reasons=sorted(set(holds)), original_eligibility=row['answer_eligible'])
        candidates[row['id']] = entry
        findings.append(dict(**entry, title=row['document_title'], section=row['heading_path'],
            verification_errors=sorted(set(errors)), quality_flags=row.get('quality_flags', []),
            employee_scope=row.get('employee_scope'), human_approved=False))
        totals['search_candidates'] += 1
    del parents, normalized, unit_signatures
    windows = list(rows(scope.INPUTS['windows']))
    vectors = np.load(scope.INPUTS['vectors'], mmap_mode='r', allow_pickle=False)
    meta = json.loads(scope.INPUTS['vector_metadata'].read_text(encoding='utf-8'))
    if (vectors.shape != (len(windows), 1024) or vectors.dtype != np.float32 or
            meta['ids'] != [w['id'] for w in windows] or meta['source_sha256'] != inputs['reviewed_units'] or
            meta['vectors_sha256'] != inputs['vectors'] or meta['windows_sha256'] != inputs['windows'] or
            meta['model'] != 'BAAI/bge-m3' or meta['revision'] != scope.MODEL_REVISION or
            meta['weights_sha256'] != scope.MODEL_WEIGHTS or meta['normalized'] is not True or meta['truncation'] is not False):
        raise ValueError('VECTOR_PROVENANCE')
    for start in range(0, len(vectors), 512):
        block = vectors[start:start+512]
        if not np.isfinite(block).all() or np.max(np.abs(np.linalg.norm(block, axis=1)-1)) > 1e-4:
            raise ValueError('VECTOR_NUMERIC_VALIDATION')
    # A second stream only retains the source text needed for window checks.
    texts = {r['id']:r['text'] for r in rows(scope.INPUTS['reviewed_units']) if r['id'] in candidates}
    window_counts = Counter()
    for w in windows:
        cid = w['unit_record_id']; entry = candidates[cid]; text = texts[cid]
        if (not w.get('retrieval_only') or not 0 <= w['start'] < w['end'] <= len(text) or
                scope.text_sha(text[w['start']:w['end']]) != w['text_sha256'] or
                w['source_file_sha256'] != entry['source_file_sha256']):
            raise ValueError('WINDOW_SOURCE_MAPPING')
        window_counts[cid] += 1
    if set(window_counts) != set(candidates):
        raise ValueError('MISSING_WINDOW')
    eligible = [e for e in candidates.values() if e['answer_eligible']]
    review_only = [e for e in candidates.values() if e['structural_verified'] and not e['answer_eligible']]
    active_docs = {e['unit_id'] for e in eligible+review_only}
    manifest = dict(schema='klink-hr-verified-source-scope-v1', company='KEPCO', ktcs_applicable=False,
        human_approved=False, inputs=inputs, documents={k:document_checks[k] for k in sorted(active_docs)},
        units=list(candidates.values()), source_audit_only=True, new_model_calls=0, new_document_embeddings=0,
        supabase_ingestion='HOLD')
    write(scope.MANIFEST, manifest)
    with (scope.OUT/'unit-audit-v2.jsonl').open('w', encoding='utf-8') as f:
        for r in findings:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    summary = dict(totals, source_documents=len(documents), original_files_verified=sum(not d['errors'] for d in document_checks.values()),
        all_windows_checked=len(windows), vectors_shape=list(vectors.shape), baseline_units=len(baseline),
        answer_units=len(eligible), answer_windows=sum(window_counts[e['id']] for e in eligible),
        answer_documents=len({e['unit_id'] for e in eligible}), new_answer_units=len({e['id'] for e in eligible}-baseline),
        previous_units_held=len(baseline-{e['id'] for e in eligible}),
        review_only_units=len(review_only), review_only_windows=sum(window_counts[e['id']] for e in review_only),
        failed_source_units=sum(not e['structural_verified'] for e in candidates.values()),
        failed_source_windows=sum(window_counts[e['id']] for e in candidates.values() if not e['structural_verified']),
        hold_reasons=dict(Counter(reason for e in candidates.values() if not e['answer_eligible'] for reason in e['hold_reasons'])),
        source_errors=dict(Counter(reason for e in findings for reason in e['verification_errors'])),
        manifest_sha256=scope.file_sha(scope.MANIFEST), new_model_calls=0, new_document_embeddings=0,
        supabase_ingestion='HOLD', human_approved=False, ktcs_applicable=False)
    write(scope.OUT/'summary-v2.json', summary)
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == '__main__':
    main()
