from fastapi.testclient import TestClient

from app.main import app
from app.services.llm.client import FallbackLLMClient, MockLLMClient
from app.services.llm import requirement_analyzer
from app.services.search.mock_provider import MockSearchProvider


def test_blocked_metadata_offers_keep_own_prices_without_images_and_survive_failure(monkeypatch):
    from app.core.config import get_settings
    from app.core.database import SessionLocal
    from app.models.search_session import SearchSession
    from app.models.requirement import Requirement
    from app.models.search_query import SearchQuery
    from app.services.search import search_service
    from app.services.search.base import SearchResult, SearchProviderError
    from app.services.extraction.product_image_resolver import ProductImageResolver
    settings = get_settings()
    monkeypatch.setattr(settings, 'demo_mode', False)
    monkeypatch.setattr(settings, 'cache_ttl_seconds', 0)
    monkeypatch.setattr(settings, 'gemini_api_key', '')
    monkeypatch.setattr(settings, 'openai_api_key', '')
    state = {'fail': False}
    class Provider:
        async def search(self, query, max_results):
            if state['fail']: raise SearchProviderError('timeout', kind='timeout')
            return [SearchResult(title=f'Samsung Galaxy {model} 128GB',
                url=f'https://{domain}/products/samsung-galaxy-{model.lower()}-128gb',
                content=f'Điện thoại Samsung Galaxy {model} 128GB. Mua ngay giá bán {price} VND tại cửa hàng.')
                for model, price, domain in [('A36', '9.000.000', 'shop-a.vn'), ('A35', '8.000.000', 'shop-b.vn')]]
    async def blocked(self, url): return None
    monkeypatch.setattr(search_service, 'get_search_provider', Provider)
    monkeypatch.setattr(ProductImageResolver, '_fetch_html', blocked)
    with SessionLocal() as db:
        session = SearchSession(raw_query='Điện thoại 10 triệu chụp ảnh')
        db.add(session); db.flush()
        session_id = session.id
        db.add(Requirement(session_id=session_id, category='điện thoại', budget_max=10000000))
        db.add(SearchQuery(session_id=session_id, query='điện thoại', position=1))
        db.commit()
    with TestClient(app) as client:
        response = client.post('/api/search', json={'session_id': session_id})
        assert response.status_code == 200
        items = response.json()['recommendations']
        assert len(items) == 2
        by_name = {item['name']: item for item in items}
        assert by_name['Samsung Galaxy A36 128GB']['price'] == 9000000
        assert 'shop-a.vn' in by_name['Samsung Galaxy A36 128GB']['product_url']
        assert by_name['Samsung Galaxy A35 128GB']['price'] == 8000000
        assert 'shop-b.vn' in by_name['Samsung Galaxy A35 128GB']['product_url']
        assert all(item['image_url'] is None and item['verification_level'] == 'VERIFIED_SEARCH_METADATA' for item in items)
        assert client.get('/api/search/' + session_id).json()['recommendations'] == items
        state['fail'] = True
        failed = client.post('/api/search', json={'session_id': session_id})
        assert failed.status_code == 503
        loaded = client.get('/api/search/' + session_id).json()
        assert loaded['status'] == 'FAILED' and loaded['recommendations'] == items
        assert any('[timeout]' in warning for warning in loaded['warnings'])


def test_gemini_429_still_analyzes_tv_and_executes_search(monkeypatch):
    class QuotaFailure:
        async def analyze_requirement(self, query):
            raise RuntimeError('Gemini 429 RESOURCE_EXHAUSTED')
    monkeypatch.setattr(requirement_analyzer, 'get_llm_client',
                        lambda: FallbackLLMClient(QuotaFailure(), MockLLMClient()))
    calls = []
    async def provider(self, query, max_results):
        calls.append(query)
        return []
    monkeypatch.setattr(MockSearchProvider, 'search', provider)
    with TestClient(app) as client:
        analysis = client.post('/api/requirements/analyze', json={'raw_query': 'Tôi cần TV khoảng 10 triệu để xem phim.'})
        assert analysis.status_code == 200
        data = analysis.json()
        assert data['needs_clarification'] is False
        assert data['requirement']['purpose'] == ['xem phim']
        assert data['requirement']['budget_max'] == 10000000
        response = client.post('/api/search', json={'session_id': data['session_id']})
        assert response.status_code == 200 and calls
