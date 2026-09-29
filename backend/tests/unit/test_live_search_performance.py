"""Deterministic local performance regressions; no provider/site calls."""
import asyncio
from dataclasses import asdict

import httpx
import pytest

from app.core.config import Settings
from app.schemas.requirement import RequirementData
from app.services.llm.client import GeminiLLMClient, FallbackLLMClient, MockLLMClient
from app.services.llm.requirement_analyzer import RequirementAnalyzer
from app.services.search.base import SearchResult
from app.services.search.progressive_retrieval import ProgressiveRetriever
from app.services.extraction.product_image_resolver import ProductImageResolver
from app.services.extraction.product_page_validator import inspect_page
from tests.fixtures.sales_pages import sales_page


def settings(**changes):
    return Settings(_env_file=None, demo_mode=False, **changes)


def row(number, domain=None):
    return SearchResult(title=f'Samsung Galaxy A{number} 128GB',
        url=f'https://{domain or f"seller{number}.example"}/dien-thoai-samsung-galaxy-a{number}-128gb',
        content=f'Điện thoại Samsung Galaxy A{number} 128GB giá bán 9.000.000 VND. Mua ngay.')


class FixtureResolver:
    def __init__(self, delay=.005, invalid=()):
        self.delay, self.invalid = delay, set(invalid)
        self.calls = []
        self.active = self.peak = 0

    async def inspect(self, url, **kwargs):
        self.calls.append(url)
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(self.delay)
            number = url.rsplit('-a', 1)[1].split('-')[0]
            if int(number) in self.invalid:
                return {'product_page_valid':False, 'verification_level':'REJECTED',
                        'reason':'No concrete price', 'image_url':None}
            return inspect_page(url, sales_page(name=f'Samsung Galaxy A{number} 128GB',
                brand='Samsung', model=f'A{number}', category='điện thoại'))
        finally:
            self.active -= 1

    async def _image_loads(self, url):
        raise AssertionError('Fixture has no image evidence')


@pytest.mark.asyncio
@pytest.mark.parametrize('message', ['503 UNAVAILABLE Authorization: private-test-token', '429 RESOURCE_EXHAUSTED'])
async def test_gemini_overload_falls_back_after_one_attempt_without_backoff(message, monkeypatch, caplog):
    client = GeminiLLMClient.__new__(GeminiLLMClient)
    client._timeout_seconds, client._retry_count = 1, 2
    calls = []
    def fail(query):
        calls.append(query)
        raise RuntimeError(message)
    async def no_sleep(*args):
        raise AssertionError('Overload must not back off')
    client._generate_sync = fail
    monkeypatch.setattr(asyncio, 'sleep', no_sleep)
    assessment = await RequirementAnalyzer(FallbackLLMClient(client, MockLLMClient())).analyze(
        'Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu')
    assert len(calls) == 1
    assert 'private-test-token' not in caplog.text and 'Authorization:' not in caplog.text
    assert not assessment.needs_clarification
    assert assessment.requirement.category == 'điện thoại'
    assert assessment.requirement.budget_mode == 'FLEXIBLE_TARGET'
    assert assessment.requirement.purpose == []  # Do not invent a purpose to bypass clarification.
    assert {item.name for item in assessment.requirement.requirements} == {'camera', 'battery'}


@pytest.mark.asyncio
async def test_non_overload_invalid_response_retains_bounded_retries(monkeypatch):
    client = GeminiLLMClient.__new__(GeminiLLMClient)
    client._timeout_seconds, client._retry_count = 1, 2
    calls, sleeps = [], []
    def fail(query):
        calls.append(query)
        raise ValueError('Invalid JSON')
    async def sleep(value): sleeps.append(value)
    client._generate_sync = fail
    monkeypatch.setattr(asyncio, 'sleep', sleep)
    with pytest.raises(RuntimeError, match='analysis failed'):
        await client.analyze_requirement('query')
    assert len(calls) == 3 and sleeps == [.5, 1.0]


def test_gemini_sdk_has_one_attempt_and_real_transport_timeout(monkeypatch):
    from google import genai
    from app.services.llm import client as module
    captured = {}
    def constructor(**kwargs): captured.update(kwargs); return object()
    monkeypatch.setattr(genai, 'Client', constructor)
    monkeypatch.setattr(module, 'get_settings', lambda: settings(gemini_api_key='test-only', llm_timeout_seconds=2))
    GeminiLLMClient()
    assert captured['http_options'].timeout == 2000
    assert captured['http_options'].retry_options.attempts == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('query,missing', [('Điện thoại 10 triệu','purpose'), ('Điện thoại camera tốt','budget'), ('10 triệu','category')])
async def test_actually_missing_input_still_clarifies(query, missing):
    assessment = await RequirementAnalyzer(MockLLMClient()).analyze(query)
    assert assessment.needs_clarification and missing in assessment.missing_fields


@pytest.mark.asyncio
async def test_query_order_and_page_merge_are_deterministic_with_shared_urls():
    async def run(reverse):
        class Provider:
            active = peak = 0
            async def search(self, query, limit):
                self.active += 1; self.peak = max(self.peak, self.active)
                await asyncio.sleep(.01 if query.startswith('first') == reverse else .001)
                self.active -= 1
                return [row(n) for n in ([50,51,52,53] if query.startswith('first') else [52,53,54,55])]
        provider, resolver = Provider(), FixtureResolver()
        retriever = ProgressiveRetriever(provider, resolver, settings(live_search_target_products=5))
        batches = await retriever.run(['first','second'], RequirementData(category='điện thoại',budget_max=10_000_000))
        assert provider.peak == 2 and 1 < resolver.peak <= 4
        assert len(resolver.calls) == len(set(resolver.calls)) == 6
        assert retriever.stop_reason == 'target_reached'
        assert retriever.summary()['valid_offers'] == 6
        assert retriever.summary()['rejected_duplicate'] == 2
        return [(q, [s.url for s in sources]) for q, sources, _ in batches], list(retriever.sources)
    assert await run(False) == await run(True)


@pytest.mark.asyncio
async def test_per_domain_limit_and_pool_expand_on_high_rejection():
    class Provider:
        async def search(self, query, limit): return [row(n,'one-shop.example') for n in range(50,62)]
    resolver = FixtureResolver(invalid=range(50,56))
    retriever = ProgressiveRetriever(Provider(),resolver,settings(live_search_initial_candidates=4,live_search_max_candidates=12))
    await retriever.run(['first'],RequirementData(category='điện thoại',budget_max=10_000_000))
    assert resolver.peak == 2
    assert retriever.candidate_cap == 12
    assert retriever.summary()['valid_offers'] == 6
    assert retriever.summary()['rejected_missing_price'] == 6


@pytest.mark.asyncio
@pytest.mark.parametrize('supply', [2,5])
async def test_continue_below_target_and_honest_exhaustion(supply):
    calls=[]
    class Provider:
        async def search(self, query, limit):
            calls.append(query)
            # Round one has only two; commercial round may discover three more.
            numbers=range(50,52) if len(calls)<=2 else range(50,50+supply)
            return [row(n) for n in numbers]
    resolver = FixtureResolver()
    retriever=ProgressiveRetriever(Provider(),resolver,settings(live_search_max_queries=6))
    await retriever.run(['first','second'],RequirementData(category='điện thoại',budget_max=10_000_000))
    assert len(calls)>2
    assert retriever.summary()['valid_offers']==supply
    assert len(resolver.calls)==supply
    assert len(calls)==4
    assert retriever.stop_reason==('target_reached' if supply==5 else 'strong_fit_no_progress')


@pytest.mark.asyncio
async def test_early_stop_avoids_optional_fetches_and_hard_cap_is_enforced():
    class Provider:
        calls=0
        async def search(self,query,limit):
            self.calls+=1
            return [row(n) for n in range(50,70)]
    for invalid, expected, stop in [((),6,'target_reached'),(range(50,70),10,'candidate_budget')]:
        provider,resolver=Provider(),FixtureResolver(invalid=invalid)
        retriever=ProgressiveRetriever(provider,resolver,settings(live_search_initial_candidates=6,live_search_max_candidates=10))
        await retriever.run(['first'],RequirementData(category='điện thoại',budget_max=10_000_000))
        # Chunks can stop at 6 (initial capacity); no need to spend all 20 URLs.
        assert len(resolver.calls)==expected
        assert provider.calls==1 and retriever.stop_reason==stop


def test_target_counts_unique_identity_and_keeps_unknown_stock_eligible():
    from app.schemas.search import SearchSourceItem
    retriever=ProgressiveRetriever(None,None,settings(live_search_target_products=3))
    retriever.requirement=RequirementData(category='điện thoại',budget_max=10_000_000)
    for i,stock in enumerate([None,'UNKNOWN','out_of_stock']):
        item=row(50+i)
        proof=inspect_page(item.url,sales_page(name=item.title,category='điện thoại'))
        proof['availability']=stock
        retriever.sources[item.url]=SearchSourceItem(**asdict(item),page_validation=proof)
    # Same model from another merchant does not count twice toward the target.
    original = next(iter(retriever.sources.values()))
    duplicate = original.model_copy(deep=True, update={'url':'https://another.example/samsung-galaxy-a50'})
    retriever.sources[duplicate.url] = duplicate
    assert not retriever.enough()
    assert retriever.summary()['valid_offers']==2
    assert retriever.summary()['rejected_out_of_stock']==1
    assert retriever.summary()['rejected_duplicate']==1


@pytest.mark.asyncio
async def test_query_semaphore_bounds_large_batch():
    import time
    class Provider:
        active = peak = 0
        async def search(self, query, limit):
            self.active += 1
            self.peak = max(self.peak, self.active)
            await asyncio.sleep(.002)
            self.active -= 1
            return []
    provider = Provider()
    retriever = ProgressiveRetriever(provider, FixtureResolver(), settings())
    retriever.deadline = time.monotonic() + 2
    await retriever.pass_queries('test', [f'query {i}' for i in range(8)])
    assert provider.peak == 2
    assert [q for q, _, _ in retriever.batches] == [f'query {i}' for i in range(8)]


@pytest.mark.asyncio
async def test_pool_handles_gzip_and_closes_on_cancellation(monkeypatch):
    import gzip
    from app.services.extraction import product_image_resolver as module
    original = httpx.AsyncClient
    clients = []
    html = '<html>Điện thoại chính hãng</html>'
    async def public(url): return True
    def handler(request):
        return httpx.Response(200, headers={'content-type':'text/html; charset=utf-8',
            'content-encoding':'gzip'}, content=gzip.compress(html.encode()))
    def factory(**kwargs):
        client = original(transport=httpx.MockTransport(handler), **kwargs)
        clients.append(client)
        return client
    monkeypatch.setattr(module, '_safe_public_url', public)
    monkeypatch.setattr(module.httpx, 'AsyncClient', factory)
    resolver = ProductImageResolver()
    with pytest.raises(asyncio.CancelledError):
        async with resolver.session():
            assert await resolver._fetch_html('https://shop.example/product') == ('https://shop.example/product', html)
            raise asyncio.CancelledError()
    assert len(clients) == 1 and clients[0].is_closed and resolver._client is None


@pytest.mark.asyncio
async def test_budget_timeout_still_closes_pool(monkeypatch):
    from contextlib import asynccontextmanager
    class Resolver(FixtureResolver):
        closed = False
        @asynccontextmanager
        async def session(self):
            try: yield
            finally: self.closed = True
    class Provider:
        async def search(self, query, limit): await asyncio.sleep(1)
    resolver = Resolver()
    retriever = ProgressiveRetriever(Provider(), resolver, settings(live_search_budget_seconds=.01))
    await retriever.run(['one'], RequirementData(category='điện thoại'))
    assert resolver.closed and retriever.stop_reason == 'time_budget'
    assert retriever.diagnostics[0]['error_kind'] == 'timeout'


@pytest.mark.asyncio
async def test_shared_client_closed_and_oversize_stream_rejected(monkeypatch):
    from app.services.extraction import product_image_resolver as module
    calls=[]
    original=httpx.AsyncClient
    async def public(url): return True
    async def handle(request):
        return httpx.Response(200,headers={'content-type':'text/html'},content=b'x'*2_000_001)
    def factory(**kwargs):
        result=original(transport=httpx.MockTransport(handle),**kwargs); calls.append(result); return result
    monkeypatch.setattr(module,'_safe_public_url',public)
    monkeypatch.setattr(module.httpx,'AsyncClient',factory)
    resolver=ProductImageResolver()
    async with resolver.session():
        assert await resolver._fetch_html('https://shop.example/a') is None
        assert await resolver._fetch_html('https://shop.example/b') is None
        assert len(calls)==1 and not calls[0].is_closed
    assert calls[0].is_closed and resolver._client is None


def test_explanation_overload_is_not_repeated_for_every_product(monkeypatch):
    from app.services.llm.explanation_service import ExplanationService
    from app.schemas.ranking import ScoringCandidate
    from app.services.scoring.scoring_engine import ScoringEngine
    from app.schemas.evidence import EvidenceReport, EvidenceBreakdown
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(),'demo_mode',False)
    service=ExplanationService()
    calls=[]
    monkeypatch.setattr(service,'_provider_order',lambda:['gemini'])
    def fail(**kwargs): calls.append(1); raise RuntimeError('503 UNAVAILABLE')
    monkeypatch.setattr(service,'_generate_with_provider',fail)
    candidate=ScoringCandidate(product_id=1,name='Samsung Galaxy A50',price=9_000_000)
    requirement=RequirementData(category='điện thoại',budget_max=10_000_000)
    score=ScoringEngine().score(candidate,requirement)
    for _ in range(5):
        evidence=EvidenceReport(confidence=50, source_count=1, offer_count=1,
            breakdown=EvidenceBreakdown(source_reliability=50, product_completeness=50,
                offer_completeness=50, consistency=50, corroboration=50))
        result=service.explain(candidate=candidate,requirement=requirement,score=score,evidence=evidence)
        assert result.generation_mode=='fallback'
    assert len(calls)==1


def test_explanation_sdk_overload_attempt_timeout_and_close(monkeypatch):
    from types import SimpleNamespace
    from google import genai
    from app.core.config import get_settings
    from app.services.llm.explanation_service import ExplanationService
    from tests.unit.test_explanation_service import make_candidate, make_requirement, make_score, make_evidence
    config = get_settings()
    for key, value in dict(demo_mode=False, gemini_api_key='test-placeholder',
                           llm_provider='gemini', llm_fallback_provider='', llm_retry_count=2,
                           llm_timeout_seconds=2).items():
        monkeypatch.setattr(config, key, value)
    calls, closed, options = [], [], []
    def fail(**kwargs):
        calls.append(1)
        raise RuntimeError('503 UNAVAILABLE')
    def client(**kwargs):
        options.append(kwargs['http_options'])
        return SimpleNamespace(models=SimpleNamespace(generate_content=fail), close=lambda:closed.append(1))
    def no_sleep(*args): raise AssertionError('Gemini overload must not sleep')
    monkeypatch.setattr(genai, 'Client', client)
    monkeypatch.setattr('app.services.llm.explanation_service.time.sleep', no_sleep)
    service = ExplanationService()
    for _ in range(5):
        result = service.explain(candidate=make_candidate(), requirement=make_requirement(),
                                 score=make_score(), evidence=make_evidence())
        assert result.generation_mode == 'fallback'
    assert len(calls) == len(closed) == len(options) == 1
    assert options[0].retry_options.attempts == 1 and options[0].timeout == 2000


@pytest.mark.asyncio
async def test_performance_trace_is_request_local_and_cleared_after_error(caplog):
    from types import SimpleNamespace
    from app.services.performance import profile_request, current_trace, measure
    @profile_request('total_search_ms')
    async def request(session_id):
        with measure('search_provider_ms'):
            await asyncio.sleep(.002 if session_id == 'first' else .001)
        current_trace.get().diagnostics['generated_queries'] = [session_id]
        return SimpleNamespace(session_id=session_id, retrieval_diagnostics=[])
    first, second = await asyncio.gather(request('first'), request('second'))
    for result in (first, second):
        trace = result.retrieval_diagnostics[0]['performance']
        assert trace['diagnostics']['generated_queries'] == [result.session_id]
        assert trace['timings']['total_search_ms'] >= trace['timings']['search_provider_ms'] > 0
    @profile_request('total_search_ms')
    async def fail(): raise RuntimeError('Authorization: private-test-token')
    with pytest.raises(RuntimeError): await fail()
    assert current_trace.get() is None and 'private-test-token' not in caplog.text
