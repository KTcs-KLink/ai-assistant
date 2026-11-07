"""Prepare bounded UI replay fixtures without changing the existing QA results."""
from pathlib import Path
import json

REPO = Path(__file__).resolve().parents[1]
QA = REPO.parent / 'outputs/klink_hr_answer_quality_20261107/final-display-replay/answers'
CASES = ['KEPCO-HR-01-001', 'KEPCO-HR-01-029', 'KEPCO-HR-08-002']
fixtures = []
for case in CASES:
    record = json.loads((QA / (case + '.json')).read_text(encoding='utf-8'))
    response = record['response']
    assert response['validation'] == 'FINAL_DETERMINISTIC_REVALIDATION_NOT_NEW_GENERATION'
    fixtures.append(dict(case_id=case, question=record['question'], response=response))
template = (REPO / 'scripts/verify_hr_condition_cards.js').read_text(encoding='utf-8')
target = REPO / 'output/playwright/verify_hr_condition_cards.generated.js'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(template.replace('/* LOCAL_REPLAY_FIXTURES */ []', json.dumps(fixtures, ensure_ascii=False)), encoding='utf-8')
print(f'Prepared {len(fixtures)} explicitly labelled local replays; model calls: 0')
