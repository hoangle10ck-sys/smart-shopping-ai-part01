"""Replay archived responses only; absent query/page responses remain unknown."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core.config import Settings
from app.schemas.requirement import RequirementData
from app.services.search.base import SearchResult
from app.services.search import progressive_retrieval as module
from scripts.replay_oos_recovery import Clock


async def replay(data):
    clock = Clock()
    original_time = module.time
    module.time = clock
    rows = {r['url']: r for r in data['observations']}
    queries = {q['query']: q['urls'] for q in data['queries']}
    costs = {p['url']: p['inspection_ms']/1000 for p in data['historical_performance']['diagnostics']['page_timings']}
    requested, missing_pages, missing_queries, executed = [], [], [], []

    class Provider:
        async def search(self, query, limit):
            executed.append(query)
            if query not in queries: missing_queries.append(query)
            return [SearchResult(url=u, title=rows[u]['title'], content=rows[u]['content'])
                    for u in queries.get(query, []) if u in rows]

    class Pages:
        async def inspect(self, url, **kwargs):
            requested.append(url)
            p = rows.get(url, {}).get('proof', {})
            if not p.get('page_requested'):
                missing_pages.append(url)
                return dict(product_page_valid=False, page_fetched=False, fetch_blocked=False,
                            result_type='UNKNOWN', verification_level='UNVERIFIED', image_url=None,
                            rejection_code='offline_unrecorded_response')
            clock.now += costs.get(url, 0)
            return deepcopy(p)

        async def resolve_image(self, source, proof):
            return None

    r = module.ProgressiveRetriever(Provider(), Pages(), Settings(_env_file=None))
    try:
        req = RequirementData.model_validate(data['requirement'])
        initial = data['historical_performance']['diagnostics']['rounds'][0]['queries_executed']
        await r.run(initial, req)
        retrieval_missing_pages = list(missing_pages)
        # A separate replay of the known unresolved URL exercises scheduling,
        # without injecting that URL into a counterfactual provider response.
        unresolved = rows['https://www.duchuymobile.com/nothing-phone-4a']
        from app.schemas.search import SearchSourceItem
        opportunity = module.ProgressiveRetriever(Provider(), Pages(), Settings(_env_file=None))
        opportunity.requirement = req
        opportunity.deadline = clock.now + 10
        for row in data['observations']:
            if row['proof'].get('product_page_valid'):
                opportunity.sources[row['url']] = SearchSourceItem(url=row['url'], title=row['title'],
                    content=row['content'], page_validation=deepcopy(row['proof']))
        s = SearchSourceItem(url=unresolved['url'], title=unresolved['title'], content=unresolved['content'],
                            page_validation=deepcopy(unresolved['proof']))
        opportunity.sources[s.url] = s
        opportunity.plans[s.url] = 'product'
        await opportunity.recover_direct()
        return dict(queries=executed, page_attempts=len(r.inspected_urls), product_attempts=len(r.product_attempts),
                    eligible=r.satisfaction()['eligible_offers'], stop_reason=r.stop_reason,
                    attempted_urls=sorted(r.inspected_urls), recovery=r.summary()['direct_recovery'],
                    final_model_hints=r.model_hints(), missing_queries=missing_queries,
                    missing_page_responses=retrieval_missing_pages,
                    known_opportunity_missing_pages=missing_pages[len(retrieval_missing_pages):],
                    known_unresolved_opportunity=opportunity.summary()['direct_recovery'],
                    known_unresolved_eligible=opportunity.satisfaction()['eligible_offers'])
    finally:
        module.time = original_time


async def main(label):
    original = socket.socket.connect
    def forbidden(*args, **kwargs): raise AssertionError('Offline replay forbids network')
    socket.socket.connect = forbidden
    try:
        data = json.loads((ROOT/'tests/fixtures/live_category_ab719401.json').read_text(encoding='utf-8'))
        result = await replay(data)
        path = ROOT.parent/'docs/CATEGORY_RECOVERY_REPLAY.json'
        output = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        output.update(session_id=data['session_id'], network_calls=0, live_success_claimed=False,
            method='Actual query policy against archived query-response map, serial recorded inspection costs. Missing queries return no recorded rows; not Live empty responses. Separate known-opportunity probe does not invent a provider response.')
        output[label] = result
        output[label+'_source_sha256'] = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        output['historical'] = {k:data['historical_performance']['diagnostics'][k] for k in
            ('product_attempts','page_attempts','stop_reason','eligible_offers','direct_recovery')}
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        socket.socket.connect = original


if __name__ == '__main__': asyncio.run(main(sys.argv[1]))
