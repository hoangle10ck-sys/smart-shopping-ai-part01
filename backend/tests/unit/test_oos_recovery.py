"""Offline reserve scheduling: no provider, DNS or real HTTP is used."""
import asyncio
import time

import pytest

from app.core.config import Settings
from app.schemas.requirement import RequirementData
from app.schemas.search import SearchSourceItem
from app.services.extraction.product_page_validator import inspect_page
from app.services.search.base import SearchResult
from app.services.search.progressive_retrieval import ProgressiveRetriever
from app.services.search.retrieval_diagnostics import source_plan
from tests.fixtures.sales_pages import sales_page


def source(n=56, domain='shop.test', prefix='products'):
    return SearchSourceItem(url=f'https://{domain}/{prefix}/samsung-galaxy-a{n}',
                           title=f'Samsung Galaxy A{n}', content='')    


def proof(s, stock='in_stock'):
    p = inspect_page(s.url, sales_page(name=s.title, category='điện thoại', brand='Samsung', price=10000000))
    p['availability'] = stock
    return p


def ledger(spent=6., failures=0, direct_failures=0):
    return dict(active=0, spent=spent, since=0., attempts=2, failures=failures,
                direct_failures=direct_failures, skipped=0)


class Pages:
    def __init__(self, stock='in_stock', hang=False):
        self.calls, self.active, self.stock, self.hang = [], set(), stock, hang

    async def inspect(self, url, **kwargs):
        self.calls.append(url)
        self.active.add(url)
        try:
            if self.hang: await asyncio.Event().wait()
            n = url.rsplit('a', 1)[-1]
            return proof(source(n), self.stock)
        finally:
            self.active.remove(url)


def setup(pages=None, *, target=1):
    r = ProgressiveRetriever(None, pages or Pages(), Settings(_env_file=None,
        live_search_target_products=target, live_search_max_queries=1))
    r.requirement = RequirementData(category='điện thoại', budget_max=10000000)
    r.deadline = time.monotonic() + 5
    for n in (50, 51):
        s = source(n); s.page_validation = proof(s, 'out_of_stock')
        r.sources[s.url] = s
        r.inspected_urls.add(s.url); r.product_attempts.add(s.url)
    return r


def pending(r, s):
    r.pending[s.url] = s
    r.plans[s.url] = source_plan(s)
    r.source_queries[s.url] = 'fixture'
    r.candidate_urls.add(s.url)


@pytest.mark.asyncio
@pytest.mark.parametrize('stock', ['in_stock', None])
async def test_two_oos_recover_unrequested_direct_and_preserve_unknown_stock(stock):
    pages = Pages(stock); r = setup(pages)
    s = source(); pending(r, s)
    r.domain_work['shop.test'] = ledger()
    await r.verify(s)  # The previous ordinary-domain path skips this URL.
    assert s.page_validation['rejection_code'] == 'resource_budget' and not pages.calls
    assert not r.enough()
    await r.recover_direct()
    assert pages.calls == [s.url] and r.summary()['valid_offers'] == 1 and r.enough()
    assert s.page_validation['availability'] == stock
    assert all(not r.eligible(v.page_validation) for u, v in r.sources.items() if u != s.url)
    await r.recover_direct()
    assert pages.calls == [s.url]  # No duplicate request after success.


@pytest.mark.asyncio
async def test_low_value_failures_cannot_consume_reserved_direct_opportunity():
    r = setup(); s = source(); pending(r, s)
    # Normal low-value HTTP time and its failure circuit are exhausted.
    r.domain_work['shop.test'] = ledger(failures=2, direct_failures=0)
    await r.recover_direct()
    assert r.resolver.calls == [s.url]
    assert r.recovery_work['shop.test']['attempts'] == 1
    assert r.domain_work['shop.test']['spent'] == 6.
    assert r.recovery_timeout <= 2 and len(r.inspected_urls) <= r.max_page_requests


@pytest.mark.asyncio
async def test_direct_failure_circuit_is_not_bypassed():
    r = setup(); s = source(); pending(r, s)
    r.domain_work['shop.test'] = ledger(failures=2, direct_failures=2)
    await r.recover_direct()
    assert not r.resolver.calls and not r.recovery_urls


@pytest.mark.asyncio
async def test_no_opportunities_and_already_satisfied_do_no_work():
    r = setup()
    await r.recover_direct()
    assert not r.enough() and not r.resolver.calls
    s = source(); s.page_validation = proof(s); r.sources[s.url] = s
    pending(r, source(57))
    await r.recover_direct()
    assert r.enough() and not r.resolver.calls


@pytest.mark.asyncio
async def test_recovery_deadline_cancels_probe_and_never_retries():
    pages = Pages(hang=True); r = setup(pages)
    r.deadline = time.monotonic() + .02
    s = source(); pending(r, s)
    await asyncio.wait_for(r.recover_direct(), timeout=.5)
    assert not pages.active and pages.calls == [s.url]
    assert not r.enough() and r.remaining() == 0
    await r.recover_direct()
    assert pages.calls == [s.url]


@pytest.mark.asyncio
@pytest.mark.parametrize('limit', ['pages', 'candidates', 'time'])
async def test_recovery_never_expands_hard_limits(limit):
    r = setup(); pending(r, source())
    if limit == 'pages': r.max_page_requests = len(r.inspected_urls)
    if limit == 'candidates': r.max_cap = len(r.product_attempts)
    if limit == 'time': r.deadline = time.monotonic() - 1
    await r.recover_direct()
    assert not r.resolver.calls


@pytest.mark.parametrize('url', [
    'https://shop.test/newsroom/press/samsung-galaxy-a56',
    'https://shop.test/events/samsung-galaxy-a56',
    'https://shop.test/blog/review-samsung-galaxy-a56',
    'https://www.youtube.com/watch?v=samsung-galaxy-a56',
    'https://shop.test/brands/samsung', 'https://shop.test/store',
])
def test_non_product_cannot_claim_reserve(url):
    r = setup()
    assert not r.recovery_candidate(SearchSourceItem(url=url, title='Samsung Galaxy A56', content=''))


@pytest.mark.asyncio
async def test_two_slot_reserve_one_per_domain_and_deterministic_order():
    orders = []
    for reverse in (False, True):
        r = setup(Pages('out_of_stock'), target=5)
        rows = [source(56, 'b.test'), source(57, 'a.test'), source(58, 'a.test'), source(59, 'c.test')]
        for s in reversed(rows) if reverse else rows: pending(r, s)
        await r.recover_direct()
        assert len(r.resolver.calls) == 2 and len(r.recovery_work) == 2
        assert not r.enough() and r.summary()['valid_offers'] == 0
        orders.append(r.resolver.calls)
    assert orders[0] == orders[1]


@pytest.mark.asyncio
async def test_existing_attempt_is_never_retried_from_pending():
    r = setup(); s = source(); pending(r, s); r.inspected_urls.add(s.url)
    s.page_validation = dict(product_page_valid=False, page_requested=True, rejection_code='resource_budget')
    r.sources[s.url] = s
    await r.recover_direct()
    assert not r.resolver.calls


@pytest.mark.asyncio
async def test_pipeline_recovers_after_query_budget_and_persists_exact_stop():
    pages = Pages('out_of_stock'); r = setup(pages)
    s = source(); r.domain_work['shop.test'] = ledger()
    class Provider:
        async def search(self, query, limit):
            return [SearchResult(url=s.url, title=s.title, content='')]
    r.provider = Provider()
    await r.run(['fixture'], r.requirement)
    assert pages.calls == [s.url]
    assert r.stop_reason == 'recovery_opportunities_exhausted'
    assert r.summary()['direct_recovery']['attempted_urls'] == [s.url]


@pytest.mark.asyncio
async def test_reserved_slots_are_not_consumed_by_generic_pages():
    r = setup()
    r.max_page_requests = 4  # Two actual OOS requests + two reserved slots.
    s = SearchResult(url='https://other.test/store', title='Store', content='')
    class Provider:
        async def search(self, query, limit): return [s]
    r.provider = Provider()
    await r.pass_queries('fixture', ['store'])
    assert not r.resolver.calls
    assert r.sources[s.url].page_validation['rejection_code'] == 'resource_budget'


def test_near_budget_unseen_direct_priority_precedes_other_seller():
    r = setup()
    near = source(56); other = source(57, 'alternate.test')
    near.title += ' giá 10 triệu'
    assert r.recovery_priority(near) < r.recovery_priority(other)


@pytest.mark.asyncio
async def test_weak_fallbacks_do_not_disable_direct_reserve():
    from tests.fixtures.discovery_scenarios import phone_requirement
    r = setup(); r.requirement = phone_requirement()
    weak = source(54); weak.page_validation = proof(weak)
    r.sources[weak.url] = weak
    assert r.eligible(weak.page_validation) and not r.ready(weak.page_validation)
    pending(r, source(56))
    await r.recover_direct()
    assert r.resolver.calls == [source(56).url] and r.summary()['valid_offers'] == 2


@pytest.mark.asyncio
async def test_reserve_timeout_limits_each_probe_even_with_long_global_deadline():
    pages = Pages(hang=True); r = setup(pages)
    r.recovery_timeout = .01
    pending(r, source(56))
    await asyncio.wait_for(r.recover_direct(), timeout=.5)
    assert r.remaining() > 0 and not pages.active
    assert pages.calls == [source(56).url]
    assert r.recovery_work['shop.test']['failures'] == 1


@pytest.mark.asyncio
async def test_archived_replay_schedules_a56_without_inventing_an_offer():
    import json
    from pathlib import Path
    from scripts.replay_oos_recovery import replay, load_baseline
    from app.services.search import progressive_retrieval as current
    baseline = load_baseline('progressive_retrieval')
    old = load_baseline('retrieval_diagnostics')
    baseline.source_plan, baseline.conversion_stats = old.source_plan, old.conversion_stats
    data = json.loads((Path(__file__).parents[1]/'fixtures/live_oos_05479307.json').read_text(encoding='utf-8'))
    before, after = await replay(data, baseline), await replay(data, current)
    assert before['page_attempts'] == 24 and after['page_attempts'] == 20
    assert before['resource_budget_rejections'] == 1 and after['resource_budget_rejections'] == 0
    assert before['explicit_editorial_attempts'] == 5 and after['explicit_editorial_attempts'] == 0
    assert before['oos_verified'] == after['oos_verified'] == 2
    assert before['eligible_verified'] == after['eligible_verified'] == 0
    url = 'https://cellphones.com.vn/dien-thoai-samsung-galaxy-a56.html'
    assert after['unrecorded_response_urls'] == after['recovery']['attempted_urls'] == [url]
    assert after['stop_reason'] == 'recovery_opportunities_exhausted'
