from fastapi.testclient import TestClient
from datetime import datetime, timezone
from sqlalchemy import select
from app.main import app
from app.core.config import get_settings
from app.services.llm import requirement_analyzer
from app.services.llm.client import MockLLMClient


def test_flexible_budget_persists_snapshot_and_survives_failed_rerun(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings,'demo_mode',False)
    monkeypatch.setattr(settings,'openai_api_key','')
    monkeypatch.setattr(settings,'gemini_api_key','')
    monkeypatch.setattr(settings,'cache_ttl_seconds',0)
    monkeypatch.setattr(requirement_analyzer,'get_llm_client',MockLLMClient)
    state = {'fail':False,'price':34_000_000}
    class Provider:
        async def search(self,query,max_results):
            if state['fail']: raise SearchProviderError('timeout',kind='timeout')
            return [SearchResult(title='Xe máy Honda Example X1',url='https://shop.vn/honda-example-x1',
                content='Xe máy Honda Example X1 mua ngay giá bán 34.000.000 VND')]
    async def fetch(self,url):
        return url,sales_page(name='Xe máy Honda Example X1',price=state['price'],brand='Honda',model='X1',category='xe máy')
    async def no_image(self,url): return False
    from app.models.product import Product
    from app.models.product_offer import ProductOffer
    from app.models.source import Source
    from app.services.search.unified.base import SourceOutcome
    from app.services.search.unified.catalog_source import DatabaseCatalogSource

    original_catalog_search = DatabaseCatalogSource.search
    def catalog_search(self, *, db, session_id, requirement):
        product = db.scalar(select(Product).where(Product.model == 'X1'))
        if product is None:
            source = Source(url='https://snapshot-shop.test/motorbike/x1', domain='snapshot-shop.test',
                title='Synthetic budget test fixture', reliability_score=80)
            db.add(source); db.flush()
            product = Product(name='Xe máy Honda Example X1', category='xe máy', brand='Honda', model='X1',
                image_url='https://snapshot-shop.test/images/honda-example-x1.jpg',
                rating=4.5, review_count=120, specifications={'engine': '125cc'})
            db.add(product); db.flush()
            db.add(ProductOffer(product_id=product.id, merchant='Snapshot Shop', price=state['price'],
                currency='VND', availability='in_stock', source_id=source.id, product_url=source.url,
                last_checked_at=datetime.now(timezone.utc)))
        else:
            product.offers[0].price = state['price']
            product.offers[0].last_checked_at = datetime.now(timezone.utc)
        db.flush()
        return original_catalog_search(self, db=db, session_id=session_id, requirement=requirement)
    monkeypatch.setattr(DatabaseCatalogSource, 'search', catalog_search)

    async def live_search(self, **kwargs):
        if state['fail']:
            return SourceOutcome(source_name=self.name, error='TimeoutError', warnings=['Test source timeout.'])
        return SourceOutcome(source_name=self.name)
    monkeypatch.setattr('app.services.search.unified.orchestrator.LiveProductSource.is_available', lambda self, db: True)
    monkeypatch.setattr('app.services.search.unified.orchestrator.LiveProductSource.search', live_search)
    with TestClient(app) as client:
        analysis=client.post('/api/requirements/analyze',json={'raw_query':'Tôi cần xe máy khoảng 33 triệu để đi học.'})
        assert analysis.status_code==200
        session=analysis.json()['session_id']
        result=client.post('/api/search',json={'session_id':session})
        assert result.status_code==200
        body=result.json()
        assert body['requirement']['budget_mode']=='FLEXIBLE_TARGET'
        assert body['requirement']['preferred_max']==35_000_000
        assert len(body['recommendations'])==1
        assert body['recommendations'][0]['price']==34_000_000
        assert body['recommendations'][0]['image_evidence']['status'] == 'VERIFIED'
        old=client.get('/api/search/'+session).json()
        assert old['requirement']==body['requirement']
        # Another session updates the same offer; old snapshot remains unchanged.
        other=client.post('/api/requirements/analyze',json={'raw_query':'Xe máy tối đa 40 triệu đi học'}).json()
        state['price']=36_000_000
        assert client.post('/api/search',json={'session_id':other['session_id']}).status_code==200
        stored=client.get('/api/search/'+session).json()
        assert stored['recommendations']==body['recommendations']
        assert stored['requirement']==body['requirement']
        state['fail']=True
        assert client.post('/api/search',json={'session_id':session}).status_code==200
        stored=client.get('/api/search/'+session).json()
        assert stored['status']=='COMPLETED' and stored['warnings']
        assert stored['recommendations']==[]
        assert stored['requirement']==body['requirement']


def test_clarification_replaces_budget_metadata_and_legacy_models_remain_hard_max():
    from app.core.database import SessionLocal
    from app.models.requirement import Requirement
    from app.models.search_session import SearchSession
    from app.services.recommendation.recommendation_service import requirement_to_schema
    with TestClient(app) as client:
        initial=client.post('/api/requirements/analyze',json={'raw_query':'xe máy khoảng 33 triệu'}).json()
        response=client.post('/api/requirements/clarify',json={'session_id':initial['session_id'],'answer':'đi học'})
        assert response.status_code==200
        assert response.json()['requirement']['budget_mode']=='FLEXIBLE_TARGET'
        with SessionLocal() as db:
            current=db.get(SearchSession,initial['session_id']).requirement
            assert requirement_to_schema(current).preferred_max==35_000_000
            old=SearchSession(raw_query='xe máy khoảng 33 triệu')
            db.add(old);db.flush()
            legacy=Requirement(session_id=old.id,category='xe máy',budget_max=33_000_000)
            db.add(legacy);db.commit();db.refresh(legacy)
            parsed=requirement_to_schema(legacy)
            assert parsed.budget_mode=='HARD_MAX' and parsed.preferred_max is None
