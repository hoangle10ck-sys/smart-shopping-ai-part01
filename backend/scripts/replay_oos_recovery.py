"""Archived scheduling replay, no DB/network and no invented page response.

The baseline is read with git show v1.2.1; no checkout/restore is performed.
Virtual serial inspection costs model budget pressure, not Live concurrency or
latency. An unrequested URL is attempted but remains unverified in the replay.
"""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core.config import Settings
from app.schemas.requirement import RequirementData
from app.services.search.base import SearchResult
from app.services.search.progressive_retrieval import ProgressiveRetriever
from app.services.filter.hard_filter import is_unavailable


class Clock:
    now = 100.
    def monotonic(self): return self.now
    def perf_counter(self): return self.now


def load_baseline(name):
    path = 'backend/app/services/search/' + name + '.py'
    code = subprocess.check_output(['git', 'show', 'v1.2.1:' + path], cwd=ROOT.parent).decode('utf-8')
    module = ModuleType('oos_baseline_' + name)
    exec(compile(code, 'v1.2.1:' + path, 'exec'), module.__dict__)
    return module


async def replay(data, module):
    clock = Clock()
    original_time = module.time
    module.time = clock
    by_url = {r['url']: r for r in data['observations']}
    queries = {r['query']: r for r in data['queries']}
    costs = {r['url']: r['inspection_ms'] / 1000 for r in data['historical_performance']['diagnostics']['page_timings']}
    unrecorded, requests = [], []
    class Provider:
        async def search(self, query, limit):
            return [SearchResult(url=url, title=by_url[url]['title'], content=by_url[url]['content'])
                    for url in queries[query]['urls'] if url in by_url]
    class Pages:
        async def inspect(self, url, **kwargs):
            requests.append(url)
            recorded = by_url[url]['proof']
            if not recorded.get('page_requested'):
                unrecorded.append(url)
                return dict(product_page_valid=False, page_fetched=False, fetch_blocked=False,
                    result_type='UNKNOWN', verification_level='UNVERIFIED', image_url=None,
                    rejection_code='offline_unrecorded_response',
                    reason='Original page response was never captured; replay cannot certify this URL.')
            # Consume the recorded inspection cost serially. This intentionally
            # does not reconstruct overlapping domain/round wall time.
            clock.now += costs.get(url, 0.)
            return deepcopy(recorded)
    r = module.ProgressiveRetriever(Provider(), Pages(), Settings(_env_file=None))
    r.requirement = RequirementData.model_validate(data['requirement'])
    r.deadline = clock.now + r.settings.live_search_budget_seconds
    try:
        for rd in data['historical_performance']['diagnostics']['rounds']:
            if not r.can_continue(): break
            await r.pass_queries(rd['kind'], rd['queries_executed'])
        if hasattr(r, 'recover_direct'): await r.recover_direct()
        if r.enough(): r.stop_reason = 'target_reached'
        elif r.remaining() <= 0: r.stop_reason = 'time_budget'
        elif len(r.product_attempts) >= r.max_cap: r.stop_reason = 'candidate_budget'
        elif len(r.inspected_urls) >= r.max_page_requests: r.stop_reason = 'page_budget'
        elif getattr(r, 'recovery_urls', []): r.stop_reason = 'recovery_opportunities_exhausted'
        summary = r.summary()
        return dict(provider_rounds=len(r.rounds), provider_calls=len(r.queries), page_attempts=len(requests),
            direct_product_attempts=len(r.product_attempts),
            evidence_only_attempts=sum(not by_url[u]['proof'].get('product_page_valid') for u in requests),
            evidence_definition='Requested URLs without a recorded valid offer, including unknown and failed pages.',
            explicit_editorial_attempts=sum('/newsroom/' in u or '/events' in u for u in requests),
            oos_verified=sum(p.get('product_page_valid', False) and is_unavailable(p.get('availability'))
                             for p in (s.page_validation for s in r.sources.values())),
            eligible_verified=summary['valid_offers'],
            resource_budget_rejections=sum(s.page_validation.get('rejection_code') == 'resource_budget' for s in r.sources.values()),
            stop_reason=r.stop_reason, attempted_urls=requests, unrecorded_response_urls=unrecorded,
            recovery=summary.get('direct_recovery'),
            cellphones_attempts=[u for u in requests if urlsplit(u).hostname == 'cellphones.com.vn'])
    finally:
        module.time = original_time


async def main():
    import socket
    # Event loop already exists; fail closed on any accidental external I/O.
    original_connect = socket.socket.connect
    def forbidden(*args, **kwargs): raise AssertionError('Offline replay forbids network')
    socket.socket.connect = forbidden
    try:
        data = json.loads((ROOT / 'tests/fixtures/live_oos_05479307.json').read_text(encoding='utf-8'))
        baseline = load_baseline('progressive_retrieval')
        old_diagnostics = load_baseline('retrieval_diagnostics')
        baseline.source_plan = old_diagnostics.source_plan
        baseline.conversion_stats = old_diagnostics.conversion_stats
        from app.services.search import progressive_retrieval as current
        output = dict(session_id=data['session_id'], baseline='v1.2.1',
            method='Fixed archived query rounds, source snippets and proofs. Serial virtual recorded inspection costs. No original HTML, real HTTP, query reordering simulation or concurrency/Live latency claim.',
            historical={k: data['historical_performance']['diagnostics'][k] for k in
                        ('provider_calls', 'round_count', 'page_attempts', 'product_attempts', 'stop_reason')},
            before=await replay(data, baseline), after=await replay(data, current),
            live_success_claimed=False, network_calls=0)
        (ROOT.parent / 'docs/LIVE_OOS_RECOVERY_REPLAY.json').write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({k:{f:v for f,v in output[k].items() if f not in
              {'attempted_urls', 'evidence_definition', 'cellphones_attempts'}} for k in ('before','after')},
              ensure_ascii=False, indent=2))
    finally:
        socket.socket.connect = original_connect


if __name__ == '__main__': asyncio.run(main())
