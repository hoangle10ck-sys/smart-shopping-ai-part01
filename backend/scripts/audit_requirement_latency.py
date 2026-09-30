"""Offline audit of persisted ce69ae93 data; never opens DB or network."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.core.config import Settings
from app.schemas.ranking import ScoringCandidate
from app.schemas.requirement import RequirementData
from app.services.scoring.scoring_engine import ScoringEngine
from app.services.search.base import SearchResult
from app.services.search.progressive_retrieval import ProgressiveRetriever


async def replay(data):
    by_url={r['url']:r for r in data['observations']}
    diagnostics=data['snapshot']['retrieval_diagnostics']
    by_query={d['query']:[v['URL'] for v in d.get('source_audit',[])] for d in diagnostics if 'query' in d}
    class Provider:
        def __init__(self):self.calls=[]
        async def search(self,q,limit):
            self.calls.append(q)
            return [SearchResult(url=u,title=by_url[u]['title'],content=by_url[u]['content'])
                    for u in dict.fromkeys(by_query[q]) if u in by_url]
    class Pages:
        async def inspect(self,url,**kwargs):return deepcopy(by_url[url]['proof'])
    provider=Provider();r=ProgressiveRetriever(provider,Pages(),Settings(_env_file=None))
    r.requirement=RequirementData.model_validate(data['snapshot']['result']['requirement'])
    r.deadline=time.monotonic()+30
    for row in diagnostics[-1]['performance']['diagnostics']['rounds']:
        if not r.can_continue():break
        await r.pass_queries(row['kind'],row['queries_executed'])
    return dict(method='Recorded query sequence, archived rows/proofs only; stop checked between rounds. Not a replay of changed model-query order or Live timing.',
        queries=provider.calls,rounds=r.rounds,stop_reason=r.stop_reason,page_attempts=len(r.inspected_urls),
        eligible_urls=[s.url for s in r.sources.values() if r.eligible(s.page_validation)],
        absent_rows=sorted({u for urls in by_query.values() for u in urls if u not in by_url}))


async def main():
    data=json.loads((ROOT/'tests/fixtures/live_match_ce69ae93.json').read_text(encoding='utf8'))
    prev=json.loads((ROOT/'tests/fixtures/live_relevance_981f372a.json').read_text(encoding='utf8'))
    diag=data['snapshot']['retrieval_diagnostics'];p=diag[-1]['performance'];d=p['diagnostics']
    old=prev['snapshot']['retrieval_diagnostics'][-1]['performance']['timings']
    req=RequirementData.model_validate(data['snapshot']['result']['requirement']);engine=ScoringEngine()
    comparisons=[]
    for rec in data['snapshot']['result']['recommendations']:
        candidate=ScoringCandidate.model_validate(rec)
        comparisons.append(dict(name=rec['name'],price=rec['price'],url=rec['product_url'],
            specifications=rec['specifications'],historical_matches=rec['requirement_matches'],
            corrected_matches=[m.model_dump() for m in engine.requirement_matches(candidate,req)],
            historical_score=rec['score'],corrected_score=engine.score(candidate,req).model_dump(),
            historical_explanation=rec['explanation']))
    # Preserve historical source reliability: it is part of the candidate, not
    # an explanation or an inferred confidence score.
    originals={c['product_id']:c for c in data['snapshot']['result']['candidates']}
    for rec,comparison in zip(data['snapshot']['result']['recommendations'],comparisons):
        comparison['corrected_score']=engine.score(ScoringCandidate.model_validate(originals[rec['product_id']]),req).model_dump()
    rounds=[];queries={q['query']:q for q in diag if 'query' in q};previous_eligible=0
    for row in d['rounds']:
        rounds.append({**row,'new_eligible_offers':row['cumulative_valid_offers']-previous_eligible,
            'queries':[dict(query=q,provider_ms=queries[q]['provider_wait_ms'],results=queries[q]['result_count'],
                            error=queries[q].get('error_kind')) for q in row['queries_executed']]})
        previous_eligible=row['cumulative_valid_offers']
    audit=dict(session=data['session'],timings=p['timings'],delta_previous_ms={k:round(v-old[k],3) for k,v in p['timings'].items()},
        counters={k:d[k] for k in ('provider_calls','round_count','page_attempts','product_attempts','candidate_cap','stop_reason','eligible_offers')},
        rounds=rounds,domain_budgets=d['domain_budgets'],page_timings=d['page_timings'],
        recommendations=comparisons,last_model_progress=next(q['model_progress'] for q in reversed(diag) if 'model_progress' in q),
        replay=await replay(data))
    (ROOT.parent/'docs/REQUIREMENT_LATENCY_AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    lines=['# Requirement match / latency — ce69ae93', '',
        'Read-only persisted-session audit; no Live requests. Original snapshot and production database remain untouched.',
        '', '## A. Exact persisted timing', '', '| Metric | Latest ms | Delta vs 54.266s session |', '|---|---:|---:|']
    lines += [f'| {k} | {v:.3f} | {audit["delta_previous_ms"][k]:+.3f} |' for k,v in p['timings'].items()]
    lines += ['', 'Total increased 18.452181s; explanation increased 19.388317s, while provider search decreased 5.547875s. Three explanations are generated sequentially by RecommendationService. Stored modes: Gemini, Gemini, fallback. The snapshot has no per-product/provider-attempt timings or error details; it cannot establish which call timed out or exhausted quota.',
        'Analysis/clarification/query-generation zeros are unmeasured in this separate search request, not zero-cost operations. Fetch is aggregate overlapping work; verification/discovery timers nest inside round wall times and must not be summed as separate stages.',
        f'Sum of retrieval-round wall durations: {sum(r["duration_ms"] for r in rounds):.3f}ms. Explanation total: {p["timings"]["explanation_ms"]:.3f}ms. Image resolution/postprocessing have no dedicated historical timing; residual time cannot be assigned precisely.',
        '', '## B. Rounds and counts', '',
        '9 provider calls, 7 rounds, 23 page attempts, 20 product attempts. Stop reason: candidate_budget; cap=20. 43 discovered URLs, 41 persisted observations, 4 candidates, 3 eligible offers. The two remaining pending sources have no persisted page proof.',
        '', '| Round | Wall ms | New direct/model/merchant/eligible | Cumulative pages/eligible |', '|---|---:|---|---|']
    lines += [f'| {r["round"]} {r["kind"]} | {r["duration_ms"]} | {r["new_direct_urls"]}/{r["new_model_hints"]}/{r["new_merchant_domains"]}/{r["new_eligible_offers"]} | {r["cumulative_pages_requested"]}/{r["cumulative_valid_offers"]} |' for r in rounds]
    for r in rounds:
        lines += ['',f'Round {r["round"]}:']+[f'- `{q["query"]}` — provider {q["provider_ms"]}ms; {q["results"]} rows; error={q["error"]}.' for q in r['queries']]
    lines += ['', 'Largest round: #4, 6927.574ms, no new eligible offer; provider wait 4656.937ms. Round #6 (6668.800ms) produced the third eligible offer and must be preserved. Round #7 cost 6360.039ms, added zero eligible offers, and exhausted the candidate cap. Its last provider call alone took 5095.521ms.',
        '', '## C–D. Deterministic root causes', '',
        '- Battery parsed a generic decimal string: 8.500 became 8.5. The mAh-specific parser now recognizes dot/comma thousands grouping, retaining true decimals and rejecting malformed groups. The phone threshold is still 4000mAh; hours, weight and RAM parsers are unchanged.',
        '- Exact spec-key matching omitted camera sau/trước and rear/front camera. Generic camera now reads these aliases. OIS remains the pre-existing qualitative rubric; megapixels alone remain UNKNOWN. An explicitly requested front camera cannot borrow rear-camera OIS.',
        '', '| Product | Old camera / battery | Corrected camera / battery | Old final | Corrected final |','|---|---|---|---:|---:|']
    for c in comparisons:
        lines.append(f'| {c["name"]} | {" / ".join(m["status"] for m in c["historical_matches"])} | {" / ".join(m["status"] for m in c["corrected_matches"])} | {c["historical_score"]["final_score"]} | {c["corrected_score"]["final_score"]} |')
    lines += ['', 'Corrected scores are offline recomputations of the archived candidates, not a rewrite of historical recommendations. The score weights remain 25/30/20/10/5/10.',
        '', '## E. Explanation consistency', '',
        'Previously the payload omitted structured requirement_matches and returned arbitrary LLM text without a semantic gate. Gemini therefore asserted camera suitability while the matcher reported UNKNOWN.',
        'The payload now includes deterministic matches plus approved statements about matches, budget, availability and evidence. LLMs may select/order those statements. Every response field is checked against its approved values; unsupported narrative returns deterministic fallback immediately, without a repair call. Required caveats are restored if omitted. This intentionally limits paraphrasing to guarantee consistency; it does not claim that keyword detection can validate arbitrary prose.',
        'Flexible budget wording now says preferred range/fallback rather than falsely treating the target as a hard maximum. Missing stock stays unknown. No LLM can alter price, specifications or scores.',
        '', '## F. Budget/retrieval and fixed-sequence replay', '',
        'All three observed prices (13.99m, 15.5m, 19.49m) remain eligible FLEXIBLE_TARGET fallbacks. Earlier code promoted structured discovery hints with missing prices as if they fit the budget. Now known near-range evidence ranks before unknown and far-range hints; verified price is attached only to the same observed model. Near-range unseen alternatives are prioritized before far fallback recovery.',
        'Stop after at least three unique eligible offers with zero budget-fit scores when no unsearched model has explicit near-range price evidence. One/two weak offers still allow bounded discovery; explicit near-range alternatives still continue. Deadlines, page/domain bounds, OOS filtering and strict page validation stay unchanged.',
        audit['replay']['method'],
        f'Replay: provider queries 9→{len(audit["replay"]["queries"])}; rounds 7→{len(audit["replay"]["rounds"])}; page attempts 23→{audit["replay"]["page_attempts"]}; retained eligible URLs={len(audit["replay"]["eligible_urls"])}; stop={audit["replay"]["stop_reason"]}.',
        'The skipped historical round cost 6.360s then; this is not a measurement or prediction of post-fix Live latency. Changed query ordering is not reconstructed for unexecuted queries.',
        '', '## G–M. Validation', '', 'Final command results are recorded in the validation appendix.',
        '', '## N. Limitations', '',
        '- No post-fix Live latency/recall measured. The main latency cost, sequential provider explanation calls, is not proven faster by this offline run.',
        '- Exact LLM paraphrases outside approved statements fall back, even when plausibly correct. This trades phrasing variety for verifiable consistency.',
        '- Price-topic article hints do not establish a near-budget offer. After the fallback minimum, unknown-price models may remain unsearched; this is a bounded recall/latency tradeoff, not a hard filter.',
        '- OIS and 4000mAh are existing heuristics, not new measurements of camera quality or battery runtime.',
        '- Historical snapshots preserve their recorded matches/scores/explanations. No backfill of the real database.',
        '- Cache retrieval version 8 avoids reusing earlier retrieval behavior; cache tests include v7 rejection. No schema/routes/UI/dependency changes.',
        '', 'No Live API, reset/undo/restore/clean, commit, merge or tag.']
    (ROOT.parent/'docs/REQUIREMENT_LATENCY_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps(dict(counters=audit['counters'],scores=[(c['name'],c['corrected_score']['final_score']) for c in comparisons],
        replay={k:audit['replay'][k] for k in ('stop_reason','page_attempts','eligible_urls')},replay_calls=len(audit['replay']['queries'])),ensure_ascii=False))


if __name__=='__main__':asyncio.run(main())
