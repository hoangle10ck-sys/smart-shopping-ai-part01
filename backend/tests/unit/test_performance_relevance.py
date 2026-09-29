"""Recorded noise + controlled pages, no external provider or network."""
from copy import deepcopy
import json
from pathlib import Path
import time

import pytest

from app.core.config import Settings
from app.schemas.search import SearchSourceItem
from app.services.search.base import SearchResult
from app.services.search.model_hints import lookup_key, observed_models
from app.services.search.progressive_retrieval import ProgressiveRetriever
from app.services.search.retrieval_relevance import irrelevant_reason
from app.services.extraction.product_page_validator import inspect_page
from tests.fixtures.discovery_scenarios import phone_requirement, LocalPages, NoisyProvider
from tests.fixtures.sales_pages import sales_page


def recorded():
    return json.loads((Path(__file__).parents[1]/'fixtures/live_relevance_981f372a.json').read_text(encoding='utf8'))


def retriever(provider=None, pages=None, **settings):
    r=ProgressiveRetriever(provider,pages,Settings(_env_file=None,**settings))
    r.requirement=phone_requirement()
    r.deadline=time.monotonic()+30
    return r


@pytest.mark.parametrize('token',['5G','VND','Samsung 5G','Xiaomi VND'])
def test_generic_tokens_cannot_seed_models(token):
    assert observed_models(token)==[]
    if token in {'5G','VND'}: assert retriever().model_query(token)==''
    assert observed_models('Xiaomi 15T giá bán')==['Xiaomi 15T']


def test_reno_spacing_capacity_and_connectivity_share_lookup_budget_only():
    assert lookup_key('OPPO Reno 10')==lookup_key('OPPO Reno10 5G 8GB/256GB')
    assert lookup_key('OPPO Reno10 Pro')!=lookup_key('OPPO Reno10')


def test_actual_session_stopped_on_page_budget_not_two_weak_offers():
    data=recorded(); r=retriever()
    p=data['snapshot']['retrieval_diagnostics'][-1]['performance']['diagnostics']
    assert len(data['observations'])==48 and p['stop_reason']=='page_budget'
    assert p['page_attempts']==24 and p['provider_calls']==12
    proofs=[o['proof'] for o in data['observations'] if o['proof'].get('product_page_valid')]
    assert len(proofs)==4
    eligible=[p for p in proofs if r.eligible(p)]
    assert len(eligible)==2 and not any(r.ready(p) for p in eligible)


@pytest.mark.asyncio
async def test_all_six_archived_network_currency_rows_cost_no_fetch_or_progress():
    rows=[o for o in recorded()['observations'] if irrelevant_reason(SearchSourceItem(**{k:o[k] for k in ('url','title','content')}),phone_requirement())]
    assert len(rows)==6
    class Provider:
        async def search(self,q,limit): return [SearchResult(**{k:o[k] for k in ('url','title','content')}) for o in rows]
    class Pages:
        async def inspect(self,*a,**kw): raise AssertionError('Irrelevant source must not fetch')
    r=retriever(Provider(),Pages())
    await r.pass_queries('requirement',['phone'])
    assert len(r.sources)==6 and not r.inspected_urls and not r.model_hints()
    assert r.rounds[0]['no_progress_rounds']==1
    for key in ('new_model_hints','new_merchant_domains','new_direct_urls'):
        assert r.rounds[0][key]==0
    assert all(s.page_validation['rejection_code']=='irrelevant_intent' for s in r.sources.values())


@pytest.mark.parametrize('title,content',[
    ('Điện thoại mới 5G','Tặng thẻ quà tặng'),
    ('Xiaomi 15T 5G giá 10.000.000 VND','Camera tốt pin lâu'),
    ('Điện thoại thương hiệu mới','Thông số chưa rõ'),
])
def test_phone_or_unknown_identity_not_rejected_for_price_network_or_promotion(title,content):
    assert irrelevant_reason(SearchSourceItem(url='https://shop.test/item',title=title,content=content),phone_requirement()) is None


def test_budget_topic_orders_model_hints_without_inventing_offer_price():
    r=retriever()
    for i,(title,text) in enumerate([
        ('Điện thoại dưới 3 triệu','Samsung Galaxy A52'),
        ('Điện thoại giá 10 triệu','Xiaomi 15T'),
        ('Điện thoại chưa có giá','OPPO Reno 10'),
    ]):
        s=SearchSourceItem(url=f'https://guide.test/news/{i}',title=title,content=text)
        r.retain_metadata(s)
    assert r.model_hints()==['Xiaomi 15T','OPPO Reno 10','Samsung Galaxy A52']
    assert not any(s.page_validation.get('price') for s in r.sources.values())


@pytest.mark.asyncio
async def test_two_weak_offers_keep_fallback_and_search_unseen_near_budget_model():
    class Provider:
        def __init__(self):self.calls=[]
        async def search(self,q,limit):
            self.calls.append(q)
            if '"Xiaomi 15T"' in q:
                return [SearchResult(title='Xiaomi 15T',url='https://new.test/products/xiaomi-15t',content='')]
            return [SearchResult(title=f'Samsung Galaxy A{n}',url=f'https://shop.test/products/a{n}',content='') for n in (51,52)]+[
                SearchResult(title='Điện thoại giá 10 triệu',url='https://guide.test/news/phone',content='Xiaomi 15T')]
    class Pages:
        async def inspect(self,url,**kw):
            near='xiaomi' in url
            name='Xiaomi 15T' if near else 'Samsung Galaxy A'+url[-2:]
            return inspect_page(url,sales_page(name=name,price=10000000 if near else 2499000,category='điện thoại',
                additionalProperty=[{'name':'camera','value':'50 MP OIS'},{'name':'battery','value':'5500 mAh'}] if near else []))
    p=Provider();r=retriever(p,Pages(),live_search_target_products=1)
    await r.run(['start'],phone_requirement())
    assert any('"Xiaomi 15T"' in q for q in p.calls)
    assert r.satisfaction()['eligible_offers']==3 and r.satisfaction()['strong_models']==1
    assert r.stop_reason=='target_reached' and len(p.calls)<=3
    assert len([s for s in r.sources.values() if r.eligible(s.page_validation) and not r.ready(s.page_validation)])==2


@pytest.mark.asyncio
async def test_two_strong_models_stop_after_no_useful_progress():
    provider=NoisyProvider(supply=2,delay=0);pages=LocalPages(delay=0)
    r=retriever(provider,pages)
    await r.run(['start'],phone_requirement())
    assert r.satisfaction()['strong_models']==2
    assert r.stop_reason=='strong_fit_no_progress'
    assert len(provider.calls)<12 and len(pages.calls)==3


@pytest.mark.asyncio
@pytest.mark.parametrize('target',[3,5])
async def test_valid_target_still_early_stops(target):
    p=NoisyProvider(supply=target,delay=0);r=retriever(p,LocalPages(delay=0),live_search_target_products=target)
    await r.run(['start'],phone_requirement())
    assert r.enough() and r.stop_reason=='target_reached' and len(p.calls)<=3
