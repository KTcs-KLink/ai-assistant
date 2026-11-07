"""Read-only original-file, offset and text-layer checks for KEPCO source units.

No gold, API keys, model calls, edits of original files, or human approval.
Complex tables, images, unknown glyphs and uncertain structure remain review-only.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import unicodedata
import zlib

REPO=Path(__file__).resolve().parents[1]
WORKSPACE=REPO.parent
BASE=WORKSPACE/'outputs/kepco_hr_full_20261102'
NORMALIZED=WORKSPACE/'outputs/kepco_parsed_normalized_20261025'
OUT=WORKSPACE/'outputs/klink_hr_corpus_expansion_20261107'


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda:file.read(1048576),b''):value.update(chunk)
    return value.hexdigest()


def readl(path):
    with Path(path).open(encoding='utf-8') as file:
        return [json.loads(line) for line in file if line.strip()]


def compact(text):return ''.join(text.split())


def paragraph_order_issues(text):
    markers=re.findall(r'(?:^|\n)[ \t]*([①-⑳➀-➉])',text)
    numbers=[ord(c)-ord('①')+1 if '①'<=c<='⑳' else ord(c)-ord('➀')+1 for c in markers]
    return ['ARTICLE_PARAGRAPH_SEQUENCE_REVIEW'] if any(b<=a for a,b in zip(numbers,numbers[1:])) else []


def incomplete_clause_issues(text):
    end=re.sub(r'(?:\s*<[^<>]*>\s*)+$','',text).rstrip()
    if re.search(r'(?:\d+\s*(?:주|일|월|년|시간|개월)\s*(?:에|의|을|를|은|는)|(?:사항|경우|내용|대상자|직원)(?:은|는|이|가)|의하여|따라서|하고|하며|에는|으로서|위하여|또는)\s*$',end):
        return ['INCOMPLETE_CLAUSE_END_REVIEW']
    return []


def decode_hwp_text(payload):
    values=struct.unpack('<'+'H'*(len(payload)//2),payload[:len(payload)//2*2])
    out=[];index=0
    extended={1,2,3,4,5,6,7,8,9,11,12,14,15,16,17,18,19,20,21,22,23}
    while index<len(values):
        value=values[index]
        if value in extended:
            if value==9:out.append(' ')
            index+=8;continue
        if value>=32:out.append(chr(value))
        elif value in {10,13}:out.append('\n')
        elif value in {30,31}:out.append(' ')
        elif value==24:out.append('-')
        index+=1
    return ''.join(out)


def hwp_records(data):
    offset=0;controls=[]
    while offset+4<=len(data):
        start=offset;header=struct.unpack_from('<I',data,offset)[0];offset+=4
        tag=header&1023;level=(header>>10)&1023;size=(header>>20)&4095
        if size==4095:
            if offset+4>len(data):raise ValueError('HWP_RECORD_SIZE')
            size=struct.unpack_from('<I',data,offset)[0];offset+=4
        if offset+size>len(data):raise ValueError('HWP_RECORD_RANGE')
        payload=data[offset:offset+size];offset+=size
        while controls and controls[-1]['level']>=level:controls.pop()
        if tag==71:
            ctrl=payload[:4].decode('latin1')
            controls.append(dict(level=level,kind=ctrl,rows=None,columns=None))
        elif tag==77:
            for ctrl in reversed(controls):
                if ctrl['kind'] in {'tbl ',' lbt'} and len(payload)>=8:
                    ctrl['rows'],ctrl['columns']=struct.unpack_from('<HH',payload,4);break
        if tag==67:
            tables=[(c['rows'],c['columns']) for c in controls if c['kind'] in {'tbl ',' lbt'}]
            yield start,decode_hwp_text(payload),tables


class OriginalAudit:
    def __init__(self,document_ids):
        self.documents={d['unit_id']:d for d in readl(NORMALIZED/'data/documents.jsonl') if d['unit_id'] in document_ids}
        self.full_docs={d['unit_id']:d for d in readl(BASE/'data/documents.jsonl') if d['unit_id'] in document_ids}
        self.block_fields=['normalized_start','normalized_end','raw_start','raw_end','source_kind','section','record_offset','page','bbox']
        self.blocks=defaultdict(list)
        with (NORMALIZED/'data/block_map.jsonl').open(encoding='utf-8') as file:
            for line in file:
                block=json.loads(line)
                if block['unit_id'] in document_ids:self.blocks[block['unit_id']].append(tuple(block.get(k) for k in self.block_fields))
        self.starts={uid:[b[0] for b in blocks] for uid,blocks in self.blocks.items()}
        self.file_proofs={}
        self.block_cache={}

    @lru_cache(maxsize=10)
    def document_texts(self,uid):
        d=self.documents[uid]
        raw=NORMALIZED/d['raw_text_path'];normalized=NORMALIZED/d['normalized_text_path']
        return raw.read_text(encoding='utf-8'),normalized.read_text(encoding='utf-8')

    def file_proof(self,uid):
        if uid in self.file_proofs:return self.file_proofs[uid]
        d=self.documents[uid];full=self.full_docs[uid]
        original=Path(d['original_local_path']);normalized=NORMALIZED/d['normalized_text_path'];raw=NORMALIZED/d['raw_text_path']
        result=dict(document_id=uid,format=d['format'],original_exists=original.is_file(),original_file_sha256=None,
            original_hash_matches=False,normalized_hash_matches=False,raw_hash_matches=False)
        if original.is_file():
            result['original_file_sha256']=sha(original)
            result['original_hash_matches']=result['original_file_sha256']==full['source_file_sha256']==d['unit_file_sha256']
        if normalized.is_file():result['normalized_hash_matches']=sha(normalized)==full['normalized_source_sha256']==d['normalized_text_sha256']
        if raw.is_file():result['raw_hash_matches']=sha(raw)==d['raw_text_sha256']
        self.file_proofs[uid]=result
        return result

    @lru_cache(maxsize=6)
    def hwp(self,uid):
        sys.path.append(str(REPO/'.demo-logs/source-audit-runtime'))
        import olefile
        d=self.documents[uid]
        result={}
        with olefile.OleFileIO(d['original_local_path']) as ole:
            header=ole.openstream('FileHeader').read()
            flags=struct.unpack_from('<I',header,36)[0]
            if flags&2:raise ValueError('HWP_ENCRYPTED')
            for parts in ole.listdir():
                section='/'.join(parts)
                if len(parts)!=2 or parts[0]!='BodyText' or not parts[1].startswith('Section'):continue
                stream=ole.openstream(parts).read()
                if flags&1:stream=zlib.decompress(stream,-15)
                for offset,text,tables in hwp_records(stream):result[(section,offset)]=(text,tables)
        return result

    @lru_cache(maxsize=4)
    def pdf(self,uid):
        import pymupdf as fitz
        return fitz.open(self.documents[uid]['original_local_path'])

    @lru_cache(maxsize=100)
    def pdf_columns(self,uid,page_number):
        page=self.pdf(uid)[page_number-1];middle=page.rect.width*.51
        words=[w for w in page.get_text('words') if w[1]>page.rect.height*.15 and w[3]<page.rect.height*.95 and str(w[4]).strip()]
        left=[w for w in words if w[2]<middle-8];right=[w for w in words if w[0]>middle+8]
        bridging=[w for w in words if w[0]<middle-8 and w[2]>middle+8]
        spread=lambda items:max((w[3] for w in items),default=0)-min((w[1] for w in items),default=0)
        return len(left)>=20 and len(right)>=20 and len(bridging)<=2 and spread(left)>150 and spread(right)>150

    def geometry_issues(self,unit):
        """Exact text equality cannot establish a multi-column reading order."""
        uid=unit['unit_id'];labels=defaultdict(list);seen=set();issues=set()
        if self.documents[uid]['format']!='pdf':return []
        for part in unit.get('source_parts',[]):
            lo,hi=part['source_normalized_range'];index=max(0,bisect_right(self.starts[uid],lo)-1)
            while index<len(self.blocks[uid]):
                block=dict(zip(self.block_fields,self.blocks[uid][index]));index+=1
                if block['normalized_start']>=hi:break
                key=(block.get('page'),block['raw_start'])
                if block['normalized_end']<=lo or key in seen:continue
                seen.add(key)
                page_number=block.get('page');bbox=block.get('bbox')
                if not page_number or not bbox or not self.pdf_columns(uid,page_number):continue
                page=self.pdf(uid)[page_number-1];middle=page.rect.width*.51
                if bbox[3]<=page.rect.height*.15:continue
                if bbox[0]<middle-8 and bbox[2]>middle+8:
                    issues.add('PDF_MULTICOLUMN_READING_ORDER_REVIEW')
                elif bbox[2]<middle:labels[page_number].append('L')
                elif bbox[0]>middle:labels[page_number].append('R')
        for sequence in labels.values():
            collapsed=[label for i,label in enumerate(sequence) if i==0 or label!=sequence[i-1]]
            if len(collapsed)>2 or collapsed==['R','L']:issues.add('PDF_MULTICOLUMN_READING_ORDER_REVIEW')
        return sorted(issues)

    @lru_cache(maxsize=50)
    def pdf_page(self,uid,page_number):
        page=self.pdf(uid)[page_number-1]
        tables=[]
        try:
            for table in page.find_tables().tables:
                if table.col_count>1:tables.append(tuple(table.bbox))
        except Exception:return page,None
        return page,tables

    @staticmethod
    def verified_document_control_header(page,table,expected):
        """A verified department label inside a page's document-control header.

        This leaves the literal source text intact. It does not clear a table
        in the policy body or excuse missing text, numbers or qualifications.
        """
        import pymupdf as fitz
        rect=fitz.Rect(table)
        if rect.y1>page.rect.height*.17 or not re.fullmatch(r'[가-힣]{2,10}',compact(expected)):return False
        label=compact(expected)
        if not re.fullmatch(r'[가-힣]+(?:실|처|부|팀)',label):return False
        header=compact(page.get_textbox(rect+(-.6,-.6,.6,.6)))
        return label in header and all(x in header for x in ['업무표준','페이지','개정일자'])

    def block_proof(self,uid,block,expected):
        kind=block.get('source_kind')
        if kind=='hwp':
            found=self.hwp(uid).get((block.get('section'),block.get('record_offset')))
            if found is None:return 'HWP_RECORD_NOT_FOUND'
            text,tables=found
            if compact(text)!=compact(expected):return 'HWP_RAW_TEXT_MISMATCH'
            if any(rows is None or columns is None or columns>1 for rows,columns in tables):return 'TABLE_LAYOUT_REVIEW'
            return None
        if kind=='pdf':
            import pymupdf as fitz
            page_number=block.get('page');bbox=block.get('bbox')
            if not page_number or not bbox:return 'PDF_POSITION_UNAVAILABLE'
            page,tables=self.pdf_page(uid,page_number)
            if tables is None:return 'PDF_TABLE_DETECTION_UNAVAILABLE'
            rect=fitz.Rect(bbox)
            actual=page.get_textbox(rect+(-.6,-.6,.6,.6))
            if compact(expected) not in compact(actual) and compact(actual)!=compact(expected):return 'PDF_RAW_TEXT_MISMATCH'
            if any((rect&fitz.Rect(table)).get_area()>0 and not self.verified_document_control_header(page,table,expected) for table in tables):return 'TABLE_LAYOUT_REVIEW'
            return None
        return 'ORIGINAL_FORMAT_REVIEW'

    def audit(self,unit):
        uid=unit['unit_id'];issues=[];file_proof=self.file_proof(uid)
        if not all(file_proof.get(k) for k in ['original_hash_matches','normalized_hash_matches','raw_hash_matches']):issues.append('ORIGINAL_FILE_HASH_OR_MISSING')
        raw,normalized=self.document_texts(uid)
        if hashlib.sha256(unit['text'].encode()).hexdigest()!=unit['text_sha256']:issues.append('SOURCE_TEXT_HASH')
        blocks_checked=0;original_issues=set();pages=set();hwp_records_checked=0
        parts=unit.get('source_parts',[])
        if not parts:issues.append('NO_SOURCE_MAPPING')
        for part in parts:
            a,b=part['excerpt_text_range'];x,y=part['source_normalized_range']
            if unit['text'][a:b]!=normalized[x:y]:issues.append('NORMALIZED_SOURCE_OFFSET_MISMATCH')
            index=max(0,bisect_right(self.starts[uid],x)-1)
            while index<len(self.blocks[uid]):
                block=dict(zip(self.block_fields,self.blocks[uid][index]));index+=1
                if block['normalized_start']>=y:break
                if block['normalized_end']<=x:continue
                expected=raw[block['raw_start']:block['raw_end']]
                if not expected.strip():continue
                cache_key=(uid,block['raw_start'],block['raw_end'])
                if cache_key not in self.block_cache:
                    try:self.block_cache[cache_key]=self.block_proof(uid,block,expected)
                    except Exception as error:self.block_cache[cache_key]='ORIGINAL_READ_'+type(error).__name__
                issue=self.block_cache[cache_key]
                if issue:original_issues.add(issue)
                blocks_checked+=1
                if block.get('page'):pages.add(block['page'])
                if block.get('record_offset') is not None:hwp_records_checked+=1
        if any(unit['text'][a:b].strip() for a,b in unit.get('source_mapping_uncovered_ranges',[])):issues.append('UNMAPPED_NON_WHITESPACE')
        if any(unicodedata.category(c)=='Co' for c in unit['text']):issues.append('UNRESOLVED_PRIVATE_USE_GLYPH')
        if any('OCR' in str(flag) for flag in unit.get('quality_flags',[])):issues.append('OCR_REQUIRES_VISUAL_REVIEW')
        if re.search(r'(?:인사|노무|경영|기술관리)\s*\d{3,5}\s*[-－]\s*\d+',unit['text']):issues.append('MARGIN_TEXT_IN_ARTICLE')
        issues+=sorted(original_issues)
        geometry=self.geometry_issues(unit);issues+=geometry
        sequence=paragraph_order_issues(unit['text'])+incomplete_clause_issues(unit['text']);issues+=sequence
        return dict(id=unit['id'],document_id=uid,source_text_sha256=unit['text_sha256'],source_file_sha256=unit['source_file_sha256'],
            normalized_offsets_checked=True,source_parts=len(parts),original_blocks_checked=blocks_checked,hwp_records_checked=hwp_records_checked,pdf_pages=sorted(pages),
            issues=sorted(set(issues)),original_text_layer_verified=blocks_checked>0 and not original_issues,
            source_structure_verified=unit.get('kind')=='ARTICLE' and bool(unit.get('article_label')) and not geometry and not sequence,
            human_approved=False,source_currentness_verified=False)
