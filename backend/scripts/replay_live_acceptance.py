"""Replay stored proofs offline; not a reconstruction of original HTTP timing."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import Settings
from app.schemas.requirement import RequirementData
from app.services.search.base import SearchResult
from app.services.search.progressive_retrieval import ProgressiveRetriever


async def main():
    data = json.loads((ROOT / 'tests/fixtures/live_acceptance_0d288192.json').read_text(encoding='utf-8'))
    observations = {o['url']: o for o in data['observations']}

    class Provider:
        def __init__(self): self.calls = []

        async def search(self, query, limit):
            self.calls.append(query)
            return [SearchResult(title=o['title'], url=o['url'], content=o['content']) for o in observations.values()]

    class Resolver:
        def __init__(self): self.calls = []

        async def inspect(self, url, **kwargs):
            self.calls.append(url)
            return deepcopy(observations[url]['proof'])

        async def _image_loads(self, url):
            raise AssertionError('No image fetch permitted in offline replay')

    provider, resolver = Provider(), Resolver()
    r = ProgressiveRetriever(provider, resolver, Settings(_env_file=None, demo_mode=False))
    await r.run(['recorded observations'], RequirementData.model_validate(data['result']['requirement']))
    result = dict(
        method='Offline stored-proof replay: all 39 observations returned on every provider call, '
               'not original Tavily ordering/HTML. No network/database writes.',
        pages_requested=len(resolver.calls), provider_calls=len(provider.calls), stop_reason=r.stop_reason,
        direct_candidates=r.summary()['conversion']['direct_product_candidates'],
        eligible_offers=r.summary()['valid_offers'], hints_after=r.model_hints(), queries=provider.calls,
        rounds=[{k: v for k, v in rd.items() if k in ('kind', 'new_verified_products', 'no_progress_rounds')}
                for rd in r.rounds],
    )
    target = ROOT.parent / 'docs/LIVE_ACCEPTANCE_DIAGNOSIS_REPLAY.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('pages_requested', 'provider_calls', 'stop_reason',
                                           'direct_candidates', 'eligible_offers')}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
