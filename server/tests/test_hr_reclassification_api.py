"""Domain selection is a read-only review operation, not answer-source promotion."""
from test_hr_domain import hr
from server import hr_evidence


def test_review_api_passes_domain_filter_and_keeps_generation_disabled(hr,monkeypatch):
    client,_=hr;seen=[]
    monkeypatch.setenv('KLINK_HR_REVIEW_DOMAINS','reclassified')
    def search(q,category):
        seen.append((q,category));return []
    monkeypatch.setattr(hr_evidence,'review_search',search)
    response=client.get('/api/benefits/hr/review-evidence',params=dict(q='계약 업무',category='non_hr'))
    assert response.status_code==200 and seen==[('계약 업무','non_hr')]
    data=response.json()
    assert data['domain_filter']=='non_hr' and data['domain_separation_enabled']
    assert data['used_for_generation'] is False and data['answer_eligible'] is False


def test_unknown_domain_and_private_query_never_reach_review_search(hr,monkeypatch):
    client,_=hr
    def forbidden(*args,**kwargs):raise AssertionError('must not search')
    monkeypatch.setattr(hr_evidence,'review_search',forbidden)
    assert client.get('/api/benefits/hr/review-evidence',params=dict(q='인사 업무',category='invented')).status_code==422
    assert client.get('/api/benefits/hr/review-evidence',params=dict(q='인사 private@example.invalid')).status_code==422
