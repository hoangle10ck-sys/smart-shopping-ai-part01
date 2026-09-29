"""Latest stored session and controlled recovery responses; no external I/O."""
import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.schemas.requirement import RequirementData
from app.schemas.search import SearchSourceItem
from app.services.extraction.product_page_validator import inspect_page
from app.services.extraction.search_metadata_validator import verify_search_metadata
from app.services.search.base import SearchResult
from app.services.search.model_hints import observed_models
from app.services.search.progressive_retrieval import ProgressiveRetriever
from app.services.search.source_strategy import SourceStrategy
from app.services.search.merchant_quality import MerchantQualityService
from tests.fixtures.sales_pages import sales_page


def recorded():
    return json.loads((Path(__file__).parents[1]/'fixtures/live_final_offer_dfc295bb.json').read_text(encoding='utf-8'))


def test_latest_fixture_preserves_all_sources_and_real_stop_reason():
    data=recorded()
    assert len(data['observations'])==len({o['url'] for o in data['observations']})==33
    perf=data['snapshot']['retrieval_diagnostics'][-1]['performance']['diagnostics']
    assert perf['provider_calls']==9 and perf['page_attempts']==15 and perf['stop_reason']=='no_progress'
    assert perf['conversion']['direct_product_candidates']==2 and perf['eligible_offers']==0


@pytest.mark.parametrize('model', ['v50','v60'])
def test_actual_vivo_observations_still_have_no_concrete_price(model):
    o=next(o for o in recorded()['observations'] if '/dtdd/vivo-'+model in o['url'])
    p=verify_search_metadata(SearchSourceItem(url=o['url'],title=o['title'],content=o['content']),o['proof'])
    assert not p['product_page_valid'] and p.get('price') is None


def test_numeric_model_and_complete_capacity_without_mixed_brand_hint():
    assert observed_models('Xiaomi 15T giá bán tại Việt Nam')==['Xiaomi 15T']
    assert observed_models('Redmi Note 13 Pro 5G 8GB 256GB')==['Redmi Note 13 Pro 5G 8GB 256GB']
    assert 'vivo X200 Pro Mini Poco X8' not in observed_models('vivo X200 Pro Mini Poco X8 giá bán')


@pytest.mark.parametrize('kind,valid', [('offer',True),('visible',True),('aggregate',False),('mixed',False)])
def test_v50_concrete_current_price_does_not_use_old_promo_or_range(kind,valid):
    name='Điện thoại vivo V50 Lite 5G 8GB/256GB'
    url='https://shop.test/dtdd/vivo-v50-lite-5g'
    offers={'@type':'Offer','price':9000000,'priceCurrency':'VND'}
    if kind=='aggregate':offers={'@type':'AggregateOffer','lowPrice':8000000,'highPrice':11000000,'priceCurrency':'VND'}
    if kind=='mixed':offers=[offers,{**offers,'price':10000000}]
    html=sales_page(name=name,offers=offers)
    if kind=='visible':
        html=f'<h1>{name}</h1><meta property="og:type" content="product"><span class="ProductPrice">9.000.000đ</span><button>Mua ngay</button>'
    html+='<del>11.000.000đ</del><p>Giảm thêm 300.000đ cho phụ kiện</p>'
    p=inspect_page(url,html)
    assert p['product_page_valid']==valid
    assert p.get('price')==(9000000 if valid else None)


def test_v50_full_same_source_identity_and_single_price_metadata():
    o=next(o for o in recorded()['observations'] if '/dtdd/vivo-v50' in o['url'])
    p=verify_search_metadata(SearchSourceItem(url=o['url'],title=o['title'],
        content='vivo V50 Lite 5G 8GB/256GB giá 9.000.000 VND. Mua ngay.'),o['proof'])
    assert p['product_page_valid'] and p['price']==9000000 and p['verification_level']=='VERIFIED_SEARCH_METADATA'


@pytest.mark.asyncio
@pytest.mark.parametrize('recover_exact', [True,False])
async def test_unavailable_models_recover_other_seller_or_allow_new_model(monkeypatch,recover_exact):
    monkeypatch.setattr(SourceStrategy,'preferred_domains',lambda *a:['old.test','other.test','third.test'])
    monkeypatch.setattr(MerchantQualityService,'discover',lambda *a:[])
    old=[SearchResult(title=f'Samsung Galaxy A{n}',url=f'https://old.test/phone-a{n}',content='') for n in (51,52)]
    evidence=SearchResult(title='Xiaomi 15T',url='https://guide.test/news/phones',content='Xiaomi 15T giá tốt')
    class Provider:
        def __init__(self):self.calls=[]
        async def search(self,q,limit):
            self.calls.append(q)
            if '"Xiaomi 15T"' in q:
                return [SearchResult(title='Xiaomi 15T',url='https://third.test/xiaomi-15t',content='')]
            if q.startswith('site:other.test') and '"Samsung Galaxy A51"' in q and recover_exact:
                return [SearchResult(title='Samsung Galaxy A51',url='https://other.test/samsung-a51',content='')]
            return old+[evidence]
    class Resolver:
        def __init__(self):self.calls=[]
        async def inspect(self,url,**kwargs):
            self.calls.append(url)
            name='Xiaomi 15T' if 'xiaomi' in url else 'Samsung Galaxy A'+('51' if '51' in url else '52')
            p=inspect_page(url,sales_page(name=name,category='điện thoại'))
            if 'old.test' in url:p['availability']='out_of_stock'
            return p
    provider,pages=Provider(),Resolver()
    r=ProgressiveRetriever(provider,pages,Settings(_env_file=None,live_search_target_products=1))
    await r.run(['start'],RequirementData(category='điện thoại',budget_max=10000000))
    assert r.enough() and r.summary()['valid_offers']==1
    expected='https://other.test/samsung-a51' if recover_exact else 'https://third.test/xiaomi-15t'
    assert r.eligible(r.sources[expected].page_validation)
    assert all(not q.startswith('site:old.test') for q in provider.calls)
    assert len(pages.calls)==len(set(pages.calls))
    assert not r.sources[evidence.url].page_validation['product_page_valid']
    if recover_exact:assert len(provider.calls)<=4  # no broad commerce/dealer detour
    if not recover_exact:assert any(rd['kind']=='alternative_model' for rd in r.rounds)


@pytest.mark.asyncio
async def test_same_merchant_new_url_for_verified_unavailable_variant_skips_fetch():
    from app.services.search.retrieval_diagnostics import source_plan
    name='Samsung Galaxy A51 8GB 128GB'
    class Provider:
        async def search(self,q,limit):
            return [SearchResult(title=name,url='https://old.test/another-a51-8gb-128gb',content='')]
    class Resolver:
        async def inspect(self,*a,**kw):raise AssertionError('Known unavailable duplicate consumed HTTP budget')
    r=ProgressiveRetriever(Provider(),Resolver(),Settings(_env_file=None,live_search_max_queries=1))
    p=inspect_page('https://old.test/samsung-a51-8gb-128gb',sales_page(name=name,category='điện thoại'))
    p['availability']='out_of_stock'
    s=SearchSourceItem(url=p['evidence_url'],title=name,page_validation=p)
    r.sources[s.url]=s;r.plans[s.url]=source_plan(s)
    await r.run(['start'],RequirementData(category='điện thoại'))
    duplicate=r.sources['https://old.test/another-a51-8gb-128gb'].page_validation
    assert not r.inspected_urls and not duplicate['page_requested']
    assert duplicate['rejection_code']=='unavailable_duplicate' and not r.enough()


@pytest.mark.asyncio
async def test_product_tier_cannot_be_displaced_by_discovery_domain_diversity():
    rows=[SearchResult(title='Phones',url='https://catalog.test/category/phones',content='')]
    rows += [SearchResult(title=f'Samsung Galaxy A{n}',url=f'https://shop.test/samsung-a{n}',content='') for n in (51,52,53)]
    rows += [SearchResult(title='Samsung Galaxy A54 review',url='https://forum.test/thread/samsung-a54',content='')]
    class Provider:
        async def search(self,q,limit):return rows
    class Resolver:
        def __init__(self):self.calls=[]
        async def inspect(self,url,**kw):
            self.calls.append(url)
            assert 'shop.test' in url,'Discovery/article displaced a waiting direct product'
            return inspect_page(url,sales_page(name='Samsung Galaxy A'+url[-2:],category='điện thoại'))
    pages=Resolver();r=ProgressiveRetriever(Provider(),pages,Settings(_env_file=None,
        live_search_target_products=3,live_search_page_concurrency=2))
    await r.run(['start'],RequirementData(category='điện thoại'))
    assert r.enough() and len(pages.calls)==3 and r.stop_reason=='target_reached'


@pytest.mark.asyncio
async def test_exact_product_path_precedes_merely_commercial_url():
    class Provider:
        async def search(self,q,limit):return [
            SearchResult(title='Điện thoại mua ngay',url='https://promo.test/special-offers',content='điện thoại mua ngay'),
            SearchResult(title='Samsung Galaxy A51',url='https://shop.test/products/samsung-a51',content='')]
    class Resolver:
        def __init__(self):self.calls=[]
        async def inspect(self,url,**kw):
            self.calls.append(url)
            return inspect_page(url,sales_page(name='Samsung Galaxy A51',category='điện thoại'))
    pages=Resolver();r=ProgressiveRetriever(Provider(),pages,Settings(_env_file=None,
        live_search_target_products=1,live_search_page_concurrency=1))
    await r.run(['start'],RequirementData(category='điện thoại'))
    assert pages.calls==['https://shop.test/products/samsung-a51']


@pytest.mark.asyncio
async def test_observed_child_precedes_generic_commercial_page():
    parent='https://catalog.test/category/phones'
    child='https://catalog.test/products/samsung-a52'
    html='<h1>Phones</h1><script type="application/ld+json">'+json.dumps({
        '@type':'ItemList','itemListElement':[{'@type':'Product','name':'Samsung Galaxy A52','url':child}]})+'</script>'
    class Provider:
        async def search(self,q,limit):return [
            SearchResult(title='Điện thoại mua ngay',url='https://promo.test/special-offers',content='điện thoại mua ngay'),
            SearchResult(title='Samsung Galaxy A51',url='https://shop.test/products/samsung-a51',content='')]
    class Resolver:
        def __init__(self):self.calls=[]
        async def inspect(self,url,**kw):
            self.calls.append(url)
            name='Samsung Galaxy A52' if url==child else 'Samsung Galaxy A51'
            return inspect_page(url,sales_page(name=name,category='điện thoại'))
    pages=Resolver();r=ProgressiveRetriever(Provider(),pages,Settings(_env_file=None,
        live_search_target_products=2,live_search_page_concurrency=1))
    source=SearchSourceItem(url=parent,title='Phones',page_validation=inspect_page(parent,html))
    r.source_queries[parent]='start'
    r.enqueue_children(source)
    await r.run(['start'],RequirementData(category='điện thoại'))
    assert pages.calls==['https://shop.test/products/samsung-a51',child]
    assert r.enough()


@pytest.mark.asyncio
@pytest.mark.parametrize('product_shaped', [True,False])
async def test_only_useful_new_urls_reset_progress_and_caps_still_apply(product_shaped):
    class Provider:
        calls=0
        async def search(self,q,limit):
            self.calls+=1
            return [SearchResult(title='Samsung Galaxy A51' if product_shaped else 'Điện thoại mua ngay',
                url=f'https://seller.test/'+('products/phone-' if product_shaped else 'promotion-')+str(self.calls),
                content='Cửa hàng điện thoại mua ngay')]
    class Resolver:
        async def inspect(self,url,**kw):
            return dict(product_page_valid=False,page_fetched=True,result_type='UNKNOWN',rejection_code='missing_price')
    provider=Provider();r=ProgressiveRetriever(provider,Resolver(),Settings(_env_file=None,live_search_max_queries=10))
    await r.run(['start'],RequirementData(category='điện thoại'))
    assert r.summary()['valid_offers']==0  # discovery/progress cannot fabricate an offer
    if product_shaped:
        assert r.stop_reason=='query_budget' and provider.calls==10
        assert r.rounds[-1]['new_direct_urls']>0 and r.rounds[-1]['no_progress_rounds']==0
    else:
        assert r.stop_reason=='no_progress' and provider.calls<10
        assert r.rounds[-1]['new_direct_urls']==0 and r.rounds[-1]['no_progress_rounds']>=3


@pytest.mark.asyncio
@pytest.mark.parametrize('has_proof', [True,False])
async def test_contaminated_snippet_never_overrides_clean_fetched_offer(has_proof):
    name='Điện thoại vivo V60 Lite 5G 8GB/256GB'
    url='https://shop.test/dtdd/vivo-v60-lite-8gb-256gb'
    class Provider:
        async def search(self,q,limit):return [SearchResult(title=name,url=url,content='So sánh top 10. Giảm thêm 200.000đ')]
    class Resolver:
        async def inspect(self,*a,**kw):
            if has_proof:return inspect_page(url,sales_page(name=name,category='điện thoại'))
            return dict(product_page_valid=False,page_fetched=False,fetch_blocked=True)
    r=ProgressiveRetriever(Provider(),Resolver(),Settings(_env_file=None,live_search_target_products=1,live_search_max_queries=1))
    await r.run(['start'],RequirementData(category='điện thoại'))
    assert r.enough()==has_proof
    if has_proof:
        assert r.sources[url].page_validation['price']==9000000
        assert r.sources[url].page_validation['verification_level']=='VERIFIED_CONTENT'
