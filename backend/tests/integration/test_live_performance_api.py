"""Live configuration, real extraction/ranking, only local provider/page fixtures."""
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.extraction.product_image_resolver import ProductImageResolver
from app.services.search import search_service
from app.services.search.base import SearchResult
from app.services.performance import TIMINGS
from tests.fixtures.sales_pages import sales_page

QUERY = 'Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu'


@pytest.fixture
def live(monkeypatch):
    settings = get_settings()
    for key, value in dict(demo_mode=False, openai_api_key='', gemini_api_key='',
                           cache_ttl_seconds=120, live_search_max_queries=6).items():
        monkeypatch.setattr(settings, key, value)
    assert settings.live_search_target_products == settings.top_k == 5
    state = dict(supply=5, calls=0, fetches=[], rejected=False)
    class Provider:
        async def search(self, query, max_results):
            state['calls'] += 1
            numbers = list(range(50, 50 + state['supply']))
            if state['rejected']: numbers += [70, 71, 72, 73, 74]
            return [SearchResult(title=f'Samsung Galaxy A{n} 128GB',
                url=f'https://seller{n}.example/dien-thoai-samsung-galaxy-a{n}-128gb',
                content=f'Điện thoại Samsung Galaxy A{n} 128GB giá 9.000.000 VND. Mua ngay.') for n in numbers]
    async def page(self, url):
        state['fetches'].append(url)
        n = int(url.rsplit('-a', 1)[1].split('-')[0])
        if n == 73:
            return url, ('<html><h1>Tin tức điện thoại</h1><article>Review Samsung</article>'
                         '<script type="application/ld+json">{"@type":"NewsArticle"}</script></html>')
        name = 'Tai nghe Sony WH1000XM5' if n == 70 else f'Samsung Galaxy A{n} 128GB'
        category = 'tai nghe' if n == 70 else 'điện thoại'
        extra = dict(brand='Sony' if n == 70 else 'Samsung', model=f'A{n}', category=category,
                     additionalProperty=[{'name':'camera','value':'50 MP'}, {'name':'battery','value':'5000 mAh'}])
        if n == 72: extra['offers'] = {'@type':'Offer','price':9000000,'priceCurrency':'VND',
            'availability':'https://schema.org/OutOfStock', 'seller':{'name':'Test Merchant'}}
        if n == 74: extra['category'] = 'tai nghe'  # Contradictory main-page evidence.
        return url, sales_page(name=name, price=None if n == 71 else 9000000, **extra)
    monkeypatch.setattr(search_service, 'get_search_provider', Provider)
    monkeypatch.setattr(ProductImageResolver, '_fetch_html', page)
    return state


def search(client, query=QUERY):
    analysis = client.post('/api/requirements/analyze', json={'raw_query':query})
    assert analysis.status_code == 200 and not analysis.json()['needs_clarification']
    response = client.post('/api/search', json={'session_id':analysis.json()['session_id']})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize('supply', [2, 3, 5])
def test_live_actual_pipeline_returns_only_verified_supply_and_snapshot(live, supply):
    live['supply'] = supply
    with TestClient(app) as client:
        body = search(client)
        assert not body['demo_mode']
        assert body['total_recommended'] == len(body['recommendations']) == supply
        assert len(live['fetches']) == len(set(live['fetches'])) == supply
        performance = body['retrieval_diagnostics'][-1]['performance']
        assert set(TIMINGS).issubset(performance['timings'])
        assert performance['timings']['total_search_ms'] > 0
        diagnostics = performance['diagnostics']
        assert diagnostics['final_recommendations'] == diagnostics['valid_offers'] == supply
        assert diagnostics['pages_verified'] == len(diagnostics['unique_candidate_urls']) == supply
        assert len(diagnostics['generated_queries']) == live['calls']
        for item in body['recommendations']:
            assert item['price'] == 9000000 and item['product_page_valid']
            assert item['image_url'] is None
            score = item['score']
            expected = sum(score[field + '_score'] * weight for field, weight in
                [('budget',.25), ('requirement',.30), ('purpose',.20), ('rating',.10), ('review',.05), ('source',.10)])
            assert score['final_score'] == pytest.approx(round(expected, 2), abs=.01)
        saved = client.get('/api/search/' + body['session_id']).json()
        assert saved['recommendations'] == body['recommendations']
        calls = live['calls']
        cached = search(client)
        assert live['calls'] == calls
        assert cached['recommendations'] == body['recommendations']
        info = cached['retrieval_diagnostics'][-1]['performance']
        assert info['diagnostics']['cache_hit'] and info['diagnostics']['final_recommendations'] == supply
        assert info['timings']['search_provider_ms'] == info['timings']['product_verification_ms'] == 0


def test_rejections_remain_strict_and_are_counted(live):
    live.update(supply=2, rejected=True)
    with TestClient(app) as client:
        body = search(client)
    assert body['total_recommended'] == 2
    stats = body['retrieval_diagnostics'][-1]['performance']['diagnostics']
    assert stats['rejected_wrong_category'] == 2
    assert stats['rejected_missing_price'] == 1
    assert stats['rejected_out_of_stock'] == 1
    assert stats['rejected_non_product_page'] == 1


@pytest.mark.parametrize('field,value', [('live_search_target_products', 3), ('live_search_min_products', 2),
    ('live_search_max_candidates', 24), ('live_search_initial_candidates', 12),
    ('live_search_max_queries', 8), ('live_search_budget_seconds', 90)])
def test_cache_scope_changes_trigger_new_retrieval(live, monkeypatch, field, value):
    with TestClient(app) as client:
        search(client)
        previous = live['calls']
        monkeypatch.setattr(get_settings(), field, value)
        body = search(client)
    assert live['calls'] > previous
    assert not body['retrieval_diagnostics'][-1]['performance']['diagnostics']['cache_hit']


def test_all_budget_modes_keep_separate_cache_entries(live):
    with TestClient(app) as client:
        for query, mode in [(QUERY, 'FLEXIBLE_TARGET'),
            ('Điện thoại tối đa 10 triệu, camera tốt, pin lâu', 'HARD_MAX'),
            ('Điện thoại từ 8 đến 10 triệu, camera tốt, pin lâu', 'RANGE')]:
            previous = live['calls']
            body = search(client, query)
            assert body['requirement']['budget_mode'] == mode
            assert live['calls'] > previous
            assert body['total_recommended'] == 5
