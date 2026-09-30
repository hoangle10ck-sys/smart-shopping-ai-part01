"""Offline regressions from session 0d288192; never contact original URLs."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.schemas.requirement import RequirementData
from app.schemas.search import SearchSourceItem
from app.services.search.base import SearchResult
from app.services.search.progressive_retrieval import ProgressiveRetriever
from app.services.search.retrieval_diagnostics import source_plan


def recorded():
    return json.loads((Path(__file__).parents[1] / 'fixtures/live_acceptance_0d288192.json').read_text(encoding='utf-8'))


def retriever(provider=None, resolver=None, **config):
    r = ProgressiveRetriever(provider, resolver, Settings(_env_file=None, demo_mode=False, **config))
    r.requirement = RequirementData.model_validate(recorded()['result']['requirement'])
    return r


def test_recorded_counts_and_rejection_are_stock_not_flexible_budget():
    from app.schemas.ranking import ScoringCandidate
    from app.services.filter.hard_filter import HardFilterService
    data = recorded()
    assert len(data['observations']) == len({o['url'] for o in data['observations']}) == 39
    assert len(data['warnings']) == len(set(data['warnings'])) == 37
    assert sum(o['proof']['page_requested'] for o in data['observations']) == 24
    assert sum(o['proof']['page_fetched'] for o in data['observations']) == 21
    req = RequirementData.model_validate(data['result']['requirement'])
    assert req.budget_mode == 'FLEXIBLE_TARGET'
    for c in data['result']['candidates']:
        candidate = ScoringCandidate.model_validate(c)
        assert HardFilterService().evaluate(candidate, req).rejection_stage == 'availability'
        candidate.availability = None
        assert HardFilterService().evaluate(candidate, req).accepted


def test_observed_editorial_paths_are_metadata_and_do_not_capture_sales_paths():
    for path in ['/sforum/dien-thoai-tam-trung', '/kinh-nghiem-mua-sam/top-dien-thoai']:
        assert source_plan(SearchSourceItem(url='https://cellphones.com.vn'+path)) == 'metadata'
    assert source_plan(SearchSourceItem(url='https://cellphones.com.vn/samsung-galaxy-s24-ultra.html')) == 'product'


def test_phone_hints_drop_components_prose_and_duplicate_connectivity():
    r = retriever()
    r.sources = {'s': SearchSourceItem(url='https://guide.test/news/phones', title='Phones',
        content='Redmi Note 13 5G+4G LTE 128GB. Redmi Note 13 5G Global. Samsung Galaxy S. '
                'Sony LYT-600. Samsung Galaxy S24 Ultra 5G Cell Phone. Samsung S24 Ultra 512GB. '
                'Oppo A5 5G 4GB/128GB Fullbox.', result_type='ARTICLE')}
    assert r.model_hints() == ['Redmi Note 13', 'Samsung Galaxy S24 Ultra 5G', 'Oppo A5 5G 4GB/128GB']
    q = r.model_query('Redmi Note 13', 'mua')
    assert 'Việt Nam' in q and 'VND' in q and '10000000' not in q


@pytest.mark.asyncio
async def test_repeated_36_evidence_and_two_unavailable_offers_stop_without_refetch():
    data = recorded()
    offers = [o for o in data['observations'] if o['proof']['product_page_valid']]
    rows = [SearchResult(title=o['title'],url=o['url'],content=o['content']) for o in offers]
    rows += [SearchResult(title='Samsung Galaxy S24 Ultra',url=f'https://guide.test/sforum/story-{i}',content='Review') for i in range(36)]
    class Provider:
        calls = 0
        async def search(self, query, limit):
            self.calls += 1
            return rows + rows  # duplicates in and across rounds
    class Resolver:
        calls = []
        async def inspect(self, url, **kwargs):
            self.calls.append(url)
            return deepcopy(next(o['proof'] for o in offers if o['url'] == url))
    provider, resolver = Provider(), Resolver()
    r = retriever(provider, resolver)
    await r.run(['first', 'second'], r.requirement)
    assert r.stop_reason == 'no_progress'
    assert provider.calls < 12 and len(resolver.calls) == len(set(resolver.calls)) == 2
    assert len(r.sources) == 38 and r.summary()['valid_offers'] == 0
    assert r.rounds[-1]['no_progress_rounds'] >= 3


@pytest.mark.asyncio
@pytest.mark.parametrize('target', [3, 5])
async def test_valid_supply_stops_at_configured_target(target):
    from tests.fixtures.discovery_scenarios import NoisyProvider, LocalPages, phone_requirement
    provider, pages = NoisyProvider(supply=target), LocalPages()
    r = retriever(provider, pages, live_search_target_products=target)
    await r.run(['first','second'], phone_requirement())
    assert r.stop_reason == 'target_reached' and len(provider.calls) == 4
    assert r.summary()['valid_offers'] == target


@pytest.mark.asyncio
async def test_deadline_cancels_all_pending_provider_calls_and_closes_session():
    from contextlib import asynccontextmanager
    active = set()
    class Provider:
        async def search(self, query, limit):
            active.add(query)
            try: await asyncio.Event().wait()
            finally: active.remove(query)
    class Resolver:
        closed = False
        @asynccontextmanager
        async def session(self):
            try: yield
            finally: self.closed = True
    resolver = Resolver()
    r = retriever(Provider(), resolver, live_search_budget_seconds=.01)
    await asyncio.wait_for(r.run(['one','two'],r.requirement), timeout=1)
    assert not active and resolver.closed and r.stop_reason == 'time_budget'


@pytest.mark.asyncio
async def test_recorded_observations_replay_never_upgrades_rejected_evidence():
    data = recorded()
    observations = {o['url']:o for o in data['observations']}
    class Provider:
        async def search(self, query, limit):
            return [SearchResult(title=o['title'],url=o['url'],content=o['content']) for o in observations.values()]
    class Resolver:
        def __init__(self): self.calls = []
        async def inspect(self, url, **kwargs):
            self.calls.append(url)
            return deepcopy(observations[url]['proof'])
    resolver = Resolver()
    r = retriever(Provider(), resolver)
    await r.run(['recorded observations'], r.requirement)
    assert len(resolver.calls) < 24 and len(resolver.calls) == len(set(resolver.calls))
    assert all('/sforum/' not in u and '/kinh-nghiem-mua-sam/' not in u for u in resolver.calls)
    assert r.summary()['conversion']['direct_product_candidates'] == 2
    assert r.summary()['valid_offers'] == 0 and r.stop_reason == 'no_progress'
