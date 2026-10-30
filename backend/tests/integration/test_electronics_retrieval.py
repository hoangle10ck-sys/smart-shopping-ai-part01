import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings
from app.services.llm.client import MockLLMClient
from app.services.llm import requirement_analyzer
from app.services.search.base import SearchResult
from app.services.search.multi_provider import MultiSearchProvider
from app.services.search.unified.external_sources import LiveProductSource
from app.services.extraction.product_image_resolver import ProductImageResolver
from tests.fixtures.sales_pages import sales_page


@pytest.mark.parametrize('category,query,name,model,url,merchant,price,variations',[
    ('tivi','Tôi cần TV khoảng 10 triệu để xem phim.','Smart Tivi Sony KD-50X80J','Sony KD-50X80J',
     'https://mediamart.vn/tivi/smart-tivi-sony-kd50x80j','MediaMart',9990000,False),
    ('điện thoại','Điện thoại khoảng 10 triệu chụp ảnh camera tốt pin lâu','Samsung Galaxy A56 8GB 128GB',
     'Samsung Galaxy A56 8GB 128GB','https://new-merchant.test/samsung-a56','New Merchant',8990000,False),
    ('điện thoại','Điện thoại khoảng 10 triệu chụp ảnh camera tốt pin lâu','Samsung Galaxy A56',
     'Samsung Galaxy A56','https://variant-merchant.test/samsung-a56','Variant Merchant',9690000,True)])
def test_electronics_exact_discovery_excludes_products_without_verified_images(
        monkeypatch,category,query,name,model,url,merchant,price,variations):
    settings=get_settings()
    for key,value in {'demo_mode':False,'cache_ttl_seconds':0,'openai_api_key':'','gemini_api_key':''}.items():
        monkeypatch.setattr(settings,key,value)
    monkeypatch.setattr(requirement_analyzer,'get_llm_client',MockLLMClient)
    calls=[]
    class Provider:
        async def search(self,q,max_results):
            calls.append(q)
            if f'"{model}"' in q:
                return [SearchResult(title=name,url=url,content=f'{name}. Mua ngay tại {merchant}.')]
            return [SearchResult(title='Gợi ý sản phẩm theo nhu cầu',url='https://guide.test/blog/buying-guide',
                content=f'{model} giá bán tham khảo. Thông tin lựa chọn sản phẩm.')]
    async def fetch(self,address):
        if address!=url:return address,'<meta property="og:type" content="article"><h1>Buying guide</h1>'
        markup=sales_page(name=name,price=price,offers={'@type':'Offer','price':price,'priceCurrency':'VND',
            'seller':{'name':merchant},'availability':'https://schema.org/InStock'})
        if variations:
            from html import escape
            rows=[{'attributes':{'memory':'12gb-256gb'},'display_price':price,'is_purchasable':True,
                   'variation_is_active':True,'is_in_stock':True}]
            markup+=f'<form class="variations_form cart" data-product_id="10" action="{url}" data-product_variations="{escape(json.dumps(rows),quote=True)}"></form>'
        return address,markup+'<script type="application/ld+json">'+json.dumps({'@type':'BreadcrumbList',
            'itemListElement':[{'name':category,'position':1},{'name':name,'position':2}]})+'</script>'
    monkeypatch.setattr(MultiSearchProvider,'__init__',lambda self, **kwargs:setattr(self,'providers',[Provider()]))
    monkeypatch.setattr(LiveProductSource,'is_available',lambda self,db:True)
    monkeypatch.setattr(ProductImageResolver,'_fetch_html',fetch)
    with TestClient(app) as client:
        analysis=client.post('/api/requirements/analyze',json={'raw_query':query}).json()
        response=client.post('/api/search',json={'session_id':analysis['session_id']})
        assert response.status_code==200,response.text
        items=response.json()['recommendations']
        assert items == []
        assert response.json()['total_recommended'] == 0
        if category=='điện thoại':
            assert len(calls)>4  # unknown did not stop discovery early
        assert any(f'"{model}"' in q for q in calls)
        assert client.get('/api/search/'+analysis['session_id']).json()['recommendations']==items
