"""Real pipeline with local HTML/HTTP fixtures and no paid provider calls."""
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.product import Product
from app.models.product_offer import ProductOffer
from app.models.requirement import Requirement
from app.models.search_query import SearchQuery
from app.models.search_session import SearchSession
from app.services.search.base import SearchResult
from app.services.search import search_service
from app.services.extraction.product_image_resolver import ProductImageResolver
from tests.fixtures.sales_pages import sales_page


@pytest.mark.parametrize('image_pattern', ['json_ld', 'lazy', 'srcset'])
def test_offer_identity_image_evidence_snapshot_and_detail(monkeypatch, image_pattern):
    settings = get_settings()
    monkeypatch.setattr(settings, 'demo_mode', False)
    monkeypatch.setattr(settings, 'openai_api_key', '')
    monkeypatch.setattr(settings, 'gemini_api_key', '')
    name = 'Laptop Example X15 16GB'
    urls = ['https://cellphones.com.vn/products/example-x15', 'https://shop.example/products/example-x15',
            'https://review.example/blog/example-x15', 'https://shop.example/',
            'https://shop.example/category/laptops']
    state = {'price': 15000000}
    class Provider:
        async def search(self, query, max_results):
            return [SearchResult(title=name, url=url,
                content=f'PRODUCT: {name} | CATEGORY: laptop | BRAND: Example | MODEL: X15 | PRICE: 1 VND | SPECS: ram=16GB') for url in reversed(urls)]
    async def fetch(self, url):
        image = '/x15.jpg' if url == urls[0] else '/other-shop.jpg'
        html = sales_page(name=name, price=state['price'] if url == urls[0] else 14000000,
                              image=image if image_pattern == 'json_ld' else None,
                              brand='Example', model='X15', additionalProperty=[{'name': 'ram', 'value': '16GB'}])
        if image_pattern == 'lazy': html += f'<img alt="{name}" src="/placeholder.png" data-original="{image}">'
        if image_pattern == 'srcset': html += f'<img alt="{name}" srcset="{image} 600w">'
        return url, html
    async def image_ok(self, url): return True
    monkeypatch.setattr(search_service, 'get_search_provider', Provider)
    monkeypatch.setattr(ProductImageResolver, '_fetch_html', fetch)
    monkeypatch.setattr(ProductImageResolver, '_image_loads', image_ok)
    def session():
        with SessionLocal() as db:
            s = SearchSession(raw_query='laptop 25 million')
            db.add(s); db.flush()
            db.add(Requirement(session_id=s.id, category='laptop', budget_max=25000000,
                               requirements=[{'name': 'ram', 'value': '16GB', 'priority': 5}]))
            db.add(SearchQuery(session_id=s.id, query='laptop', position=1))
            db.commit()
            return s.id
    with TestClient(app) as client:
        a = session()
        response = client.post('/api/search', json={'session_id': a})
        assert response.status_code == 200
        assert [source['result_type'] for source in response.json()['sources'][:2]] == ['DIRECT_PRODUCT', 'DIRECT_PRODUCT']
        items = response.json()['recommendations']
        assert len(items) == 1
        saved = deepcopy(items[0])
        assert saved['price'] == 15000000  # HTML Offer, never misleading snippet price=1.
        assert saved['product_url'] == urls[0]  # Verified trusted merchant outranks cheaper unknown shop.
        assert saved['image_url'] == 'https://cellphones.com.vn/x15.jpg'
        assert saved['merchant'] == 'Test Merchant'
        assert saved['product_page_valid'] is True
        assert saved['image_source'] == ('json_ld_product' if image_pattern == 'json_ld' else 'html_product_image')
        assert any(e['url'] == urls[2] for e in saved['evidence']['fields'])
        with SessionLocal() as db:
            offers = list(db.scalars(select(ProductOffer)))
            assert len(offers) == 2 and {o.product_url for o in offers} == set(urls[:2])
            assert len(list(db.scalars(select(Product)))) == 1
        state['price'] = 20000000
        b = session()
        assert client.post('/api/search', json={'session_id': b}).status_code == 200
        assert client.get(f'/api/search/{a}').json()['recommendations'] == items
        assert client.get(f'/api/history/{a}').json()['result']['recommendations'] == items
        detail = client.get(f"/api/products/{saved['product_id']}?session_id={a}")
        assert detail.status_code == 200
        body = detail.json()
        assert body['recommendation'] == saved
        by_url = {o['product_url']: o for o in body['offers']}
        assert by_url[urls[0]]['price'] == 20000000
        assert by_url[urls[1]]['image_url'] == 'https://shop.example/other-shop.jpg'


def test_dedup_keeps_storage_and_pro_variants_separate():
    from app.services.normalization.normalization_service import NormalizationService
    from app.schemas.search import RawProductCandidateData
    with SessionLocal() as db:
        service = NormalizationService()
        ids = []
        for name in ('iPhone 15 128GB', 'iPhone 15 Pro 128GB', 'iPhone 15 256GB'):
            item = service.persist_candidate(db=db, candidate=RawProductCandidateData(
                name=name, brand='Apple', model='iPhone 15', product_url='https://shop.example/products/' + name.replace(' ', '-')))
            ids.append(item.product_id)
        assert len(set(ids)) == 3
