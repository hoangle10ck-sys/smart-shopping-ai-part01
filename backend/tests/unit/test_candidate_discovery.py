"""Regression for articles exhausting the product verification budget."""
import pytest
from app.core.config import Settings
from app.services.search.progressive_retrieval import ProgressiveRetriever
from tests.fixtures.discovery_scenarios import NoisyProvider, LocalPages, phone_requirement


@pytest.mark.asyncio
async def test_noisy_rounds_do_not_starve_direct_product_discovery():
    provider, pages = NoisyProvider(), LocalPages()
    retriever = ProgressiveRetriever(provider, pages, Settings(_env_file=None, demo_mode=False))
    await retriever.run(['điện thoại mua giá bán', 'điện thoại mua chính hãng'], phone_requirement())
    assert retriever.summary()['valid_offers'] == 5
    assert any('"' in query for query in provider.calls)
    assert all('/news/' not in url for url in pages.calls)
    assert len(pages.calls) == len(set(pages.calls)) == 6
    assert retriever.stop_reason == 'target_reached'
    first, second = retriever.rounds
    assert first['conversion']['pages_requested'] == first['conversion']['pages_verified'] == 1
    assert first['conversion']['out_of_stock'] == 1
    assert first['conversion']['evidence_only_results'] == first['conversion']['rejected_before_fetch'] == 9
    assert first['unique_search_results'] == 10
    assert list(first['raw_search_results_per_query'].values()) == [5, 5]
    assert first['conversion']['eligible_offers'] == 0
    assert second['kind'] == 'model_discovery' and second['conversion']['pages_requested'] == 5
    assert sum(d['conversion']['pages_requested'] for d in retriever.diagnostics) == len(pages.calls)


@pytest.mark.asyncio
async def test_one_valid_in_round_one_must_continue_below_minimum():
    provider, pages = NoisyProvider(), LocalPages(initial_in_stock=True)
    retriever = ProgressiveRetriever(provider, pages, Settings(_env_file=None, demo_mode=False))
    await retriever.run(['first', 'second'], phone_requirement())
    assert retriever.rounds[0]['cumulative_valid_offers'] == 1
    assert retriever.rounds[1]['queries_executed']
    assert retriever.rounds[1]['cumulative_valid_offers'] >= 5


@pytest.mark.asyncio
async def test_unknown_urls_that_turn_out_editorial_have_bounded_http_budget():
    from app.services.search.base import SearchResult
    calls = []
    class Provider:
        async def search(self, query, limit):
            index = len(calls); calls.append(query)
            return [SearchResult(title='Samsung Galaxy A50', content='Bài đánh giá',
                url=f'https://guide.example/entry-{index}-{i}') for i in range(limit)]
    class Resolver:
        async def inspect(self, url, **kwargs):
            return {'product_page_valid':False, 'result_type':'ARTICLE', 'page_fetched':True}
    r = ProgressiveRetriever(Provider(), Resolver(), Settings(_env_file=None, demo_mode=False))
    await r.run(['first', 'second'], phone_requirement())
    assert len(r.inspected_urls) == r.max_page_requests == 24
    assert not r.product_attempts and not r.enough()
    assert r.stop_reason == 'page_budget' and len(calls) <= 12


def test_recorded_live_candidate_was_filtered_for_stock_not_budget():
    import json
    from pathlib import Path
    from app.schemas.ranking import ScoringCandidate
    from app.schemas.requirement import RequirementData
    from app.services.filter.hard_filter import HardFilterService
    trace = json.loads((Path(__file__).parents[1]/'fixtures/live_acceptance_phone.json').read_text(encoding='utf-8'))
    result = trace['result']
    assert len(trace['observations']) == 19 and len(result['candidates']) == 1
    requirement = RequirementData.model_validate(result['requirement'])
    candidate = ScoringCandidate.model_validate(result['candidates'][0])
    decision = HardFilterService().evaluate(candidate, requirement)
    assert candidate.name == 'vivo V30E 12GB 256GB' and candidate.price == 10490000
    assert decision.rejection_stage == result['filter_decisions'][0]['rejection_stage'] == 'availability'
    assert not decision.accepted
    candidate.availability = None
    assert HardFilterService().evaluate(candidate, requirement).accepted
    assert sum(bool(o['proof'].get('product_page_valid')) for o in trace['observations']) == 1


def test_glued_navigation_suffix_never_becomes_exact_model():
    from app.services.search.model_hints import observed_models
    assert observed_models('Samsung Note 20 UltraThay camera sau iPhone') == ['Samsung Note 20 Ultra']
    assert observed_models('HP ProBook 440 G10 giá bán') == ['HP ProBook 440 G10']


def test_query_criteria_does_not_repeat_property_label():
    from app.services.llm.query_generator import QueryGenerator
    queries = QueryGenerator(max_queries=2).generate(phone_requirement())
    assert len(queries) == 2 and all('pin pin' not in q and 'pin lâu' in q for q in queries)


@pytest.mark.asyncio
async def test_tavily_forwards_limit_and_preserves_multiple_results(monkeypatch):
    import json, httpx
    from types import SimpleNamespace
    from app.services.search import tavily_provider as module
    original = httpx.AsyncClient
    def handle(request):
        payload = json.loads(request.content)
        assert payload['max_results'] == 5
        return httpx.Response(200, json={'results':[dict(title=f'Samsung A{i}',
            url=f'https://shop.example/samsung-a{i}', content='Mua ngay') for i in range(5)]})
    monkeypatch.setattr(module, 'get_settings', lambda:SimpleNamespace(tavily_api_key='fixture',
        search_timeout_seconds=2, search_retry_count=0))
    monkeypatch.setattr(module.httpx, 'AsyncClient', lambda **kw:original(transport=httpx.MockTransport(handle), **kw))
    result = await module.TavilyProvider().search('phone', 5)
    assert len(result) == len({item.url for item in result}) == 5


@pytest.mark.asyncio
async def test_query_diagnostics_separate_filter_identity_price_and_network_failures():
    from app.services.search.base import SearchResult
    rows = [SearchResult(title=f'Item X{i}', url=f'https://shop.example/item-x{i}', content='Details') for i in range(3)]
    rows += [rows[0], SearchResult(title='Bad', url='not-a-url')]
    class Provider:
        async def search(self, query, limit): return rows
    class Resolver:
        async def inspect(self, url, **kwargs):
            i = int(url[-1])
            return dict(product_page_valid=False, page_fetched=i < 2, fetch_blocked=i == 2,
                rejection_code=['missing_identity', 'missing_price', None][i])
    r = ProgressiveRetriever(Provider(), Resolver(), Settings(_env_file=None, demo_mode=False, live_search_max_queries=2))
    await r.run(['first', 'second'], phone_requirement())
    first, reused = r.diagnostics
    assert first['result_count'] == 5 and first['source_filter_rejected'] == 2
    assert first['source_filter_reason_counts'] == {'duplicate_url':1, 'invalid_url':1}
    stats = first['conversion']
    assert stats['pages_requested'] == stats['verification_failed'] == 3
    assert stats['pages_fetched'] == 2 and stats['pages_verified'] == 0
    assert stats['missing_identity'] == stats['missing_price'] == stats['http_network_failure'] == 1
    assert reused['conversion']['pages_requested'] == 0 and reused['conversion']['reused_pages'] == 3
