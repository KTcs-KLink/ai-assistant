"""Question meaning, condition preservation and paid-call boundaries, no real API."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from server import hr_answer,hr_evidence,hr_intent,hr_vectors


def proposal(**changes):
    return hr_intent.Proposal(**(dict(status='ready',intents=['regular_payday'],employment='unspecified',
        condition_quotes=[],clarifying_question='')|changes))


def test_equivalent_wording_gets_the_same_trusted_query_without_an_invented_payday():
    questions=['월급 언제 들어와요?','급여 입금일은?','회사에서 주는 돈이 통장에 들어오는 날은?']
    plans=[hr_intent.accept(proposal(),q,'configured-test-model') for q in questions]
    assert len({p.canonical_query for p in plans})==1
    assert all(p.queries(q)[0]==q for p,q in zip(plans,questions))
    assert all('25' not in p.canonical_query for p in plans)


def test_similar_pay_topics_do_not_share_the_same_query():
    a=hr_intent.accept(proposal(), '급여 지급일은?', 'test')
    b=hr_intent.accept(proposal(intents=['salary_period']), '급여 계산기간은?', 'test')
    c=hr_intent.accept(proposal(intents=['retirement_benefit']), '퇴직금 지급일은?', 'test')
    assert len({a.canonical_query,b.canonical_query,c.canonical_query})==3


def test_changed_employee_kind_duration_and_negation_are_preserved():
    q='계약직이 6개월 미만 근무하고 퇴직하면 퇴직금을 받을 수 없나요?'
    plan=hr_intent.accept(proposal(intents=['retirement_benefit'],employment='non_regular',condition_quotes=['6개월 미만']),q,'test')
    assert '계약직' in plan.conditions and '6개월 미만' in plan.conditions
    assert '비정규직' in plan.canonical_query and '6개월 미만' in plan.canonical_query
    with pytest.raises(hr_intent.IntentUnavailable,match='고용형태'):
        hr_intent.accept(proposal(employment='regular'),q,'test')
    with pytest.raises(hr_intent.IntentUnavailable):plan.queries(q.replace('미만','이상'))


def test_conditions_must_be_actual_question_quotes_and_not_model_paraphrases():
    q='기간제 직원이 네 달 뒤 재계약할 때 공백은 어떻게 보나요?'
    with pytest.raises(hr_intent.IntentUnavailable):
        hr_intent.accept(proposal(intents=['contract_renewal'],employment='non_regular',condition_quotes=['4개월']),q,'test')
    plan=hr_intent.accept(proposal(intents=['contract_renewal'],employment='non_regular',condition_quotes=['네 달']),q,'test')
    assert '네 달' in plan.conditions


def test_unspecified_employee_does_not_become_a_regular_employee():
    with pytest.raises(hr_intent.IntentUnavailable):
        hr_intent.accept(proposal(employment='regular'),'직원의 월급 지급일은?','test')
    assert hr_intent.accept(proposal(),'직원의 월급 지급일은?','test').proposal.employment=='unspecified'


@pytest.mark.parametrize('question,employment',[
    ('시간제 직원의 근무시간은?','unspecified'),('단시간근로자와 시간선택제 채용직원의 근무시간은?','unspecified'),
    ('정규직 단시간근로자의 근무시간은?','regular'),('계약직 시간제 직원의 근무시간은?','non_regular'),
])
def test_working_time_pattern_does_not_invent_an_employment_contract(question,employment):
    plan=hr_intent.accept(proposal(intents=['general_hr'],employment=employment),question,'test')
    assert plan.proposal.employment==employment
    assert any(word in plan.conditions for word in ['시간제','시간선택제','단시간근로자'])


@pytest.mark.parametrize('q',['병가 문의 test@example.invalid','병가 sk-TEST_ONLY_ABCDEFGHIJKLMNOP','병가 ｓｋ－ＴＥＳＴ＿ＯＮＬＹ＿ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰ'])
def test_private_or_obfuscated_key_is_blocked_before_model_settings_or_network(monkeypatch,q):
    def forbidden():raise AssertionError('must not read credentials')
    monkeypatch.setattr(hr_intent.benefit_explanation,'settings',forbidden)
    with pytest.raises(hr_intent.IntentUnavailable):hr_intent.understand(q)


def test_clarification_does_not_invent_a_regulatory_number():
    with pytest.raises(hr_intent.IntentUnavailable):
        hr_intent.accept(proposal(status='needs_clarification',intents=[],clarifying_question='25일 지급을 말씀하시나요?'),'그거 언제 돼요?','test')


def test_understanding_uses_the_existing_model_and_never_sends_credentials_or_profile(monkeypatch):
    monkeypatch.setattr(hr_intent.benefit_explanation,'settings',lambda:('test-only-provider-credential','existing-model'))
    class Fake:
        def __init__(self,**kw):
            self.responses=SimpleNamespace(input_tokens=SimpleNamespace(count=self.count),create=self.create)
        def count(self,**payload):
            assert payload['model']=='existing-model' and payload['truncation']=='disabled'
            assert 'test-only-provider-credential' not in str(payload) and 'hire_date' not in str(payload)
            return SimpleNamespace(input_tokens=1500)
        def create(self,**payload):
            assert payload['store'] is False
            assert payload['text']['format']['strict'] is True
            assert payload['text']['format']['schema']['properties']['employment']['enum']==['unspecified']
            return SimpleNamespace(status='completed',output_text=proposal().model_dump_json(),usage=None)
        def __enter__(self):return self
        def __exit__(self,*a):pass
    monkeypatch.setattr('openai.OpenAI',Fake)
    result=hr_intent.understand('월급 언제 받아요?')
    assert result.model=='existing-model' and result.call['phase']=='question_understanding'


def test_original_and_intent_queries_use_the_same_allowlist_with_no_golden_inputs(monkeypatch):
    rows=[dict(id='source-a',section='취업규칙 > 제1조',title='취업규칙'),dict(id='source-b',section='취업규칙 > 제2조',title='취업규칙')]
    monkeypatch.setattr(hr_evidence,'corpus',lambda:(rows,None,None,None,0))
    monkeypatch.setattr(hr_evidence.local_evidence,'corpus_path',lambda:'fixed-kepco-path')
    monkeypatch.setattr(hr_evidence,'lexical_search',lambda *a:[])
    monkeypatch.setattr(hr_evidence,'select_facets',lambda q,ranking,records:ranking)
    monkeypatch.setenv('KLINK_HR_RETRIEVAL','hybrid')
    seen=[]
    class Index:
        def search(self,q):seen.append(q);return {'source-a':.9,'source-b':.1}
    def index(sources,path):
        assert sources is rows and path=='fixed-kepco-path'
        return Index()
    monkeypatch.setattr(hr_vectors,'get_index',index)
    q='회사에서 주는 돈이 통장에 들어오는 날은?'
    plan=hr_intent.accept(proposal(),q,'test')
    result=hr_evidence.search(q,5,semantic_plan=plan)
    assert seen==[q,plan.canonical_query]
    assert {r['id'] for r in result}=={'source-a','source-b'}


def test_ambiguous_question_asks_for_clarification_without_retrieval_or_answer_generation(monkeypatch):
    q='그거 언제 돼요?'
    plan=hr_intent.accept(proposal(status='needs_clarification',intents=[],clarifying_question='급여 지급일과 휴가 신청 중 어떤 업무인가요?'),q,'test',dict(phase='question_understanding'))
    monkeypatch.setenv('KLINK_HR_INTENT_MODE','llm')
    monkeypatch.setattr(hr_evidence,'summary',lambda:{})
    monkeypatch.setattr(hr_intent,'understand',lambda value:plan)
    def forbidden(*a,**kw):raise AssertionError('must not retrieve or generate')
    monkeypatch.setattr(hr_evidence,'search',forbidden)
    monkeypatch.setattr(hr_answer.benefit_explanation,'settings',forbidden)
    result=hr_answer.generate(q)
    assert result['validation']=='QUESTION_CLARIFICATION_REQUIRED' and not result['paragraphs']
    assert len(result['provider_calls'])==1 and result['understanding']['original_question_preserved']


def test_answer_keeps_original_question_and_three_distinct_phases(monkeypatch):
    q='회사에서 주는 돈이 통장에 들어오는 날은?'
    plan=hr_intent.accept(proposal(),q,'existing-model',dict(phase='question_understanding'))
    text='가상 검사 규정은 매월 25일을 지급일로 정한다.'
    source=dict(id='test-source',title='가상 검사 규정',section='제1조',text=text,
        sha256=hashlib.sha256(text.encode()).hexdigest(),version='test-only',company='KEPCO',human_approved=False)
    monkeypatch.setenv('KLINK_HR_INTENT_MODE','llm')
    monkeypatch.setattr(hr_evidence,'summary',lambda:{})
    monkeypatch.setattr(hr_intent,'understand',lambda value:plan)
    def search(value,**kw):
        assert value==q and kw['semantic_plan'] is plan
        return [source]
    monkeypatch.setattr(hr_evidence,'search',search)
    monkeypatch.setattr(hr_answer.benefit_explanation,'settings',lambda:('test-only-key','existing-model'))
    class Fake:
        def __init__(self,**kw):
            self.responses=SimpleNamespace(input_tokens=SimpleNamespace(count=lambda **kw:SimpleNamespace(input_tokens=1000)),create=self.create)
        def create(self,**payload):
            user=json.loads(payload['input'])
            assert user['question']==q and user['question_meaning']['topics']==['정기 급여 지급일']
            assert 'test-only-key' not in str(payload) and 'hire_date' not in str(payload)
            return SimpleNamespace(status='completed',usage=None,output_text=json.dumps(dict(status='answered',paragraphs=[dict(text='가상 검사 규정의 지급일은 매월 25일입니다.',citations=[dict(source_id='test-source',span_ids=['S0'])])],missing_information=[])))
        def __enter__(self):return self
        def __exit__(self,*a):pass
    monkeypatch.setattr('openai.OpenAI',Fake)
    result=hr_answer.generate(q)
    assert [c['phase'] for c in result['provider_calls']]==['question_understanding','draft','source_comparison']
    assert result['paragraphs'] and not result['employee_data_sent'] and not result['human_approved']


def test_failed_meaning_request_is_accounted_for_and_never_falls_through_to_generation(monkeypatch):
    monkeypatch.setenv('KLINK_HR_INTENT_MODE','llm')
    monkeypatch.setattr(hr_evidence,'summary',lambda:{})
    def fail(q):
        error=hr_intent.IntentUnavailable()
        error.call=dict(phase='question_understanding',request_attempted=True,usage=None)
        raise error
    monkeypatch.setattr(hr_intent,'understand',fail)
    def forbidden(*a,**kw):raise AssertionError('must not retrieve or generate')
    monkeypatch.setattr(hr_evidence,'search',forbidden)
    result=hr_answer.generate('월급 지급일은?')
    assert not result['paragraphs'] and result['provider_calls'][0]['request_attempted']


def test_provider_error_hides_raw_body_but_keeps_attempt_accounting(monkeypatch):
    monkeypatch.setattr(hr_intent.benefit_explanation,'settings',lambda:('test-only-provider-key','existing-model'))
    class Fake:
        def __init__(self,**kw):self.responses=SimpleNamespace(input_tokens=SimpleNamespace(count=lambda **kw:SimpleNamespace(input_tokens=100)),create=self.create)
        def create(self,**kw):raise RuntimeError('provider-body-never-show-this')
        def __enter__(self):return self
        def __exit__(self,*a):pass
    monkeypatch.setattr('openai.OpenAI',Fake)
    with pytest.raises(hr_intent.IntentUnavailable) as caught:hr_intent.understand('월급 언제 받아요?')
    assert 'provider-body-never-show-this' not in str(caught.value)
    assert caught.value.call['request_attempted']


def test_answer_blocks_full_width_secret_even_when_meaning_mode_is_off(monkeypatch):
    monkeypatch.delenv('KLINK_HR_INTENT_MODE',raising=False)
    def forbidden(*a,**kw):raise AssertionError('must not read credentials')
    monkeypatch.setattr(hr_answer.benefit_explanation,'settings',forbidden)
    with pytest.raises(hr_answer.AnswerUnavailable):hr_answer.generate('병가 ｓｋ－ＴＥＳＴ＿ＯＮＬＹ＿ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰ')


def test_payday_fact_is_read_from_the_source_instead_of_a_fixed_or_generated_answer():
    source=dict(id='synthetic-source',title='연봉 및 복리후생관리규정',section='제3장 직원연봉 > 제17조 지급일',
        text='가상 시험용 원문: 보수의 지급일은 매월 27일로 한다. 다만 지급일이 휴일 또는 토요일이면 그 전일로 한다.')
    outputs=[]
    for q in ['월급 언제 들어와요?','회사에서 주는 돈이 통장에 들어오는 날은?']:
        plan=hr_intent.accept(proposal(),q,'test')
        draft=hr_answer.source_payday(q,plan,[source])
        assert draft and draft.paragraphs[0].citations[0].quote==source['text']
        outputs.append(draft.paragraphs[0].text)
    assert outputs[0]==outputs[1] and '27일' in outputs[0] and '25일' not in outputs[0]


def test_payday_shortcut_rejects_wrong_scope_clock_times_and_conflicting_dates():
    source=dict(id='a',title='연봉 및 복리후생관리규정',section='제3장 직원연봉 > 제17조 지급일',text='가상 시험용 원문: 정기 보수는 매월 27일 지급한다.')
    q='계약직 월급 지급일은?'
    plan=hr_intent.accept(proposal(employment='non_regular'),q,'test')
    assert hr_answer.source_payday(q,plan,[source]) is None
    q='은행에서 급여가 실제 몇 시에 반영되나요?'
    assert hr_answer.source_payday(q,hr_intent.accept(proposal(),q,'test'),[source]) is None
    q='월급 언제 받아요?';plan=hr_intent.accept(proposal(),q,'test')
    conflict=source|dict(id='b',text=source['text'].replace('27일','28일'))
    assert hr_answer.source_payday(q,plan,[source,conflict]) is None


def test_small_cosine_reduction_preserves_window_maximum_and_source_order():
    import numpy as np
    index=hr_vectors.VectorIndex.__new__(hr_vectors.VectorIndex)
    index.ids=['a','a','b']
    index.vectors=np.zeros((3,1024),dtype=np.float32)
    index.vectors[0,:2]=[.8,.6];index.vectors[1,1]=1;index.vectors[2,:2]=[.6,.8]
    query=np.zeros(1024,dtype=np.float32);query[0]=1
    assert index.score(query)==pytest.approx({'a':.8,'b':.6},abs=1e-6)
