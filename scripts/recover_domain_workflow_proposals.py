"""Revalidate retained model responses without new API calls or fuzzy quote repair."""
from collections import defaultdict
import json
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.classify_domain_workflows import OUT, context, result_path
from scripts.reclassify_hr_review import write
from server import domain_workflow as domain, hr_evidence


def main():
    protocol, pieces, _, tasks = context()
    candidates = defaultdict(list); active = set()
    for path in (OUT/'calls').glob('*.json'):
        call = json.loads(path.read_text(encoding='utf-8'))
        if call['status'] == 'STARTED':
            active.update(call['ids'])
        for finding in call.get('proposals', []):
            if finding['id'] in pieces and not result_path(finding['id']).exists():
                candidates[finding['id']].append((path.name, call, finding))
    recovered = []
    for pid, responses in candidates.items():
        # The main runner may still be retrying a batch. Only recover a failed
        # item after its three genuine response records have been retained.
        if pid in active or len(responses) < 3 or result_path(pid).exists():
            continue
        for filename, call, original in reversed(responses):
            raw = dict(original); unique = []; seen = set()
            for assignment in raw['assignments']:
                fingerprint = json.dumps(assignment, sort_keys=True, ensure_ascii=False)
                if fingerprint not in seen:
                    unique.append(assignment); seen.add(fingerprint)
            raw['assignments'] = unique
            try:
                checked = domain.validate(domain.Finding.model_validate(raw), pieces[pid], tasks, hr_evidence.PRIVATE)
            except (ValueError, KeyError, TypeError):
                continue
            normalized = len(unique) != len(original['assignments'])
            checked.update(unit_record_id=pieces[pid]['unit_record_id'], source_range=pieces[pid]['source_range'],
                model=protocol['model'], method='RECOVERED_RETAINED_GPT_PROPOSAL_WITH_CODE_CHECKS',
                call_record=filename, exact_duplicate_assignments_removed=normalized, new_model_calls=0)
            write(result_path(pid), checked)
            recovered.append(dict(piece_id=pid, call_record=filename, exact_duplicate_assignments_removed=normalized))
            break
    record = dict(recovered_pieces=recovered, new_model_calls=0,
        source_quotes_changed=False, independent_human_approval=False)
    write(OUT/'recovery-runs'/f'{uuid.uuid4().hex}.json', record)
    print(json.dumps(dict(recovered_pieces=len(recovered), new_model_calls=0)))


if __name__ == '__main__':
    main()
