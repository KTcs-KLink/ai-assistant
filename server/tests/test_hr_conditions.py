import hashlib
from server import hr_conditions


def source(text):
    return dict(id="TEST",text=text,sha256=hashlib.sha256(text.encode()).hexdigest(),title="가상 테스트",section="제1조")


def test_whole_paragraph_keeps_principle_before_quote_and_exception_after_quote():
    text="제1조(가상 조건)\n① 사전 승인이 원칙이다. 다만 불가피하면 당일 승인하여야 한다.\n② 다른 요건은 별도로 정한다."
    row=source(text)
    answer=[dict(text="일부 요약",citations=[dict(source_id="TEST",quote="다만 불가피하면 당일 승인하여야 한다.")])]
    result=hr_conditions.build(answer,[row])
    assert len(result["source_conditions"])==1
    card=result["source_conditions"][0]
    assert "사전 승인이 원칙" in card["quote"] and "당일 승인" in card["quote"]
    assert "다른 요건" not in card["quote"]
    assert card["quote"]==text[card["start"]:card["end"]]
    assert not card["human_approved"]


def test_no_numbered_paragraph_preserves_entire_article_including_scope_and_exception():
    text="제20조(가상) 교육·휴직 등의 기간이 6개월 이상인 경우 보충할 수 있다. 다만 출산휴가에 이어 3개월 이상인 경우도 가능하다."
    result=hr_conditions.build([dict(citations=[dict(source_id="TEST",quote="교육·휴직 등의 기간이 6개월 이상인 경우")])],[source(text)])
    assert result["source_conditions"][0]["quote"]==text
    assert result["condition_coverage"]=="CITED_PARAGRAPHS_ONLY_NOT_ALL_REQUIRED_ARTICLES"


def test_unmatched_duplicate_tampered_or_oversized_evidence_is_not_silently_selected_or_cut():
    for text,quote,patch in [("가상 조건은 승인하여야 한다.","없는 원문 인용",{}),
        ("승인하여야 한다. 승인하여야 한다.","승인하여야 한다.",{}),
        ("가상 조건은 승인하여야 한다.","가상 조건은 승인하여야 한다.",dict(sha256="0"*64)),
        ("가상 승인 원칙 "+"조건"*5000,"가상 승인 원칙",{})]:
        result=hr_conditions.build([dict(citations=[dict(source_id="TEST",quote=quote)])],[source(text)|patch])
        assert not result["source_conditions"] and result["condition_review_required"]
