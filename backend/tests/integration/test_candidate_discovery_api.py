"""Real Live pipeline on isolated DB with local sources only."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings
from app.services.search import search_service
from app.services.search.multi_provider import MultiSearchProvider
from app.services.extraction.product_image_resolver import ProductImageResolver
from tests.fixtures.discovery_scenarios import NoisyProvider, LocalPages


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
    def configure_provider(self, *, include_searxng=True): self.providers = [provider]
    monkeypatch.setattr(MultiSearchProvider, '__init__', configure_provider)
    monkeypatch.setattr(ProductImageResolver, 'inspect', pages.inspect)
    monkeypatch.setattr('app.services.search.unified.orchestrator.LiveProductSource.is_available', lambda self, db: True)
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
        live_source = next(item for item in result['unified_sources']
                           if item['source'] == 'configured_web_search')
        assert live_source['available'] and live_source['error'] is None
        assert live_source['ingested_rows'] > 0
        assert len(provider.calls) <= 12 and len(pages.calls) == len(set(pages.calls)) == supply + 1
        assert all('/news/' not in item['product_url'] and item['product_page_valid'] for item in result['recommendations'])
        saved = client.get('/api/search/'+result['session_id']).json()
        assert saved['recommendations'] == result['recommendations']
        assert saved['unified_sources'] == result['unified_sources']


def test_flexible_outside_window_survives_real_pipeline(live):
    _, pages = live
    pages.price = 12000000
    with TestClient(app) as client:
        result = execute(client)
    assert result['requirement']['preferred_max'] == 10600000
    assert result['total_recommended'] == 5
    assert all(item['price'] == 12000000 for item in result['recommendations'])
    assert all(d['accepted'] or d['rejection_stage'] == 'availability' for d in result['filter_decisions'])


def test_failed_live_refresh_keeps_recommendations_and_reports_partial_source(live, monkeypatch):
    provider, _ = live
    with TestClient(app) as client:
        original = execute(client)
        url = '/api/search/' + original['session_id']
        saved = client.get(url).json()
        async def fail(*args, **kwargs):
            raise RuntimeError('fixture unavailable')
        monkeypatch.setattr(provider, 'search', fail)
        failed = client.post('/api/search', json={'session_id': original['session_id']})
        assert failed.status_code == 200
        assert failed.json()['status'] == 'COMPLETED'
        live_source = next(item for item in failed.json()['unified_sources']
                           if item['source'] == 'configured_web_search')
        assert live_source['error'] == 'AllSearchQueriesFailed'
        again = client.get(url).json()
        assert again['status'] == 'COMPLETED' and again['warnings']
        assert {item['product_id'] for item in again['recommendations']} == {
            item['product_id'] for item in saved['recommendations']
        }
        assert {item['product_url'] for item in again['recommendations']} == {
            item['product_url'] for item in saved['recommendations']
        }
        assert again['unified_sources'] == failed.json()['unified_sources']


def test_automatic_search_rechecks_configured_source_on_repeat(live):
    provider, _ = live
    with TestClient(app) as client:
        first = execute(client)
        calls = len(provider.calls)
        refreshed = client.post('/api/search', json={'session_id': first['session_id']})

    assert refreshed.status_code == 200
    assert refreshed.json()['total_recommended'] == 5
    assert len(provider.calls) > calls
