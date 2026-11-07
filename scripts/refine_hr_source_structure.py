"""Preserve audit v1 and quarantine repeated/reset paragraph sequences."""
from collections import Counter
import json
import shutil
import sys

from hr_source_audit import OUT,BASE,paragraph_order_issues,sha
from expand_hr_sources import readl,write,writel,holds


def main():
    path=OUT/'original-proofs.jsonl';previous=OUT/'post-layout-original-proofs.jsonl'
    if previous.exists():raise SystemExit('This structure refinement is already recorded.')
    shutil.copy2(path,previous)
    proofs={r['id']:r for r in readl(path)};changed=[];holds_count=Counter()
    for line in (BASE/'data/reviewed_units.jsonl').open(encoding='utf-8'):
        row=json.loads(line)
        if not row.get('searchable'):continue
        proof=proofs[row['id']]
        issues=paragraph_order_issues(row['text'])
        if issues:
            proof['issues']=sorted(set(proof['issues']+issues));proof['source_structure_verified']=False
            changed.append(dict(id=row['id'],title=row['document_title'],section=row['heading_path'],previously_eligible=row['answer_eligible'],issue=issues[0]))
        if not row['answer_eligible']:holds_count.update(holds(row,proof))
    temporary=path.with_suffix('.structure.tmp');writel(temporary,list(proofs.values()));temporary.replace(path)
    summary_path=OUT/'final-original-audit-summary.json';summary=json.loads(summary_path.read_text(encoding='utf-8'))
    shutil.copy2(summary_path,OUT/'post-layout-original-audit-summary.json')
    summary.update(paragraph_sequence_units_held=len(changed),held_reasons=dict(holds_count),audit_code_sha256=sha(__import__('pathlib').Path(__file__).with_name('hr_source_audit.py')))
    write(summary_path,summary);write(OUT/'paragraph-sequence-holds.json',changed)
    for name in ['review-overlay.json','review-summary.json','review-final-ledger.jsonl']:
        if (OUT/name).exists():shutil.copy2(OUT/name,OUT/('initial-199-'+name))
    print(json.dumps(dict(paragraph_sequence_holds=len(changed),previously_eligible_held=sum(c['previously_eligible'] for c in changed)),ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
