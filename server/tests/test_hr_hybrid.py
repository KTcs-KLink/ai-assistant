"""Source boundaries and retrieval regressions, no model/API/DB calls or real data."""
from contextlib import contextmanager
import hashlib
import json

import numpy as np
import pytest

from server import hr_answer, hr_evidence, hr_vectors


def record(rid, title, heading, text="", version="v1", links=()):
    return dict(id=rid, title=title, section=f"{title} > 제1장 > {heading}", text=text,
        version=version, referenced_source_ids=list(links))


def test_amendment_closing_angle_bracket_is_not_a_hierarchy_separator():
    heading="제24조 지각·조퇴·외출 <개정 2008.12.23. 2019.12.3>"
    assert hr_evidence.section_heading("취업규칙 > 제2장 복무 > "+heading)==heading
    assert hr_evidence.article_key(hr_evidence.section_heading("취업규칙 > "+heading))==(24,0)


def test_bare_article_reference_does_not_displace_the_actual_question_topic(monkeypatch):
    rows=[record("topic","인사관리규정","제26조의4 전문분야 보직")]
    rows += [record(f"background{i}",title,"제8조 채용") for i,title in enumerate(["인사관리규정","인사관리지침","취업규칙","비정규직관리규정","5직급관리규정"])]
    ranking=[r['id'] for r in rows]
    monkeypatch.setattr(hr_evidence,"lexical_search",lambda *args:[])
    assert hr_evidence.select_facets("제8조에 따라 채용된 직원의 전문분야 보직을 변경할 수 있나요?",ranking,rows)[0]=="topic"


def test_named_article_only_prioritizes_the_named_regulation(monkeypatch):
    rows=[record("general","인사관리규정","제8조 채용"),record("specific","복지업무실무지침","제8조 공상 및 순직의 인정")]
    monkeypatch.setattr(hr_evidence,"lexical_search",lambda *args:[])
    result=hr_evidence.select_facets("복지업무 실무지침 제8조의 인정 절차는?",["general","specific"],rows)
    assert result[0]=="specific"


def test_retirement_and_contract_comparison_keeps_both_scopes_and_retirement_date(monkeypatch):
    rows=[record("form","비정규직관리규정","제13조 근로계약서",version="contract"),
        record("duration","비정규직관리규정","제10조 계약기간 단위 <개정 2020.1.1>",version="contract"),
        record("age","취업규칙","제60조 정년퇴직",version="employee"),
        record("date","취업규칙","제61조 시기",version="employee",links=["age"])]
    def lexical(q,limit):
        return [rows[1]] if "계약기간" in q else [rows[2]]
    monkeypatch.setattr(hr_evidence,"lexical_search",lexical)
    result=hr_evidence.select_facets("정규직 정년퇴직과 비정규직 근로계약 만료 시점을 같은 방식으로 정하나요?",["form","duration","age","date"],rows)
    assert set(result[:4])=={"form","duration","age","date"}


def test_article_dependencies_are_version_bound_and_skip_external_law():
    rows=[record("a","취업규칙","제1조 목적","제2조 및 근로기준법 제3조에 따른다."),
        record("b","취업규칙","제2조 적용"),record("c","취업규칙","제3조 용어"),
        record("old","취업규칙","제2조 적용",version="old")]
    assert hr_evidence.reference_links(rows)["a"]=={"b"}


@pytest.fixture
def vector_files(tmp_path,monkeypatch):
    source=tmp_path/"source";index=tmp_path/"index"
    (source/"data").mkdir(parents=True);(source/"indexes").mkdir();index.mkdir()
    corpus=source/"data/reviewed_units.jsonl";corpus.write_text("fixed source\n")
    text="원문의 허용 구간입니다."
    allowed=dict(id="allowed",text=text,source_file_sha256="f"*64,sha256=hashlib.sha256(text.encode()).hexdigest())
    window=dict(id="w1",unit_record_id="allowed",retrieval_only=True,source_file_sha256="f"*64,
        start=0,end=len(text),text_sha256=allowed["sha256"])
    other=window|dict(id="w2",unit_record_id="outside")
    window_path=source/"indexes/windows.jsonl"
    window_path.write_text("\n".join(json.dumps(w,ensure_ascii=False) for w in [window,other]),encoding="utf-8")
    values=np.zeros((2,1024),dtype=np.float32);values[0,0]=1;values[1,1]=1
    np.save(index/"windows.npy",values)
    meta=dict(model=hr_vectors.MODEL,revision=hr_vectors.REVISION,weights_sha256=hr_vectors.WEIGHTS,
        dimension=1024,truncation=False,normalized=True,source_sha256=hr_vectors.sha(corpus),
        vectors_sha256=hr_vectors.sha(index/"windows.npy"),windows_sha256=hr_vectors.sha(window_path),ids=["w1","w2"])
    (index/"windows_vectors.json").write_text(json.dumps(meta),encoding="utf-8")
    monkeypatch.setattr(hr_vectors,"SOURCE",source);monkeypatch.setattr(hr_vectors,"INDEX",index)
    return allowed,corpus,index,meta


def test_vector_scoring_excludes_every_source_outside_the_allowlist(vector_files):
    allowed,corpus,_,_=vector_files
    index=hr_vectors.VectorIndex([allowed],corpus)
    query=np.zeros(1024,dtype=np.float32);query[1]=1
    assert index.ids==["allowed"]
    assert index.score(query)=={"allowed":0.0}


def test_vector_source_span_tampering_and_cross_project_path_are_rejected(vector_files):
    allowed,corpus,_,_=vector_files
    with pytest.raises(hr_vectors.VectorUnavailable):
        hr_vectors.VectorIndex([allowed|dict(text="변경한 원문")],corpus)
    with pytest.raises(hr_vectors.VectorUnavailable):
        hr_vectors.VectorIndex([allowed],corpus.parent/"another-project.jsonl")


def test_different_model_cannot_reuse_the_kepco_vectors(vector_files):
    allowed,corpus,index,meta=vector_files
    (index/"windows_vectors.json").write_text(json.dumps(meta|dict(model="another-model")),encoding="utf-8")
    with pytest.raises(hr_vectors.VectorUnavailable):hr_vectors.VectorIndex([allowed],corpus)


@pytest.mark.parametrize("origin",["https://127.0.0.1:8841","http://localhost:8841","http://127.0.0.1:8841/path","http://someone:password@127.0.0.1:8841","http://example.invalid:8841"])
def test_encoder_connection_cannot_be_redirected_to_another_host(monkeypatch,origin):
    monkeypatch.setenv("KLINK_HR_ENCODER_URL",origin)
    with pytest.raises(hr_vectors.VectorUnavailable):hr_vectors.endpoint()


def test_encoder_identity_is_checked_before_a_vector_can_be_accepted(monkeypatch):
    @contextmanager
    def fake(*a,**kw):
        from io import BytesIO
        yield BytesIO(json.dumps(dict(app_id="other-project",model=hr_vectors.MODEL,dimension=1024)).encode())
    monkeypatch.setattr(hr_vectors.urllib.request,"urlopen",fake)
    monkeypatch.setenv("KLINK_HR_ENCODER_URL","http://127.0.0.1:8841")
    with pytest.raises(hr_vectors.VectorUnavailable,match="다른 프로젝트"):
        hr_vectors.request("/embed",dict(text="일반 인사 질문"))


def test_missing_hybrid_service_withholds_without_any_generation_or_silent_fallback(monkeypatch):
    monkeypatch.setattr(hr_evidence,"summary",lambda:{"method":"hr_bge_m3_hybrid"})
    def unavailable(*a,**kw):raise hr_vectors.VectorUnavailable("Unavailable")
    monkeypatch.setattr(hr_evidence,"search",unavailable)
    def forbidden():raise AssertionError("must not read a generation credential")
    monkeypatch.setattr(hr_answer.benefit_explanation,"settings",forbidden)
    response=hr_answer.generate("연차휴가 계산 기간을 알려 주세요")
    assert response["validation"]=="KEPCO_RETRIEVAL_UNAVAILABLE_NO_GENERATION"
    assert not response["paragraphs"] and not response["sources"]


def test_many_citations_keep_the_full_intervening_original_text():
    text="\n".join(f"{i}. 원문의 실제 조건은 보존한다." for i in range(1,7))
    paragraph=hr_answer.Paragraph(text="원문의 조건을 함께 확인합니다.",citations=[hr_answer.Citation(source_id="a",quote=line) for line in text.splitlines()])
    draft=hr_answer.Draft(status="answered",paragraphs=[paragraph],missing_information=[])
    result=hr_answer.validate(draft,[dict(id="a",text=text)])
    assert len(result.paragraphs[0].citations)==1
    assert result.paragraphs[0].citations[0].quote==text


def test_qualified_paragraph_reference_restores_its_enclosing_original_context():
    text="제60조의3(명예퇴직)\n① 적용 대상의 원칙이다.\n② 별도 지급 규정이다.\n③ 다음 기간을 제외한다.\n1. 직위해제기간\n2. 정직처분기간\n④ 별도 절차를 따른다."
    source=dict(id="a",text=text,section="취업규칙 > 제60조의3 명예퇴직")
    draft=hr_answer.Draft(status="answered",paragraphs=[hr_answer.Paragraph(text="제60조의3 제3항은 정직처분기간을 제외합니다.",citations=[hr_answer.Citation(source_id="a",quote="2. 정직처분기간")])],missing_information=[])
    result=hr_answer.validate(draft,[source])
    quote=result.paragraphs[0].citations[0].quote
    assert quote.startswith("③") and "2. 정직처분기간" in quote and quote in text
    bad=result.model_copy(deep=True)
    bad.paragraphs[0].text="제60조의3 제3항은 97년을 제외합니다."
    with pytest.raises(hr_answer.AnswerUnavailable,match="수치"):hr_answer.validate(bad,[source])


def test_model_span_ids_reconstruct_original_punctuation_and_preserve_every_character():
    source=dict(id="a",text="제1조(범위)\n① 첫 조건이다. <개정 2026.1.1>\n② 실험․조사 등 지원업무는 별도로 정한다.")
    spans=hr_answer.source_spans(source)
    assert "".join(s['text'] for s in spans)==source['text']
    refs=hr_answer.SpanDraft(status="answered",paragraphs=[hr_answer.SpanParagraph(text="지원업무는 별도로 정합니다.",citations=[hr_answer.SpanCitation(source_id="a",span_ids=["S2"])])],missing_information=[])
    result=hr_answer.resolve_spans(refs,[source])
    assert result.paragraphs[0].citations[0].quote=="② 실험․조사 등 지원업무는 별도로 정한다."
    for bad in [dict(source_id="outside",span_ids=["S2"]),dict(source_id="a",span_ids=["S999"]),dict(source_id="a",span_ids=[])]:
        refs.paragraphs[0].citations=[hr_answer.SpanCitation(**bad)]
        with pytest.raises(hr_answer.AnswerUnavailable):hr_answer.resolve_spans(refs,[source])


def test_cross_article_comparison_gets_real_retrieved_context_without_approving_invented_article():
    first=dict(id="a",title="취업규칙",section="취업규칙 > 제1조 범위",text="제1조(범위)\n① 이 규정의 적용 범위를 정한다.")
    second=dict(id="b",title="취업규칙",section="취업규칙 > 제2조 예외",text="제2조(예외)\n① 별도 예외 조건을 적용한다.")
    paragraph=hr_answer.Paragraph(text="취업규칙 제1조 제1항과 제2조 제1항은 범위와 예외를 나누어 정합니다.",citations=[hr_answer.Citation(source_id="a",quote=first['text'])])
    draft=hr_answer.Draft(status="answered",paragraphs=[paragraph],missing_information=[])
    result=hr_answer.validate(draft,[first,second])
    assert {c.source_id for c in result.paragraphs[0].citations}=={"a","b"}
    assert result.paragraphs[0].citations[1].quote in second['text']
    bad=result.model_copy(deep=True);bad.paragraphs[0].text+=" 제999조도 적용됩니다."
    with pytest.raises(hr_answer.AnswerUnavailable,match="조문"):hr_answer.validate(bad,[first,second])


def test_free_use_principle_does_not_authorize_an_unlisted_personal_outing():
    sources=[dict(id="free",text="휴게시간은 질서와 규율을 지키는 범위에서 자유롭게 이용할 수 있다."),
        dict(id="purpose",text="외출은 사회공헌활동, 당직근무휴무 목적으로 사용할 수 있다.")]
    paragraph=hr_answer.Paragraph(text="질서와 규율을 지키면 근무장소 밖에서 개인 용무를 보는 것도 원칙적으로 가능하다고 볼 수 있습니다.",
        citations=[hr_answer.Citation(source_id="free",quote=sources[0]['text'])])
    draft=hr_answer.Draft(status="answered",paragraphs=[paragraph],missing_information=[])
    with pytest.raises(hr_answer.AnswerUnavailable,match="외출 허용"):
        hr_answer.validate(draft,sources,"휴게시간에 근무장소 밖으로 나가 개인 용무를 볼 수 있나요?")
    draft.paragraphs[0].text="휴게시간 중 근무장소 밖의 개인 용무까지 허용된다고 단정할 수 없습니다."
    assert hr_answer.validate(draft,sources,"휴게시간에 근무장소 밖으로 나가 개인 용무를 볼 수 있나요?")


def test_number_repair_diagnostic_does_not_weaken_the_source_number_check():
    source=dict(id="a",text="규정에서 정한 기간은 3일이다.")
    paragraph=hr_answer.Paragraph(text="규정에서 정한 기간은 92일입니다.",citations=[hr_answer.Citation(source_id="a",quote=source['text'])])
    with pytest.raises(hr_answer.AnswerUnavailable) as error:
        hr_answer.validate(hr_answer.Draft(status="answered",paragraphs=[paragraph],missing_information=[]),[source])
    assert error.value.repair_details['unsupported_numbers']==['92']


def test_general_leave_duration_is_not_lost_when_only_the_shorter_exception_is_answered():
    text="교육·휴직 등의 기간이 9개월 이상인 경우와 출산휴가에 이어 육아휴직을 2개월 이상 사용하는 경우에는 결원을 보충할 수 있다."
    source=dict(id="a",text=text)
    draft=hr_answer.Draft(status="answered",paragraphs=[hr_answer.Paragraph(
        text="교육은 9개월 이상, 출산휴가에 이어 육아휴직을 2개월 이상 쓰면 결원을 보충할 수 있습니다.",
        citations=[hr_answer.Citation(source_id="a",quote=text)])],missing_information=[])
    with pytest.raises(hr_answer.AnswerUnavailable) as error:
        hr_answer.finalize(draft,[source],"장기 교육이나 육아휴직 때 결원을 보충할 수 있나요?")
    assert error.value.code=="CRITICAL_CONDITION_OMISSION"
    assert error.value.repair_details['general_minimum']=='9개월'
    draft.paragraphs[0].text+=" 육아휴직도 일반 휴직으로서 9개월 이상이면 해당합니다."
    assert hr_answer.validate(draft,[source],"장기 교육이나 육아휴직 때 결원을 보충할 수 있나요?")


@pytest.mark.parametrize('claim',["이 예외는 4직급 직원도 포함합니다.","이 예외는 4직급 직원에게 적용되는 예외가 아닙니다."])
def test_grade_exception_does_not_assume_an_unprovided_organizational_rank_order(claim):
    source=dict(id="a",text="4직급 이상 직원은 원칙적으로 전환할 수 없다. 다만 필요한 경우 2직급 이하 직원에 대해 전환할 수 있다.")
    draft=hr_answer.Draft(status="answered",paragraphs=[hr_answer.Paragraph(text=claim,citations=[hr_answer.Citation(source_id="a",quote=source['text'])])],missing_information=[])
    with pytest.raises(hr_answer.AnswerUnavailable) as error:
        hr_answer.validate(draft,[source])
    assert error.value.code=='UNVERIFIED_RANK_SCOPE'
    draft.paragraphs[0].text="이 예외에 4직급 직원이 포함되는지는 직급 체계의 확인이 필요합니다."
    assert hr_answer.validate(draft,[source])
