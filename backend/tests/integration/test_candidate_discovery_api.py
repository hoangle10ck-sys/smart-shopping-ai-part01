"""Real Live pipeline on isolated DB with local sources only."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings
from app.services.search import search_service, cached_search_service
from app.services.extraction.product_image_resolver import ProductImageResolver
from tests.fixtures.discovery_scenarios import NoisyProvider, LocalPages, product


QUERY = 'Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu'


@pytest.fixture
def live(monkeypatch):
    settings = get_settings()
    for key, value in dict(demo_mode=False, openai_api_key='', gemini_api_key='', cache_ttl_seconds=120,
                           max_search_queries=2, live_search_max_queries=12, top_k=5,
                           live_search_target_products=5).items():
        monkeypatch.setattr(settings, key, value)
    provider, pages = NoisyProvider(), LocalPages()
    monkeypatch.setattr(search_service, 'get_search_provider', lambda:provider)
    async def fetch(self, url): return await pages.html(url)
    monkeypatch.setattr(ProductImageResolver, '_fetch_html', fetch)
    return provider, pages


def execute(client):
    response = client.post('/api/requirements/analyze', json={'raw_query':QUERY})
    assert response.status_code == 200 and not response.json()['needs_clarification']
    response = client.post('/api/search', json={'session_id':response.json()['session_id']})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize('supply', [2, 3, 5])
def test_editorial_discovery_promotes_only_actual_direct_offers(live, supply):
    provider, pages = live
    provider.supply = supply
    with TestClient(app) as client:
        result = execute(client)
        assert result['total_found'] == supply + 1  # The first out-of-stock product remains auditable.
        assert result['total_filtered'] == result['total_recommended'] == supply
        assert len({item['product_id'] for item in result['recommendations']}) == supply
        assert {item['name'] for item in result['recommendations']} == {
            f'Samsung Galaxy A{n} 128GB' for n in range(50, 50 + supply)}
        info = result['retrieval_diagnostics'][-1]['performance']['diagnostics']
        assert info['valid_candidates'] == supply + 1 and info['eligible_offers'] == supply
        assert info['final_recommendations'] == supply
        assert info['filter_reason_counts'] == {'availability':1}
        assert info['filter_rejections'][0]['name'] == 'Samsung Galaxy A49 128GB'
        assert info['conversion']['direct_product_candidates'] == supply + 1
        assert info['conversion']['evidence_only_results'] >= 9
        assert info['rounds'][1]['kind'] == 'model_discovery'
        assert len(provider.calls) <= 12 and len(pages.calls) == len(set(pages.calls)) == supply + 1
        assert all('/news/' not in item['product_url'] and item['product_page_valid'] for item in result['recommendations'])
        assert client.get('/api/search/'+result['session_id']).json()['recommendations'] == result['recommendations']
        saved = client.get('/api/search/'+result['session_id']).json()['retrieval_diagnostics']
        assert saved[-1]['performance']['diagnostics'] == info
        assert saved[-1]['performance']['timings']['total_search_ms'] > 0
        assert saved[-1]['performance']['diagnostics']['page_timings']


def test_flexible_outside_window_survives_real_pipeline(live):
    _, pages = live
    pages.price = 12000000
    with TestClient(app) as client:
        result = execute(client)
    assert result['requirement']['preferred_max'] == 10600000
    assert result['total_recommended'] == 5
    assert all(item['price'] == 12000000 for item in result['recommendations'])
    assert all(d['accepted'] or d['rejection_stage'] == 'availability' for d in result['filter_decisions'])


def test_saved_trace_survives_failed_refresh_without_replacing_snapshot(live, monkeypatch):
    provider, _ = live
    with TestClient(app) as client:
        original = execute(client)
        url = '/api/search/' + original['session_id']
        saved = client.get(url).json()
        async def fail(*args, **kwargs):
            raise RuntimeError('fixture unavailable')
        monkeypatch.setattr(provider, 'search', fail)
        failed = client.post('/api/search', json={'session_id': original['session_id']})
        assert failed.status_code == 503
        again = client.get(url).json()
        assert again['status'] == 'FAILED' and again['warnings']
        assert again['recommendations'] == saved['recommendations']
        assert again['retrieval_diagnostics'] == saved['retrieval_diagnostics']


@pytest.mark.parametrize('old_scope', ['target_1', 'retrieval_version_2', 'retrieval_version_5', 'retrieval_version_6', 'retrieval_version_7'])
def test_old_small_or_legacy_cache_cannot_mask_target_five(live, monkeypatch, old_scope):
    provider, pages = live
    # Healthy one-offer result without editorial warnings is genuinely cached.
    async def search(query, limit):
        provider.calls.append(query)
        return [product(n) for n in (range(50,55) if '"' in query else [50])]
    monkeypatch.setattr(provider, 'search', search)
    settings = get_settings()
    original_key = cached_search_service.make_cache_key
    if old_scope == 'target_1': monkeypatch.setattr(settings, 'live_search_target_products', 1)
    else:
        def legacy_key(requirement, *, scope):
            scope = {**scope, 'retrieval_version':int(old_scope.rsplit('_',1)[-1])}
            if old_scope == 'retrieval_version_2': scope.pop('live_search_discovery_pages', None)
            return original_key(requirement, scope=scope)
        monkeypatch.setattr(cached_search_service, 'make_cache_key', legacy_key)
    with TestClient(app) as client:
        first = execute(client)
        if old_scope == 'target_1': assert first['total_recommended'] == 1
        # Prove that the old entry exists and is reusable in its own scope.
        calls = len(provider.calls)
        hit = execute(client)
        assert len(provider.calls) == calls
        assert hit['retrieval_diagnostics'][-1]['performance']['diagnostics']['cache_hit']
        monkeypatch.setattr(settings, 'live_search_target_products', 5)
        monkeypatch.setattr(cached_search_service, 'make_cache_key', original_key)
        fresh = execute(client)
        assert len(provider.calls) > calls and fresh['total_recommended'] == 5
        assert not fresh['retrieval_diagnostics'][-1]['performance']['diagnostics']['cache_hit']
