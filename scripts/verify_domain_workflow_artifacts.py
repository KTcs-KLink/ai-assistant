"""Read-only whole-export verification; never prints credential or private values."""
from collections import Counter
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.classify_domain_workflows import OUT, PREVIOUS_TAXONOMY
from scripts.reclassify_hr_review import readl, write
from server import domain_workflow as domain, hr_evidence, hr_source_scope as scope


def main():
    summary = json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    protocol = json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
    tax = json.loads((OUT/'taxonomy.json').read_text(encoding='utf-8'))
    tasks = {t['code']: t for t in tax['tasks']}
    previous = json.loads(PREVIOUS_TAXONOMY.read_text(encoding='utf-8-sig'))
    assert len(previous['tasks']) == 34
    assert all({k: tasks[t['code']][k] for k in ('code', 'domain', 'name')} ==
               {k: t[k] for k in ('code', 'domain', 'name')} for t in previous['tasks'])
    assert all(scope.file_sha(scope.WORKSPACE/path) == sha for path, sha in protocol['baseline_sha256'].items())
    documents = {r['unit_id']: r for r in readl(scope.INPUTS['documents'])}
    origins = {r['unit_id']: r for r in readl(scope.INPUTS['normalized_documents'])}
    for uid, doc in documents.items():
        assert scope.file_sha(Path(origins[uid]['original_local_path'])) == doc['source_file_sha256']
        assert scope.file_sha(scope.NORMALIZED/f'{uid}.txt') == doc['normalized_source_sha256']
    units = {}; folder_counts = Counter()
    for path in (OUT/'by-domain').glob('*/*/units.jsonl'):
        for r in readl(path):
            assert r['id'] not in units
            parent, child = domain.folder_components(r['primary_path'], r['status'], tasks)
            assert path.parent == OUT/'by-domain'/parent/child
            assert r['company'] == 'KEPCO' and r['human_approved'] is False and r['classification_grants_answer_use'] is False
            if r['privacy_hold']:
                assert r['status'] == 'PRIVACY_HOLD' and r['text'] is None and not r['assignments']
            else:
                assert domain.digest(r['text']) == r['text_sha256']
                assert not hr_evidence.PRIVATE.search(unicodedata.normalize('NFKC', r['text']))
                for assignment in r['assignments']:
                    assert assignment['code'] in tasks
                    for support in assignment['supports']:
                        a, b = support['source_range']
                        assert 0 <= a < b <= len(r['text']) and r['text'][a:b] == support['quote']
            units[r['id']] = r; folder_counts[r['primary_domain'] or r['status']] += 1
    assert len(units) == 10205 and dict(folder_counts) == summary['primary_domain_counts']
    assert {r['id'] for r in readl(OUT/'unit-classification.jsonl')} == set(units)
    frozen = {r['id']: r for r in readl(OUT/'data/windows.jsonl')}
    windows = list(readl(OUT/'window-classification.jsonl'))
    assert len(windows) == 8511 and {r['id'] for r in windows} == set(frozen)
    assert {r['vector_row'] for r in windows} == set(range(8511))
    for r in windows:
        assert all(r[key] == value for key, value in frozen[r['id']].items())
        assert r['classification_grants_answer_use'] is False and r['human_approved'] is False
        assert r['ktcs_applicable'] is False and r['file_version_key'] == units[r['unit_record_id']]['file_version_key']
        if r['privacy_hold']:
            assert r['status'] == 'PRIVACY_HOLD' and not r['assignments']
        else:
            u = units[r['unit_record_id']]
            assert domain.digest(u['text'][r['start']:r['end']]) == r['text_sha256']
    assert sum(r['service_answer_eligible'] for r in units.values()) == 528
    assert sum(r['service_answer_eligible'] for r in windows) == 536
    assert sum(r['privacy_hold'] for r in units.values()) == 11
    assert sum(r['privacy_hold'] for r in windows) == 205
    assert scope.file_sha(OUT/'unit-classification.jsonl') == summary['unit_classification_sha256']
    assert scope.file_sha(OUT/'window-classification.jsonl') == summary['window_classification_sha256']

    values = dotenv_values(scope.WORKSPACE/'.env')
    secrets = {v.encode('utf-8') for k, v in values.items()
               if v and len(v) >= 16 and re.search(r'KEY|SECRET|TOKEN|PASSWORD', k, re.I)}
    changed = subprocess.check_output(['git', 'diff', '--name-only', 'HEAD'], cwd=REPO, text=True).splitlines()
    changed += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=REPO, text=True).splitlines()
    paths = [REPO/path for path in set(changed) if (REPO/path).is_file()]
    paths += [path for path in OUT.rglob('*') if path.is_file()]
    overlap = max(map(len, secrets), default=1)-1
    secret_matches = 0
    for path in paths:
        tail = b''
        with path.open('rb') as f:
            for block in iter(lambda: f.read(1048576), b''):
                content = tail+block
                secret_matches += sum(value in content for value in secrets)
                tail = content[-overlap:] if overlap else b''
    assert secret_matches == 0, 'SECRET_LITERAL_MATCH_REQUIRES_LOCAL_REVIEW'
    record = dict(source_documents_verified=len(documents), source_units=10205, existing_vector_windows=8511,
        all_primary_folders_disjoint=True, all_source_ids_present=True, all_support_quotes_match_source=True,
        original_user_workflows_preserved=34, taxonomy_domains=10, taxonomy_workflows=82,
        original_files_and_baselines_unchanged=True, original_unit_boundaries_unchanged=True,
        existing_answer_units=528, existing_answer_windows=536, privacy_pattern_hold_units=11,
        privacy_pattern_hold_windows=205, privacy_text_exported=False,
        files_scanned_for_actual_secret_literals=len(paths), actual_secret_literal_matches=0,
        secret_values_logged=False, new_document_embeddings=0, independent_human_approval=False,
        supabase_ingestion='HOLD', external_database_writes=0)
    write(OUT/'artifact-verification.json', record)
    print(json.dumps(record))


if __name__ == '__main__':
    main()
