"""Resolve observed page-header false positives and retain verified form context.

The first audit snapshot is preserved. Original files, text units and vector
arrays are never edited. Ambiguous body tables and text mismatches stay held.
"""
from collections import Counter,defaultdict
import hashlib
import json
import re
import shutil
import sys

from hr_source_audit import BASE,NORMALIZED,OUT,OriginalAudit,readl,sha
from expand_hr_sources import write,writel,holds
from server import hr_evidence


def main():
    proof_path=OUT/'original-proofs.jsonl'
    proofs={p['id']:p for p in readl(proof_path)}
    if len(proofs)!=3870:raise SystemExit('Finish the initial 3870-unit audit first.')
    preserved=OUT/'initial-original-proofs.jsonl'
    if preserved.exists():
        if (OUT/'final-original-audit-summary.json').exists() or sha(preserved)!=sha(proof_path):raise SystemExit('Final audit is already published; preserve its history before repeating.')
    else:shutil.copy2(proof_path,preserved)
    documents={d['unit_id']:d for d in readl(NORMALIZED/'data/documents.jsonl')}
    rows=[];recheck=[]
    with (BASE/'data/reviewed_units.jsonl').open(encoding='utf-8') as file:
        for line in file:
            r=json.loads(line)
            if not r.get('searchable'):continue
            r['_lo']=min((p['source_normalized_range'][0] for p in r.get('source_parts',[])),default=None)
            if 'TABLE_LAYOUT_REVIEW' in proofs[r['id']]['issues'] and hr_evidence.title_key(r['document_title'])=='감사규정시행지침':
                recheck.append(r)
            elif documents[r['unit_id']]['format']!='pdf':r.pop('source_parts',None)
            rows.append(r)
    audit=OriginalAudit({r['unit_id'] for r in rows})
    for uid in audit.documents:audit.file_proof(uid)
    print(json.dumps(dict(stage='files_verified',documents=len(audit.file_proofs),header_targets=len(recheck))),flush=True)
    resolved=[]
    for index,row in enumerate(recheck,1):
        before=proofs[row['id']];after=audit.audit(row)
        after['audit_method']='ORIGINAL_BINARY_TEXT_LAYER_WITH_VERIFIED_DOCUMENT_CONTROL_HEADER'
        if before.get('recovered_structure'):
            after.update(source_structure_verified='PDF_MULTICOLUMN_READING_ORDER_REVIEW' not in after['issues'],recovered_structure=before['recovered_structure'])
        proofs[row['id']]=after
        if before['issues']!=after['issues']:resolved.append(dict(id=row['id'],before=before['issues'],after=after['issues']))
        if index%25==0:print(json.dumps(dict(header_recheck=index,total=len(recheck))),flush=True)
    geometry_count=0
    for index,row in enumerate(rows,1):
        proof=proofs[row['id']]
        if proof['original_blocks_checked'] and documents[row['unit_id']]['format']=='pdf':
            issues=audit.geometry_issues(row)
            if issues:
                proof['issues']=sorted(set(proof['issues']+issues));proof['source_structure_verified']=False;geometry_count+=1
        if index%500==0:print(json.dumps(dict(stage='column_order_checked',units=index,total=3870)),flush=True)
    contexts={};role_count=0
    for row in rows:
        uid=row['unit_id']
        if uid not in contexts:
            _,text=audit.document_texts(uid);items=[]
            pattern=r'(?m)^[ \t]*(?:\[[^\]\n]+\][ \t]*)?[가-힣 ·ㆍ]{0,30}계약서[ \t]*$'
            for match in re.finditer(pattern,text):
                title=match.group().strip()
                if not re.search(r'근로|단시간|고용',title):continue
                following=re.search(r'(?m)^[ \t]*(?:[〈<\[(]?별[ \t]*(?:표|지)[ \t]*\d|부[ \t]*칙)',text[match.end():])
                end=match.end()+following.start() if following else len(text)
                synthetic=dict(id='FORM-HEADER',unit_id=uid,text=match.group(),text_sha256=hashlib.sha256(match.group().encode()).hexdigest(),
                    source_file_sha256=row['source_file_sha256'],kind='UNSTRUCTURED',article_label='',quality_flags=[],
                    source_parts=[dict(excerpt_text_range=[0,len(match.group())],source_normalized_range=[match.start(),match.end()])])
                proof=audit.audit(synthetic)
                if not proof['issues'] and proof['original_text_layer_verified']:
                    items.append(dict(start=match.end(),end=end,title=title,source_text=match.group(),
                        source_text_sha256=synthetic['text_sha256'],source_file_sha256=row['source_file_sha256'],
                        normalized_range=[match.start(),match.end()],original_text_layer_verified=True))
            contexts[uid]=items
        candidates=[c for c in contexts[uid] if row['_lo'] is not None and c['start']<=row['_lo']<c['end']]
        if len(candidates)==1:
            proofs[row['id']].update(source_role='contract_template',source_context=candidates[0]);role_count+=1
    temp=proof_path.with_suffix('.final.tmp');writel(temp,list(proofs.values()));temp.replace(proof_path)
    write(OUT/'original-files.json',list(audit.file_proofs.values()))
    target=[r for r in rows if not r['answer_eligible']]
    summary=dict(total_source_units_code_checked=3870,review_target=3268,all_target_units_code_checked=len(target),
        actual_original_text_layer_passed=sum(p['original_text_layer_verified'] for p in proofs.values()),
        structural_holds_without_original_text_approval=sum(p.get('audit_method')=='STRUCTURAL_HOLD_NO_ORIGINAL_TEXT_APPROVAL' for p in proofs.values()),
        verified_original_files=sum(p['original_hash_matches'] for p in audit.file_proofs.values()),
        document_versions=len(audit.file_proofs),verified_contract_template_units=role_count,
        multi_column_units_held=geometry_count,
        ready_for_semantic_review=sum(not holds(r,proofs[r['id']]) for r in target),
        held_reasons=dict(Counter(i for r in target for i in holds(r,proofs[r['id']]))),
        observed_header_false_positives_resolved=resolved,source_unchanged=True,human_approved=False,
        source_currentness_verified=False,ktcs_applicable=False,supabase_ingestion='HOLD',
        audit_code_sha256=sha(__import__('pathlib').Path(__file__).with_name('hr_source_audit.py')))
    write(OUT/'final-original-audit-summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='observed_header_false_positives_resolved'}|dict(header_resolutions=len(resolved)),ensure_ascii=False),flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
