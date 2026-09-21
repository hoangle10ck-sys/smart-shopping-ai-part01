from collections import Counter
from types import SimpleNamespace

import pytest

from app.schemas.requirement import RequirementData, RequirementItem
from app.schemas.search import SearchSourceItem
from app.services.extraction.product_page_validator import inspect_page
from app.services.filter.hard_filter import category_matches
from app.services.search.base import SearchResult
from app.services.search.progressive_retrieval import ProgressiveRetriever
from app.services.scoring.scoring_engine import ScoringEngine
from tests.fixtures.sales_pages import sales_page


def settings(**changes):
    return SimpleNamespace(**{**dict(live_search_budget_seconds=3, live_search_max_queries=12,
        live_search_target_products=1,max_results_per_query=5),**changes})


def requirement(**changes):
    return RequirementData(**{**dict(category='tivi',budget_mode='FLEXIBLE_TARGET',budget_target=10000000,
        preferred_min=9400000,preferred_max=10600000,purpose=['xem phim']),**changes})


def offer(**changes):
    return {**dict(product_page_valid=True,result_type='DIRECT_PRODUCT',verification_level='VERIFIED_CONTENT',
        name='Sony X100',brand='Sony',model='X100',category='tivi',price=9990000,
        availability='in_stock',product_url='https://seller.test/sony-x100',image_candidates=[]),**changes}


@pytest.mark.parametrize('availability',[None,'unknown','in_stock','https://schema.org/InStock'])
def test_tv_unknown_stock_is_not_out_of_stock(availability):
    r=ProgressiveRetriever(None,None,settings());r.requirement=requirement()
    assert r.eligible(offer(availability=availability))
    assert r.ready(offer(availability=availability))


def test_unknown_movie_evidence_and_outside_window_remain_fallback():
    r=ProgressiveRetriever(None,None,settings())
    r.requirement=requirement(requirements=[RequirementItem(name='movie_quality',value='xem phim',priority=5)])
    near=offer();far=offer(price=12000000)
    assert r.eligible(near) and r.eligible(far)
    assert not r.ready(near) and not r.ready(far)
    assert ScoringEngine().requirement_matches(r.candidate(near),r.requirement)[0].status=='unknown'
    assert ScoringEngine().budget_score(r.candidate(far),r.requirement)<ScoringEngine().budget_score(r.candidate(near),r.requirement)


@pytest.mark.parametrize('name',['AirTag X200','Giá treo TV X200','Remote TV X200','Chân đế TV X200',
    'Kệ TV X200','Phụ kiện TV X200','HDMI cable for TV X200','Cáp HDMI cho TV X200','Android TV Box X200','TV box X200'])
def test_tv_accessory_cannot_be_a_main_tv(name):
    p=inspect_page('https://seller.test/item-x200',sales_page(name=name))
    assert not category_matches('tivi',p.get('category'))


@pytest.mark.parametrize('name,brand',[('Smart TV Sony X200','Sony'),('Tivi Sony X200','Sony'),
    ('Samsung TV X200','Samsung'),('LG TV X200','LG')])
def test_main_tv_remains_eligible_after_accessory_detection(name,brand):
    from app.services.normalization.product_normalizer import infer_product_category
    assert infer_product_category('Smart TV X200')=='tivi'
    p=inspect_page('https://seller.test/item-x200',sales_page(name=name,brand=brand,model='X200'))
    assert p['product_page_valid']
    assert p['category']=='tivi'
    assert category_matches('tivi',p['category'])


@pytest.mark.asyncio
async def test_out_of_stock_first_model_continues_to_another_model():
    calls=[]
    class Provider:
        async def search(self,q,max_results):
            calls.append(q)
            if '"LG B200"' in q:
                return [SearchResult(title='LG B200',url='https://other.test/lg-b200',content='Smart TV LG B200 mua ngay')]
            return [SearchResult(title='Sony X100',url='https://seller.test/sony-x100',content='Smart TV Sony X100. LG B200 giá bán.')]
    class Resolver:
        async def inspect(self,url,**kwargs):
            return offer(name='LG B200',brand='LG',model='B200',availability=None,product_url=url) if 'b200' in url else offer(availability='out_of_stock')
    r=ProgressiveRetriever(Provider(),Resolver(),settings())
    await r.run(['tivi khoảng 10 triệu'],requirement())
    assert any('"LG B200"' in q for q in calls)
    assert r.enough() and len(calls)<=12
    rejected=[row for d in r.diagnostics for row in d['source_audit'] if row.get('NAME')=='Sony X100']
    assert rejected and all(row['REJECT_STAGE']=='availability' for row in rejected)


@pytest.mark.asyncio
async def test_unavailable_merchant_is_not_requeried_for_same_model(monkeypatch):
    from app.services.search.source_strategy import SourceStrategy
    monkeypatch.setattr(SourceStrategy,'preferred_domains',lambda self,category:['new.test','third.test'])
    calls=[]
    class Provider:
        async def search(self,q,max_results):
            calls.append(q)
            if q.startswith('site:new.test'):
                return [SearchResult(title='Sony X100',url='https://new.test/sony-x100',content='Smart TV Sony X100 mua ngay')]
            return [SearchResult(title='Sony X100',url='https://old.test/sony-x100',content='Smart TV Sony X100 mua ngay')]
    class Resolver:
        async def inspect(self,url,**kwargs):return offer(product_url=url,availability=None if 'new.test' in url else 'out_of_stock')
    r=ProgressiveRetriever(Provider(),Resolver(),settings())
    await r.run(['tivi khoảng 10 triệu'],requirement())
    assert any(q.startswith('site:new.test') for q in calls)
    assert not any(q.startswith('site:old.test') and '"Sony X100"' in q for q in calls)
    assert r.enough()


@pytest.mark.asyncio
async def test_slots_cover_generic_intent_alternatives_and_distinct_merchants(monkeypatch):
    from app.services.search.source_strategy import SourceStrategy
    monkeypatch.setattr(SourceStrategy,'preferred_domains',lambda self,category:['first.test','second.test','third.test'])
    calls=[]
    class Provider:
        async def search(self,q,max_results):
            calls.append(q)
            return [SearchResult(title='Sony X100',url='https://first.test/sony-x100',
                content='Smart TV Sony X100 mua ngay. LG B200 giá bán. TCL C300 mua ngay. Samsung D400 giá bán.')]
    class Resolver:
        async def inspect(self,url,**kwargs):return offer(availability='out_of_stock')
    r=ProgressiveRetriever(Provider(),Resolver(),settings())
    await r.run(['tivi xem phim theo nhu cầu'],requirement())
    assert len(calls)<=12 and not r.enough()
    assert any('10000000' in q and 'xem phim' not in q and '"' not in q for q in calls)
    assert any('xem phim' in q for q in calls)
    assert any('"LG B200"' in q for q in calls)
    domains=[q.split()[0] for q in calls if q.startswith('site:')]
    assert len(set(domains))>=2 and max(Counter(domains).values())<=2
    assert sum('"Sony X100"' in q for q in calls)<=2
