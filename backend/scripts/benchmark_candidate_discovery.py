"""Local noisy-source replay; --before accepts the captured pre-fix Python file.

No database and no external network. The fixture offers are NOT Live evidence.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
import statistics
import sys
import time
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.core.config import Settings
from app.services.search.progressive_retrieval import ProgressiveRetriever
from app.services.extraction.dealer_offers import concrete_proofs
from app.services.extraction.product_page_validator import identity_tokens
from app.services.recommendation.ranking_service import RankingService
from tests.fixtures.discovery_scenarios import NoisyProvider, LocalPages, phone_requirement


async def measure(retriever_type):
    provider, pages = NoisyProvider(delay=.02), LocalPages(delay=.04)
    settings = Settings(_env_file=None, demo_mode=False, live_search_budget_seconds=5)
    retriever = retriever_type(provider, pages, settings)
    requirement = phone_requirement()
    started = time.perf_counter()
    await retriever.run(['điện thoại mua giá bán', 'điện thoại mua chính hãng'], requirement)
    unique = {}
    for source in retriever.sources.values():
        for proof in concrete_proofs(source.page_validation):
            if retriever.eligible(proof):
                unique.setdefault(tuple(sorted(identity_tokens(proof['name']))), retriever.candidate(proof))
    candidates = list(unique.values())
    for i, c in enumerate(candidates): c.product_id = i+1
    ranked = RankingService().rank(candidates, requirement)
    return dict(duration_ms=round((time.perf_counter()-started)*1000, 3),
        provider_calls=len(provider.calls), pages_requested=len(pages.calls),
        evidence_pages_requested=sum('/news/' in url for url in pages.calls),
        direct_candidates=sum(bool(s.page_validation.get('product_page_valid')) for s in retriever.sources.values()),
        eligible_offers=len(unique), final_recommendations=len(ranked), stop_reason=retriever.stop_reason,
        queries=provider.calls, rounds=getattr(retriever, 'rounds', []))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', type=Path)
    args = parser.parse_args()
    def no_network(*args, **kwargs): raise AssertionError('Benchmark forbids network')
    socket.socket.connect = no_network
    versions = {'after': ProgressiveRetriever}
    report = dict(method='Median of 3 local runs, query delay 20ms/page delay 40ms; no DB/network.',
        limitation='Synthetic provider behavior based on the observed failure pattern; not a raw Tavily response replay or Live acceptance.',
        before_sha256=None, runs={}, medians={})
    if args.before:
        code = args.before.read_bytes()
        report['before_sha256'] = hashlib.sha256(code).hexdigest()
        module = ModuleType('candidate_discovery_before')
        exec(compile(code, str(args.before), 'exec'), module.__dict__)
        versions = {'before':module.ProgressiveRetriever, **versions}
    for name, cls in versions.items():
        runs = [await measure(cls) for _ in range(3)]
        report['runs'][name] = runs
        report['medians'][name] = {key:statistics.median(row[key] for row in runs)
            for key in ('duration_ms','provider_calls','pages_requested','evidence_pages_requested',
                        'direct_candidates','eligible_offers','final_recommendations')}
    (ROOT/'docs/LIVE_CANDIDATE_DISCOVERY_BENCHMARK.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report['medians'], indent=2))


if __name__ == '__main__': asyncio.run(main())
