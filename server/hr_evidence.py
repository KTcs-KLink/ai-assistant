"""Read-only HR subset and lexical BM25. This is not the existing 960-question benchmark."""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import hashlib
import json
import math
import re
from pathlib import Path

try:
    from . import local_evidence
except ImportError:
    import local_evidence


HR_TITLES = frozenset({"인사관리규정", "인사관리지침", "취업규칙", "취업관리시행세칙", "5직급관리규정",
    "비정규직관리규정", "연봉및복리후생관리규정", "연봉및복리후생관리규정시행세칙", "노사협의회규정", "복지업무실무지침", "성희롱예방지침"})
HR_TERMS = re.compile(r"인사|근로|근무|급여|임금|수당|복지|복리|휴가|연차|병가|휴직|퇴직|사직|입사|채용|징계|교육|연수|출장|경조|육아|출산|자녀|정년|재직|해고|포상|노사|계약|재고용|비정규|보직|전보|겸직|임용|승진|승급|발령|직급|직위|평정|성과급|보수|결근|지각|조퇴|휴게|신원보증|학자금|학비|건강검진|건강진단|산재|재해|공상|순직|퇴교|업무량|업무부여|업무를.*부여|재배분|해임|파견|전근|직군|전기원|응시|선발|지원자|공가|휴일|출근|외출|직무급|연봉|공로금|공로기금|체육|후생시설|동호회|써클|위로금|조위금|자기개발|전문원|연구원|평가|임명|임기")
STOPWORDS = frozenset("무엇 무엇인가요 어떻게 있나요 있습니까 알려 주세요 직원 직원이 직원의 경우 경우에는 규정 기준 내용 확인 대한 대해서 합니다 하려고 해야 하나요 되나요 할 수 있는 어떤 각각 위해 관련 다음".split())
# A small, source-heading vocabulary. No questions, answers, gold IDs or test labels
# are indexed or consulted by retrieval.
QUERY_ALIASES = ((r"급여|월급", "보수"), (r"건강검진", "건강진단"),
    (r"점심|휴게", "휴게시간"), (r"아파|사전.*결근|갑자기.*승인", "결근"),
    (r"업무량|재배분", "업무부여"), (r"보직.*기준|희망.*보직", "보직 원칙"),
    (r"다시.*계약|재계약|계약.*공백|계약.*갱신", "재고용계약"),
    (r"제출.*서류|서류.*제출", "구비서류"), (r"허위사실|거짓.*서류", "결격사유"),
    (r"계약기간|계약.*기간.*단위", "계약기간 단위"))
PRIVATE = re.compile(r"(?:sk-[A-Za-z0-9_-]{15,}|sb_(?:secret|publishable)_[A-Za-z0-9_-]+|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|\b\d{6}[- ]?[1-8]\d{6}\b|\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b)", re.I)


def title_key(title: str) -> str:
    return re.sub(r"\s", "", re.sub(r"[_ -]+\d{6,8}$", "", title))


def tokens(text: str) -> list[str]:
    result = []
    for word in re.findall(r"[가-힣]{2,}|[a-z0-9]+", text.lower()):
        result.append(word)
        if re.fullmatch(r"[가-힣]{3,}", word):
            result.extend(word[i:i+2] for i in range(len(word)-1))
    return result


@lru_cache(maxsize=2)
def _load(path: str, mtime: int, size: int):
    records, seen, rejected = [], set(), 0
    with Path(path).open(encoding="utf-8") as file:
        for line in file:
            row = json.loads(line)
            if title_key(row.get("document_title", "")) not in HR_TITLES:
                continue
            if not all(row.get(key) is True for key in ("searchable", "answer_eligible", "source_scope_reviewed")):
                continue
            if hashlib.sha256(row.get("text", "").encode()).hexdigest() != row.get("text_sha256") or row["id"] in seen or PRIVATE.search(row.get("text", "")):
                rejected += 1
                continue
            seen.add(row["id"])
            records.append(dict(id=row["id"], title=row["document_title"], section=row["heading_path"], text=row["text"],
                sha256=row["text_sha256"], source_file_sha256=row.get("source_file_sha256"), version=row.get("file_version_key"),
                company="KEPCO", employee_scope=row.get("employee_scope", "적용 대상 확인 필요"),
                review_status=row.get("review_status"), human_approved=row.get("human_approved") is True,
                effective_status=row.get("effective_status"), ktcs_applicable=False))
    counters = [Counter(tokens(r["title"] + " " + r["section"]) * 3 + tokens(r["text"])) for r in records]
    frequencies = Counter(t for counter in counters for t in counter)
    lengths = [sum(c.values()) for c in counters]
    return records, counters, frequencies, lengths, rejected


def corpus():
    path = local_evidence.corpus_path()
    if not path or not path.is_file():
        return [], [], Counter(), [], 0
    stat = path.stat()
    return _load(str(path), stat.st_mtime_ns, stat.st_size)


def summary() -> dict:
    rows, _, _, _, rejected = corpus()
    return dict(method="hr_lexical_bm25", company="KEPCO", ktcs_applicable=False, source_count=len(rows),
        document_count=len({r["title"] for r in rows}), human_approved_count=sum(r["human_approved"] for r in rows),
        rejected_sources=rejected, scope="HR title allowlist plus existing automatic source-scope and answer gates")


def search(question: str, limit: int = 3) -> list[dict]:
    if PRIVATE.search(question):
        raise ValueError("개인정보나 키를 제외하고 일반적인 업무 질문만 입력해 주세요.")
    if not HR_TERMS.search(question):
        return []
    rows, counters, df, lengths, _ = corpus()
    expanded = question + " " + " ".join(alias for pattern, alias in QUERY_ALIASES if re.search(pattern, question))
    if re.search(r"급여|보수|임금", question) and re.search(r"입사|신규|승진|전근|신분.*변경", question):
        expanded += " 지급기준 발령일"
    terms = set(tokens(expanded)) - STOPWORDS
    if not rows:
        return []
    average = sum(lengths)/len(rows) or 1
    hits = []
    for row, counts, length in zip(rows, counters, lengths):
        # A contract form cannot establish a universal payday for all employees.
        if re.search(r"급여|월급|임금|보수", question) and re.search(r"언제|지급일|급여일|월급날|며칠", question) and "계약서" not in question:
            if re.search(r"계약서|서식|별지", row["section"]):
                continue
        heading = row["section"].split(">")[-1]
        heading_terms = set(tokens(heading))
        score = sum(math.log(1+(len(rows)-df[t]+.5)/(df[t]+.5))*counts[t]*2.2/(counts[t]+1.2*(.25+.75*length/average))
                    * (2.0 if t in heading_terms else 1.0) for t in terms if counts[t])
        if "비정규직" in question and title_key(row["title"]) == "비정규직관리규정":
            score *= 1.6
        if "5직급" in question and title_key(row["title"]) == "5직급관리규정":
            score *= 1.6
        # Preserve exact multiword heading matches across Korean spacing. This
        # helps specific topics compete with generic words such as '직원/계약'.
        heading_compact = re.sub(r"\s", "", heading)
        for pattern, alias in QUERY_ALIASES:
            if re.search(pattern, question) and re.sub(r"\s", "", alias) in heading_compact:
                score += 12
        if score > 0:
            hits.append((score, row))
    hits.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    return [{**row, "score": round(score, 5)} for score, row in hits[:max(1, min(limit, 5))]]


def source(source_id: str) -> dict | None:
    return next((row for row in corpus()[0] if row["id"] == source_id), None)
