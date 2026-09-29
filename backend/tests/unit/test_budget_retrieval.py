import asyncio
import json
from types import SimpleNamespace

import pytest

from app.schemas.requirement import RequirementData, RequirementItem
from app.schemas.ranking import ScoringCandidate
from app.services.budget import apply_budget_semantics, tolerance
from app.services.cache.search_cache import make_cache_key
from app.services.filter.hard_filter import HardFilterService
from app.services.scoring.scoring_engine import ScoringEngine
from app.services.llm.client import MockLLMClient
from app.services.llm.requirement_analyzer import RequirementAnalyzer
from app.services.llm.query_generator import QueryGenerator
from app.services.extraction.product_page_validator import inspect_page
from app.services.search.progressive_retrieval import ProgressiveRetriever
from app.services.search.base import SearchResult


def budget(text='xe máy khoảng 33 triệu'):
    return apply_budget_semantics(RequirementData(category='xe máy'), text)


@pytest.mark.asyncio
@pytest.mark.parametrize('text,mode,minimum,maximum', [
    ('xe máy khoảng 33 triệu', 'FLEXIBLE_TARGET', None, 33_000_000),
    ('xe máy tầm 33 triệu', 'FLEXIBLE_TARGET', None, 33_000_000),
    ('xe máy tối đa 33 triệu', 'HARD_MAX', None, 33_000_000),
    ('xe máy không quá 33 triệu', 'HARD_MAX', None, 33_000_000),
    ('xe máy dưới 33 triệu', 'HARD_MAX', None, 33_000_000),
    ('xe máy từ 31 đến 35 triệu', 'RANGE', 31_000_000, 35_000_000),
    ('xe máy 31 đến 35 triệu', 'RANGE', 31_000_000, 35_000_000),
    ('xe máy 33 triệu', 'HARD_MAX', None, 33_000_000),
])
async def test_modes_are_backend_deterministic(text, mode, minimum, maximum):
    result = (await RequirementAnalyzer(MockLLMClient()).analyze(text)).requirement
    assert (result.budget_mode, result.budget_min, result.budget_max) == (mode, minimum, maximum)
    if mode == 'FLEXIBLE_TARGET':
        assert (result.budget_target, result.preferred_min, result.preferred_max) == (33_000_000,31_000_000,35_000_000)


@pytest.mark.parametrize('target,delta', [(500_000,30_000),(5_000_000,300_000),
    (33_000_000,2_000_000),(100_000_000,5_000_000),(1000,1000),(0,0)])
def test_tolerance_is_scaled_and_capped(target,delta):
    assert tolerance(target) == delta


def candidate(price, **changes):
    return ScoringCandidate(product_id=1, name='Honda Example X1',category='xe máy',price=price,**changes)


@pytest.mark.parametrize('price',[31_000_000,32_000_000,33_000_000,34_000_000,35_000_000])
def test_flexible_target_is_not_a_maximum(price):
    assert HardFilterService().evaluate(candidate(price),budget()).accepted


@pytest.mark.parametrize('price,accepted',[(31_000_000,True),(33_000_000,True),(34_000_000,False)])
def test_maximum_remains_strict(price,accepted):
    assert HardFilterService().evaluate(candidate(price),budget('tối đa 33 triệu')).accepted == accepted


@pytest.mark.parametrize('price,accepted',[(30_000_000,False),(31_000_000,True),(35_000_000,True),(36_000_000,False)])
def test_range_never_expands(price,accepted):
    assert HardFilterService().evaluate(candidate(price),budget('31 đến 35 triệu')).accepted == accepted


def test_better_requirement_can_outrank_cheaper_product_without_changing_weights():
    req = budget()
    req.requirements = [RequirementItem(name='fuel',value='tiết kiệm',priority=5)]
    engine = ScoringEngine()
    cheap = engine.score(candidate(31_000_000),req)
    better = engine.score(candidate(34_000_000,specifications={'fuel':'tiết kiệm'}),req)
    assert better.final_score > cheap.final_score
    assert engine.budget_score(candidate(33_000_000),req) > better.budget_score > cheap.budget_score
    assert better.final_score == round(better.budget_score*.25 + better.requirement_score*.30 +
        better.purpose_score*.20 + better.rating_score*.10 + better.review_score*.05 + better.source_score*.10,2)


def test_cache_keys_distinguish_flexible_and_hard_max():
    assert make_cache_key(budget()) != make_cache_key(budget('tối đa 33 triệu'))


@pytest.mark.asyncio
async def test_llm_cannot_choose_budget_mode_or_incomplete_tolerance_window():
    from app.services.llm.client import RequirementExtraction, parsed_requirement
    from app.services.budget import BUDGET_FIELDS
    assert not set(BUDGET_FIELDS) & RequirementExtraction.model_json_schema()['properties'].keys()
    class Client:
        async def analyze_requirement(self,query):
            return parsed_requirement({'category':'xe máy','budget_max':33_000_000,'purpose':['đi học'],
                'budget_mode':'FLEXIBLE_TARGET','preferred_max':1_000_000_000})
    analyzer=RequirementAnalyzer(Client())
    flex=(await analyzer.analyze('xe máy khoảng 33 triệu')).requirement
    hard=(await analyzer.analyze('xe máy tối đa 33 triệu')).requirement
    assert flex.budget_mode=='FLEXIBLE_TARGET' and flex.preferred_max==35_000_000
    assert hard.budget_mode=='HARD_MAX' and hard.preferred_max is None


@pytest.mark.parametrize('name,category',[('Giá treo Tivi 19-32 K19','tivi'),('Ốp lưng iPhone 15','điện thoại')])
def test_accessory_does_not_inherit_category_of_device_it_fits(name,category):
    from app.services.normalization.product_normalizer import infer_product_category
    actual=infer_product_category(name,category)
    item=ScoringCandidate(product_id=1,name=name,category=actual,price=150000)
    assert actual != category
    assert not HardFilterService().evaluate(item,RequirementData(category=category)).accepted


def test_aggregate_model_page_supplies_merchant_domain_without_copying_category():
    from app.schemas.search import SearchSourceItem
    from app.services.search.merchant_quality import MerchantQualityService
    source=SearchSourceItem(url='https://newdealer.vn/vario-125',title='Vario 125',content='Vario 125',
        page_validation={'discovery':[{'name':'Vario 125','price_type':'AGGREGATE_RANGE'}]})
    assert MerchantQualityService().discover([source],'xe máy')==['newdealer.vn']
    assert source.page_validation.get('product_page_valid') is None


@pytest.mark.parametrize('path,category',[('/dien-thoai-samsung-galaxy-a56.html','điện thoại'),
                                       ('/products/samsung-galaxy-a56',None)])
def test_verified_product_path_is_category_evidence_but_generic_path_stays_unknown(path,category):
    from tests.fixtures.sales_pages import sales_page
    html=sales_page(name='Samsung Galaxy A56',price=8990000,brand='Samsung',
                    description='Camera 50 MP và màn hình AMOLED')
    result=inspect_page('https://shop.vn'+path,html)
    assert result['product_page_valid']
    assert result['category']==category


def test_flexible_window_is_soft_but_outside_it_does_not_stop_retrieval():
    req=budget()
    assert HardFilterService().evaluate(candidate(30_000_000),req).accepted
    assert not HardFilterService().evaluate(candidate(None),req).accepted
    retriever=ProgressiveRetriever(None,None,settings())
    retriever.requirement=req
    offer=proof();offer['price']=30_000_000
    assert retriever.eligible(offer) and not retriever.ready(offer)
    assert ScoringEngine().budget_score(candidate(30_000_000),req)<ScoringEngine().budget_score(candidate(31_000_000),req)


def settings(**changes):
    return SimpleNamespace(**{**dict(live_search_budget_seconds=2,live_search_max_queries=12,
        live_search_target_products=1,max_results_per_query=5),**changes})


def proof(**changes):
    return dict(product_page_valid=True,name='Honda Example X1',category='xe máy',price=33_000_000,
                verification_level='VERIFIED_CONTENT',result_type='DIRECT_PRODUCT',**changes)


@pytest.mark.parametrize('availability',[None,'in_stock','https://schema.org/InStock'])
def test_missing_availability_is_not_unavailable(availability):
    retriever = ProgressiveRetriever(None,None,settings())
    retriever.requirement = budget()
    assert retriever.ready(proof(availability=availability))


@pytest.mark.parametrize('availability',['out_of_stock','out of stock','unavailable','https://schema.org/OutOfStock','https://schema.org/Discontinued'])
def test_unavailable_cannot_stop(availability):
    retriever = ProgressiveRetriever(None,None,settings())
    retriever.requirement = budget()
    assert not retriever.ready(proof(availability=availability))


@pytest.mark.asyncio
async def test_unknown_evidence_keeps_fallback_and_searches_to_query_budget():
    calls,images = [],[]
    class Provider:
        async def search(self, query, max_results):
            calls.append(query)
            return [SearchResult(title='Honda Example X1',url='https://shop.vn/honda-example-x1',
                                 content='Xe máy Honda Example X1 mua ngay giá bán 33.000.000 VND.')]
    class Resolver:
        async def inspect(self, url, **kwargs): return proof(image_candidates=[])
        async def _image_loads(self,url): images.append(url); return True
    req = budget()
    req.purpose = ['đi học']
    req.requirements = [RequirementItem(name='fuel',value='tiết kiệm xăng',priority=5)]
    retriever = ProgressiveRetriever(Provider(),Resolver(),settings(live_search_max_queries=5))
    batches = await retriever.run(QueryGenerator(max_queries=2).generate(req),req)
    assert len(calls) == 5 and not retriever.enough()
    assert any(retriever.eligible(s.page_validation) for _,sources,_ in batches for s in sources)
    for query in calls:
        if '"' not in query:
            assert 'xe máy' in query and '33000000' in query
    for diagnostic in retriever.diagnostics:
        if diagnostic['pass']=='requirement':
            assert all(fragment in diagnostic['query'] for fragment in
                       ['31000000','35000000','đi học','tiết kiệm xăng'])
    assert all(d['requirement_context']['budget_target']==33000000 and
               d['requirement_context']['preferred_min']==31000000 and
               d['requirement_context']['preferred_max']==35000000 and
               d['requirement_context']['requirements'][0]['value']=='tiết kiệm xăng'
               for d in retriever.diagnostics)
    assert not images
    assert all(d['requirement_context']==req.model_dump() for d in retriever.diagnostics)


def aggregate_page():
    node = {'@type':'Product','name':'Honda Example X1','brand':{'name':'Honda'},'model':'X1',
            'color':'Đỏ','offers':{'@type':'AggregateOffer','lowPrice':31000000,'highPrice':35000000,
                                  'price':31000000,'priceCurrency':'VND'}}
    return '<h1>Honda Example X1</h1><script type="application/ld+json">'+json.dumps(node)+'</script>'


def test_aggregate_preserves_discovery_not_concrete_price_even_with_price_property():
    result = inspect_page('https://honda.vn/example-x1',aggregate_page())
    assert not result['product_page_valid'] and result.get('price') is None
    hint = result['discovery'][0]
    assert (hint['brand'],hint['model'],hint['variant']['color']) == ('Honda','X1','Đỏ')
    assert (hint['price_min'],hint['price_max']) == (31_000_000,35_000_000)


@pytest.mark.asyncio
async def test_aggregate_feeds_model_variant_followups_with_budget_and_intent():
    calls = []
    class Provider:
        async def search(self,query,max_results):
            calls.append(query)
            if len(calls)==1:
                return [SearchResult(title='Honda Example X1',url='https://honda.vn/example-x1',content='Xe máy Honda Example X1')]
            return []
    class Resolver:
        async def inspect(self,url,**kwargs): return inspect_page(url,aggregate_page())
    req = budget();req.purpose=['đi học']
    retriever=ProgressiveRetriever(Provider(),Resolver(),settings())
    await retriever.run(['xe máy'],req)
    assert any('Honda Example X1' in q and 'Đỏ' in q for q in calls[1:])
    assert all('33000000' in q for q in calls if '"' not in q)
    assert all('đi học' in d['query'] for d in retriever.diagnostics if d['pass']=='requirement')
    assert all(d['requirement_context']['purpose']==['đi học'] and
               d['requirement_context']['budget_target']==33000000 for d in retriever.diagnostics)
    exact = [d for d in retriever.diagnostics if '"' in d['query']]
    assert exact and all(d['requirement_context']['budget_target']==33000000 and
        d['requirement_context']['purpose']==['đi học'] for d in exact)
    assert any(d['query']=='"Honda Example X1 Đỏ" mua Việt Nam VND' for d in exact)
    assert all(d['requirement_context']==req.model_dump() for d in retriever.diagnostics)
    assert not retriever.enough()


@pytest.mark.asyncio
async def test_time_exhaustion_retains_best_valid_fallback():
    class Provider:
        async def search(self,query,max_results):
            if 'initial' not in query: await asyncio.sleep(1)
            return [SearchResult(title='Honda Example X1',url='https://shop.vn/example-x1',content='Xe máy mua ngay')]
    class Resolver:
        async def inspect(self,url,**kwargs): return proof()
    req=budget();req.requirements=[RequirementItem(name='fuel',value='tiết kiệm',priority=5)]
    retriever=ProgressiveRetriever(Provider(),Resolver(),settings(live_search_budget_seconds=.05))
    batches=await retriever.run(['initial'],req)
    assert any(retriever.eligible(s.page_validation) for _,rows,_ in batches for s in rows)
    assert retriever.remaining()==0 and not retriever.enough()
