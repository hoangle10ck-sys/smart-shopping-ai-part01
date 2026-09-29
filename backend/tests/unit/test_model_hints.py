import pytest
from app.services.search.model_hints import observed_models
from app.services.search.progressive_retrieval import ProgressiveRetriever
from app.schemas.requirement import RequirementData


@pytest.mark.parametrize('text,expected',[
    ('Chọn Samsung Galaxy A56 8/128GB giá tốt.','Samsung Galaxy A56 8/128GB'),
    ('Smart Tivi Sony KD-50X80J 50 inch Google TV giá bán','Sony KD-50X80J'),
    ('Honda Future 125FI giá bán 32 triệu','Honda Future 125FI'),
    ('Samsung Galaxy A56 8.990.000 VND','Samsung Galaxy A56'),
    ('Xe máy Honda Vision giá bán','Honda Vision')])
def test_short_contiguous_model_mentions(text,expected):
    assert expected in observed_models(text)


def test_catalog_year_does_not_make_a_model_lookup_into_a_marketing_title():
    assert observed_models('Honda Vision 2026 mới nhất')==['Honda Vision']


def test_capacity_spellings_do_not_starve_a_different_model():
    from app.schemas.search import SearchSourceItem
    r=ProgressiveRetriever(None,None,None)
    r.sources={'s':SearchSourceItem(title='Vivo V30E 12GB 256GB',url='https://seller.test/v30e',
        content='Vivo V30e giá bán. Samsung Galaxy A56 5G giá tốt.',result_type='DIRECT_PRODUCT')}
    assert r.model_hints()==['Vivo V30E 12GB 256GB','Samsung Galaxy A56 5G']


def test_review_and_marketing_suffixes_are_not_part_of_model():
    assert observed_models('Vivo V30e Camera Review')==['Vivo V30e']
    assert observed_models('Samsung U8500F Crystal UHD 4K Business')==['Samsung U8500F']
    assert observed_models('Redmi Note 14 Specs')==['Redmi Note 14']


def test_combined_model_catalog_heading_is_not_an_exact_model():
    assert observed_models('OPPO Reno14 Pro/Reno14/Reno14 F')==[]


def test_sentence_after_model_cannot_extend_the_exact_lookup():
    assert observed_models('Honda Wave RSX FI. Theo thong tin')==['Honda Wave RSX FI']


def test_news_index_cannot_gain_priority_by_having_unknown_page_type():
    from app.schemas.search import SearchSourceItem
    r=ProgressiveRetriever(None,None,None)
    r.sources={'article':SearchSourceItem(title='Sony KD-50X80J',url='https://guide.test/article',
        content='',result_type='ARTICLE'),
        'index':SearchSourceItem(title='Samsung Q80X',url='https://vnexpress.net/oto-xe-may/v-bike',
        content='',result_type='UNKNOWN')}
    assert r.model_hints()[:2]==['Sony KD-50X80J','Samsung Q80X']


def test_structured_discovery_also_cleans_marketing_and_capacity_spellings():
    from app.schemas.search import SearchSourceItem
    r=ProgressiveRetriever(None,None,None)
    r.sources={'s':SearchSourceItem(title='Catalog',url='https://seller.test/catalog',content='',
        page_validation={'discovery':[
            {'brand':'Samsung','name':'Samsung 55 Crystal UHD U8500F 4K Smart TV'},
            {'brand':'Samsung','name':'Samsung Galaxy A56 5G (256 GB)'},
            {'brand':'Samsung','name':'Samsung Galaxy A56 5G'},
            {'brand':'Sony','name':'Smart Tivi Sony KD-50X80J 50 inch Google TV'}]})}
    assert r.model_hints()==['Samsung Galaxy A56 5G','Sony KD-50X80J']


def test_one_catalogs_versions_cannot_starve_other_base_models():
    from app.schemas.search import SearchSourceItem
    r=ProgressiveRetriever(None,None,None)
    r.sources={'catalog':SearchSourceItem(title='Models',url='https://seller.test/catalog',content='',
        result_type='UNKNOWN',page_validation={'discovery':[
            {'brand':'Acme','name':'Acme Orbit X1','variant':{'version':v},'price_type':'DISCOVERY_ONLY'}
            for v in ['Standard','Special','Premium']]+[
            {'brand':'Acme','name':'Acme Urban X2','variant':{},'price_type':'DISCOVERY_ONLY'}]})}
    assert r.model_hints()[:2]==['Acme Orbit X1','Acme Urban X2']


@pytest.mark.parametrize('text',[
    'Samsung 15 59 Hàng thì','Samsung Sony LG TCL 3 22 với',
    'Samsung Neo QLED 8K là chiếc TV tốt nhất','Samsung or LG Chan Ngan TV 6',
    'Ốp lưng Samsung Galaxy A56','Giá treo TV Sony KD-50X80J',
    'Samsung 10000000 VND','Samsung giá khoảng 10 triệu'])
def test_noisy_accessory_or_budget_mentions_are_not_models(text):
    assert observed_models(text)==[]


@pytest.mark.parametrize('category,model',[('tivi','Sony KD-50X80J'),('điện thoại','Samsung A56 8/128GB'),('xe máy','Honda Vision')])
def test_exact_queries_do_not_append_requirements_or_budget(category,model):
    r=ProgressiveRetriever(None,None,None)
    r.requirement=RequirementData(category=category,budget_max=33000000,purpose=['xem phim'])
    assert r.model_query(model,'mua')==f'"{model}" mua Việt Nam VND'
    assert r.model_query(model,'giá','seller.test')==f'site:seller.test "{model}" giá Việt Nam VND'
    assert r.requirement.budget_max==33000000


@pytest.mark.asyncio
async def test_many_saved_queries_cannot_starve_exact_model_and_merchant_slots():
    from types import SimpleNamespace
    from app.services.search.base import SearchResult
    calls=[]
    class Provider:
        async def search(self,query,max_results):
            calls.append(query)
            return [SearchResult(title='Acme Orbit X1',url='https://seller.test/orbit-x1',
                content='Sản phẩm Acme Orbit X1 mua ngay tại cửa hàng.')]
    class Resolver:
        async def inspect(self,url,**kwargs):
            return {'product_page_valid':False,'result_type':'UNKNOWN','discovery':[
                {'brand':'Acme','model':'Orbit X1','name':'Acme Orbit X1','variant':{},'price_type':'DISCOVERY_ONLY'}]}
    settings=SimpleNamespace(live_search_budget_seconds=2,live_search_max_queries=8,
                             live_search_target_products=1,max_results_per_query=5)
    r=ProgressiveRetriever(Provider(),Resolver(),settings)
    await r.run([f'legacy {i}' for i in range(20)],RequirementData(category='device'))
    assert len(calls)<=8
    assert sum(q.startswith('legacy') for q in calls)==2
    assert '"Acme Orbit X1" mua' in calls
    assert any(q.startswith('site:seller.test "Acme Orbit X1"') for q in calls)
    assert not r.enough()  # discovery alone is never a recommendation


@pytest.mark.asyncio
async def test_later_pass_compares_model_identity_not_connectivity_spelling():
    from types import SimpleNamespace
    r=ProgressiveRetriever(None,None,SimpleNamespace(live_search_budget_seconds=2,live_search_target_products=1))
    r.model_hints=lambda: (['Redmi K80 5G','Samsung A56 5G'] if not any('"' in q for q in r.queries) else
                          ['REDMI K80','Samsung A56','Sony X80J'])
    calls=[]
    async def pass_queries(label,queries):
        calls.extend((label,q) for q in queries)
        r.queries.update(queries)
    r.pass_queries=pass_queries
    await r.run([],RequirementData(category='device'))
    late=[q for label,q in calls if label=='merchant_products']
    assert late[0]=='"Sony X80J" giá'
