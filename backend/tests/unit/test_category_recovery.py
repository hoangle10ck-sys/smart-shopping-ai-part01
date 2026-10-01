"""Category safety before queries/fetch; deterministic offline recovery."""
import json
from pathlib import Path

import pytest

from app.schemas.requirement import RequirementData
from app.schemas.search import SearchSourceItem
from app.services.search.base import SearchResult
from tests.unit.test_oos_recovery import setup, source, proof, pending


@pytest.mark.parametrize('category,name,allowed', [
    ('điện thoại', 'Samsung Galaxy Tab S10 Ultra', False),
    ('điện thoại', 'Apple iPad Pro M4', False),
    ('điện thoại', 'Lenovo Tablet P12', False),
    ('điện thoại', 'Xiaomi Redmi Pad Pro 12', False),
    ('máy tính bảng', 'Samsung Galaxy Tab S10 Ultra', True),
    ('tablet', 'Samsung Galaxy Tab S10 Ultra', True),
    ('điện thoại', 'Samsung Galaxy S25 Ultra', True),
    ('laptop', 'Apple iPhone 16 Pro', False),
    ('tai nghe', 'Apple MacBook Pro M4', False),
    ('tivi', 'Samsung Galaxy S25 Ultra', False),
    ('laptop', 'Dell UnknownBook Z12', True),
])
def test_hint_category_gate_and_query_boundary(category, name, allowed):
    r = setup(); r.sources.clear(); r.requirement = RequirementData(category=category)
    s = SearchSourceItem(url='https://shop.test/products/item-12', title=name, content='',
        page_validation={'discovery': [dict(name=name, brand=name.split()[0], price_type='DISCOVERY_ONLY')]})
    r.sources[s.url] = s
    hints = r.model_hints()
    assert bool(hints) is allowed
    query = r.model_query(name)
    if allowed: assert name in query
    else:
        assert name not in query
        assert category in query


def test_related_snippet_and_discovery_cannot_contaminate_phone_queries():
    r = setup(); r.sources.clear()
    s = source(56); s.content = 'Samsung Galaxy Tab S10 Ultra 5G\nSamsung Galaxy S25 Ultra'
    s.page_validation = {'discovery': [dict(name='Samsung Galaxy Tab S9 FE WIFI 6GB 128GB', brand='Samsung'),
                                     dict(name='Samsung Galaxy A57', brand='Samsung')]}
    r.sources[s.url] = s
    hints = r.model_hints()
    assert 'Samsung Galaxy S25 Ultra' in hints and 'Samsung Galaxy A57' in hints
    assert all('Tab' not in h for h in hints)
    assert 'Tab' not in r.continuation_query('điện thoại', False)


def test_related_child_preserves_same_category_only():
    r = setup(); parent = source(); r.source_queries[parent.url] = 'fixture'
    parent.page_validation = {'child_products': [
        dict(name='Samsung Galaxy Tab S10 Ultra', url='https://shop.test/products/galaxy-tab-s10'),
        dict(name='Samsung Galaxy A57', url='https://shop.test/products/galaxy-a57')]}
    r.enqueue_children(parent)
    assert list(r.pending) == ['https://shop.test/products/galaxy-a57']


@pytest.mark.parametrize('origin', ['title', 'discovery', 'proof'])
def test_generic_model_retains_its_own_category_evidence(origin):
    r = setup(); r.sources.clear()
    s = source(56); s.title = 'Catalog'; s.content = 'Dell Z12\nSamsung Galaxy S25 Ultra'
    if origin == 'title': s.title = 'Máy tính bảng Dell Z12'
    if origin == 'discovery':
        s.page_validation = {'discovery': [dict(name='Dell Z12', brand='Dell', category='tablet')]}
    if origin == 'proof':
        s.page_validation = dict(product_page_valid=True, name='Dell Z12', category='máy tính bảng', price=10000000)
    r.sources[s.url] = s
    assert 'Dell Z12' not in r.model_hints()
    assert 'Samsung Galaxy S25 Ultra' in r.model_hints()
    assert 'Dell Z12' not in r.model_query('Dell Z12')


@pytest.mark.asyncio
@pytest.mark.parametrize('reason', ['category', 'availability', 'budget', 'brand', 'exclusion'])
async def test_all_hard_rejected_still_recover_phone_and_never_retry_rejected(reason):
    r = setup(); r.sources.clear()
    old = source(50); old.page_validation = proof(old)
    if reason == 'category': old.page_validation['category'] = 'máy tính bảng'
    if reason == 'availability': old.page_validation['availability'] = 'out_of_stock'
    if reason == 'budget': old.page_validation['price'] = 20000000
    if reason == 'brand': r.requirement.brands = ['Samsung']; old.page_validation['brand'] = 'Other'
    if reason == 'exclusion': r.requirement.excluded_requirements = ['A50']
    r.sources[old.url] = old
    bad = SearchSourceItem(url='https://other.test/products/samsung-galaxy-tab-s10',
                          title='Samsung Galaxy Tab S10 Ultra', content='')
    pending(r, bad); good = source(56); pending(r, good)
    assert r.satisfaction()['eligible_offers'] == 0 and r.recovery_needed()
    await r.recover_direct()
    assert r.resolver.calls == [good.url]
    assert r.eligible(good.page_validation) and not r.eligible(old.page_validation)


@pytest.mark.asyncio
async def test_low_value_product_work_cannot_exhaust_product_reserve():
    r = setup(); r.max_cap = r.candidate_cap = 4
    # Two old OOS attempts and room for exactly two more product attempts.
    generic = SearchResult(url='https://other.test/offers/unidentified', title='Store deals', content='')
    class Provider:
        async def search(self, query, limit): return [generic]
    r.provider = Provider()
    await r.pass_queries('fixture', ['store'])
    assert not r.resolver.calls and len(r.product_attempts) == 2
    good = source(56); pending(r, good)
    await r.recover_direct()
    assert r.resolver.calls == [good.url] and len(r.product_attempts) == 3


@pytest.mark.asyncio
async def test_wrong_category_search_title_does_not_consume_product_budget():
    r = setup(); r.sources.clear()
    class Provider:
        async def search(self, query, limit):
            return [SearchResult(url='https://shop.test/products/samsung-galaxy-tab-s10',
                                 title='Samsung Galaxy Tab S10 Ultra', content='')]
    r.provider = Provider()
    await r.pass_queries('fixture', ['phones'])
    assert not r.resolver.calls and not r.model_hints() and not r.recovery_urls


def test_recovery_prioritizes_category_evidence_before_budget_and_unknown():
    r = setup()
    phone = source(56)
    unknown = SearchSourceItem(url='https://other.test/products/dell-z12', title='Dell Z12 giá 10 triệu', content='')
    assert r.recovery_priority(phone) < r.recovery_priority(unknown)


def test_archived_contamination_provenance_and_safe_hints():
    data = json.loads((Path(__file__).parents[1]/'fixtures/live_category_ab719401.json').read_text(encoding='utf-8'))
    row = next(x for x in data['observations'] if x['url']=='https://www.duchuymobile.com/oppo-find-x8s-plus')
    assert 'Samsung Galaxy Tab S10 Ultra' in row['content'] and not row['proof']['discovery']
    r = setup(); r.sources.clear()
    r.sources[row['url']] = SearchSourceItem(url=row['url'], title=row['title'], content=row['content'],
                                           page_validation=row['proof'])
    assert all('Tab' not in h for h in r.model_hints())
    assert any('Find X8' in h for h in r.model_hints())


@pytest.mark.asyncio
async def test_archived_policy_no_tablet_queries_or_invented_offers(monkeypatch):
    import socket
    from scripts.replay_category_recovery import replay
    def forbidden(*args, **kwargs): raise AssertionError('No network in archived replay')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    data = json.loads((Path(__file__).parents[1]/'fixtures/live_category_ab719401.json').read_text(encoding='utf-8'))
    result = await replay(data)
    assert not any('Galaxy Tab' in q for q in result['queries'])
    assert result['product_attempts'] < 20 and result['page_attempts'] < 23
    assert result['eligible'] == result['known_unresolved_eligible'] == 0
    url = 'https://www.duchuymobile.com/nothing-phone-4a'
    assert url in result['attempted_urls'] and url in result['missing_page_responses']
    assert result['known_unresolved_opportunity']['attempted_urls'] == [url]


def test_phone_family_feature_is_not_misread_as_camera_product():
    r = setup()
    s = source(56); s.title += ' camera 50MP pin tốt'
    assert r.recovery_candidate(s)
