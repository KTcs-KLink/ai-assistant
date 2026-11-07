"""Read-only HR subset and lexical BM25. This is not the existing 960-question benchmark."""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import hashlib
import json
import math
import os
import re
from pathlib import Path

from . import hr_source_scope

try:
    from . import local_evidence
except ImportError:
    import local_evidence


HR_TITLES = frozenset({"인사관리규정", "인사관리지침", "취업규칙", "취업관리시행세칙", "5직급관리규정",
    "비정규직관리규정", "연봉및복리후생관리규정", "연봉및복리후생관리규정시행세칙", "노사협의회규정", "복지업무실무지침", "성희롱예방지침"})
HR_TERMS = re.compile(r"인사|근로|근무|급여|임금|수당|복지|복리|휴가|연차|병가|휴직|퇴직|사직|입사|채용|징계|교육|연수|출장|경조|육아|출산|자녀|정년|재직|해고|포상|노사|계약|재고용|비정규|보직|전보|겸직|임용|승진|승급|발령|직급|직위|평정|성과급|보수|결근|지각|조퇴|휴게|신원보증|학자금|학비|건강검진|건강진단|산재|재해|공상|순직|퇴교|업무량|업무부여|업무를.*부여|재배분|해임|파견|전근|직군|전기원|응시|선발|지원자|공가|휴일|출근|외출|직무급|연봉|공로금|공로기금|체육|후생시설|동호회|써클|위로금|조위금|자기개발|전문원|연구원|평가|임명|임기|뽑|비서|근속|격려금|인계")
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
    (r"평가기간|이전.*실적", "근무평정원칙"), (r"격려금|조위금|위로금", "적용례"))
PRIVATE = re.compile(r"(?:sk-[A-Za-z0-9_-]{15,}|sb_(?:secret|publishable)_[A-Za-z0-9_-]+|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|\b\d{6}[- ]?[1-8]\d{6}\b|\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b)", re.I)


def title_key(title: str) -> str:
    return re.sub(r"\s", "", re.sub(r"[_ -]+\d{6,8}$", "", title))


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


@lru_cache(maxsize=4)
def _load(path: str, mtime: int, size: int, verified=None, review_only=False):
    records, seen, rejected = [], set(), 0
    with Path(path).open(encoding="utf-8") as file:
        for line in file:
            row = json.loads(line)
            if verified is None:
                if title_key(row.get("document_title", "")) not in HR_TITLES:
                    continue
            elif (row['id'],row.get('text_sha256'),row.get('source_file_sha256'),row.get('file_version_key')) not in verified:
                continue
            required = ("searchable", "source_scope_reviewed") if review_only else ("searchable", "answer_eligible", "source_scope_reviewed")
            if not all(row.get(key) is True for key in required):
                continue
            if hashlib.sha256(row.get("text", "").encode()).hexdigest() != row.get("text_sha256") or row["id"] in seen or PRIVATE.search(row.get("text", "")):
                rejected += 1
                continue
            seen.add(row["id"])
            records.append(dict(id=row["id"], title=row["document_title"], section=row["heading_path"], text=row["text"],
                sha256=row["text_sha256"], source_file_sha256=row.get("source_file_sha256"), version=row.get("file_version_key"),
                company="KEPCO", employee_scope=row.get("employee_scope", "적용 대상 확인 필요"),
                review_status=row.get("review_status"), human_approved=row.get("human_approved") is True,
                effective_status=row.get("effective_status"), ktcs_applicable=False,
                answer_eligible=not review_only, review_only=review_only,
                source_mapping_verified=verified is not None,
                needs_layout_review=bool(row.get('needs_layout_review')),
                scope_gate=row.get('scope_gate'), source_scope_decision=row.get('decision')))
    links=reference_links(records)
    lookup={r['id']:r for r in records}
    for row in records:
        row['referenced_source_ids']=sorted(links[row['id']])
    counters = [Counter(tokens(r["title"] + " " + r["section"]) * 3 + tokens(r["text"])+
        tokens(' '.join(section_heading(lookup[rid]['section']) for rid in links[r['id']]))) for r in records]
    frequencies = Counter(t for counter in counters for t in counter)
    lengths = [sum(c.values()) for c in counters]
    return records, counters, frequencies, lengths, rejected


def corpus(review_only=False):
    path = local_evidence.corpus_path()
    if not path or not path.is_file():
        return [], [], Counter(), [], 0
    manifest = hr_source_scope.load(path)
    if review_only and manifest is None:
        return [], [], Counter(), [], 0
    verified = None if manifest is None else hr_source_scope.signature(e for e in manifest['units']
        if e['structural_verified'] and (not e['answer_eligible'] if review_only else e['answer_eligible']))
    stat = path.stat()
    return _load(str(path), stat.st_mtime_ns, stat.st_size, verified, review_only)


def summary() -> dict:
    rows, _, _, _, rejected = corpus()
    manifest=hr_source_scope.load(local_evidence.corpus_path()) if hr_source_scope.expanded() and local_evidence.corpus_path() else None
    return dict(method="hr_bge_m3_hybrid" if os.getenv('KLINK_HR_RETRIEVAL')=='hybrid' else "hr_lexical_bm25", company="KEPCO", ktcs_applicable=False, source_count=len(rows),
        document_count=len({r["title"] for r in rows}), human_approved_count=sum(r["human_approved"] for r in rows),
        rejected_sources=rejected, source_scope="expanded" if hr_source_scope.expanded() else "baseline",
        review_only_count=sum(e['structural_verified'] and not e['answer_eligible'] for e in manifest['units']) if manifest else 0,
        scope="Original-file and source-span verified HR units; held units excluded from answers" if hr_source_scope.expanded()
            else "HR title allowlist plus existing automatic source-scope and answer gates")


def lexical_search(question: str, limit: int | None = None) -> list[dict]:
    return _lexical_search(question, corpus(), limit)


def review_search(question: str, limit: int=5) -> list[dict]:
    """Source-only review search; never used as an answer evidence provider."""
    from . import hr_review_index
    return hr_review_index.search(question,limit)


def _lexical_search(question, data, limit):
    if PRIVATE.search(question):
        raise ValueError("개인정보나 키를 제외하고 일반적인 업무 질문만 입력해 주세요.")
    rows, counters, df, lengths, _ = data
    known_titles={title_key(row['title']) for row in rows}
    named={name for name in known_titles if name in title_key(question)}
    if not HR_TERMS.search(question) and not named:
        return []
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
    for row, counts, length in zip(rows, counters, lengths):
        # A contract form cannot establish a universal payday for all employees.
        if re.search(r"급여|월급|임금|보수", question) and re.search(r"언제|지급일|급여일|월급날|며칠", question) and "계약서" not in question:
            if re.search(r"계약서|서식|별지", row["section"]):
                continue
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
    maximum = len(rows) if limit is None else max(1,min(limit,len(rows)))
    return [{**row, "score": round(score, 5)} for score, row in hits[:maximum]]


def search(question: str,limit: int=3,semantic_plan=None) -> list[dict]:
    if semantic_plan is not None:
        return semantic_search(question,semantic_plan,limit)
    hits=lexical_search(question)
    if os.getenv('KLINK_HR_RETRIEVAL')!='hybrid':return hits[:max(1,min(limit,5))]
    if PRIVATE.search(question):return []
    if not hits and not HR_TERMS.search(question):return []
    from . import hr_vectors
    rows=corpus()[0]
    if not rows:return []
    dense=hr_vectors.get_index(rows,local_evidence.corpus_path()).search(question)
    fused=hr_vectors.fuse([r['id'] for r in hits],dense)
    ordered=select_facets(question,sorted(fused,key=lambda rid:(-fused[rid],rid)),rows)
    lookup={r['id']:r for r in rows}
    return [{**lookup[rid],'score':round(fused[rid],7)} for rid in ordered[:max(1,min(limit,5))]]


def semantic_search(question,plan,limit=5):
    """Fuse original and checked intent queries over the same source allowlist.

    The original question stays present. Intent queries do not retrieve a
    different corpus, read a golden answer, or authorize an employee.
    """
    from .hr_intent import Understanding,private_or_invalid
    if not isinstance(plan,Understanding) or private_or_invalid(question):
        raise ValueError('검증된 질문 의미 분석이 필요해요.')
    queries=plan.queries(question)
    rows=corpus()[0]
    if not rows:return []
    scores={r['id']:0. for r in rows}
    if os.getenv('KLINK_HR_RETRIEVAL')=='hybrid':
        from . import hr_vectors
        index=hr_vectors.get_index(rows,local_evidence.corpus_path())
    else:index=None
    for i,query in enumerate(queries):
        lexical=lexical_search(query)
        if index is not None:
            fused=hr_vectors.fuse([r['id'] for r in lexical],index.search(query))
            ranking=sorted(fused,key=lambda rid:(-fused[rid],rid))
        else:ranking=[r['id'] for r in lexical]
        weight=1.0 if i==0 else 2.0
        for position,rid in enumerate(ranking[:100],1):scores[rid]+=weight/(10+position)
    ranking=sorted(scores,key=lambda rid:(-scores[rid],rid))
    context=question+' '+plan.canonical_query
    ranking=select_facets(context,ranking,rows)
    lookup={r['id']:r for r in rows}
    return [{**lookup[rid],'score':round(scores[rid],7)} for rid in ranking[:max(1,min(limit,5))] if scores[rid]>0]


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
    # A named specialist regulation owns the requested topic even without an
    # article number. Do not replace part-time hours with general staff hours.
    if named and not explicit:
        for rid in [rid for rid in ranking if title_key(lookup[rid]['title']) in named][:2]:add(rid)
    if ranking:add(ranking[0])
    mixed=bool(re.search(r'(?<!비)정규직|일반\s*직원',question)) and '비정규직' in question
    if not (explicit and named and not mixed):
        facets=[]
        if re.search(r'넘기|인수인계|사무인계|인계',question):facets.append(('사무 인계 담당사무 후임자','인계'))
        if re.search(r'근무장소.*밖|밖으로.*나가|외출',question):facets.append(('근무 장소 이탈 외출','외출'))
        if re.search(r'계약.*(?:만료|종료|기간)|(?:만료|종료).*계약',question):facets.append(('비정규직 계약기간 단위','계약기간'))
        if '정년퇴직' in question:facets.append(('직원 정년퇴직','정년퇴직'))
        if '비정규직' in question and re.search(r'재해|(?:공상|순직).*인정',question):facets.append(('비정규직 재해보상','재해보상'))
        if re.search(r'보수|급여',question) and re.search(r'각각|구분|연결|별도\s*규정',question):facets.append(('직원 보수','보수'))
        for subquery,heading in facets:
            candidates=[r for r in lexical_search(subquery,len(rows)) if heading in section_heading(r['section'])]
            if candidates:add(candidates[0]['id'])
        query_terms=set(tokens(question))-STOPWORDS-{'규정','제조','기준','내용','경우','직원','계약','대한','하는','하여'}
        for seed in list(dict.fromkeys(result+ranking[:2])):
            row=lookup[seed]
            # Referenced articles that explicitly match the question's topic.
            for target in row.get('referenced_source_ids',[]):
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
