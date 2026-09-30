"""Offline identity/discovery regressions; source-shaped fixtures, no Live I/O."""
import json
from pathlib import Path
from copy import deepcopy

import pytest

from app.schemas.search import SearchSourceItem
from app.services.extraction.search_metadata_validator import verify_search_metadata
from app.services.extraction.product_page_validator import inspect_page, same_identity
from app.services.search.retrieval_diagnostics import source_plan
from tests.fixtures.sales_pages import sales_page


def recorded():
    return json.loads((Path(__file__).parents[1]/'fixtures/live_direct_offer_d082d501.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('model', ['v60', 'v50'])
def test_observed_full_heading_reconciles_abbreviated_direct_slug_but_not_price(model):
    row = next(o for o in recorded()['observations'] if f'/dtdd/vivo-{model}-lite' in o['url'])
    result = verify_search_metadata(SearchSourceItem(url=row['url'],title=row['title'],content=row['content']),row['proof'])
    assert result.get('identity_match') is True
    assert not result['product_page_valid']  # promo/multiple prices are not an offer
    assert 'price' in result['reason']


@pytest.mark.parametrize('slug', ['vivo-v60-lite-8gb-256gb','vivo-v50-lite-5g'])
def test_full_heading_and_single_same_source_price_can_verify_metadata(slug):
    model = 'V60' if 'v60' in slug else 'V50'
    name = f'Điện thoại vivo {model} Lite 5G 8GB/256GB'
    s = SearchSourceItem(url='https://www.thegioididong.com/dtdd/'+slug,title=name,
                         content=f'vivo {model} Lite 5G 8GB/256GB giá 9.000.000 VND. Mua ngay tại cửa hàng.')
    p = verify_search_metadata(s,dict(fetch_blocked=True,page_fetched=True,page_heading=name))
    assert p['product_page_valid'] and p['price'] == 9000000
    assert p['verification_level'] == 'VERIFIED_SEARCH_METADATA'


@pytest.mark.parametrize('slug,heading', [
    ('vivo-v60-lite-12gb-512gb','vivo V60 Lite 5G 8GB/256GB'),
    ('vivo-v60-pro-8gb-256gb','vivo V60 Lite 5G 8GB/256GB'),
    ('vivo-v60-lite-4g-8gb-256gb','vivo V60 Lite 5G 8GB/256GB'),
    ('vivo-v50-lite-5g','vivo V60 Lite 5G 8GB/256GB'),
    ('vivo-v60-lite-8gb-256gb','vivo V60 Lite 5G 12GB/512GB')])
def test_conflicting_variant_or_model_never_matches(slug,heading):
    s=SearchSourceItem(url='https://shop.test/'+slug,title='vivo V60 Lite 5G 8GB/256GB',content='Mua ngay giá 9.000.000 VND')
    p=verify_search_metadata(s,dict(fetch_blocked=True,page_fetched=True,page_heading=heading))
    assert not p.get('identity_match') and not p['product_page_valid']
    assert not same_identity('vivo V60 Lite 5G 8GB/256GB','vivo V60 Lite 5G 12GB/512GB')


def test_missing_full_page_heading_does_not_fill_url_variant_from_title_alone():
    s=SearchSourceItem(url='https://shop.test/vivo-v50-lite-5g',title='vivo V50 Lite 5G 8GB/256GB',content='vivo V50 Lite 5G 8GB/256GB giá 9.000.000 VND')
    assert not verify_search_metadata(s,dict(fetch_blocked=True))['product_page_valid']


def test_repeated_model_phrase_is_normalized_without_removing_variant():
    from app.services.extraction.search_metadata_validator import page_backed_identity
    title='Điện thoại vivo V60 Lite 5G 8GB/256GB vivo V60'
    proof=dict(page_fetched=True,fetch_blocked=True,page_heading='vivo V60 Lite 5G 8GB/256GB')
    assert page_backed_identity(title,'vivo v60 lite 8gb 256gb',proof)
    source=SearchSourceItem(url='https://thegioididong.com/dtdd/vivo-v60-lite-8gb-256gb',title=title,
        content='vivo V60 Lite 5G 8GB/256GB giá 9.000.000 VND. Mua ngay.')
    result=verify_search_metadata(source,proof)
    assert result['product_page_valid'] and result['name']=='vivo V60 Lite 5G 8GB/256GB'
    assert not page_backed_identity(title+' 12GB/512GB','vivo v60 lite 8gb 256gb',proof)


def test_abbreviated_slug_cannot_borrow_heading_from_redirected_other_page():
    from app.services.extraction.search_metadata_validator import page_backed_identity
    proof=dict(page_fetched=True,page_heading='vivo V60 Lite 5G 8GB/256GB',
               evidence_url='https://other.test/v60-lite')
    assert not page_backed_identity(proof['page_heading'],'vivo v60 lite 8gb 256gb',proof,
                                   'https://shop.test/vivo-v60-lite-8gb-256gb')


@pytest.mark.parametrize('url', ['https://viettablet.com/vivo-v30e','https://thegioididong.com/dtdd/vivo-v30e-12gb',
 'https://mobilecity.vn/dien-thoai/xiaomi-redmi-note-13-gia-re.html','https://dienthoaihay.vn/xiaomi/xiaomi-redmi-note-13-5g-p705.html'])
def test_direct_shapes_get_verification_budget_not_certification(url):
    assert source_plan(SearchSourceItem(url=url,title='Điện thoại vivo V30e')) == 'product'
    assert not inspect_page(url,'<h1>Điện thoại vivo V30e</h1>')['product_page_valid']


def category_page():
    return '<h1>Điện thoại</h1><script type="application/ld+json">'+json.dumps({'@type':'ItemList','itemListElement':[
        {'@type':'ListItem','item':{'@type':'Product','name':'Điện thoại Example X1','url':'/dtdd/example-x1'}},
        {'@type':'ListItem','item':{'@type':'Product','name':'Never Invent X2'}},
        {'@type':'ListItem','item':{'@type':'Product','name':'Unsafe X3','url':'http://127.0.0.1/private'}},
    ]})+'</script><a class="product-card" href="/dtdd/example-x4">Điện thoại Example X4</a>'


def test_category_child_urls_are_observed_safe_and_parent_stays_unverified():
    p=inspect_page('https://shop.test/category/phones',category_page())
    assert not p['product_page_valid']
    assert {c['url'] for c in p.get('child_products',[])} == {'https://shop.test/dtdd/example-x1','https://shop.test/dtdd/example-x4'}


def test_recorded_redmi_phone_family_is_page_evidence_not_merchant_inference():
    url='https://shop.test/xiaomi-redmi-note-13-5g'
    p=inspect_page(url,sales_page(name='Xiaomi Redmi Note 13 5G 8GB 128GB - Cũ Đẹp'))
    assert p['category'] == 'điện thoại' and p['category_evidence']['source'] == 'h1'
    assert inspect_page(url,sales_page(name='Ốp lưng Xiaomi Redmi Note 13'))['category'] == 'ốp lưng'
    assert inspect_page('https://phone-shop.test/device-x1',sales_page(name='Device X1'))['category'] is None


def test_redmi_family_never_overrides_contradictory_explicit_taxonomy():
    p=inspect_page('https://shop.test/redmi-note-13',sales_page(name='Xiaomi Redmi Note 13',category='tai nghe'))
    assert not p['product_page_valid'] and p['category_evidence']['conflict']


@pytest.mark.asyncio
@pytest.mark.parametrize('cap', [1, 2])
async def test_child_links_enter_bounded_queue_and_remain_attached_to_parent_query(cap):
    from app.core.config import Settings
    from app.schemas.requirement import RequirementData
    from app.services.search.base import SearchResult
    from app.services.search.progressive_retrieval import ProgressiveRetriever
    class Provider:
        async def search(self,q,limit): return [SearchResult(url='https://shop.test/category/phones',title='Điện thoại',content='')]
    class Resolver:
        def __init__(self): self.calls=[]
        async def inspect(self,url,**kw):
            self.calls.append(url)
            html=category_page() if '/category/' in url else sales_page(name='Điện thoại Example '+url.rsplit('-',1)[-1].upper())
            return inspect_page(url,html)
    pages=Resolver()
    r=ProgressiveRetriever(Provider(),pages,Settings(_env_file=None,live_search_target_products=2,
        live_search_initial_candidates=cap,live_search_max_candidates=cap))
    batches=await r.run(['phone'],RequirementData(category='điện thoại'))
    assert len(pages.calls)==len(set(pages.calls))==cap+1 and r.enough()==(cap==2)
    assert len(r.child_urls)==cap and all('never' not in url for url in pages.calls)
    assert {s.url for _,sources,_ in batches for s in sources}==set(pages.calls)
    assert len(r.product_attempts)==cap and len(r.discovery_attempts)==1


@pytest.mark.asyncio
async def test_two_unavailable_models_each_get_alternate_merchant_lookup(monkeypatch):
    from app.core.config import Settings
    from app.schemas.requirement import RequirementData
    from app.services.search.progressive_retrieval import ProgressiveRetriever
    from app.services.search.source_strategy import SourceStrategy
    from app.services.search.merchant_quality import MerchantQualityService
    monkeypatch.setattr(SourceStrategy,'preferred_domains',lambda *a:['other.test','third.test'])
    monkeypatch.setattr(MerchantQualityService,'discover',lambda *a:[])
    r=ProgressiveRetriever(None,None,Settings(_env_file=None))
    r.requirement=RequirementData(category='điện thoại')
    for n in [51,52]:
        url=f'https://old.test/phone-x{n}'
        p=inspect_page(url,sales_page(name=f'Samsung Galaxy A{n}',brand='Samsung',category='điện thoại'))
        p['availability']='out_of_stock'
        r.sources[url]=SearchSourceItem(url=url,title=p['name'],page_validation=p)
    for name in r.model_hints(): r.queries.add(r.model_query(name,'mua'))
    first=r.continuation_query('điện thoại',True);r.queries.add(first)
    second=r.continuation_query('điện thoại',True)
    assert 'site:other.test' in first and '"Samsung Galaxy A51"' in first
    assert 'site:third.test' in second and '"Samsung Galaxy A52"' in second
    assert not r.enough()


@pytest.mark.asyncio
async def test_slow_domain_cancellation_does_not_starve_fast_merchant():
    import asyncio
    from app.core.config import Settings
    from app.schemas.requirement import RequirementData
    from app.services.search.base import SearchResult
    from app.services.search.progressive_retrieval import ProgressiveRetriever
    active=set()
    class Provider:
        async def search(self,q,limit):
            return [SearchResult(title=f'Phone X{i}',url=f'https://slow.test/phone-x{i}',content='') for i in range(8)]+[
                SearchResult(title='Phone Good X9',url='https://fast.test/phone-x9',content='')]
    class Resolver:
        async def inspect(self,url,**kw):
            if 'slow.test' in url:
                active.add(url)
                try: await asyncio.Event().wait()
                finally: active.remove(url)
            return inspect_page(url,sales_page(name='Phone Good X9'))
    r=ProgressiveRetriever(Provider(),Resolver(),Settings(_env_file=None,live_search_page_budget_seconds=.02,
        live_search_domain_budget_seconds=.03,live_search_target_products=5,live_search_max_queries=2))
    await asyncio.wait_for(r.run(['one'],RequirementData(category='điện thoại')),timeout=1)
    assert not active and r.summary()['valid_offers']==1
    assert r.domain_work['slow.test']['attempts']==2
    assert r.domain_work['slow.test']['skipped']==6
    assert r.domain_work['fast.test']['attempts']==1
    assert r.domain_work['slow.test']['spent'] < .2


@pytest.mark.asyncio
async def test_healthy_work_also_has_cumulative_domain_time_bound():
    import asyncio
    from app.core.config import Settings
    from app.schemas.requirement import RequirementData
    from app.services.search.base import SearchResult
    from app.services.search.progressive_retrieval import ProgressiveRetriever
    class Provider:
        async def search(self,q,limit):
            return [SearchResult(title=f'Phone X{i}',url=f'https://shop.test/phone-x{i}',content='') for i in range(8)]
    class Resolver:
        async def inspect(self,url,**kw):
            await asyncio.sleep(.02)
            return dict(product_page_valid=False,page_fetched=True,result_type='UNKNOWN')
    r=ProgressiveRetriever(Provider(),Resolver(),Settings(_env_file=None,live_search_domain_budget_seconds=.03,
        live_search_page_budget_seconds=.5,live_search_max_queries=1))
    await asyncio.wait_for(r.run(['one'],RequirementData(category='điện thoại')),timeout=1)
    w=r.domain_work['shop.test']
    assert w['attempts']<=4 and w['skipped']>=4 and w['spent']<.2
