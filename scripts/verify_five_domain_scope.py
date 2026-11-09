"""Verify the local scope correction against retained sources; print counts only."""
from collections import Counter
import gc
from itertools import zip_longest
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
from urllib.parse import urlparse

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.build_five_domain_scope import ORIGINAL, OUT, PREVIOUS
from scripts.classify_domain_workflows import write
from scripts.reclassify_hr_review import readl
from server import five_domain_scope as five, domain_workflow as domain, hr_evidence, hr_source_scope as source


def read_units(root):
    paths = list((root/'by-domain').glob('*/*/units.jsonl'))
    if root == OUT:
        paths += [root/name/'units.jsonl' for name in ('outside-five-domains', 'review-required', 'privacy-hold')]
    values = {}; locations = {}
    for path in paths:
        for record in readl(path):
            assert record['id'] not in values, 'DUPLICATE_SOURCE_ID'
            values[record['id']] = record; locations[record['id']] = path
    return values, locations


def secret_scan(paths):
    values = dotenv_values(source.WORKSPACE/'.env')
    secrets = {v.encode('utf-8') for k, v in values.items()
               if v and len(v) >= 16 and re.search(r'KEY|SECRET|TOKEN|PASSWORD', k, re.I)}
    overlap = max(map(len, secrets), default=1)-1
    for path in paths:
        tail = b''
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1048576), b''):
                content = tail+block
                assert not any(value in content for value in secrets), 'SECRET_LITERAL_MATCH_REQUIRES_LOCAL_REVIEW'
                tail = content[-overlap:] if overlap else b''


def check_record(record, prior, tasks):
    projected = five.project(prior, tasks)
    assert record == projected, 'SOURCE_OR_SCOPE_PROJECTION_CHANGED'
    assert record['company'] == 'KEPCO' and not record['human_approved']
    assert not record['classification_grants_answer_use'] and not record['ktcs_applicable']
    assert record['scope_decision'] in five.SCOPES
    assert record['primary_domain'] is None or record['primary_domain'] in five.DOMAINS
    assert record['primary_path'] is None or record['primary_path'] in tasks
    assert set(record['direct_paths']) <= tasks.keys()
    assert all(a['code'] in tasks for a in record['assignments'])
    if record['scope_decision'] == 'IN_SCOPE':
        assert record['primary_path'] in record['direct_paths']
    else:
        assert not record['direct_paths'] and record['primary_path'] is None
    if record['scope_decision'] in ('OUTSIDE_SCOPE', 'REVIEW_REQUIRED', 'PRIVACY_HOLD'):
        assert record['primary_domain'] is None


def main():
    summary = json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    protocol = json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
    tax = json.loads((OUT/'taxonomy.json').read_text(encoding='utf-8'))
    original = json.loads(ORIGINAL.read_text(encoding='utf-8-sig'))
    assert tax == five.taxonomy(original) and len(tax['domains']) == 5 and len(tax['tasks']) == 34
    tasks = {t['code']: t for t in tax['tasks']}
    assert set(tasks) == {t['code'] for t in original['tasks']}
    assert all(source.file_sha(source.WORKSPACE/path) == sha for path, sha in protocol['original_baseline_sha256'].items())
    assert all(source.file_sha(PREVIOUS/path) == sha for path, sha in protocol['previous_result_sha256'].items())
    documents = {r['unit_id']: r for r in readl(source.INPUTS['documents'])}
    origins = {r['unit_id']: r for r in readl(source.INPUTS['normalized_documents'])}
    assert len(documents) == 203
    for uid, doc in documents.items():
        assert source.file_sha(Path(origins[uid]['original_local_path'])) == doc['source_file_sha256']
        assert source.file_sha(source.NORMALIZED/f'{uid}.txt') == doc['normalized_source_sha256']
    units, locations = read_units(OUT)
    assert len(units) == 10205
    prior_ids = set()
    for path in (PREVIOUS/'by-domain').glob('*/*/units.jsonl'):
        for prior in readl(path):
            assert prior['id'] not in prior_ids
            prior_ids.add(prior['id'])
            check_record(units[prior['id']], prior, tasks)
    assert prior_ids == set(units)
    for uid, record in units.items():
        if record['scope_decision'] == 'IN_SCOPE':
            parent, child = domain.folder_components(record['primary_path'], record['status'], tasks)
            expected = OUT/'by-domain'/parent/child/'units.jsonl'
        elif record['scope_decision'] == 'ADJACENT_SCOPE':
            name = five.DOMAINS[record['primary_domain']].replace('/', '·')
            expected = OUT/'by-domain'/(record['primary_domain']+'_'+name)/'세부업무검토/units.jsonl'
        else:
            folder = {'OUTSIDE_SCOPE': 'outside-five-domains', 'REVIEW_REQUIRED': 'review-required', 'PRIVACY_HOLD': 'privacy-hold'}[record['scope_decision']]
            expected = OUT/folder/'units.jsonl'
        assert locations[uid] == expected
        assert urlparse(record['original_download_url']).hostname == 'www.kepco.co.kr'
        if record['privacy_hold']:
            assert record['text'] is None and not record['assignments']
        else:
            assert domain.digest(record['text']) == record['text_sha256']
            assert not hr_evidence.PRIVATE.search(unicodedata.normalize('NFKC', record['text']))
            for assignment in record['assignments']:
                for support in assignment['supports']:
                    a, b = support['source_range']
                    assert record['text'][a:b] == support['quote']
    overlay_ids = set()
    for record in readl(OUT/'unit-classification.jsonl'):
        assert record['id'] not in overlay_ids
        overlay_ids.add(record['id'])
        assert record == {k: v for k, v in units[record['id']].items() if k != 'text'}
    assert overlay_ids == set(units)
    window_ids = set(); vector_rows = set(); window_counts = Counter(); window_answer = window_private = 0
    for record, prior in zip_longest(readl(OUT/'window-classification.jsonl'), readl(PREVIOUS/'window-classification.jsonl')):
        assert record is not None and prior is not None and record['id'] == prior['id']
        assert record['id'] not in window_ids
        window_ids.add(record['id']); vector_rows.add(record['vector_row']); window_counts[record['scope_decision']] += 1
        window_answer += record['service_answer_eligible']; window_private += record['privacy_hold']
        check_record(record, prior, tasks)
        parent = units[record['unit_record_id']]
        assert record['file_version_key'] == parent['file_version_key']
        if not record['privacy_hold']:
            assert domain.digest(parent['text'][record['start']:record['end']]) == record['text_sha256']
    assert sum(r['service_answer_eligible'] for r in units.values()) == 528
    assert len(window_ids) == 8511 and vector_rows == set(range(8511))
    assert window_answer == 536
    assert sum(r['privacy_hold'] for r in units.values()) == 11
    assert window_private == 205
    assert all(summary[key] == value for key, value in five.counts(units.values()).items())
    assert summary['window_scope_counts'] == dict(window_counts)
    assert source.file_sha(OUT/'unit-classification.jsonl') == summary['unit_classification_sha256']
    assert source.file_sha(OUT/'window-classification.jsonl') == summary['window_classification_sha256']
    expected_memberships = (dict(id=r['id'], workflow=a['code'], supports=a['supports'], scope_decision=r['scope_decision'])
                           for r in readl(OUT/'unit-classification.jsonl') for a in r['assignments'])
    for actual, expected in zip_longest(readl(OUT/'workflow-memberships.jsonl'), expected_memberships):
        assert actual == expected
    # Release full source records before parsing the browser's smaller preview payload.
    expected_view = {uid: dict(preview=(r['text'] or '')[:240], direct_paths=r['direct_paths'],
        scope_decision=r['scope_decision'], privacy_hold=r['privacy_hold']) for uid, r in units.items()}
    del units
    gc.collect()
    html = (OUT/'index.html').read_text(encoding='utf-8')
    begin = html.index('<script type="application/json" id="report-data">')+len('<script type="application/json" id="report-data">')
    end = html.index('</script>', begin)
    payload = json.loads(html[begin:end])
    del html
    assert len(payload['records']) == 10205 and {r['id'] for r in payload['records']} == set(expected_view)
    assert payload['taxonomy'] == tax and payload['summary'] == summary
    for row in payload['records']:
        record = expected_view[row['id']]
        assert row['preview'] == record['preview']
        assert row['direct_paths'] == record['direct_paths'] and row['scope_decision'] == record['scope_decision']
        assert (OUT/row['export']).resolve() == locations[row['id']].resolve()
        if row['privacy_hold']:
            assert not row['preview'] and not row['links']
    changed = subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], cwd=REPO, text=True).splitlines()
    changed += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=REPO, text=True).splitlines()
    paths = [REPO/name for name in set(changed) if (REPO/name).is_file()]
    paths += [path for path in OUT.rglob('*') if path.is_file()]
    secret_scan(paths)
    result = dict(taxonomy_domains=5, taxonomy_workflows=34, extra_domain_or_workflow_codes=0,
        source_documents_verified=203, source_units_verified=10205, existing_vector_windows_verified=8511,
        all_source_ids_present=True, all_source_text_and_metadata_preserved=True,
        original_files_normalized_text_chunks_vectors_and_gold_unchanged=True,
        previous_expanded_classification_preserved=True, all_quotes_match_source=True,
        all_primary_folders_disjoint=True, memberships_only_original_tasks=True,
        scope_counts=summary['scope_counts'], existing_answer_units=528, existing_answer_windows=536,
        privacy_hold_units=11, privacy_hold_windows=205, private_body_exported=False,
        files_scanned_for_actual_secret_literals=len(paths), actual_secret_literal_matches=0,
        model_calls=0, new_document_embeddings=0, independent_human_approval=False,
        supabase_ingestion='HOLD', external_database_writes=0)
    write(OUT/'artifact-verification.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
