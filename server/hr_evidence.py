"""Read-only KEPCO HR source gates and lexical retrieval; no gold/employee data."""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import hashlib
import json
import math
import os
import re
from pathlib import Path

try:
    from . import local_evidence,hr_source_review
except ImportError:
    import local_evidence,hr_source_review


HR_TITLES = frozenset({"인사관리규정", "인사관리지침", "취업규칙", "취업관리시행세칙", "5직급관리규정",
    "비정규직관리규정", "연봉및복리후생관리규정", "연봉및복리후생관리규정시행세칙", "노사협의회규정", "복지업무실무지침", "성희롱예방지침"})
CANONICAL_CORPUS=hr_source_review.CORPUS
HR_TERMS = re.compile(r"인사|근로|근무|급여|임금|수당|복지|복리|휴가|연차|병가|휴직|퇴직|사직|입사|채용|징계|교육|연수|출장|경조|육아|출산|자녀|정년|재직|해고|포상|노사|계약|재고용|비정규|보직|전보|겸직|임용|승진|승급|발령|직급|직위|평정|성과급|보수|결근|지각|조퇴|휴게|신원보증|학자금|학비|건강검진|건강진단|산재|재해|공상|순직|퇴교|업무량|업무부여|업무를.*부여|재배분|해임|파견|전근|직군|전기원|응시|선발|지원자|공가|휴일|출근|외출|직무급|연봉|공로금|공로기금|체육|후생시설|동호회|써클|위로금|조위금|자기개발|전문원|연구원|평가|임명|임기|뽑|비서|근속|격려금|인계")
HR_TERMS = re.compile(HR_TERMS.pattern+r'|임원|단시간|면직|외부강의|사례금|비위|행동강령|청탁|법률지원|공익신고|내부신고|인권|성희롱|괴롭힘|고충|차별|면책|수습')
STOPWORDS = frozenset("무엇 무엇인가요 어떻게 있나요 있습니까 알려 주세요 직원 직원이 직원의 경우 경우에는 규정 기준 내용 확인 대한 대해서 합니다 하려고 해야 하나요 되나요 할 수 있는 어떤 각각 위해 관련 다음".split())
# A small, source-heading vocabulary. No questions, answers, gold IDs or test labels
# are indexed or consulted by retrieval.
QUERY_ALIASES = ((r"급여|월급", "보수"), (r"건강검진", "건강진단"),
    (r"점심|휴게", "휴게시간"), (r"아파|사전.*결근|갑자기.*승인", "결근"),
    (r"업무량|재배분", "업무부여"), (r"보직.*기준|희망.*보직", "보직 원칙"),
    (r"다시.*계약|재계약|계약.*공백|계약.*갱신", "재고용계약"),
    (r"제출.*서류|서류.*제출", "구비서류"), (r"허위사실|거짓.*서류", "결격사유"),
    (r"계약기간|계약.*기간.*단위", "계약기간 단위"),
    (r"연차", "연차유급휴가"), (r"자진.*퇴사|사직.*통보|사직원", "퇴직"),
    (r"넘기|인수인계|사무인계", "인계"), (r"비서", "보직변경"),
    (r"근무장소.*밖|밖으로.*나가|외출", "외출"),
    (r"평가기간|이전.*실적", "근무평정원칙"), (r"격려금|조위금|위로금", "적용례"),
    (r"소정.*(?:넘|초과)|초과.?근로|연장.?근무", "연장근무 초과근로"))
PRIVATE = re.compile(r"(?:sk-[A-Za-z0-9_-]{15,}|sb_(?:secret|publishable)_[A-Za-z0-9_-]+|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|\b\d{6}[- ]?[1-8]\d{6}\b|\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b)", re.I)


def is_hr_question(question):
    return bool(HR_TERMS.search(question) or
        (re.search(r'직원|임직원|근로자|감사인|종업원|관리감독자',question)
         and re.search(r'신고|보호|구제|금지|위반|불이익|책임|서약|동의|청렴|보상|권익|제안|재정보증',question)))


def title_key(title: str) -> str:
    value=re.sub(r"\s", "", re.sub(r"[_ -]+\d{6,8}$", "", title))
    return re.sub(r'제\d+차개정$','',value)


def tokens(text: str) -> list[str]:
    result = []
    for word in re.findall(r"[가-힣]{2,}|[a-z0-9]+", text.lower()):
        result.append(word)
        for suffix in ("으로부터","에게는","에서는","으로는","까지는","으로","에게","에서","에는","이나","이면","부터","까지","의","을","를","은","는","이","가","과","와","도","로"):
            if word.endswith(suffix) and len(word)-len(suffix)>=2:
                result.append(word[:-len(suffix)])
                break
        if re.fullmatch(r"[가-힣]{3,}", word):
            result.extend(word[i:i+2] for i in range(len(word)-1))
    return result


def article_key(text):
    match=re.search(r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?",text)
    return (int(match[1]),int(match[2] or 0)) if match else None


def section_heading(path):
    # Hierarchy separators have surrounding whitespace. The '>' ending an
    # amendment date (<개정 ...>) is part of the heading, not a separator.
    return re.split(r'\s+>\s+',path)[-1]


def reference_links(records):
    """Source-only, version-bound article references. No gold/question inputs."""
    articles={}
    titles={}
    for row in records:
        articles.setdefault((row['version'],article_key(section_heading(row['section']))),[]).append(row)
        titles.setdefault(title_key(row['title']),set()).add(row['version'])
    result={r['id']:set() for r in records}
    for row in records:
        text=row['text']
        for match in re.finditer(r"제\s*\d+\s*조(?:\s*의\s*\d+)?",text):
            prefix=re.sub(r'\s','',text[max(0,match.start()-45):match.start()])
            versions={row['version']}
            named=next((name for name in sorted(titles,key=len,reverse=True) if prefix.endswith(name)),None)
            if named:versions=titles[named]
            elif re.search(r'(?:법|시행령|시행규칙)$',prefix):continue
            if len(versions)!=1:continue
            candidates=articles.get((next(iter(versions)),article_key(match.group())),[])
            sections={r['section'] for r in candidates}
            if len(sections)>1:continue
            result[row['id']].update(r['id'] for r in candidates if r['id']!=row['id'])
    return result


def scope_profile() -> str:
    profile=os.getenv('KLINK_HR_SCOPE_PROFILE','expanded')
    if profile not in {'core','expanded'}:
        raise ValueError('인사 원문 연결 범위를 확인해야 해요.')
    return profile


@lru_cache(maxsize=2)
def _load(path: str, mtime: int, size: int, profile: str, review_fingerprint: tuple):
    records, seen, rejected = [], set(), 0
    proposals=hr_source_review.load(*review_fingerprint,path,mtime,size) if review_fingerprint[0] else {}
    used=set()
    read_path=hr_source_review.source_view(path,review_fingerprint,proposals)
    with read_path.open(encoding="utf-8") as file:
        for line in file:
            row = json.loads(line)
            if row['id'] in proposals:
                row=hr_source_review.apply(row,proposals[row['id']],PRIVATE)
                used.add(row['id'])
            if profile=='core' and title_key(row.get("document_title", "")) not in HR_TITLES:
                continue
            if profile=='expanded' and row.get('decision')!='HR':
                continue
            if not all(row.get(key) is True for key in ("searchable", "answer_eligible", "source_scope_reviewed")):
                continue
            if hashlib.sha256(row.get("text", "").encode()).hexdigest() != row.get("text_sha256") or row["id"] in seen or PRIVATE.search(row.get("text", "")):
                rejected += 1
                continue
            seen.add(row["id"])
            section=row['heading_path']
            if row.get('source_role')=='contract_template':
                section=section.rsplit(' > ',1)[0]+' > 첨부 '+row['source_context']['title']+' > '+section_heading(section)
            records.append(dict(id=row["id"], title=row["document_title"], section=section, text=row["text"],
                sha256=row["text_sha256"], source_file_sha256=row.get("source_file_sha256"), version=row.get("file_version_key"),
                company="KEPCO", employee_scope=row.get("employee_scope", "적용 대상 확인 필요"),
                review_status=row.get("review_status"), human_approved=row.get("human_approved") is True,
                effective_status=row.get("effective_status"), ktcs_applicable=False,
                review_origin=row.get('source_review_origin','existing_automatic_gate'),
                original_text_layer_verified=row.get('original_text_layer_verified') is True,
                source_role=row.get('source_role','policy_article'),source_context=row.get('source_context'),
                prior_review_decision=row.get('prior_review_decision')))
    if used!=set(proposals):raise ValueError('원문 검토 기록의 일부 ID를 현재 원문에서 찾지 못했어요.')
    versions={}
    for row in records:versions.setdefault(title_key(row['title']),{})[row['version']]=row['title']
    for row in records:
        row['version_options']=[dict(version=key,title=value) for key,value in sorted(versions[title_key(row['title'])].items(),key=lambda item:str(item[0]))]
    links=reference_links(records)
    lookup={r['id']:r for r in records}
    for row in records:
        row['referenced_source_ids']=sorted(links[row['id']])
    counters = [Counter(tokens(r["title"] + " " + r["section"]) * 3 + tokens(r["text"])+
        tokens(' '.join(section_heading(lookup[rid]['section']) for rid in links[r['id']]))) for r in records]
    frequencies = Counter(t for counter in counters for t in counter)
    lengths = [sum(c.values()) for c in counters]
    return records, counters, frequencies, lengths, rejected


def corpus():
    path = local_evidence.corpus_path()
    if not path or not path.is_file():
        return [], [], Counter(), [], 0
    if path.resolve()!=CANONICAL_CORPUS.resolve():
        raise ValueError('이 인사 도메인은 KTCS 작업 폴더의 고정된 한전 원문만 사용해요.')
    stat = path.stat()
    profile=scope_profile()
    review=hr_source_review.fingerprint(path) if profile=='expanded' else ('',0,0)
    return _load(str(path), stat.st_mtime_ns, stat.st_size,profile,review)


def summary() -> dict:
    rows, _, _, _, rejected = corpus()
    return dict(method="hr_bge_m3_hybrid" if os.getenv('KLINK_HR_RETRIEVAL')=='hybrid' else "hr_lexical_bm25", company="KEPCO", ktcs_applicable=False, source_count=len(rows),
        document_count=len({r["title"] for r in rows}), human_approved_count=sum(r["human_approved"] for r in rows),
        document_version_count=len({r['version'] for r in rows if r.get('version')}),
        newly_reviewed_source_count=sum(r['review_origin']=='local_original_source_review' for r in rows),
        original_text_layer_checked_count=sum(r['original_text_layer_verified'] for r in rows),
        rejected_sources=rejected, scope_profile=scope_profile(),
        scope="Verified source-scope and answer gates across all document titles; automated, not human approval" if scope_profile()=='expanded' else "Core HR title allowlist plus existing source gates")


def lexical_search(question: str, limit: int | None = None) -> list[dict]:
    if PRIVATE.search(question):
        raise ValueError("개인정보나 키를 제외하고 일반적인 업무 질문만 입력해 주세요.")
    if not is_hr_question(question):
        return []
    rows, counters, df, lengths, _ = corpus()
    expanded = question + " " + " ".join(alias for pattern, alias in QUERY_ALIASES if re.search(pattern, question))
    if re.search(r"급여|보수|임금", question) and re.search(r"입사|신규|승진|전근|신분.*변경", question):
        expanded += " 지급기준 발령일"
    if "보직" in question and (question.count('직급')>=2 or '다른 직급' in question):expanded+=' 전방위 보직'
    terms = set(tokens(expanded)) - STOPWORDS
    if not rows:
        return []
    average = sum(lengths)/len(rows) or 1
    hits = []
    lookup={r['id']:r for r in rows}
    mixed_scope=bool(re.search(r'(?<!비)정규직|일반\s*직원',question)) and '비정규직' in question
    q_articles={article_key(m) for m in re.findall(r'제\s*\d+\s*조(?:\s*의\s*\d+)?',question)}
    named={title_key(row['title']) for row in rows if title_key(row['title']) in title_key(question)}
    for row, counts, length in zip(rows, counters, lengths):
        # A contract form cannot establish a universal payday for all employees.
        if not query_source_allowed(question,row):continue
        heading = section_heading(row["section"])
        linked=' '.join(section_heading(lookup[rid]['section']) for rid in row.get('referenced_source_ids',[]))
        heading_terms = set(tokens(heading+' '+linked))
        score = sum(math.log(1+(len(rows)-df[t]+.5)/(df[t]+.5))*counts[t]*2.2/(counts[t]+1.2*(.25+.75*length/average))
                    * (2.0 if t in heading_terms else 1.0) for t in terms if counts[t])
        if "비정규직" in question and not mixed_scope and title_key(row["title"]) == "비정규직관리규정":
            score *= 1.6
        if '직원' in question and '임원' not in question and '> 제2장 임원연봉' in row['section']:
            score *= .2
        if "5직급" in question and title_key(row["title"]) == "5직급관리규정":
            score *= 1.6
        # Preserve exact multiword heading matches across Korean spacing. This
        # helps specific topics compete with generic words such as '직원/계약'.
        heading_compact = re.sub(r"\s", "", heading)
        for pattern, alias in QUERY_ALIASES:
            if re.search(pattern, question) and re.sub(r"\s", "", alias) in heading_compact:
                score += 12
        if '전방위 보직' in expanded and '전방위' in heading:score+=12
        if article_key(heading) in q_articles:
            # A bare article number may refer to background conditions in any
            # document. Only an explicitly named regulation warrants a large
            # exact-match boost; do not swamp the actual question topic.
            if named and title_key(row['title']) in named:score+=40
            elif not named:score+=4
        if score > 0:
            hits.append((score, row))
    hits.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    count=len(rows) if limit is None else max(1,min(limit,len(rows)))
    return [{**row, "score": round(score, 5)} for score, row in hits[:count]]


def search(question: str,limit: int=3) -> list[dict]:
    hits=lexical_search(question)
    if os.getenv('KLINK_HR_RETRIEVAL')!='hybrid':return hits[:max(1,min(limit,5))]
    if PRIVATE.search(question) or not is_hr_question(question):return []
    from . import hr_vectors
    rows=corpus()[0]
    if not rows:return []
    dense=hr_vectors.get_index(rows,local_evidence.corpus_path()).search(question)
    query_rows=[r for r in rows if query_source_allowed(question,r)]
    allowed={r['id'] for r in query_rows}
    dense={rid:value for rid,value in dense.items() if rid in allowed}
    fused=hr_vectors.fuse([r['id'] for r in hits],dense)
    ordered=select_facets(question,sorted(fused,key=lambda rid:(-fused[rid],rid)),query_rows)
    lookup={r['id']:r for r in rows}
    return [{**lookup[rid],'score':round(fused[rid],7)} for rid in ordered[:max(1,min(limit,5))]]


def query_source_allowed(question,row):
    if (re.search(r'급여|월급|임금|보수',question) and re.search(r'언제|지급일|급여일|월급날|며칠',question)
        and not re.search(r'계약서|첨부|서식|양식',question)):
        if row.get('source_role')=='contract_template' or re.search(r'계약서|서식|별지',row['section']):return False
    return True


def ambiguous_versions(question,sources):
    compact_question=re.sub(r'\s','',question)
    ambiguous=[]
    for row in sources:
        options=row.get('version_options',[])
        if len(options)<2:continue
        explicit=[v for v in options if (re.search(r'[_ -]\d{6,8}$|제\s*\d+\s*차\s*개정$',v['title']) and re.sub(r'\s','',v['title']) in compact_question)
            or (v['version'] and len(v['version'])>20 and v['version'] in question)]
        if len(explicit)!=1 or row['version']!=explicit[0]['version']:ambiguous.append(row['id'])
    return ambiguous


def select_facets(question,ranking,rows):
    """Balance explicit question topics and version-bound references, not gold labels.

    Subqueries use regulation heading vocabulary. They never contain an answer,
    case identifier, expected source ID or a qualification amount.
    """
    lookup={r['id']:r for r in rows}
    result=[]
    def add(rid):
        if rid in lookup and rid not in result:result.append(rid)
    qrefs={article_key(m) for m in re.findall(r'제\s*\d+\s*조(?:\s*의\s*\d+)?',question)}
    named={title_key(row['title']) for row in rows if title_key(row['title']) in title_key(question)}
    explicit=[rid for rid in ranking if named and article_key(section_heading(lookup[rid]['section'])) in qrefs and
        title_key(lookup[rid]['title']) in named]
    for rid in explicit:add(rid)
    if ranking:add(ranking[0])
    mixed=bool(re.search(r'(?<!비)정규직|일반\s*직원',question)) and '비정규직' in question
    if not (explicit and named and not mixed):
        facets=[]
        for pattern,alias in QUERY_ALIASES:
            compact_alias=re.sub(r'\s','',alias)
            if len(compact_alias)>=4 and re.search(pattern,question):
                matches=[r for r in lexical_search(question+' '+alias,None)
                    if compact_alias in re.sub(r'\s','',section_heading(r['section']))]
                if matches:add(matches[0]['id'])
        if re.search(r'넘기|인수인계|사무인계|인계',question):facets.append(('사무 인계 담당사무 후임자','인계'))
        if re.search(r'근무장소.*밖|밖으로.*나가|외출',question):facets.append(('근무 장소 이탈 외출','외출'))
        if re.search(r'계약.*(?:만료|종료|기간)|(?:만료|종료).*계약',question):facets.append(('비정규직 계약기간 단위','계약기간'))
        if '비정규직' in question and re.search(r'재계약|재고용|계약.*다시|같은\s*사람.*(?:다시|고용)',question):
            facets.append(('비정규직 재계약 근로계약서 서면','근로계약서'))
        if '정년퇴직' in question:facets.append(('직원 정년퇴직','정년퇴직'))
        if '비정규직' in question and re.search(r'재해|(?:공상|순직).*인정',question):facets.append(('비정규직 재해보상','재해보상'))
        if re.search(r'보수|급여',question) and re.search(r'각각|구분|연결|별도\s*규정',question):facets.append(('직원 보수','보수'))
        if re.search(r'소정.*(?:넘|초과)|초과.?근로|연장.?근무',question):
            if re.search(r'연소|미성년|15\s*세|18\s*세',question):facets.append(('연소자 직원 연장근무 제한','연장근무의제한'))
            if '단시간' in question:facets.append(('단시간근로자 초과근로','초과근로'))
        if '단시간' in question and re.search(r'임금|급여|보수',question):facets.append(('단시간근로자 임금','임금'))
        if '가족' in question and '채용' in question:
            # Family preference, a scope-specific hiring prohibition and undue
            # influence are different rules. Bring the actual prohibitory clause.
            for candidate in lexical_search(question,None):
                if re.search(r'채용권자[^.]*가족[^.]*채용하여서는',re.sub(r'\s','',candidate['text'])):add(candidate['id'])
            facets.append(('인사관리규정 공개경쟁 가족 우대 채용','채용'))
        if ('비정규직' in question and re.search(r'(?<!비)정규직|일반\s*직원',question)
            and re.search(r'신체|정신|직무.*어렵|직무.*곤란',question)):
            facets.append(('직원 신체 정신 직무 해임','해임'))
        for subquery,heading in facets:
            candidates=[r for r in lexical_search(subquery,None) if re.sub(r'\s','',heading) in re.sub(r'\s','',section_heading(r['section']))]
            if candidates:add(candidates[0]['id'])
        query_terms=set(tokens(question))-STOPWORDS-{'규정','제조','기준','내용','경우','직원','계약','대한','하는','하여'}
        for seed in list(dict.fromkeys(result+ranking[:2])):
            row=lookup[seed]
            # Referenced articles that explicitly match the question's topic.
            for target in row.get('referenced_source_ids',[]):
                if target not in lookup:continue
                heading=section_heading(lookup[target]['section'])
                clean=re.sub(r'제\s*\d+\s*조(?:의\s*\d+)?|<[^>]*>','',heading)
                shared=(set(tokens(clean))-{'사항','일반','기준'})&query_terms
                if shared and re.search(r'열거|제외|산정|계산|인용|준용|참조|연결|출근율',question):add(target)
            # A bare heading such as '시기' borrows its topic from its exact
            # reference (e.g. retirement age -> retirement date), same version.
            for candidate in rows:
                clean=re.sub(r'제\s*\d+\s*조(?:의\s*\d+)?|<[^>]*>|\s','',section_heading(candidate['section']))
                if clean in {'시기','기간','신청','절차'} and re.search(r'시기|시점|일자|날짜|언제|예정|신청|절차',question) and candidate['version']==row['version'] and seed in candidate.get('referenced_source_ids',[]):add(candidate['id'])
    for rid in ranking:add(rid)
    return result


def source(source_id: str) -> dict | None:
    return next((row for row in corpus()[0] if row["id"] == source_id), None)
