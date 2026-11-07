"""Read-only original-source diagnostics; save no credential or private matches."""
from bisect import bisect_right
from difflib import SequenceMatcher
import json
import sys

from hr_source_audit import BASE,OUT,OriginalAudit,compact,readl
from expand_hr_sources import source_units,write
from server import hr_evidence


def main():
    proofs={p['id']:p for p in readl(OUT/'original-proofs.jsonl')}
    rows=[r for r in source_units() if r['answer_eligible'] and r['id'] in proofs and proofs[r['id']]['issues']]
    audit=OriginalAudit({r['unit_id'] for r in rows})
    result=[]
    for row in rows:
        raw,_=audit.document_texts(row['unit_id']);bad=[];seen=set()
        for part in row['source_parts']:
            lo,hi=part['source_normalized_range'];index=max(0,bisect_right(audit.starts[row['unit_id']],lo)-1)
            while index<len(audit.blocks[row['unit_id']]):
                block=dict(zip(audit.block_fields,audit.blocks[row['unit_id']][index]));index+=1
                if block['normalized_start']>=hi:break
                if block['normalized_end']<=lo or block['raw_start'] in seen:continue
                seen.add(block['raw_start']);expected=raw[block['raw_start']:block['raw_end']]
                issue=audit.block_proof(row['unit_id'],block,expected)
                if not issue:continue
                data=dict(issue=issue,page=block.get('page'),bbox=block.get('bbox'),record_offset=block.get('record_offset'),expected=expected)
                if block['source_kind']=='pdf':
                    import pymupdf as fitz
                    page,_=audit.pdf_page(row['unit_id'],block['page'])
                    actual=page.get_textbox(fitz.Rect(block['bbox'])+(-.6,-.6,.6,.6))
                    data['actual']=actual
                    a,b=compact(expected),compact(actual)
                    data['differences']=[dict(op=op,expected=a[x:y],actual=b[u:v]) for op,x,y,u,v in SequenceMatcher(None,a,b).get_opcodes() if op!='equal']
                if not hr_evidence.PRIVATE.search(json.dumps(data,ensure_ascii=False)):bad.append(data)
        result.append(dict(id=row['id'],title=row['document_title'],section=row['heading_path'],issues=proofs[row['id']]['issues'],blocks=bad))
    write(OUT/'existing-source-original-issues.json',result)
    print(json.dumps([dict(id=r['id'],title=r['title'],section=r['section'],issues=r['issues'],diffs=[b.get('differences') for b in r['blocks']]) for r in result],ensure_ascii=False),flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
