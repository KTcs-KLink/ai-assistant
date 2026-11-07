"""Independent original-file parser controls; no model, private files or network."""
import importlib.util
from pathlib import Path
import struct


spec=importlib.util.spec_from_file_location('testable_source_audit',Path(__file__).resolve().parents[1]/'hr_source_audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def record(tag,level,payload):
    return struct.pack('<I',tag|(level<<10)|(len(payload)<<20))+payload


def test_hwp_control_bytes_are_not_misread_as_source_text_and_numbers_survive():
    text='제3조 근로자 15일\n'
    payload=text.encode('utf-16le')+struct.pack('<8H',2,100,200,300,400,500,600,2)+'예외'.encode('utf-16le')
    assert audit.decode_hwp_text(payload)==text+'예외'


def test_hwp_table_columns_are_tracked_until_the_control_closes():
    table_header=struct.pack('<IHH',0,2,3)
    stream=(record(71,1,b' lbt')+record(77,2,table_header)+record(67,3,'표의 셀'.encode('utf-16le'))
        +record(67,0,'일반 조문'.encode('utf-16le')))
    rows=list(audit.hwp_records(stream))
    assert rows[0][1:] == ('표의 셀',[(2,3)])
    assert rows[1][1:] == ('일반 조문',[])


def test_hwp_record_truncation_does_not_silently_drop_a_condition():
    import pytest
    stream=record(67,0,'필수 조건'.encode('utf-16le'))[:-2]
    with pytest.raises(ValueError,match='HWP_RECORD_RANGE'):list(audit.hwp_records(stream))


def test_document_control_header_cannot_clear_a_benefit_or_body_table():
    import pymupdf as fitz
    class Page:
        rect=fitz.Rect(0,0,600,840)
        def get_textbox(self,rect):return '업무표준No 개정·페이지 제·개정일자 감 사 실'
    assert audit.OriginalAudit.verified_document_control_header(Page(),(40,50,550,115),'감 사 실')
    assert not audit.OriginalAudit.verified_document_control_header(Page(),(40,200,550,400),'감 사 실')
    assert not audit.OriginalAudit.verified_document_control_header(Page(),(40,50,550,115),'직원 30만원')


def test_two_column_text_equality_does_not_excuse_interleaved_reading_order():
    import pymupdf as fitz
    checker=audit.OriginalAudit.__new__(audit.OriginalAudit)
    checker.documents={'DOC':dict(format='pdf')}
    checker.block_fields=['normalized_start','normalized_end','raw_start','raw_end','source_kind','section','record_offset','page','bbox']
    checker.pdf_columns=lambda *args:True
    class Page:rect=fitz.Rect(0,0,600,840)
    checker.pdf=lambda uid:[Page()]
    def run(boxes):
        checker.blocks={'DOC':[(i*10,i*10+10,i*10,i*10+10,'pdf',None,None,1,box) for i,box in enumerate(boxes)]}
        checker.starts={'DOC':[i*10 for i in range(len(boxes))]}
        return checker.geometry_issues(dict(unit_id='DOC',source_parts=[dict(source_normalized_range=[0,len(boxes)*10])]))
    left=(40,200,280,215);right=(330,200,560,215)
    assert not run([left,left,right])
    assert run([left,right,left])==['PDF_MULTICOLUMN_READING_ORDER_REVIEW']
    assert run([(40,200,560,215)])==['PDF_MULTICOLUMN_READING_ORDER_REVIEW']


def test_reset_paragraph_numbers_require_review_but_inline_references_do_not():
    assert audit.paragraph_order_issues('제1조\n①첫 항\n②둘째 항\n①다른 조문이 섞임')
    assert not audit.paragraph_order_issues('제1조\n①첫 항\n②본문에서 ①을 참조함\n③셋째 항')


def test_a_clause_cut_after_a_duration_cannot_be_called_a_complete_article():
    assert audit.incomplete_clause_issues('제1조 수당은 1주에')
    assert not audit.incomplete_clause_issues('제1조 수당은 1주에 한 번 지급한다.')
