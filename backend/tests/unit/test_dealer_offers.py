import html
import json

import pytest

from app.services.extraction.product_page_validator import inspect_page
from app.services.extraction.dealer_offers import concrete_proofs

URL='https://dealer.test/xe-may/acme-orbit-125'


def dealer_page(rows=None, *, action=URL, table='', buy='Đặt xe', article=False):
    node={'@type':'Product','name':'Acme Orbit 125','brand':'Acme','model':'Orbit 125','category':'xe máy',
          'offers':{'@type':'AggregateOffer','lowPrice':31900000,'highPrice':35200000,'priceCurrency':'VND',
                    'seller':{'name':'Example Dealer'}}}
    if article: node={'@type':'Article','mainEntity':node}
    form=''
    if rows is not None:
        form=f'<form class="variations_form cart" data-product_id="10" action="{action}" data-product_variations="{html.escape(json.dumps(rows),quote=True)}"></form>'
    return ('<title>Acme Orbit 125</title><h1>Acme Orbit 125</h1>'
            '<script type="application/ld+json">'+json.dumps(node)+'</script>'+form+table+f'<a>{buy}</a>')


def variation(version,price,**changes):
    return {**dict(attributes={'version':version},display_price=price,is_purchasable=True,
                   variation_is_active=True,is_in_stock=True,variation_id=price),**changes}


def test_each_variant_has_own_price_and_base_model_has_no_price():
    result=inspect_page(URL,dealer_page([variation('Standard',31900000),variation('Special',33500000),variation('Premium',35200000)]))
    assert result['product_page_valid'] and result.get('price') is None
    offers=concrete_proofs(result)
    assert [(o['variant']['version'],o['price']) for o in offers]==[('Standard',31900000),('Special',33500000),('Premium',35200000)]
    assert all(o['price_type']=='CONCRETE' and o['merchant']=='Example Dealer' and o['product_url']==URL for o in offers)
    assert all(o['image_url'] is None for o in offers)
    checked=inspect_page(URL,dealer_page([variation('Special',33500000)]),'Acme Orbit 125 - Special')
    assert checked['price']==33500000 and checked['variant']=={'version':'Special'}


@pytest.mark.parametrize('changes',[{'is_purchasable':False},{'variation_is_active':False},
                                  {'attributes':{'version':''}},{'display_price':None}])
def test_invalid_variation_is_never_replaced_by_aggregate_minimum(changes):
    result=inspect_page(URL,dealer_page([variation('Standard',31900000,**changes)]))
    assert not result['product_page_valid'] and result.get('price') is None


def test_conflicting_prices_for_same_variant_are_rejected():
    result=inspect_page(URL,dealer_page([variation('Standard',31900000),variation('Standard',33500000)]))
    assert not result['product_page_valid']


def test_related_product_form_cannot_supply_main_product_price():
    result=inspect_page(URL,dealer_page([variation('Standard',31900000)],action='https://dealer.test/xe-may/other-999'))
    assert not result['product_page_valid']


@pytest.mark.parametrize('url,article',[(URL,True),('https://dealer.test/',False),
    ('https://dealer.test/category/xe-may',False),('https://dealer.test/news/acme-orbit-125',False)])
def test_nonsales_pages_cannot_promote_embedded_variations(url,article):
    assert not inspect_page(url,dealer_page([variation('Standard',31900000)],article=article))['product_page_valid']


def table(product='Acme Orbit 125', price='31.900.000'):
    return f'<table data-product="{product}"><tr><th>Phiên bản</th><th>Giá bán VND</th></tr><tr><td>Standard</td><td>{price}</td></tr></table>'


def test_explicit_variant_price_table_requires_purchase_action_but_not_cart():
    result=inspect_page(URL,dealer_page(table=table()))
    assert concrete_proofs(result)[0]['price']==31900000
    assert concrete_proofs(result)[0]['mapping_source']=='variant_price_table'
    assert not inspect_page(URL,dealer_page(table=table(),buy='Liên hệ'))['product_page_valid']


@pytest.mark.parametrize('table_html',[table(product='Other Bike 999'),table(price='31.000.000–33.000.000'),
                                    table(price='Liên hệ'),table().replace('VND','USD')])
def test_ambiguous_table_or_currency_does_not_create_offer(table_html):
    assert not inspect_page(URL,dealer_page(table=table_html))['product_page_valid']


def test_no_product_schema_dealer_page_uses_title_path_price_table_and_contact_purchase():
    markup='<title>Acme Orbit 125</title><h1>Acme Orbit 125</h1>'+table()+'<a>Liên hệ mua xe</a>'
    result=inspect_page(URL,markup)
    assert concrete_proofs(result)[0]['price']==31900000
    assert not inspect_page('https://dealer.test/other-999',markup)['product_page_valid']


def test_official_breadcrumb_and_suggested_price_remain_discovery_only():
    markup=('<title>Suzuki | Products</title><meta property="product:brand" content="Suzuki"><a class="breadcrumb-current">Orbit 125</a>'
        '<h2 class="suggested-price">33.500.000 VND</h2><select name="version"><option value="2">Special</option></select>')
    result=inspect_page('https://manufacturer.test/products/orbit-125',markup)
    assert not result['product_page_valid'] and result.get('price') is None
    hint=result['discovery'][0]
    assert (hint['brand'],hint['model'],hint['price_min'])==('Suzuki','Orbit 125',33500000)
    assert result['discovery'][1]['variant']=={'version':'Special'}


@pytest.mark.parametrize('name,path,expected',[('Giá treo Tivi 19-32 K19','/dien-thoai/gia-treo-tivi-k19','giá treo'),
    ('Smart Tivi Sony X80J','/dien-thoai/sony-x80j','tivi'),('Acme X125','/products/acme-x125',None)])
def test_category_is_from_verified_product_evidence_not_domain_or_conflicting_path(name,path,expected):
    from tests.fixtures.sales_pages import sales_page
    proof=inspect_page('https://dien-thoai.test'+path,sales_page(name=name,price=9990000))
    assert proof['product_page_valid'] and proof['category']==expected


def test_unverified_page_path_never_supplies_product_category():
    result=inspect_page('https://shop.test/dien-thoai/acme-x125','<h1>Acme X125</h1>')
    assert not result['product_page_valid'] and result.get('category') is None


def test_secondary_article_heading_does_not_pollute_main_variant_identity():
    markup=dealer_page([variation('Standard',31900000)])+'<h1>Other models and the latest marketing news</h1>'
    result=inspect_page(URL,markup)
    assert concrete_proofs(result)[0]['name']=='Acme Orbit 125 - Standard'


@pytest.mark.parametrize('entity,heading,accepted',[
    (URL+'#webpage','Acme Orbit 125',True),
    ('https://dealer.test/other#webpage','Acme Orbit 125',False),
    (URL+'#webpage','Acme Orbit 125 2025',False),
])
def test_schema_year_needs_explicit_main_page_binding_and_no_conflicting_year(entity,heading,accepted):
    from app.services.extraction.product_page_validator import main_product_identity
    product={'name':'Acme Orbit 125 2026 - New motorcycle', 'mainEntityOfPage':{'@id':entity}}
    assert main_product_identity(product,heading,URL) == accepted


def test_bound_schema_year_with_marketing_suffix_still_verifies_main_product_variations():
    markup=dealer_page([variation('Standard',31900000)])
    markup=markup.replace('"name": "Acme Orbit 125", "brand"',
        '"name": "Acme Orbit 125 2026 - New motorcycle", "mainEntityOfPage": {"@id": "'+URL+'#webpage"}, "brand"')
    assert concrete_proofs(inspect_page(URL,markup))[0]['price']==31900000


def test_same_commercial_version_and_price_combines_colors_without_duplicate_products():
    rows=[variation('Standard',31900000,attributes={'version':'Standard','attribute_pa_mau-sac':color}) for color in ('red','black')]
    offers=concrete_proofs(inspect_page(URL,dealer_page(rows)))
    assert len(offers)==1
    assert offers[0]['variant']=={'version':'Standard','color_options':'black / red'}
    assert offers[0]['name']=='Acme Orbit 125 - Standard'
    assert offers[0]['specifications']['variant']=='version=Standard'


def test_same_version_with_different_color_prices_remains_separate():
    rows=[variation('Standard',price,attributes={'version':'Standard','color':color}) for color,price in [('red',31900000),('black',33500000)]]
    offers=concrete_proofs(inspect_page(URL,dealer_page(rows)))
    assert len(offers)==2 and {x['price'] for x in offers}=={31900000,33500000}
    assert len({x['specifications']['variant'] for x in offers})==2


@pytest.mark.parametrize('stock,status,accepted',[(True,'in_stock',True),(False,'out_of_stock',False),(None,None,True)])
def test_variation_availability_is_observed_not_invented(stock,status,accepted):
    from app.services.search.progressive_retrieval import ProgressiveRetriever
    from app.schemas.requirement import RequirementData
    proof=concrete_proofs(inspect_page(URL,dealer_page([variation('Standard',31900000,is_in_stock=stock)])))[0]
    retriever=ProgressiveRetriever(None,None,None)
    retriever.requirement=RequirementData(category='xe máy',budget_max=33000000)
    assert proof['availability']==status
    assert retriever.eligible(proof)==accepted


def test_out_of_stock_color_does_not_hide_available_color_or_claim_both_available():
    rows=[variation('Standard',31900000,attributes={'version':'Standard','color':'red'},is_in_stock=False),
          variation('Standard',31900000,attributes={'version':'Standard','color':'black'})]
    offers=concrete_proofs(inspect_page(URL,dealer_page(rows)))
    assert len(offers)==1 and offers[0]['availability']=='in_stock'
    assert offers[0]['variant']['color_options']=='black'


@pytest.mark.parametrize('alt,expected',[('Acme Orbit 125 Standard',True),('Honda Vision Standard',False),('',False)])
def test_variation_image_requires_same_model_and_version_evidence(alt,expected):
    row=variation('Standard',31900000,image={'url':'https://dealer.test/images/photo.jpg','alt':alt})
    proof=concrete_proofs(inspect_page(URL,dealer_page([row])))[0]
    assert bool(proof['image_candidates'])==expected
    assert proof['image_url'] is None  # Network load is only after offer verification.


def test_multiple_model_price_table_cannot_be_misread_as_variants():
    markup='<table data-product="Acme Orbit 125"><tr><th>Model</th><th>Variant</th><th>Price VND</th></tr>'
    markup+='<tr><td>Different 999</td><td>Standard</td><td>31900000</td></tr></table>'
    assert not inspect_page(URL,dealer_page(table=markup))['product_page_valid']


@pytest.mark.parametrize('leaf,expected',[('Xe ga','xe máy'),('Xe số','xe máy'),('Phụ kiện','Xe máy &gt; Phụ kiện')])
def test_verified_motorcycle_taxonomy_normalizes_only_explicit_vehicle_subtypes(leaf,expected):
    markup=dealer_page([variation('Standard',31900000)])
    markup=markup.replace(json.dumps('xe máy'),json.dumps('Xe máy &gt; '+leaf))
    assert concrete_proofs(inspect_page(URL,markup))[0]['category']==expected


@pytest.mark.parametrize('suffix,accepted',[('trả góp 0%',True),('256GB',False),('2025 2026',False),('Pro',False)])
def test_bound_financing_text_and_fi_spacing_do_not_change_model_identity(suffix,accepted):
    from app.services.extraction.product_page_validator import main_product_identity
    url='https://dealer.test/xe-may/acme-orbit-125-fi'
    product={'name':'Acme Orbit 125FI - '+suffix,'mainEntityOfPage':{'@id':url+'#webpage'}}
    # Capacity/version changes and ambiguous multiple years remain conflicts.
    assert main_product_identity(product,'Acme Orbit 125FI',url)==accepted


def test_financing_suffix_without_page_binding_is_not_used_to_override_identity():
    from app.services.extraction.product_page_validator import main_product_identity
    assert not main_product_identity({'name':'Acme Orbit 125 - trả góp 0%'},'Acme Orbit 125',URL)
