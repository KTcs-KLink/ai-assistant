"""Expose complete source paragraphs beside prose, without inferring policy or eligibility.

These are source excerpts, not an approved rule registry. They cannot establish that
retrieval found every required article or that another company's rules apply.
"""
from __future__ import annotations

import hashlib
import re


MARKERS=re.compile(r"다만|원칙|불구|제외|한도|이내|한하여|하여야|해서는|경우|할 수|갈음|따르|신청|승인|보고|절상|계산|지급|청구")
BOUNDARY=re.compile(r"(?m)^\s*[①-⑳]|[①-⑳](?=\s)")


def build(paragraphs: list[dict], sources: list[dict]) -> dict:
    allowed={s["id"]:s for s in sources}
    cards=[]
    unresolved=[]
    seen=set()
    for p in paragraphs:
        for citation in p["citations"]:
            source=allowed.get(citation["source_id"])
            quote=citation["quote"]
            if not source or quote not in source["text"]:
                unresolved.append("인용과 원문의 연결을 확인해야 해요.")
                continue
            text=source["text"]
            source_hash=hashlib.sha256(text.encode()).hexdigest()
            if source.get("sha256",source_hash)!=source_hash:
                unresolved.append("원문 버전과 본문 해시를 다시 확인해야 해요.")
                continue
            if text.count(quote)!=1:
                unresolved.append(source["id"]+"의 인용 위치가 중복되어 전체 원문 확인이 필요해요.")
                continue
            start=text.index(quote)
            end=start+len(quote)
            boundaries=[0]+[m.start() for m in BOUNDARY.finditer(text) if m.start()>0]+[len(text)]
            for a,b in zip(boundaries,boundaries[1:]):
                if a>=end or b<=start:continue
                original=text[a:b]
                # A condition can be implicit ('출석 및 성적이 미달된 자') rather
                # than contain a cue such as '다만'. Keep every cited paragraph.
                key=(source["id"],a,b)
                if key in seen:continue
                seen.add(key)
                # Never shorten a paragraph at its exception or numeric limit.
                if len(original)>8000:
                    unresolved.append(source["id"]+"의 조건 원문이 길어 전체 원문 확인이 필요해요.")
                    continue
                cards.append(dict(source_id=source["id"],title=source.get("title"),section=source.get("section"),
                    quote=original,start=a,end=b,source_sha256=source_hash,
                    quote_sha256=hashlib.sha256(original.encode()).hexdigest(),
                    kind="ORIGINAL_SOURCE_PARAGRAPH_NOT_GENERATED",human_approved=False))
    return dict(source_conditions=cards,condition_review_required=list(dict.fromkeys(unresolved)),
        condition_coverage="CITED_PARAGRAPHS_ONLY_NOT_ALL_REQUIRED_ARTICLES")
