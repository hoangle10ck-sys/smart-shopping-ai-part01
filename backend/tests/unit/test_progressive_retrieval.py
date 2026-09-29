import asyncio
from types import SimpleNamespace

import pytest

from app.schemas.search import SearchSourceItem
from app.services.extraction.search_metadata_validator import verify_search_metadata
from app.services.search.base import SearchResult, SearchProviderError
from app.services.search.progressive_retrieval import ProgressiveRetriever


def source(**changes):
    data = dict(url='https://new-shop.vn/products/samsung-galaxy-a36-128gb',
                title='Samsung Galaxy A36 128GB',
                content='Điện thoại Samsung Galaxy A36 128GB giá bán 9.000.000 VND. Mua ngay tại cửa hàng.')
    return SearchSourceItem(**{**data, **changes})


def test_blocked_page_with_strong_same_offer_metadata():
    result = verify_search_metadata(source(), {'fetch_blocked': True})
    assert result['product_page_valid']
    assert result['verification_level'] == 'VERIFIED_SEARCH_METADATA'
    assert result['price'] == 9000000
    assert result['product_page_confidence'] >= 90
    assert result['product_url'] == result['evidence_url'] == source().url
    assert result['merchant'] == 'new-shop.vn'
    assert result['image_url'] is None


@pytest.mark.parametrize('changes', [
    {'url': 'https://new-shop.vn/'}, {'url': 'https://new-shop.vn/category/phones'},
    {'url': 'https://new-shop.vn/search?q=phone'}, {'url': 'https://new-shop.vn/blog/samsung-galaxy-a36-128gb'},
    {'title': 'Samsung Galaxy A35 128GB'}, {'title': 'Samsung Galaxy A36 Pro 128GB'},
    {'content': 'Mua ngay giá bán 9.000.000 VND'},
    {'content': 'Samsung Galaxy A36 128GB mua ngay giá 9.000.000 VND hoặc 10.000.000 VND'},
    {'content': 'Samsung Galaxy A36 128GB Pro mua ngay giá 9.000.000 VND'},
    {'content': 'Samsung Galaxy A36 128GB đánh giá giá 9.000.000 VND'},
    {'title': 'Samsung Galaxy', 'url': 'https://new-shop.vn/samsung-galaxy',
     'content': 'Samsung Galaxy giá bán 9.000.000 VND. Mua ngay tại cửa hàng.'},
])
def test_weak_wrong_or_editorial_metadata_never_verifies(changes):
    assert not verify_search_metadata(source(**changes), {'fetch_blocked': True})['product_page_valid']


def test_metadata_cannot_override_fetched_invalid_content():
    assert not verify_search_metadata(source(), {'fetch_blocked': False})['product_page_valid']


def test_explicit_main_product_price_does_not_borrow_related_card_price_or_wrong_brand_image():
    from app.services.extraction.product_page_validator import inspect_page
    html = ('<h1>Phone Example X15</h1><meta property="og:type" content="product">'
            '<span class="current-price ProductPrice">9.000.000₫</span><button>Mua ngay</button>'
            '<meta property="og:image" content="https://shop.vn/vivo-y02.jpg">'
            '<div class="related"><span class="current-price">5.000.000₫</span></div>')
    proof = inspect_page('https://shop.vn/phone-example-x15', html)
    assert proof['product_page_valid'] and proof['price'] == 9000000
    assert proof['image_candidates'] == []


@pytest.mark.asyncio
@pytest.mark.parametrize('html', ['<title>Just a moment</title><p>Verify you are human</p>',
                                '<html><div id="root"></div><script src="/app.js"></script></html>'])
async def test_js_or_antibot_html_uses_strong_metadata_without_image(monkeypatch, html):
    from app.services.extraction.product_image_resolver import ProductImageResolver
    async def fetch(self, url): return url, html
    monkeypatch.setattr(ProductImageResolver, '_fetch_html', fetch)
    proof = await ProductImageResolver().inspect(source().url, resolve_images=False)
    assert proof['fetch_blocked']
    result = verify_search_metadata(source(), proof)
    assert result['verification_level'] == 'VERIFIED_SEARCH_METADATA'
    assert result['image_url'] is None


class BlockedResolver:
    async def inspect(self, url, **kwargs):
        return {'product_page_valid': False, 'fetch_blocked': True}

    async def _image_loads(self, url):
        raise AssertionError('No verified image evidence; must not fetch provider image')


def settings(**changes):
    return SimpleNamespace(**{**dict(live_search_budget_seconds=2, live_search_max_queries=12,
        live_search_target_products=1, max_results_per_query=5), **changes})


def test_selected_official_version_price_does_not_deprioritize_whole_model():
    from app.schemas.requirement import RequirementData
    retriever = ProgressiveRetriever(None, None, settings())
    retriever.requirement = RequirementData(category='xe máy', budget_max=33000000)
    retriever.sources = {'official': source(result_type='UNKNOWN', page_validation={'discovery': [
        {'name':'Suzuki Orbit 125', 'brand':'Suzuki', 'variant':{}, 'price_type':'SUGGESTED_RANGE',
         'price_min':36800000, 'price_max':36800000},
        {'name':'Acme Urban 110', 'brand':'Acme', 'variant':{}, 'price_type':'RANGE',
         'price_min':30000000, 'price_max':32000000}]})}
    assert retriever.model_hints()[:2] == ['Suzuki Orbit 125', 'Acme Urban 110']
    query = retriever.model_query('Suzuki Orbit 125')
    assert query == '"Suzuki Orbit 125" giá bán Việt Nam VND'
    assert retriever.requirement.budget_max == 33000000


def test_unrelated_snippet_numbers_cannot_become_exact_model_hint():
    retriever = ProgressiveRetriever(None, None, settings())
    retriever.sources = {'video':source(title='Best TVs for movies',result_type='UNKNOWN',page_validation={},
        content='Samsung 15 59 Hàng thì giá bán 10.000.000 VND mua ngay')}
    assert retriever.model_hints() == []


def test_observed_model_mention_in_snippet_can_seed_lookup_but_not_an_offer():
    retriever = ProgressiveRetriever(None, None, settings())
    retriever.sources = {'mention':source(title='Affordable vehicles for students',result_type='UNKNOWN',
        page_validation={'product_page_valid':False},
        content='Honda Vision giá bán 33.000.000 VND. Xe máy cho sinh viên.')}
    assert 'Honda Vision' in retriever.model_hints()
    assert not retriever.enough()


def test_multiple_brand_phrase_never_becomes_model_hint():
    retriever=ProgressiveRetriever(None,None,settings())
    retriever.sources={'mention':source(title='TV comparison',result_type='UNKNOWN',page_validation={},
        content='Samsung Sony LG TCL 3 22 với giá bán 10.000.000 VND mua ngay')}
    assert retriever.model_hints()==[]


@pytest.mark.asyncio
async def test_discovery_followed_by_direct_product_on_new_domain():
    calls = []
    class Provider:
        async def search(self, query, max_results):
            calls.append(query)
            if query.startswith('site:new-shop.vn'):
                item = source()
                return [SearchResult(title=item.title, content=item.content, url=item.url)]
            if query.endswith('đại lý'):
                return [SearchResult(title='Cửa hàng điện thoại New Shop', url='https://new-shop.vn/',
                                     content='Cửa hàng điện thoại chính hãng, mua ngay tại đại lý.')]
            return []
    retriever = ProgressiveRetriever(Provider(), BlockedResolver(), settings())
    batches = await retriever.run(['điện thoại theo nhu cầu'], SimpleNamespace(category='điện thoại', brands=[]))
    assert any(query.startswith('site:new-shop.vn') for query in calls)
    assert len(calls) <= 12
    verified = [s for _, sources, _ in batches for s in sources if s.page_validation['product_page_valid']]
    assert len(verified) == 1 and verified[0].image_url is None
    assert any(d['pass'] == 'merchant_products' and d['verified'] == 1 for d in retriever.diagnostics)


@pytest.mark.asyncio
async def test_one_timeout_keeps_other_query_and_stops_when_target_met():
    class Provider:
        async def search(self, query, max_results):
            if query == 'bad': raise SearchProviderError('timeout', kind='timeout')
            item = source()
            return [SearchResult(title=item.title, content=item.content, url=item.url)]
    retriever = ProgressiveRetriever(Provider(), BlockedResolver(), settings())
    batches = await retriever.run(['bad', 'good'], SimpleNamespace(category='điện thoại', brands=[]))
    assert len(batches) == 2
    assert any('[timeout]' in (warning or '') for _, _, warning in batches)
    assert any(s.page_validation['product_page_valid'] for _, sources, _ in batches for s in sources)


@pytest.mark.asyncio
async def test_total_budget_cancels_provider_and_does_not_start_unbounded_passes():
    class Slow:
        async def search(self, query, max_results):
            await asyncio.sleep(10)
    retriever = ProgressiveRetriever(Slow(), BlockedResolver(), settings(live_search_budget_seconds=.02))
    batches = await retriever.run(['slow'], SimpleNamespace(category='tool', brands=[]))
    assert len(batches) == 1 and batches[0][2]
    assert retriever.diagnostics[0]['error_kind'] == 'timeout'
