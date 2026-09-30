"""Measured local benchmark against Git source; no DB or external provider calls.

Run from backend: .venv/Scripts/python.exe -B -X utf8 scripts/benchmark_live_search.py
The baseline classes are read with git show, without checkout or worktree writes.
"""
import asyncio
from collections import Counter
import json
import logging
from pathlib import Path
import socket
import statistics
import subprocess
import sys
import time
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from app.core.config import Settings
from app.schemas.requirement import RequirementData
from app.services.extraction.product_page_validator import inspect_page, identity_tokens
from app.services.extraction.dealer_offers import concrete_proofs
from app.services.llm.client import GeminiLLMClient, MockLLMClient, FallbackLLMClient
from app.services.recommendation.ranking_service import RankingService
from app.services.search.base import SearchResult
from app.services.search.progressive_retrieval import ProgressiveRetriever
from tests.fixtures.sales_pages import sales_page

BASELINE = 'v1.2.0'
REPEATS = 3
PROVIDER_DELAY = .02
PAGE_DELAY = .04
LLM_DELAY = .02


def baseline_class(path, name):
    source = subprocess.check_output(['git', 'show', f'{BASELINE}:{path}'], cwd=ROOT).decode('utf-8')
    module = ModuleType('benchmark_baseline_' + name)
    sys.modules[module.__name__] = module
    exec(compile(source, f'{BASELINE}:{path}', 'exec'), module.__dict__)
    return getattr(module, name)


async def overload(client_type):
    client = client_type.__new__(client_type)
    client._timeout_seconds, client._retry_count = 1, 2
    calls = []
    def generate(query):
        calls.append(query)
        time.sleep(LLM_DELAY)
        raise RuntimeError('503 UNAVAILABLE')
    client._generate_sync = generate
    started = time.perf_counter()
    result = await FallbackLLMClient(client, MockLLMClient()).analyze_requirement(
        'Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu')
    assert result.category == 'điện thoại' and result.budget_max == 10000000
    return dict(duration_ms=(time.perf_counter()-started)*1000, attempts=len(calls))


async def retrieval(retriever_type, target):
    # Two shared candidates first; subsequent commercial queries reveal five.
    # Every input is a local fictional fixture on .example, never Live evidence.
    class Provider:
        calls = 0
        async def search(self, query, max_results):
            self.calls += 1
            count = 2 if self.calls <= 2 else 5
            await asyncio.sleep(PROVIDER_DELAY)
            return [SearchResult(title=f'Samsung Galaxy A{n} 128GB',
                url=f'https://seller{n}.example/dien-thoai-samsung-galaxy-a{n}-128gb',
                content=f'Điện thoại Samsung Galaxy A{n} 128GB, giá 9.000.000 VND. Mua ngay.')
                for n in range(50, 50+count)]
    class Resolver:
        def __init__(self): self.calls = []
        async def inspect(self, url, **kwargs):
            self.calls.append(url)
            await asyncio.sleep(PAGE_DELAY)
            n = url.rsplit('-a', 1)[1].split('-')[0]
            return inspect_page(url, sales_page(name=f'Samsung Galaxy A{n} 128GB',
                brand='Samsung', model=f'A{n}', category='điện thoại'))
        async def _image_loads(self, url): raise AssertionError('No image fixture')
    config = Settings(_env_file=None, demo_mode=False, live_search_target_products=target,
                      live_search_max_queries=6, live_search_budget_seconds=5)
    requirement = RequirementData(category='điện thoại', budget_max=10000000)
    provider, resolver = Provider(), Resolver()
    retriever = retriever_type(provider, resolver, config)
    started = time.perf_counter()
    await retriever.run(['điện thoại giá bán', 'điện thoại mua online'], requirement)
    unique = {}
    for source in retriever.sources.values():
        for proof in concrete_proofs(source.page_validation):
            if retriever.eligible(proof):
                key = tuple(sorted(identity_tokens(proof['name'])))
                unique.setdefault(key, retriever.candidate(proof))
    candidates = list(unique.values())
    for number, candidate in enumerate(candidates): candidate.product_id = number + 1
    ranked = RankingService().rank(candidates, requirement, top_k=5)
    return dict(duration_ms=(time.perf_counter()-started)*1000,
        provider_calls=provider.calls, page_fetches=len(resolver.calls),
        duplicate_fetches=sum(count-1 for count in Counter(resolver.calls).values()),
        final_valid_offers=len(unique), final_recommendations=len(ranked),
        ranked=[{'name':r.candidate.name,'price':r.candidate.price,'score':r.score.final_score} for r in ranked])


async def main():
    def no_network(*args, **kwargs): raise AssertionError('Benchmark forbids external network')
    socket.socket.connect = no_network
    logging.disable(logging.CRITICAL)
    old_retriever = baseline_class('backend/app/services/search/progressive_retrieval.py', 'ProgressiveRetriever')
    old_client = baseline_class('backend/app/services/llm/client.py', 'GeminiLLMClient')
    result = dict(baseline_ref=BASELINE,
        baseline_commit=subprocess.check_output(['git','rev-parse',BASELINE],cwd=ROOT,text=True).strip(),
        repeats=REPEATS, method='median wall-clock; fixed local delays; no DB/network; actual Python ranking',
        limitations=['Does not model real provider latency, SDK-internal retry time, browser/human clarification, '
                     'database persistence, image downloads or explanation generation.',
                     'Only baseline retriever/LLM classes loaded from Git; unchanged dependencies use current tree.',
                     'Synthetic overall duration is the sum of separate overload and retrieval measurements.'],
        configured_delays_ms=dict(provider=PROVIDER_DELAY*1000, page=PAGE_DELAY*1000, llm=LLM_DELAY*1000),
        runs={}, medians={})
    for label, cls, target in [('before_default_target_1',old_retriever,1),
                                ('before_equal_target_5',old_retriever,5),('after_target_5',ProgressiveRetriever,5)]:
        runs = [await retrieval(cls, target) for _ in range(REPEATS)]
        assert all(r['ranked'] == runs[0]['ranked'] for r in runs)
        result['runs'][label] = runs
        result['medians'][label] = {key: round(statistics.median(r[key] for r in runs),3)
                                   for key in runs[0] if key != 'ranked'}
    assert result['runs']['before_equal_target_5'][0]['ranked'] == result['runs']['after_target_5'][0]['ranked']
    for label, cls in [('gemini_before',old_client),('gemini_after',GeminiLLMClient)]:
        runs = [await overload(cls) for _ in range(REPEATS)]
        result['runs'][label] = runs
        result['medians'][label] = {key: round(statistics.median(r[key] for r in runs),3) for key in runs[0]}
    for label, search, llm in [('synthetic_before','before_default_target_1','gemini_before'),
                              ('synthetic_after','after_target_5','gemini_after')]:
        result['medians'][label] = {'duration_ms':round(result['medians'][search]['duration_ms']+
                                                       result['medians'][llm]['duration_ms'],3)}
    output = ROOT / 'docs' / 'LIVE_SEARCH_PERFORMANCE_BENCHMARK.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result['medians'], indent=2))


if __name__ == '__main__':
    asyncio.run(main())
