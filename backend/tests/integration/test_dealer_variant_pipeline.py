import html
import json
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings
from app.services.llm import requirement_analyzer
from app.services.llm.client import MockLLMClient
from app.services.search import search_service
from app.services.search.base import SearchResult
from app.services.extraction.product_image_resolver import ProductImageResolver


def test_variants_have_separate_prices_filters_and_historical_snapshots(monkeypatch):
    settings=get_settings()
    for key,value in {'demo_mode':False,'cache_ttl_seconds':0,'gemini_api_key':'','openai_api_key':''}.items():
        monkeypatch.setattr(settings,key,value)
    monkeypatch.setattr(requirement_analyzer,'get_llm_client',MockLLMClient)
    url='https://dealer.test/xe-may/acme-orbit-125'
    prices={'Standard':31900000,'Special':33500000,'Premium':35200000}
    class Provider:
        async def search(self,query,max_results):
            return [SearchResult(title='Acme Orbit 125',url=url,content='Xe máy Acme Orbit 125 đặt xe tại đại lý.')]
    async def fetch(self,address):
        product={'@type':'Product','name':'Acme Orbit 125','brand':'Acme','model':'Orbit 125','category':'xe máy',
                 'offers':{'@type':'AggregateOffer','lowPrice':1,'highPrice':99999999,'priceCurrency':'VND'}}
        variants=[dict(attributes={'version':version},display_price=price,is_purchasable=True,
                       variation_is_active=True,is_in_stock=True) for version,price in prices.items()]
        variants[0]['attributes']['color']='red'
        variants.append({**variants[0],'attributes':{'version':'Standard','color':'black'}})
        markup=('<title>Acme Orbit 125</title><h1>Acme Orbit 125</h1><a>Đặt xe</a>'
            '<script type="application/ld+json">'+json.dumps(product)+'</script>'
            '<form class="variations_form cart" data-product_id="1" action="'+url+'" data-product_variations="'+html.escape(json.dumps(variants),quote=True)+'"></form>')
        return address,markup
    monkeypatch.setattr(search_service,'get_search_provider',Provider)
    monkeypatch.setattr(ProductImageResolver,'_fetch_html',fetch)
    with TestClient(app) as client:
        def run(query):
            analyzed=client.post('/api/requirements/analyze',json={'raw_query':query})
            assert analyzed.status_code==200
            sid=analyzed.json()['session_id']
            response=client.post('/api/search',json={'session_id':sid})
            assert response.status_code==200,response.text
            return sid,response.json()
        sid,flex=run('Xe máy khoảng 33 triệu đi học')
        items=flex['recommendations']
        assert len(items)==3 and len({x['product_id'] for x in items})==3
        assert items[0]['price']==33500000
        assert {x['variant']['version']:x['price'] for x in items}==prices
        assert all(x['product_url']==url and x['price_type']=='CONCRETE' and x['image_url'] is None for x in items)
        _,hard=run('Xe máy tối đa 33 triệu đi học')
        assert [x['price'] for x in hard['recommendations']]==[31900000]
        assert sum(not d['accepted'] for d in hard['filter_decisions'])==2
        prices['Special']=34500000
        run('Xe máy từ 30 đến 36 triệu đi học')
        old=client.get('/api/search/'+sid).json()
        assert old['recommendations']==items
        history=client.get('/api/history/'+sid).json()['result']
        assert history['recommendations']==items
        assert history['requirement']['budget_mode']=='FLEXIBLE_TARGET'
        assert history['requirement']['preferred_max']==35000000
