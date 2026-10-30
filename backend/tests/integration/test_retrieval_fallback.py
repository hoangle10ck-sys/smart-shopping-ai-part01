from fastapi.testclient import TestClient

from app.main import app
from app.services.llm.client import FallbackLLMClient, MockLLMClient
from app.services.llm import requirement_analyzer
from app.services.search.mock_provider import MockSearchProvider


def test_blocked_metadata_offers_without_verified_images_are_excluded(monkeypatch):
    from app.core.config import get_settings
    from app.core.database import SessionLocal
    from app.models.search_session import SearchSession
    from app.services.search.base import SearchResult, SearchProviderError
    from app.services.extraction.product_image_resolver import ProductImageResolver
    from app.services.search.multi_provider import MultiSearchProvider
    from app.services.search.unified.external_sources import LiveProductSource
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
    monkeypatch.setattr(MultiSearchProvider, '__init__', lambda self, **kwargs: setattr(self, 'providers', [Provider()]))
    monkeypatch.setattr(LiveProductSource, 'is_available', lambda self, db: True)
    monkeypatch.setattr(ProductImageResolver, '_fetch_html', blocked)
    with TestClient(app) as client:
        analyzed = client.post(
            '/api/requirements/analyze',
            json={'raw_query': 'Điện thoại 10 triệu chụp ảnh'},
        )
        assert analyzed.status_code == 200, analyzed.text
        session_id = analyzed.json()['session_id']
        with SessionLocal() as db:
            session = db.get(SearchSession, session_id)
            session.requirement.category = 'điện thoại'
            session.requirement.budget_max = 10000000
            db.commit()
        response = client.post('/api/search', json={'session_id': session_id})
        assert response.status_code == 200
        items = response.json()['recommendations']
        assert items == []
        assert response.json()['total_recommended'] == 0
        assert client.get('/api/search/' + session_id).json()['recommendations'] == []
        state['fail'] = True
        failed = client.post('/api/search', json={'session_id': session_id})
        assert failed.status_code == 200
        loaded = client.get('/api/search/' + session_id).json()
        assert loaded['recommendations'] == []


def test_gemini_429_still_analyzes_tv_and_executes_search(monkeypatch):
    from app.services.search.multi_provider import MultiSearchProvider
    from app.services.search.unified.external_sources import LiveProductSource
    class QuotaFailure:
        async def analyze_requirement(self, query):
            raise RuntimeError('Gemini 429 RESOURCE_EXHAUSTED')
    monkeypatch.setattr(requirement_analyzer, 'get_llm_client',
                        lambda: FallbackLLMClient(QuotaFailure(), MockLLMClient()))
    calls = []
    async def provider(self, query, max_results):
        calls.append(query)
        return []
    class Provider:
        search = provider
    monkeypatch.setattr(MultiSearchProvider, '__init__', lambda self, **kwargs: setattr(self, 'providers', [Provider()]))
    monkeypatch.setattr(LiveProductSource, 'is_available', lambda self, db: True)
    with TestClient(app) as client:
        analysis = client.post('/api/requirements/analyze', json={'raw_query': 'Tôi cần TV khoảng 10 triệu để xem phim.'})
        assert analysis.status_code == 200
        data = analysis.json()
        assert data['needs_clarification'] is False
        assert data['requirement']['purpose'] == ['xem phim']
        assert data['requirement']['budget_max'] == 10000000
        response = client.post('/api/search', json={'session_id': data['session_id']})
        assert response.status_code == 200 and calls
