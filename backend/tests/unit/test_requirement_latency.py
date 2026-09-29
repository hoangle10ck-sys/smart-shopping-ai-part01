"""Latest archived offers, deterministic matching and constrained LLM mocks."""
from copy import deepcopy
import json
from pathlib import Path
import time

import pytest

from app.core.config import get_settings, Settings
from app.schemas.requirement import RequirementData, RequirementItem
from app.schemas.ranking import ScoringCandidate
from app.schemas.evidence import RecommendationExplanation, EvidenceReport
from app.schemas.search import SearchSourceItem
from app.services.scoring.scoring_engine import ScoringEngine, _battery_mah
from app.services.llm.explanation_service import ExplanationService
from app.services.search.progressive_retrieval import ProgressiveRetriever
from tests.unit.test_explanation_service import make_evidence


def archive():
    return json.loads((Path(__file__).parents[1]/'fixtures/live_match_ce69ae93.json').read_text(encoding='utf8'))


def requirement():
    return RequirementData.model_validate(archive()['snapshot']['result']['requirement'])


@pytest.mark.parametrize('text,value', [('8500 mAh',8500),('8.500 mAh',8500),('8,500 mAh',8500),
    ('6000mAh',6000),('6.000 mAh',6000),('6,000 mAh',6000),('3999 mAh',3999),('3.999 mAh',3999),
    ('8.5 mAh',8.5),('8,5 mAh',8.5),('unknown',None),('8.50.0 mAh',None)])
def test_battery_locale_without_changing_threshold(text,value):
    assert _battery_mah(text)==value
    c=ScoringCandidate(product_id=1,name='Phone',category='điện thoại',specifications={'pin':text})
    req=RequirementData(category='điện thoại',requirements=[RequirementItem(name='pin',value='lâu')])
    expected='unknown' if value is None else ('matched' if value>=4000 else 'unmet')
    assert ScoringEngine().requirement_matches(c,req)[0].status==expected


@pytest.mark.parametrize('key',['camera','camera sau','camera trước','rear camera','front camera'])
def test_camera_alias_uses_existing_ois_rubric(key):
    c=ScoringCandidate(product_id=1,name='Phone',specifications={key:'50 MP OIS'})
    req=RequirementData(requirements=[RequirementItem(name='camera',value='tốt')])
    assert ScoringEngine().requirement_matches(c,req)[0].status=='matched'
    c.specifications[key]='50 MP'
    assert ScoringEngine().requirement_matches(c,req)[0].status=='unknown'


def test_front_camera_cannot_borrow_rear_ois():
    c=ScoringCandidate(product_id=1,name='Phone',specifications={'camera sau':'50 MP OIS','camera trước':'50 MP'})
    req=RequirementData(requirements=[RequirementItem(name='front camera',value='good')])
    assert ScoringEngine().requirement_matches(c,req)[0].status=='unknown'


def test_actual_three_fallbacks_and_unchanged_weights_after_parsing_fix():
    data=archive();req=requirement();engine=ScoringEngine()
    r=ProgressiveRetriever(None,None,Settings(_env_file=None));r.requirement=req
    accepted=[]
    for raw in data['snapshot']['result']['candidates']:
        c=ScoringCandidate.model_validate(raw)
        if c.availability=='out_of_stock': continue
        assert [m.status for m in engine.requirement_matches(c,req)]==['matched','matched']
        score=engine.score(c,req)
        assert score.budget_score==0 and score.requirement_score==100
        expected=sum(getattr(score,k)*w for k,w in [('budget_score',.25),('requirement_score',.30),
            ('purpose_score',.20),('rating_score',.10),('review_score',.05),('source_score',.10)])
        assert score.final_score==round(expected,2)
        assert r.eligible({'product_page_valid':True,**c.model_dump()})
        accepted.append(c.name)
    assert len(accepted)==3
    poco=next(r for r in data['snapshot']['result']['recommendations'] if r['name'].startswith('POCO'))
    assert poco['specifications']['pin']=='8.500 mAh' and poco['requirement_matches'][1]['status']=='unmet'


@pytest.mark.parametrize('status,specs',[('unknown',{'camera sau':'50 MP'}),('unmet',{'camera':'không tốt'}),('matched',{'camera sau':'50 MP OIS'})])
@pytest.mark.parametrize('field',['summary','why_fit','tradeoffs','evidence_notes'])
def test_llm_contradiction_in_any_field_falls_back_without_retry(monkeypatch,status,specs,field):
    s=get_settings();monkeypatch.setattr(s,'demo_mode',False);monkeypatch.setattr(s,'llm_provider','gemini');monkeypatch.setattr(s,'llm_fallback_provider','')
    c=ScoringCandidate(product_id=1,name='Phone',category='điện thoại',price=15000000,availability='in_stock',specifications=specs)
    req=requirement();score=ScoringEngine().score(c,req);e=make_evidence();service=ExplanationService()
    safe=service.build_deterministic(candidate=c,requirement=req,score=score,evidence=e)
    bad=safe.model_copy(deep=True);sentence='Camera đáp ứng xuất sắc, pin đáp ứng và giá hoàn toàn trong ngân sách.' if status!='matched' else 'Camera không đáp ứng dù có OIS.'
    setattr(bad,field,sentence if field=='summary' else [sentence]);calls=[]
    monkeypatch.setattr(service,'_generate_with_provider',lambda **kw:(calls.append(kw) or bad))
    before=c.model_dump();result=service.explain(candidate=c,requirement=req,score=score,evidence=e)
    assert result.generation_mode=='fallback' and len(calls)==1 and c.model_dump()==before
    assert result.model_dump(exclude={'generation_mode'})==safe.model_dump(exclude={'generation_mode'})
    assert ScoringEngine().requirement_matches(c,req)[0].status==status
    assert 'ngân sách tối đa' not in str(result.model_dump())


def test_payload_and_valid_llm_selection_keep_unknown_budget_and_stock_warnings(monkeypatch):
    s=get_settings();monkeypatch.setattr(s,'demo_mode',False);monkeypatch.setattr(s,'llm_provider','openai')
    c=ScoringCandidate(product_id=1,name='Phone',category='điện thoại',price=15000000,specifications={'camera trước':'50 MP'})
    req=requirement();score=ScoringEngine().score(c,req);e=make_evidence();service=ExplanationService()
    payload=service._build_payload(candidate=c,requirement=req,score=score,evidence=e)
    assert payload['requirement_matches'][0]['status']=='unknown'
    result=RecommendationExplanation.model_validate(payload['approved_explanation'])
    result.tradeoffs=[]  # LLM may not remove mandatory warnings.
    monkeypatch.setattr(service,'_generate_with_provider',lambda **kw:result)
    out=service.explain(candidate=c,requirement=req,score=score,evidence=e)
    assert out.generation_mode=='openai' and out.tradeoffs==payload['approved_explanation']['tradeoffs']
    assert any('còn hàng' in v for v in out.tradeoffs)


def seeded_retriever():
    r=ProgressiveRetriever(None,None,Settings(_env_file=None));r.requirement=requirement();r.deadline=time.monotonic()+30
    for o in archive()['observations']:
        if o['proof'].get('product_page_valid'):
            r.sources[o['url']]=SearchSourceItem(url=o['url'],title=o['title'],content=o['content'],page_validation=deepcopy(o['proof']))
    return r


def test_three_actual_far_offers_stop_without_losing_any_offer():
    r=seeded_retriever()
    assert r.satisfaction()['eligible_offers']==3
    assert not r.can_continue() and r.stop_reason=='fallback_minimum_no_near_evidence'
    assert r.satisfaction()['eligible_offers']==3


def test_near_budget_model_evidence_prioritized_before_far_fallback():
    r=seeded_retriever()
    url='https://shop.test/category/phones'
    r.sources[url]=SearchSourceItem(url=url,title='Điện thoại',content='',result_type='CATEGORY',page_validation={
        'discovery':[{'name':'Xiaomi 15T','brand':'Xiaomi','price_min':10000000,'price_max':10000000,'price_type':'CONCRETE'}]})
    assert r.model_hints()[0]=='Xiaomi 15T' and r.can_continue()
    assert '"Xiaomi 15T"' in r.continuation_query('điện thoại',False)
