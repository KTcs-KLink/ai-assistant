"""Expansion must prove provenance and must not promote source-only review items."""
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from server import hr_answer, hr_evidence, hr_review_index, hr_source_scope as scope


def source_record(cid, eligible):
    text = '가상 테스트: 단시간 근로자의 근무시간 및 병가 확인 절차입니다.'
    return dict(id=cid, document_title='단시간근로자 운영지침', heading_path='가상 제1조 근무시간',
        text=text, text_sha256=scope.text_sha(text), source_file_sha256='a'*64, file_version_key='test-version',
        searchable=True, answer_eligible=eligible, source_scope_reviewed=True,
        needs_layout_review=not eligible, decision='HR', scope_gate='HR_CORE', human_approved=False)


def manifest_entry(row, eligible):
    return dict(id=row['id'], text_sha256=row['text_sha256'], source_file_sha256=row['source_file_sha256'],
        file_version_key=row['file_version_key'], structural_verified=True, answer_eligible=eligible)


@pytest.fixture
def expanded_source(tmp_path, monkeypatch):
    good, held = source_record('new',True), source_record('held',False)
    path=tmp_path/'reviewed.jsonl'
    path.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in [good,held]),encoding='utf-8')
    monkeypatch.setenv('KLINK_LOCAL_REVIEWED_UNITS', str(path))
    manifest=dict(units=[manifest_entry(good,True),manifest_entry(held,False)])
    monkeypatch.setattr(scope,'load',lambda p:manifest)
    dbpath=tmp_path/'review.sqlite3'
    with sqlite3.connect(dbpath) as db:
        db.executescript(hr_review_index.SCHEMA)
        db.execute('INSERT INTO metadata VALUES (?)',(scope.MANIFEST_SHA256,))
        db.execute('INSERT INTO excerpts VALUES (?,?,?,?,?,?,?,?,?,?)',(' '.join(hr_evidence.tokens(held['text'])),held['id'],held['document_title'],held['heading_path'],held['text'],'test-window',0,len(held['text']),True,'HR'))
    monkeypatch.setattr(hr_review_index,'DB',dbpath)
    monkeypatch.setattr(hr_review_index,'DB_SHA256',scope.file_sha(dbpath))
    return good,held,manifest


def test_expanded_reader_includes_new_titles_but_keeps_review_sources_separate(expanded_source):
    good,held,_=expanded_source
    assert [r['id'] for r in hr_evidence.corpus()[0]]==[good['id']]
    assert [r['id'] for r in hr_evidence.review_search('근무 병가')]==[held['id']]
    assert hr_evidence.source(held['id']) is None
    assert hr_evidence.lexical_search('근무 병가')[0]['source_mapping_verified'] is True
    assert hr_evidence.review_search('근무 병가')[0]['answer_eligible'] is False


def test_forged_manifest_cannot_promote_a_held_source(expanded_source):
    _,held,manifest=expanded_source
    manifest['units'][1]['answer_eligible']=True
    assert held['id'] not in {r['id'] for r in hr_evidence.corpus()[0]}


def test_review_search_is_read_only_and_rejects_a_changed_index(expanded_source):
    before=scope.file_sha(hr_review_index.DB)
    assert hr_evidence.review_search('근무 병가')
    assert scope.file_sha(hr_review_index.DB)==before
    with hr_review_index.DB.open('ab') as f:f.write(b'changed')
    with pytest.raises(ValueError,match='버전'):hr_evidence.review_search('근무 병가')


def test_manifest_version_and_text_must_match_the_actual_source(expanded_source):
    _,_,manifest=expanded_source
    manifest['units'][0]['file_version_key']='another-version'
    assert not hr_evidence.corpus()[0]


def test_source_only_review_cannot_authorize_an_answer_or_reach_the_model(monkeypatch):
    held=source_record('held',False)|dict(review_only=True)
    monkeypatch.setenv('KLINK_HR_INTENT_MODE','off')
    monkeypatch.setattr(hr_evidence,'summary',lambda:{})
    monkeypatch.setattr(hr_evidence,'search',lambda *a,**kw:[held])
    monkeypatch.setattr(hr_answer.benefit_explanation,'settings',lambda:pytest.fail('must not call model'))
    result=hr_answer.generate('단시간 근로자의 병가 규정은?')
    assert result['validation']=='REVIEW_ONLY_SOURCE_NOT_FOR_GENERATION' and not result['provider_calls']
    draft=hr_answer.Draft(status='answered',paragraphs=[],missing_information=[])
    with pytest.raises(hr_answer.AnswerUnavailable,match='추가 검토'):
        hr_answer.validate(draft,[held])


@pytest.fixture
def audit_files(tmp_path,monkeypatch):
    raw=tmp_path/'original.hwp';raw.write_bytes(b'public test source')
    norm=tmp_path/'norm';norm.mkdir();(norm/'TEST.txt').write_text('test source',encoding='utf-8')
    originals=tmp_path/'originals.jsonl'
    originals.write_text(json.dumps(dict(unit_id='TEST',original_local_path=str(raw),unit_file_sha256=scope.file_sha(raw),normalized_text_sha256=scope.file_sha(norm/'TEST.txt'))),encoding='utf-8')
    corpus=tmp_path/'reviewed.jsonl';corpus.write_text('source',encoding='utf-8')
    inputs=dict(reviewed_units=corpus,normalized_documents=originals)
    documents=tmp_path/'documents.jsonl';documents.write_text(json.dumps(dict(unit_id='TEST',document_title='가상 테스트 규정')),encoding='utf-8')
    inputs['documents']=documents
    manifest_path=tmp_path/'manifest.json'
    manifest=dict(schema='klink-hr-verified-source-scope-v1',company='KEPCO',human_approved=False,ktcs_applicable=False,supabase_ingestion='HOLD',
        inputs={k:scope.file_sha(p) for k,p in inputs.items()},documents={'TEST':dict(source_sha256=scope.file_sha(raw),normalized_sha256=scope.file_sha(norm/'TEST.txt'),errors=[])},units=[])
    manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
    monkeypatch.setattr(scope,'INPUTS',inputs);monkeypatch.setattr(scope,'MANIFEST',manifest_path);monkeypatch.setattr(scope,'NORMALIZED',norm)
    monkeypatch.setattr(scope,'MANIFEST_SHA256',scope.file_sha(manifest_path))
    monkeypatch.setenv('KLINK_HR_SOURCE_SCOPE','expanded')
    return corpus,raw,norm,manifest_path


@pytest.mark.parametrize('target',['original','normalized','corpus','other_project'])
def test_expanded_scope_rechecks_changes_after_cached_validation(audit_files,target):
    corpus,raw,norm,_=audit_files
    assert scope.load(corpus)['company']=='KEPCO'
    if target=='other_project':
        with pytest.raises(ValueError):scope.load(corpus.parent/'other.jsonl')
        return
    path={'original':raw,'normalized':norm/'TEST.txt','corpus':corpus}[target]
    path.write_bytes(b'changed source file')
    with pytest.raises(ValueError):scope.load(corpus)


def test_missing_manifest_is_not_a_silent_baseline_fallback(audit_files):
    corpus,_,_,manifest=audit_files
    manifest.unlink()
    with pytest.raises(OSError):scope.load(corpus)


def test_changed_manifest_cannot_promote_layout_review(audit_files):
    corpus,_,_,manifest=audit_files
    assert scope.load(corpus)['company']=='KEPCO'
    data=json.loads(manifest.read_text(encoding='utf-8'));data['units']=[dict(id='unreviewed',answer_eligible=True)]
    manifest.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(ValueError,match='변경'):scope.load(corpus)


def test_source_mapping_allows_only_whitespace_between_verified_spans():
    path=Path(__file__).resolve().parents[2]/'scripts/audit_hr_source_expansion.py'
    spec=importlib.util.spec_from_file_location('hr_audit_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    text='abc def';sha=scope.text_sha(text)
    row=dict(text=text,text_sha256=sha,parent_text_sha256=sha,parent_range=[0,len(text)],source_parts=[
        dict(excerpt_text_range=[0,3],parent_text_range=[0,3],source_normalized_range=[0,3],source_location='paragraph 1',source_method='TEST'),
        dict(excerpt_text_range=[4,7],parent_text_range=[4,7],source_normalized_range=[4,7],source_location='paragraph 2',source_method='TEST')])
    parent=dict(text=text,text_sha256=sha)
    assert module.mapping_errors(row,parent,text)==[]
    row['source_parts'].pop()
    assert 'UNMAPPED_NON_WHITESPACE' in module.mapping_errors(row,parent,text)


def test_new_table_mixed_or_heading_only_article_stays_on_hold():
    path=Path(__file__).resolve().parents[2]/'scripts/audit_hr_source_expansion.py'
    spec=importlib.util.spec_from_file_location('hr_quality_audit_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.additional_answer_holds(dict(text='제13조(구비서류)\n',quality_flags=[]),False)==['ARTICLE_BODY_MISSING_OR_TOO_SHORT']
    mixed=dict(text='제16조(해고 예고) 취업규칙을 준용한다.\n② 양도에 관해서는 기술 규정을 준용한다.',quality_flags=['NESTED_OBJECT_TABLE_ORDER_UNVERIFIED'])
    assert 'NEW_SOURCE_LAYOUT_OR_BOUNDARY_UNVERIFIED' in module.additional_answer_holds(mixed,False)
    assert 'PARAGRAPH_SEQUENCE_INCOMPLETE' in module.additional_answer_holds(mixed,False)


def test_keyword_retrieval_does_not_keep_the_old_449_result_ceiling(tmp_path,monkeypatch):
    rows=[source_record(f'test-{i}',True)|dict(document_title='취업규칙') for i in range(510)]
    path=tmp_path/'many.jsonl';path.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows),encoding='utf-8')
    monkeypatch.setattr(scope,'load',lambda p:None)
    monkeypatch.setenv('KLINK_LOCAL_REVIEWED_UNITS',str(path))
    assert len(hr_evidence.lexical_search('근무 병가'))==510


def test_new_verified_document_names_work_without_the_old_title_vocabulary(tmp_path,monkeypatch):
    row=source_record('audit',True)|dict(document_title='감사규정 시행지침',heading_path='감사규정 시행지침 > 제46조 정보보고')
    path=tmp_path/'new-title.jsonl';path.write_text(json.dumps(row,ensure_ascii=False),encoding='utf-8')
    monkeypatch.setattr(scope,'load',lambda p:dict(units=[manifest_entry(row,True)]))
    monkeypatch.setenv('KLINK_LOCAL_REVIEWED_UNITS',str(path))
    assert hr_evidence.lexical_search('감사규정 시행지침 제46조 정보보고')[0]['id']=='audit'
    correct=hr_evidence.corpus()[0][0]
    other=correct|dict(id='other',title='취업규칙')
    assert hr_evidence.select_facets('감사규정 시행지침 제46조 정보보고',['other','audit'],[other,correct])[0]=='audit'
    assert hr_evidence.select_facets('감사규정 시행지침의 정보보고 대상은?',['other','audit'],[other,correct])[0]=='audit'


def test_held_specialist_document_is_not_replaced_by_another_rule_or_sent_to_gpt(monkeypatch):
    monkeypatch.setenv('KLINK_HR_SOURCE_SCOPE','expanded')
    monkeypatch.setattr(hr_evidence.local_evidence,'corpus_path',lambda:Path('test'))
    monkeypatch.setattr(scope,'load',lambda p:dict(_document_titles={'a':'단시간근로자 운영지침','b':'취업규칙'},units=[
        dict(unit_id='a',answer_eligible=False,structural_verified=True),dict(unit_id='b',answer_eligible=True,structural_verified=True)]))
    monkeypatch.setattr(hr_evidence,'summary',lambda:{})
    monkeypatch.setattr(hr_answer.benefit_explanation,'settings',lambda:pytest.fail('must not read credentials or call model'))
    result=hr_answer.generate('단시간근로자 운영지침의 근무시간은?')
    assert result['validation']=='NAMED_SOURCE_HELD_NO_SUBSTITUTE_OR_GENERATION'
    assert result['review_search_available'] and not result['provider_calls'] and not result['paragraphs']
