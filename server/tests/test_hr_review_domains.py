"""Separated search must never leak non-HR into the default HR candidate view."""
import json
import sqlite3

import pytest

from server import hr_review_domains as domains,hr_source_scope as scope


@pytest.fixture
def domain_index(tmp_path,monkeypatch):
    path=tmp_path/'domains.sqlite3';classification=tmp_path/'classification.jsonl';classification.write_text('test labels\n')
    class_sha=scope.file_sha(classification)
    with sqlite3.connect(path) as db:
        db.executescript(domains.SCHEMA)
        db.execute('INSERT INTO metadata VALUES (?,?)',(scope.MANIFEST_SHA256,class_sha))
        for number,label in enumerate(['HR','NON_HR','MIXED','REVIEW_REQUIRED']):
            db.execute('INSERT INTO excerpts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',('인사 근무 교육',f'source-{number}','가상 테스트 규정','가상 제1조',f'공개 테스트 교육 자료 {number}',f'w{number}',0,20,True,'REVIEW_REQUIRED',label,'test-only'))
    monkeypatch.setattr(domains,'DB',path);monkeypatch.setattr(domains,'CLASSIFICATIONS',classification)
    monkeypatch.setattr(domains,'DB_SHA256',scope.file_sha(path));monkeypatch.setattr(domains,'CLASSIFICATION_SHA256',class_sha)
    return dict(units=[dict(id=f'source-{i}',structural_verified=True,answer_eligible=False) for i in range(4)])


def test_default_search_keeps_mixed_and_unknown_but_excludes_non_hr(domain_index):
    before=scope.file_sha(domains.DB)
    hits=domains.search('인사 교육',domain_index)
    assert {r['domain_label'] for r in hits}=={'HR','MIXED','REVIEW_REQUIRED'}
    assert all(r['review_only'] and not r['answer_eligible'] and not r['human_approved'] for r in hits)
    assert scope.file_sha(domains.DB)==before


def test_non_hr_can_be_queried_only_in_its_separate_view(domain_index):
    assert [r['domain_label'] for r in domains.search('인사 교육',domain_index,'non_hr')]==['NON_HR']
    assert len(domains.search('인사 교육',domain_index,'all'))==4


def test_index_or_classification_changes_cannot_silently_fall_back(domain_index):
    assert domains.search('인사 교육',domain_index)
    domains.CLASSIFICATIONS.write_text('changed classification')
    with pytest.raises(ValueError):domains.search('인사 교육',domain_index)


def test_unapproved_source_ids_are_still_excluded(domain_index):
    domain_index['units']=[]
    assert not domains.search('인사 교육',domain_index,'all')


def test_category_and_private_inputs_are_rejected_before_search(domain_index):
    with pytest.raises(ValueError):domains.search('인사 교육',domain_index,'invented')
    with pytest.raises(ValueError):domains.search('인사 test@example.invalid',domain_index)
