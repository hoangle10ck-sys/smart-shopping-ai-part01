"""Reproducible archived-session audit. No database, HTTP or real providers."""
import asyncio
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import time
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.core.config import Settings
from app.schemas.requirement import RequirementData
from app.schemas.search import SearchSourceItem
from app.services.search.base import SearchResult
from app.services.search.progressive_retrieval import ProgressiveRetriever
from app.services.search.retrieval_diagnostics import source_plan
from app.services.search.retrieval_relevance import irrelevant_reason


def shape(row, req, children):
    s=SearchSourceItem(**{k:row[k] for k in ('url','title','content')})
    p=row['proof']; path=urlsplit(row['url']).path
    if irrelevant_reason(s,req):return 'irrelevant_noise'
    if p.get('product_page_valid'):return 'direct_product'
    if row['url'] in children:return 'child_product'
    if (source_plan(s)=='discovery' or path.startswith(('/bo-loc/','/tags/'))
            or re.search(r'/dien-thoai-\d+-\d+-trieu\.html$',path)):
        return 'listing'
    if (source_plan(s)=='metadata' or p.get('result_type') in {'ARTICLE','NEWS','REVIEW'}
            or '/newsroom/' in path):return 'article_review_news_video'
    return 'likely_product_unverified'


async def scheduling_replay(rows,req,gate):
    """Fixed batch, frozen page proofs: isolate relevance-gate work savings.

    Not a provider replay: all 48 archived rows are supplied together. No new
    query responses, offers, images or HTML are fabricated.
    """
    by_url={r['url']:r for r in rows}
    class Provider:
        async def search(self,q,limit):
            return [SearchResult(**{k:r[k] for k in ('url','title','content')}) for r in rows]
    class Pages:
        def __init__(self):self.calls=[]
        async def inspect(self,url,**kwargs):
            self.calls.append(url)
            return deepcopy(by_url[url]['proof'])
    pages=Pages(); r=ProgressiveRetriever(Provider(),pages,Settings(_env_file=None))
    r.requirement=req; r.deadline=time.monotonic()+30
    with patch('app.services.search.progressive_retrieval.irrelevant_reason',
               irrelevant_reason if gate else lambda *a:None):
        await r.pass_queries('fixed_archived_batch',['offline fixture'])
    return dict(page_attempts=len(pages.calls),page_urls=pages.calls,
        verified=sum(bool(s.page_validation.get('product_page_valid')) for s in r.sources.values()),
        eligible_urls=[s.url for s in r.sources.values() if r.eligible(s.page_validation)],
        source_count=len(r.sources),model_hints=r.model_hints(),rounds=r.rounds)


async def main():
    data=json.loads((ROOT/'tests/fixtures/live_relevance_981f372a.json').read_text(encoding='utf8'))
    old=json.loads((ROOT/'tests/fixtures/live_final_offer_dfc295bb.json').read_text(encoding='utf8'))
    diag=data['snapshot']['retrieval_diagnostics']; perf=diag[-1]['performance']; pd=perf['diagnostics']
    op=old['snapshot']['retrieval_diagnostics'][-1]['performance']
    req=RequirementData.model_validate(data['snapshot']['result']['requirement'])
    rows=data['observations']; new_urls={r['url'] for r in rows}; old_urls={r['url'] for r in old['observations']}
    audits=[]
    for i,row in enumerate(rows,1):
        p=row['proof']
        audits.append(dict(index=i,url=row['url'],title=row['title'],query=row['query'],
            classification=shape(row,req,pd['child_product_urls']),
            requested=p.get('page_requested',False),fetched=p.get('page_fetched',False),
            verified=p.get('product_page_valid',False),availability=p.get('availability'),
            rejection_code=p.get('rejection_code'),fetch_failure=p.get('fetch_failure'),reason=p.get('reason')))
    queries={d['query']:d for d in diag if 'query' in d}
    rounds=[]
    for r in pd['rounds']:
        rounds.append({**r,'query_details':[dict(query=q,provider_ms=queries[q]['provider_wait_ms'],
            results=queries[q]['result_count'],errors=queries[q].get('error_kind')) for q in r['queries_executed']],
            'continuation_note': 'page_budget reached' if r['round']==len(pd['rounds']) else
                ('not satisfied; novelty reset no_progress' if r['no_progress_rounds']==0 else
                 'not satisfied; one stale round below bounded no_progress limit')})
    counts=Counter(a['classification'] for a in audits)
    recs=[{k:r.get(k) for k in ('name','price','merchant','product_url','availability','verification_level','specifications','score','requirement_matches')}
          for r in data['snapshot']['result']['recommendations']]
    before=await scheduling_replay(rows,req,False); after=await scheduling_replay(rows,req,True)
    audit=dict(session=data['session'],source_counts=dict(counts),sources=audits,
        timings=perf['timings'],previous_timings=op['timings'],
        delta_ms={k:round(v-op['timings'].get(k,0),3) for k,v in perf['timings'].items()},
        previous_counts={k:op['diagnostics'][k] for k in ('provider_calls','round_count','page_attempts','stop_reason')},
        current_counts={k:pd[k] for k in ('provider_calls','round_count','page_attempts','stop_reason')},
        source_delta=dict(old=33,new=48,overlap=len(new_urls&old_urls),new_urls=sorted(new_urls-old_urls),removed_urls=sorted(old_urls-new_urls),
            provider_rows=sum(q['result_count'] for q in queries.values()),
            previous_provider_rows=sum(d['result_count'] for d in old['snapshot']['retrieval_diagnostics'] if 'query' in d)),
        rounds=rounds,domain_budgets=pd['domain_budgets'],page_timings=pd['page_timings'],
        recommendations=recs,last_model_progress=next(d['model_progress'] for d in reversed(diag) if 'model_progress' in d),
        fixture=dict(method='Fixed batch of all 48 archived sources, frozen page proofs. Only relevance gate toggled. Not Live latency or a replay of unrecorded queries.',before=before,after=after))
    target=ROOT.parent/'docs/PERFORMANCE_RELEVANCE_AUDIT.json'
    target.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    lines=['# Performance / relevance audit — session 981f372a',
        '', 'Offline audit of saved evidence. No Live API; production SQLite was opened read-only only when exporting the fixture.',
        '', '## A–B. Timing and latency', '',
        '| Metric | Previous ms | Latest ms | Delta ms |','|---|---:|---:|---:|']
    for k,v in perf['timings'].items():lines.append(f'| {k} | {op["timings"].get(k,0):.3f} | {v:.3f} | {audit["delta_ms"][k]:+.3f} |')
    lines += ['', 'Analysis/clarification/query-generation zeros mean not measured in this search request. Their separate request times are not recoverable from this snapshot.',
        'Provider timing is accumulated batch wall time. Page-fetch and verification timing can overlap/nest with rounds; these metrics must not be summed as disjoint stages.',
        f'Total recorded round wall time: {sum(r["duration_ms"] for r in rounds):.3f} ms. Image resolution has no separate persisted timer; the residual cannot be attributed precisely.',
        'Measured increases: 9→12 provider calls, 6→9 rounds, 15→24 page attempts. Provider wait +10.982s, verification batch wall +3.395s, discovery CPU +1.904s; explanation adds 4.156s. The provider/network component dominates. No evidence establishes a provider quota error.',
        '', '### Every retrieval round', '',
        '| Round | Wall ms | New direct / merchant / model / child | Cumulative pages / eligible | Continue/stop |',
        '|---|---:|---|---|---|']
    for r in rounds:
        lines.append(f'| {r["round"]} {r["kind"]} | {r["duration_ms"]} | {r["new_direct_urls"]} / {r["new_merchant_domains"]} / {r["new_model_hints"]} / {r["new_child_urls"]} | {r["cumulative_pages_requested"]} / {r["cumulative_valid_offers"]} | {r["continuation_note"]} |')
    for r in rounds:
        lines += ['', f'Round {r["round"]} queries:']
        lines += [f'- `{q["query"]}` — {q["provider_ms"]} ms, {q["results"]} rows; error={q["errors"]}.' for q in r['query_details']]
    lines += ['', '### Domain budgets / cancellation', '', '| Domain | Active ms | Attempts | Consecutive failures | Skipped |','|---|---:|---:|---:|---:|']
    for domain,w in pd['domain_budgets'].items():lines.append(f'| {domain} | {w["active_ms"]} | {w["attempts"]} | {w["failures"]} | {w["skipped"]} |')
    lines += ['', 'Domain active time is union wall time, not a sum of parallel fetches. CellphoneS exhausted the 6000ms domain budget (6004ms including cancellation overhead). Two MTCGAME failures suppressed its third URL. The stored proof for CellphoneS Reno10 records timeout. Other HTTP/network failures are listed in the JSON; no historical unclosed-client event can be inferred from this snapshot.',
        '', '## C–D. Source expansion and relevance', '',
        f'Provider rows {audit["source_delta"]["previous_provider_rows"]}→{audit["source_delta"]["provider_rows"]}; unique sources 33→48. URL overlap={audit["source_delta"]["overlap"]}, added={len(new_urls-old_urls)}, absent from latest={len(old_urls-new_urls)}. This is not simply the same 33 plus 15.',
        f'Classification: {dict(counts)}; child products=0.',
        'Four currency/game-credit rows came from the full quoted OPPO A5 query. Wikipedia/Ericsson came from the full quoted OPPO Reno10 query. No saved query was standalone 5G or VND. The provider drifted; the scheduler lacked an explicit irrelevant-intent gate.',
        'Old-phone articles were evidence-only but seeded old/cheap models and new-model progress. Their content was not certified product evidence. Repeated broad discovery and Reno 10/Reno10 alias splitting used bounded query/page capacity.',
        '', '## E. Why only two weak offers', '',
        'Stop reason was page_budget (24), not target satisfaction. Four verified offers include two out-of-stock and two eligible A52 seller offers. Both eligible offers have empty specifications and camera/battery UNKNOWN; both lie below the preferred 9.4–10.6m window. They remain valid flexible-budget fallback offers.',
        'A52 Like New: 2,499,000 VND, budget=0, requirement=0, final=36. A52 Anh Duc: 8,190,000 VND, budget=24.58, requirement=0, final=31.15. Fixed weights are unchanged.',
        'Observed but unsearched: Xiaomi 15T Pro, Redmi Note 14 Pro, OPPO Reno13 F, Redmi Note 15 and other models (complete states in JSON). Their actual in-range, in-stock offers are NOT established by article mentions. Exact Xiaomi 15T is a regression fixture, not a certified latest-session offer.',
        'Model order was source/discovery order, not a preference for easier direct pages. It nevertheless selected older A52 ahead of later relevant mentions. Live success for those alternatives cannot be inferred without provider results.',
        '', '## F–G. Changes', '',
        '- Explicit currency/game-credit and generic-network intents: retain diagnostic metadata, zero page fetch, no model/merchant/direct progress. No URL/domain blacklist. Unknown product identity remains discoverable.',
        '- Use the article title’s explicit budget topic to prioritize observed model hints. This does not assign a price to a model or change offer evidence.',
        '- Treat Reno 10/Reno10 capacity/connectivity spellings as the same lookup budget only; catalog/offer identities remain unchanged.',
        '- Prefer unseen alternatives when existing offers are weak; avoid generic commercial/dealer rounds while useful unsearched models exist.',
        '- Keep eligible and strong-fit counts separate. Target 3/5 still stops early; two strong models stop after a stale round when no unseen model remains. Two weak offers do not cause a quality stop.',
        '- Standalone 5G/VND cannot form model queries; Xiaomi 15T remains valid. Cache retrieval version 7 prevents reuse of old orchestration results.',
        '', '## H. Fixed-input fixture before / after', '',
        audit['fixture']['method'],
        f'Page attempts: {before["page_attempts"]}→{after["page_attempts"]}; verified: {before["verified"]}→{after["verified"]}; eligible: {len(before["eligible_urls"])}→{len(after["eligible_urls"])}.',
        'This isolates scheduling; it is NOT a new Live benchmark or evidence of a particular post-fix response time.',
        '', '## I–N. Validation', '', 'See final validation appendix below.',
        '', '## O. Remaining limitations', '',
        '- Live latency/recall after the fix is unmeasured, as requested. No claimed 54s→X Live improvement.',
        '- Archived HTML and responses for unexecuted queries are absent. No omitted URL can be declared a valid missed offer from these records alone.',
        '- Condition is only present in names such as Like New/trôi bảo hành; there is no structured condition field or price normalization by condition. No new used/refurbished exclusion policy.',
        '- Article budget-topic relevance is a lookup hint, not proof of current price, stock, camera or battery. Provider freshness and supported model parsing remain limited.',
        '- Numeric timings overlap; separate historical analysis/image durations cannot be reconstructed exactly.',
        '', '## Full 48-source audit', '', '| # | Classification | Requested | URL |','|---|---|---|---|']
    lines += [f'| {a["index"]} | {a["classification"]} | {a["requested"]} | {a["url"]} |' for a in audits]
    (ROOT.parent/'docs/PERFORMANCE_RELEVANCE_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps(dict(counts=dict(counts),source_delta={k:v for k,v in audit['source_delta'].items() if not isinstance(v,list)},
        fixture={label:{k:r[k] for k in ('page_attempts','verified','eligible_urls')} for label,r in [('before',before),('after',after)]}),ensure_ascii=False))


if __name__=='__main__':asyncio.run(main())
