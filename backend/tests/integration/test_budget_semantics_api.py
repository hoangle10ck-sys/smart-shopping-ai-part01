from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings
from app.services.llm import requirement_analyzer
from app.services.llm.client import MockLLMClient
from app.services.search import search_service
from app.services.search.base import SearchResult, SearchProviderError
from app.services.extraction.product_image_resolver import ProductImageResolver
from tests.fixtures.sales_pages import sales_page


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
    monkeypatch.setattr(search_service,'get_search_provider',Provider)
    monkeypatch.setattr(ProductImageResolver,'_fetch_html',fetch)
    monkeypatch.setattr(ProductImageResolver,'_image_loads',no_image)
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
        assert body['recommendations'][0]['image_url'] is None
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
        assert client.post('/api/search',json={'session_id':session}).status_code==503
        stored=client.get('/api/search/'+session).json()
        assert stored['status']=='FAILED' and stored['warnings']
        assert stored['recommendations']==body['recommendations']
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
