import json
import pytest
from app.services.extraction.product_page_validator import inspect_page, PageParser
from app.services.extraction.category_evidence import category_evidence
from app.services.filter.hard_filter import category_matches
from tests.fixtures.sales_pages import sales_page


def crumbs(names):
    return '<script type="application/ld+json">'+json.dumps({'@type':'BreadcrumbList','itemListElement':[
        {'@type':'ListItem','position':i+1,'item':{'name':name}} for i,name in enumerate(names)]})+'</script>'


def test_missing_schema_category_uses_breadcrumb_and_records_provenance():
    proof=inspect_page('https://shop.test/samsung-galaxy-s24.html',
        sales_page(name='Samsung Galaxy S24')+crumbs(['Trang chủ','Điện thoại','Samsung','Samsung Galaxy S24']))
    assert proof['product_page_valid'] and proof['category']=='điện thoại'
    assert proof['category_evidence']['source']=='breadcrumb'
    assert not proof['category_evidence']['conflict']


@pytest.mark.parametrize('path,category',[
    ('dien-thoai-samsung-a56','điện thoại'),('smartphone/samsung-a56','điện thoại'),
    ('smart-tivi-sony-x80j','tivi'),('tivi-samsung-q80','tivi')])
def test_verified_direct_path_is_category_evidence(path,category):
    proof=inspect_page('https://shop.test/'+path,sales_page(name='Example X80'))
    assert proof['product_page_valid'] and proof['category']==category
    assert proof['category_evidence']['source']=='verified_url_path'


def test_accessory_breadcrumb_does_not_promote_phone_parent():
    proof=inspect_page('https://shop.test/clear-case-x24',sales_page(name='Ốp lưng Samsung X24')+
                       crumbs(['Điện thoại','Phụ kiện','Ốp lưng']))
    assert proof['category']=='ốp lưng'
    assert not category_matches('điện thoại',proof['category'])


def test_accessory_url_does_not_promote_phone_breadcrumb():
    proof=inspect_page('https://shop.test/products/op-lung-samsung-a56',
                      sales_page(name='Samsung A56')+crumbs(['Điện thoại']))
    assert not proof['product_page_valid'] and proof['category_evidence']['conflict']


def test_schema_and_breadcrumb_conflict_is_not_overridden():
    proof=inspect_page('https://shop.test/samsung-a56',sales_page(name='Samsung A56',category='phụ kiện')+
                      crumbs(['Điện thoại']))
    assert not proof['product_page_valid'] and proof['category_evidence']['category'] is None
    assert proof['category_evidence']['conflict']


@pytest.mark.parametrize('alias',['TV','Tivi','Smart TV','Smart Tivi','Television'])
def test_tv_family_is_normalized_in_evidence_and_filter(alias):
    proof=inspect_page('https://shop.test/sony-x80j',sales_page(name='Sony X80J',category=alias))
    assert proof['category']=='tivi'
    assert category_matches(alias,'tivi') and category_matches('tivi',alias)


@pytest.mark.parametrize('name',['Giá treo TV K19','Remote tivi Sony X80','Kệ TV gỗ X20','Chân đế tivi X20','Phụ kiện TV X80'])
def test_tv_accessories_never_satisfy_main_tv(name):
    proof=inspect_page('https://shop.test/tivi/accessory-x80',sales_page(name=name))
    assert not category_matches('tivi',proof.get('category'))


def test_unverified_page_and_merchant_domain_do_not_supply_category():
    parser=PageParser();parser.feed('<h1>Samsung A56</h1>'+crumbs(['Điện thoại']))
    assert category_evidence(parser,None,'https://shop.test/dien-thoai-a56',verified=False)['category'] is None
    proof=inspect_page('https://dien-thoai.test/samsung-a56',sales_page(name='Samsung A56'))
    assert proof['category'] is None


def test_html_breadcrumb_retains_deep_accessory_taxonomy():
    markup='<nav aria-label="breadcrumb"><a>Điện thoại</a><span>Phụ kiện</span><span>Ốp lưng</span></nav>'
    proof=inspect_page('https://shop.test/case-a56',sales_page(name='Ốp lưng Samsung A56')+markup)
    assert proof['category']=='ốp lưng' and proof['category_evidence']['source']=='breadcrumb'


VARIANT_URL='https://merchant.test/samsung-a56'


def phone_variants(*, related=False, accessory=False, conflict=False):
    from html import escape
    rows=[{'attributes':{'memory':memory},'display_price':price,'is_purchasable':True,
           'variation_is_active':True,'is_in_stock':True} for memory,price in
          [('8gb-128gb',7880000),('8gb-256gb',8990000),('12gb-256gb',9690000)]]
    if accessory:
        rows.append({**rows[0],'attributes':{'type':'Ốp lưng Samsung A56'},'display_price':250000})
    action='https://merchant.test/op-lung-a56' if related else VARIANT_URL
    form=f'<form class="variations_form cart" data-product_id="10" action="{action}" data-product_variations="{escape(json.dumps(rows),quote=True)}"></form>'
    return sales_page(name='Samsung Galaxy A56',**({'category':'phụ kiện'} if conflict else {}),
                      offers={'@type':'AggregateOffer','lowPrice':7880000,'highPrice':9690000,'priceCurrency':'VND'})+form+crumbs(['Trang chủ','Điện thoại','Samsung'])


def test_all_main_phone_variants_inherit_verified_breadcrumb_with_own_prices():
    from app.services.extraction.dealer_offers import concrete_proofs
    offers=concrete_proofs(inspect_page(VARIANT_URL,phone_variants()))
    assert len(offers)==3
    assert [p['price'] for p in offers]==[7880000,8990000,9690000]
    assert all(p['category']=='điện thoại' and p['category_evidence']['source']=='breadcrumb'
               and p['availability']=='in_stock' and p['image_url'] is None for p in offers)


def test_related_accessory_form_cannot_inherit_parent_phone_category():
    from app.services.extraction.dealer_offers import concrete_proofs
    assert concrete_proofs(inspect_page(VARIANT_URL,phone_variants(related=True)))==[]


def test_accessory_variant_type_is_rejected_without_losing_valid_phone_variants():
    from app.services.extraction.dealer_offers import concrete_proofs
    proof=inspect_page(VARIANT_URL,phone_variants(accessory=True))
    assert len(concrete_proofs(proof))==3
    assert len(proof['rejected_variants'])==1
    assert proof['rejected_variants'][0]['category_evidence']['conflict']


def test_variant_schema_breadcrumb_conflict_remains_unverified():
    from app.services.extraction.dealer_offers import concrete_proofs
    proof=inspect_page(VARIANT_URL,phone_variants(conflict=True))
    assert concrete_proofs(proof)==[] and proof['category_evidence']['conflict']


@pytest.mark.parametrize('subtype',['Xe ga','Xe số'])
def test_existing_vehicle_taxonomy_normalization_agrees_with_html_breadcrumb(subtype):
    from html import escape
    from app.services.extraction.dealer_offers import concrete_proofs
    url='https://dealer.test/xe-may/acme-orbit-125'
    rows=[{'attributes':{'version':'Standard'},'display_price':31900000,
           'is_purchasable':True,'variation_is_active':True,'is_in_stock':True}]
    form=f'<form class="variations_form cart" data-product_id="10" action="{url}" data-product_variations="{escape(json.dumps(rows),quote=True)}"></form>'
    markup=sales_page(name='Acme Orbit 125',category='Xe máy &gt; '+subtype)+form
    markup+=f'<nav aria-label="breadcrumb"><a>Trang chủ</a><a>Xe máy</a><a>{subtype}</a></nav>'
    offers=concrete_proofs(inspect_page(url,markup))
    assert len(offers)==1 and offers[0]['category']=='xe máy'
    assert offers[0]['price']==31900000 and offers[0]['category_evidence']['source']=='product_schema'
    assert not offers[0]['category_evidence']['conflict']
    assert offers[0]['category_evidence']['observations']['json_ld_category']=='Xe máy &gt; '+subtype
