"""Validated local source-review overlay; never a human/company policy approval."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path

WORKSPACE=Path(__file__).resolve().parents[2]
CORPUS=WORKSPACE/'outputs/kepco_hr_full_20261102/data/reviewed_units.jsonl'
REVIEW_DIR=WORKSPACE/'outputs/klink_hr_corpus_expansion_20261107'
SCHEMA='klink-kepco-source-review-overlay-v1'
VIEW_NAME='runtime-source-units.jsonl'
VIEW_FIELDS=('id','decision','kind','article_label','document_title','heading_path','text','text_sha256',
    'source_file_sha256','file_version_key','searchable','answer_eligible','source_scope_reviewed',
    'employee_scope','review_status','human_approved','effective_status','needs_layout_review')


def file_sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda:file.read(1048576),b''):value.update(block)
    return value.hexdigest()


def fingerprint(corpus_path):
    configured=os.getenv('KLINK_HR_SOURCE_REVIEW')
    if not configured and Path(corpus_path).resolve()!=CORPUS.resolve():return ('',0,0)
    path=Path(configured).resolve() if configured else REVIEW_DIR/'review-overlay.json'
    if path.parent.resolve()!=REVIEW_DIR.resolve() or path.name!='review-overlay.json':
        raise ValueError('한전 작업 폴더의 원문 검토 기록만 연결할 수 있어요.')
    if not path.is_file():
        raise ValueError('완료된 원문 검토 기록이 없어 답변 연결을 보류했어요.')
    stat=path.stat()
    return str(path),stat.st_mtime_ns,stat.st_size


@lru_cache(maxsize=2)
def load(path,mtime,size,corpus_path,source_mtime,source_size):
    if not path:return {}
    try:
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        if (data.get('schema')!=SCHEMA or data.get('company')!='KEPCO' or data.get('human_approved') is not False
            or data.get('source_corpus_sha256')!=file_sha(corpus_path) or data.get('all_target_units_audited')!=3268
            or data.get('source_currentness_verified') is not False or data.get('ktcs_applicable') is not False
            or data.get('original_proof_sha256')!=file_sha(REVIEW_DIR/'original-proofs.jsonl')
            or data.get('semantic_review_protocol_sha256')!=file_sha(REVIEW_DIR/'review-protocol.json')):raise ValueError()
        rows=data['promotions']+data.get('existing_source_reviews',[])
        if len({r['id'] for r in rows})!=len(rows):raise ValueError()
        return {r['id']:r for r in rows}
    except (OSError,KeyError,TypeError,ValueError):
        raise ValueError('원문 검토 기록의 버전·출처·범위 검사를 통과하지 못했어요.') from None


def source_view(corpus_path,review_fingerprint,proposals):
    """A hashed, original-field-only view avoids parsing unrelated giant units.

    Canonical corpus/hash and per-source body hashes are still verified. No
    original text, ID, condition or exception is shortened for this view.
    """
    if not review_fingerprint[0]:return Path(corpus_path)
    data=json.loads(Path(review_fingerprint[0]).read_text(encoding='utf-8'))
    if 'runtime_view_file' not in data:return Path(corpus_path)
    try:
        path=Path(review_fingerprint[0]).parent/VIEW_NAME
        if (data['runtime_view_file']!=VIEW_NAME or path.parent.resolve()!=REVIEW_DIR.resolve()
            or data['runtime_view_sha256']!=file_sha(path)):raise ValueError()
        ids=[]
        with path.open(encoding='utf-8') as file:
            for line in file:
                row=json.loads(line)
                if set(row)!=set(VIEW_FIELDS):raise ValueError()
                ids.append(row['id'])
        if len(ids)!=len(set(ids)) or len(ids)!=data['runtime_view_count'] or set(ids)!=set(proposals):raise ValueError()
        return path
    except (OSError,KeyError,TypeError,ValueError):
        raise ValueError('답변용 원문 목록의 해시·항목·허용 범위가 일치하지 않아요.') from None


def apply(row,proposal,private_pattern):
    """Recheck exact identity/support; retain the unchanged original text and ID."""
    try:
        context=proposal.get('source_context')
        context_fields={}
        if context is not None:
            if (proposal.get('source_role')!='contract_template' or context['original_text_layer_verified'] is not True
                or context['source_file_sha256']!=row['source_file_sha256'] or '계약서' not in context['title']
                or hashlib.sha256(context['source_text'].encode()).hexdigest()!=context['source_text_sha256']
                or context['title']!=context['source_text'].strip()):raise ValueError()
            context_fields=dict(source_role='contract_template',source_context=context)
        action=proposal.get('action','include')
        if action in {'confirm','hold'}:
            if (proposal['id']!=row['id'] or proposal['source_text_sha256']!=row['text_sha256']
                or proposal['source_file_sha256']!=row['source_file_sha256'] or proposal['version']!=row['file_version_key']
                or proposal['human_approved'] is not False or row.get('answer_eligible') is not True
                or private_pattern.search(json.dumps(proposal,ensure_ascii=False))):raise ValueError()
            if action=='hold':
                if not proposal['issues']:raise ValueError()
                return row|dict(answer_eligible=False,source_review_origin='original_recheck_held',original_review_issues=proposal['issues'])
            if proposal['issues'] or proposal['original_text_layer_verified'] is not True:raise ValueError()
            return row|dict(source_review_origin='existing_scope_original_rechecked',original_text_layer_verified=True)|context_fields
        if action!='include':raise ValueError()
        if (proposal['id']!=row['id'] or proposal['source_text_sha256']!=row['text_sha256']
            or proposal['source_file_sha256']!=row['source_file_sha256'] or proposal['version']!=row['file_version_key']
            or proposal['decision']!='HR' or proposal['human_approved'] is not False
            or not proposal['original_text_layer_verified'] or not proposal['source_structure_verified']
            or not proposal['employee_scope'].strip() or not proposal['support_ranges']
            or private_pattern.search(json.dumps(proposal,ensure_ascii=False))):raise ValueError()
        if not proposal['task_codes'] or any(t not in {f'01.{i:02}' for i in range(1,10)} for t in proposal['task_codes']):raise ValueError()
        for span in proposal['support_ranges']:
            a,b=span['start'],span['end']
            if not 0<=a<b<=len(row['text']) or hashlib.sha256(row['text'][a:b].encode()).hexdigest()!=span['sha256']:raise ValueError()
        recovered=proposal.get('recovered_structure')
        if row.get('kind')!='ARTICLE' and not recovered:raise ValueError()
        patched=row|dict(decision='HR',answer_eligible=True,source_scope_reviewed=True,needs_layout_review=False,
            employee_scope=proposal['employee_scope'],review_status='LOCAL_ORIGINAL_SOURCE_AND_SCOPE_CODE_CHECKED_NOT_HUMAN',
            human_approved=False,source_review_origin='local_original_source_review',prior_review_decision=row.get('decision'),
            prior_layout_review=row.get('needs_layout_review'),task_codes=proposal['task_codes'])
        patched['original_text_layer_verified']=True
        if recovered:
            if not row['text'].lstrip().startswith(recovered['article_label']):raise ValueError()
            patched.update(kind='ARTICLE',article_label=recovered['article_label'],heading_path=recovered['section'])
        return patched|context_fields
    except (KeyError,TypeError,ValueError):
        raise ValueError('추가할 원문의 ID·본문·적용 범위를 확인해야 해요.') from None
