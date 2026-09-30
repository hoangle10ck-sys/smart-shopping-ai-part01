"""Audit archived proofs and query responses offline. No database/network access."""
import asyncio
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.core.config import Settings
from app.schemas.requirement import RequirementData
from app.schemas.search import SearchSourceItem
from app.services.search.base import SearchResult
from app.services.search.progressive_retrieval import ProgressiveRetriever
from app.services.search.retrieval_diagnostics import source_plan


def shape(row):
    path=urlsplit(row['url']).path
    # Explicitly audit the three observed catalog URL shapes. This does not
    # change runtime validation or certify any page as a product.
    if path.startswith('/bo-loc/') or re.fullmatch(r'/dtdd-[a-z]+|/dien-thoai-\d+-\d+-trieu.html',path):
        return 'category_listing'
    source=SearchSourceItem(url=row['url'],title=row['title'],content=row['content'])
    if source_plan(source)=='metadata':return 'article_news_review_video'
    return 'direct_product' if row['proof'].get('product_page_valid') else 'direct_looking_unverified'


async def main():
    data=json.loads((ROOT/'tests/fixtures/live_final_offer_dfc295bb.json').read_text(encoding='utf-8'))
    rows=data['observations'];by_url={r['url']:r for r in rows}
    diagnostics=data['snapshot']['retrieval_diagnostics']
    perf=diagnostics[-1]['performance']
    audit=[]
    for i,row in enumerate(rows,1):
        proof=row['proof']
        audit.append(dict(index=i,url=row['url'],shape=shape(row),query=row['query'],
            requested=proof.get('page_requested',False),fetched=proof.get('page_fetched',False),
            verified=proof.get('product_page_valid',False),availability=proof.get('availability'),
            rejection_code=proof.get('rejection_code'),reason=proof.get('reason')))
    archived_queries={d['query']:list(dict.fromkeys(r['URL'] for r in d.get('source_audit',[])))
                      for d in diagnostics if 'query' in d}
    class Provider:
        def __init__(self):self.calls=[];self.unrecorded=[]
        async def search(self,query,limit):
            self.calls.append(query)
            if query not in archived_queries:self.unrecorded.append(query)
            return [SearchResult(title=by_url[u]['title'],url=u,content=by_url[u]['content'])
                    for u in archived_queries.get(query,[]) if u in by_url]
    class Pages:
        def __init__(self):self.calls=[]
        async def inspect(self,url,**kwargs):
            self.calls.append(url)
            return deepcopy(by_url[url]['proof'])
        async def _image_loads(self,url):raise AssertionError('Offline audit cannot load images')
    provider,pages=Provider(),Pages()
    retriever=ProgressiveRetriever(provider,pages,Settings(_env_file=None))
    requirement=RequirementData.model_validate(data['snapshot']['result']['requirement'])
    initial=[d['query'] for d in diagnostics if d.get('pass')=='requirement']
    await retriever.run(initial,requirement)
    result=dict(session_id=data['session']['id'],source_count=len(rows),
        shape_counts=dict(Counter(r['shape'] for r in audit)),
        confirmed_valid_direct_false_negatives=0,
        classification_note='No omitted valid offer established by stored proof. Original HTML absent; unverified pages are not certified false-negatives.',
        historical_rejection_counts=perf['diagnostics']['conversion']['reason_counts'],
        historical_duplicate_provider_rows=perf['diagnostics']['rejected_duplicate'],
        historical_timings=perf['timings'],historical_domain_budgets=perf['diagnostics']['domain_budgets'],
        historical_rounds=perf['diagnostics']['rounds'],sources=audit,
        alternate_merchant_trace=[dict(query=d['query'],provider_results=d['result_count'],domains=d['result_domains'],
            urls=archived_queries[d['query']],model_progress=d.get('model_progress',[]))
            for d in diagnostics if d.get('pass')=='merchant_products'],
        offline_replay=dict(method='Archived query responses/proofs only. Unrecorded queries return empty, not invented offers. No HTML/timing reconstruction.',
            queries=provider.calls,unrecorded_queries=provider.unrecorded,page_urls=pages.calls,
            direct_candidates=retriever.summary()['conversion']['direct_product_candidates'],
            eligible_offers=retriever.summary()['valid_offers'],stop_reason=retriever.stop_reason,
            model_hints=retriever.model_hints(),rounds=retriever.rounds))
    (ROOT.parent/'docs/FINAL_LIVE_OFFER_RECOVERY_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('source_count','shape_counts','historical_rejection_counts')},ensure_ascii=False))
    print(json.dumps({k:result['offline_replay'][k] for k in ('queries','unrecorded_queries','direct_candidates','eligible_offers','stop_reason')},ensure_ascii=False))


if __name__=='__main__':asyncio.run(main())
