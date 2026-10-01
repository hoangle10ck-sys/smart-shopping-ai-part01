"""Real validation/filter/ranking/snapshot pipeline; only local provider/HTML."""
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.core.config import get_settings
from app.services.search import search_service
from app.services.search.base import SearchResult
from app.services.search.progressive_retrieval import ProgressiveRetriever
from app.services.extraction.product_image_resolver import ProductImageResolver
from tests.fixtures.sales_pages import sales_page


@pytest.mark.parametrize('recovered_stock', ['InStock', 'OutOfStock', 'unknown'])
@pytest.mark.parametrize('rejected_by', ['availability', 'category'])
def test_oos_recovery_preserves_filter_score_image_null_and_get(monkeypatch, recovered_stock, rejected_by):
    settings = get_settings()
    for k, v in dict(demo_mode=False, openai_api_key='', gemini_api_key='',
                     live_search_max_queries=1, cache_ttl_seconds=0).items():
        monkeypatch.setattr(settings, k, v)
    urls = [f'https://shop.test/products/samsung-galaxy-a{n}' for n in (50, 51, 56)]
    class Provider:
        async def search(self, query, max_results):
            return [SearchResult(url=url, title=f'Samsung Galaxy A{n}', content='')
                    for n, url in zip((50, 51, 56), urls)]
    async def fetch(self, url):
        n = url.rsplit('a', 1)[-1]
        category = 'máy tính bảng' if rejected_by == 'category' and url != urls[-1] else 'điện thoại'
        html = sales_page(name=f'Samsung Galaxy A{n}', brand='Samsung', category=category, price=10000000)
        stock = ('OutOfStock' if rejected_by == 'availability' else 'InStock') if url != urls[-1] else recovered_stock
        html = html.replace('InStock', stock)
        return url, html
    original = ProgressiveRetriever.verify
    async def exhausted(self, source, *, recovery=False):
        if source.url == urls[-1] and not recovery:
            self.domain_work.setdefault('shop.test', dict(active=0, spent=0., since=0., attempts=0,
                failures=0, direct_failures=0, skipped=0))['spent'] = self.domain_budget
        return await original(self, source, recovery=recovery)
    monkeypatch.setattr(search_service, 'get_search_provider', Provider)
    monkeypatch.setattr(ProductImageResolver, '_fetch_html', fetch)
    monkeypatch.setattr(ProgressiveRetriever, 'verify', exhausted)
    with TestClient(app) as client:
        analysis = client.post('/api/requirements/analyze', json={'raw_query':'Điện thoại khoảng 10 triệu để học online'})
        sid = analysis.json()['session_id']
        response = client.post('/api/search', json={'session_id':sid})
        assert response.status_code == 200, response.text
        body = response.json()
        count = 0 if recovered_stock == 'OutOfStock' else 1
        assert body['total_found'] == 3 and body['total_filtered'] == body['total_recommended'] == count
        assert len(body['recommendations']) == count
        assert sum(d['rejection_stage'] == rejected_by for d in body['filter_decisions']) == (3 - count if rejected_by == 'availability' else 2)
        if rejected_by == 'category':
            assert sum(d['rejection_stage'] == 'availability' for d in body['filter_decisions']) == 1 - count
        if count:
            rec = body['recommendations'][0]
            assert rec['name'] == 'Samsung Galaxy A56' and rec['price'] == 10000000
            assert rec['image_url'] is None and rec['product_page_valid']
            assert rec['availability'] == ('in_stock' if recovered_stock == 'InStock' else 'unknown')
            score = rec['score']
            assert score['final_score'] == round(sum(score[k+'_score'] * w for k,w in
                [('budget',.25),('requirement',.30),('purpose',.20),('rating',.10),('review',.05),('source',.10)]),2)
        else:
            assert body['retrieval_diagnostics'][-1]['performance']['diagnostics']['stop_reason'] == 'recovery_opportunities_exhausted'
        recovery = body['retrieval_diagnostics'][-1]['performance']['diagnostics']['direct_recovery']
        assert recovery['attempted_urls'] == [urls[-1]]
        saved = client.get('/api/search/'+sid).json()
        assert saved['recommendations'] == body['recommendations']
        assert saved['retrieval_diagnostics'][-1]['performance']['diagnostics']['direct_recovery'] == recovery
