"""Verified page -> evidence -> normalized/persisted candidate -> snapshot."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.product import Product
from app.models.raw_product_candidate import RawProductCandidate
from app.models.recommendation_snapshot import RecommendationSnapshot
from app.services.search import search_service
from app.services.search.base import SearchResult
from app.services.extraction.product_image_resolver import ProductImageResolver
from tests.fixtures.sales_pages import sales_page


@pytest.mark.parametrize('stock', ['InStock', 'OutOfStock'])
def test_redmi_category_and_separate_fetch_validation_timings_survive_get(monkeypatch,stock):
    settings=get_settings()
    for key,value in dict(demo_mode=False,openai_api_key='',gemini_api_key='',cache_ttl_seconds=0,
                          live_search_max_queries=2).items(): monkeypatch.setattr(settings,key,value)
    url='https://merchant.test/xiaomi-redmi-note-13-5g-8gb-128gb'
    name='Xiaomi Redmi Note 13 5G 8GB 128GB - Cũ Đẹp'
    html=sales_page(name=name,brand='Xiaomi',offers={'@type':'Offer','price':3690000,'priceCurrency':'VND',
        'availability':'https://schema.org/'+stock,'seller':{'name':'Fixture merchant'}})
    class Provider:
        async def search(self,q,limit):return [SearchResult(title=name,url=url,content='')]
    async def fetch(self,link):
        assert link==url
        return link,html
    monkeypatch.setattr(search_service,'get_search_provider',Provider)
    monkeypatch.setattr(ProductImageResolver,'_fetch_html',fetch)
    with TestClient(app) as client:
        analysis=client.post('/api/requirements/analyze',json={'raw_query':'Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu'}).json()
        response=client.post('/api/search',json={'session_id':analysis['session_id']})
        assert response.status_code==200,response.text
        data=response.json()
        assert data['total_found']==1 and data['candidates'][0]['category']=='điện thoại'
        if stock=='OutOfStock':
            assert data['total_recommended']==0 and data['filter_decisions'][0]['rejection_stage']=='availability'
        else: assert data['total_recommended']==1
        saved=client.get('/api/search/'+analysis['session_id']).json()
        assert saved['recommendations']==data['recommendations']
        perf=saved['retrieval_diagnostics'][-1]['performance']
        assert perf['timings']['page_fetch_ms']>0 and perf['timings']['verification_ms']>0
        assert perf['diagnostics']['page_attempts']==1 and perf['diagnostics']['provider_calls']==2
        assert perf['diagnostics']['round_count']==1 and perf['diagnostics']['stop_reason']=='query_budget'
    with SessionLocal() as db:
        product=db.scalar(select(Product))
        raw=db.scalar(select(RawProductCandidate)).payload
        assert product.category==raw['category']==raw['page_validation']['category_evidence']['category']=='điện thoại'
        assert db.get(RecommendationSnapshot,analysis['session_id']).payload['retrieval_diagnostics']
