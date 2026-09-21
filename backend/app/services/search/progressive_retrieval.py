"""Bounded Live retrieval: requirements, commerce, then discovered merchants.

No persistence here. A failed retrieval cannot delete any previous session data.
"""
import asyncio
import time
import re
from collections import Counter
from urllib.parse import urlsplit

from app.services.extraction.product_page_validator import classify_source, identity_tokens
from app.services.extraction.search_metadata_validator import verify_search_metadata
from app.services.search.source_filter import SourceFilter
from app.services.search.source_strategy import SourceStrategy
from app.services.search.merchant_quality import MerchantQualityService
from app.services.filter.hard_filter import HardFilterService, is_unavailable
from app.schemas.requirement import RequirementData
from app.schemas.ranking import ScoringCandidate
from app.services.budget import stored_budget, bounds
from app.services.llm.query_generator import QueryGenerator
from app.services.scoring.scoring_engine import ScoringEngine, normalized
from app.services.extraction.dealer_offers import concrete_proofs
from app.services.search.model_hints import observed_models, lookup_key


class ProgressiveRetriever:
    def __init__(self, provider, resolver, settings):
        self.provider, self.resolver, self.settings = provider, resolver, settings
        self.diagnostics = []
        self.sources = {}
        self.batches = []
        self.queries = set()
        self.deadline = 0.0
        self.requirement = None

    def remaining(self):
        return max(0, self.deadline - time.monotonic())

    def enough(self):
        names = {tuple(sorted(identity_tokens(proof.get('name'))))
                 for s in self.sources.values() for proof in concrete_proofs(s.page_validation) if self.ready(proof)}
        return len(names) >= max(1, self.settings.live_search_target_products)

    def candidate(self, proof):
        return ScoringCandidate(product_id=0, **{key: proof[key] for key in
            ('name', 'category', 'brand', 'model', 'price', 'availability', 'specifications') if key in proof})

    def eligible(self, proof):
        if proof.get('variant_offers'): return any(self.eligible(p) for p in concrete_proofs(proof))
        if not proof.get('product_page_valid'): return False
        if self.requirement is None: return True
        return HardFilterService().evaluate(self.candidate(proof), self.requirement).accepted

    def ready(self, proof):
        if proof.get('variant_offers'): return any(self.ready(p) for p in concrete_proofs(proof))
        if not self.eligible(proof): return False
        if self.requirement:
            low, high = bounds(self.requirement)
            price = proof.get('price')
            if price is None or (low is not None and price < low) or (high is not None and price > high):
                return False
        if self.requirement is None or not self.requirement.requirements: return True
        matches = ScoringEngine().requirement_matches(self.candidate(proof), self.requirement)
        pairs = list(zip(self.requirement.requirements, matches))
        important = [(r, m) for r, m in pairs if r.priority >= 4] or pairs
        # More than half of priority weight must have observed values, and at
        # least one criterion must match. Unknown offers remain fallback data.
        total = sum(r.priority for r, _ in important)
        known = sum(r.priority for r, m in important if m.status != 'unknown')
        return known > total / 2 and any(m.status == 'matched' for _, m in important)

    def intent_query(self, extra='', prefix=''):
        req = self.requirement
        if req is None: return QueryGenerator._join(prefix, extra)
        return QueryGenerator._join(prefix, req.category or '', ' '.join(req.brands),
            QueryGenerator._budget_text(req), ' '.join(req.purpose),
            QueryGenerator._requirement_text(req), extra)

    def category_query(self, extra='giá bán', domain=None):
        """Broad recall near budget; complete intent still governs candidates."""
        req = self.requirement
        budget = (f'giá khoảng {req.budget_target} VND' if req.budget_mode=='FLEXIBLE_TARGET'
                  else QueryGenerator._budget_text(req))
        return QueryGenerator._join(f'site:{domain}' if domain else '',req.category or '',
                                    ' '.join(req.brands),budget,extra)

    def model_progress(self, name):
        """Search observations only; one unavailable seller is not all sellers."""
        key = lookup_key(name)
        attempts = sum(any(lookup_key(n)==key for n in re.findall(r'"([^"]+)"',query))
                       for query in self.queries)
        observations = []
        for source in self.sources.values():
            for proof in concrete_proofs(source.page_validation or {}):
                names = observed_models(proof.get('name',''),extra_brands=(proof['brand'],) if proof.get('brand') else ())
                if any(lookup_key(n)==key for n in names):
                    observations.append((source,proof))
        failed_domains = {(urlsplit(s.url).hostname or '').removeprefix('www.') for s,p in observations
                          if is_unavailable(p.get('availability')) or not self.eligible(p)}
        if any(self.ready(p) for _,p in observations): state='ready'
        elif observations and all(is_unavailable(p.get('availability')) for _,p in observations): state='unavailable'
        elif observations: state='fallback_or_rejected'
        else: state='evidence_missing' if attempts else 'unsearched'
        return {'model':name,'attempts':attempts,'state':state,'failed_domains':sorted(failed_domains),
                'unscoped_exhausted':attempts>0,'exhausted':attempts>=2}

    def continuation_query(self, category, prefer_domain):
        models = self.model_hints()
        progress = [self.model_progress(name) for name in models]
        unsearched = [p for p in progress if not p['attempts']]
        plain = [self.model_query(p['model'],'giá') for p in unsearched]
        used = Counter(query.split()[0][5:] for query in self.queries if query.startswith('site:'))
        domains = list(dict.fromkeys([*MerchantQualityService().discover(list(self.sources.values()),category),
                                     *SourceStrategy().preferred_domains(category)]))
        failed = {domain for p in progress for domain in p['failed_domains']}
        domains = sorted(domains,key=lambda domain:(used[domain],domain in failed,domains.index(domain)))
        scoped = []
        for domain in domains:
            if used[domain]>=2: continue
            # First scoped slot can try the observed model at another seller.
            # Subsequent domains get broad budget recall, not the same old SKU.
            if not used:
                for p in progress:
                    if not p['exhausted'] and domain not in p['failed_domains']:
                        scoped.append(self.model_query(p['model'],'giá bán',domain))
                        break
            scoped.append(self.category_query(domain=domain))
        options = [*scoped,*plain] if prefer_domain else [*plain,*scoped]
        options += [self.category_query('mua chính hãng'),self.category_query('mua online')]
        return next((q for q in options if q not in self.queries),None)

    def fetch_priority(self, source):
        quality = MerchantQualityService().assess(source)
        text = normalized((source.title or '') + ' ' + source.content)
        category = set(normalized(self.requirement.category if self.requirement else '').split())
        kind = classify_source(source.url)
        return (kind in {'ARTICLE', 'NEWS', 'REVIEW', 'HOMEPAGE', 'CATEGORY', 'SEARCH_PAGE'},
                not category.issubset(set(text.split())), not quality['commercial'],
                not any(c.isdigit() for c in text), -quality['boost'])

    def model_hints(self):
        hints = []
        for source in self.sources.values():
            for hint in (source.page_validation or {}).get('discovery', []):
                if not hint.get('brand'): continue
                extra = ' '.join(str(value) for key,value in hint.get('variant', {}).items() if key != 'sku')
                brand = hint.get('brand') or ''
                base_name = QueryGenerator._join(brand if brand.lower() not in hint['name'].lower() else '', hint['name'])
                clean_names = observed_models(base_name, extra_brands=(brand,))
                if not clean_names: continue
                base_name = clean_names[0]
                name = QueryGenerator._join(base_name, extra)
                low, high = bounds(self.requirement) if self.requirement else (None, None)
                outside = ((low is not None and hint.get('price_max') is not None and hint['price_max'] < low)
                           or (high is not None and hint.get('price_min') is not None and hint['price_min'] > high))
                # An official page can show the selected version's MSRP only;
                # it does not establish that every version is outside budget.
                if hint.get('price_type') == 'SUGGESTED_RANGE': outside = False
                hints.append((outside, base_name, False, False))
                if extra: hints.append((outside, name, True, False))
            if source.result_type not in {'HOMEPAGE', 'CATEGORY', 'SEARCH_PAGE'}:
                # Editorial mentions can seed lookups, never verified offers.
                for name in observed_models((source.title or '')+'\n'+source.content):
                    editorial = MerchantQualityService().assess(source)['kind']=='editorial_news'
                    hints.append((True,name,False,editorial))
        names = {}
        for entry in sorted(hints, key=lambda x: (x[2],x[0],x[3])):
            names.setdefault(lookup_key(entry[1]), entry[1])
        return list(names.values())

    def model_query(self, name, action='giá bán', domain=None):
        # Exact model lookup avoids drifting back into generic fuel/budget articles.
        # Full requirements remain attached to diagnostics and eligibility/scoring.
        name = name.replace('"',' ').strip()
        return QueryGenerator._join(f'site:{domain}' if domain else '', f'"{name}"', action)

    async def verify(self, source):
        if source.url in self.sources:
            return self.sources[source.url]
        source.image_url = None  # Query images do not certify product identity.
        try:
            async with asyncio.timeout(max(.001, self.remaining())):
                proof = await self.resolver.inspect(source.url, resolve_images=False)
        except TimeoutError:
            proof = {'product_page_valid': False, 'fetch_blocked': True,
                     'reason': 'Retrieval time budget reached.', 'evidence_url': source.url}
        except Exception:
            proof = {'product_page_valid': False, 'fetch_blocked': False,
                     'reason': 'Malformed page metadata; source remains unverified.', 'evidence_url': source.url}
        if not proof.get('product_page_valid') and proof.get('fetch_blocked'):
            proof = verify_search_metadata(source, proof)
        proof.setdefault('verification_level', 'UNVERIFIED')
        proof.setdefault('product_page_confidence', 0)
        source.page_validation = proof
        source.result_type = proof.get('result_type') or classify_source(source.url)
        self.sources[source.url] = source
        return source

    async def pass_queries(self, label, queries):
        limit = min(24, max(1, self.settings.live_search_max_queries))
        selected = []
        for query in queries:
            query = ' '.join(query.split())
            if query and query not in self.queries and len(self.queries) < limit and self.remaining() > 0:
                self.queries.add(query)
                selected.append(query)
        async def execute(query):
            diagnostic = {'pass': label, 'query': query, 'result_count': 0, 'source_filter_rejected': 0,
                          'requirement_context':self.requirement.model_dump() if self.requirement else None}
            self.diagnostics.append(diagnostic)
            try:
                async with asyncio.timeout(max(.001, self.remaining())):
                    rows = await self.provider.search(query, self.settings.max_results_per_query)
                filtered = SourceFilter().filter(rows)
                diagnostic.update(result_count=len(rows), source_filter_rejected=len(rows) - len(filtered))
            except Exception as exc:
                kind = getattr(exc, 'kind', 'timeout' if isinstance(exc, TimeoutError) else 'unexpected_error')
                diagnostic['error_kind'] = kind
                self.batches.append((query, [], f"Query '{query}' [{kind}]: {exc}"))
                return
            filtered.sort(key=self.fetch_priority)
            verified = []
            for start in range(0, len(filtered), 4):
                verified.extend(await asyncio.gather(*(self.verify(s) for s in filtered[start:start + 4])))
            counts = Counter({key: 0 for key in ('DIRECT_PRODUCT', 'CATEGORY', 'HOMEPAGE', 'SEARCH_PAGE',
                'ARTICLE', 'NEWS', 'REVIEW', 'UNKNOWN', 'REJECTED', 'UNVERIFIED',
                'FETCH_BLOCKED', 'VERIFIED_CONTENT', 'VERIFIED_SEARCH_METADATA')})
            counts.update(source.result_type for source in verified)
            counts.update(source.page_validation['verification_level'] for source in verified)
            counts['FETCH_BLOCKED'] = sum(bool(s.page_validation.get('fetch_blocked')) for s in verified)
            diagnostic['counts'] = dict(counts)
            diagnostic['verified'] = sum(bool(s.page_validation.get('product_page_valid')) for s in verified)
            diagnostic['verification_rejected'] = len(verified) - diagnostic['verified']
            diagnostic['eligible'] = sum(self.eligible(s.page_validation) for s in verified)
            diagnostic['ready_to_stop'] = sum(self.ready(s.page_validation) for s in verified)
            diagnostic['discovery_models'] = sum(len(s.page_validation.get('discovery', [])) for s in verified)
            diagnostic['model_progress'] = [self.model_progress(name) for name in self.model_hints()]
            from app.services.search.retrieval_diagnostics import audit_source
            diagnostic['source_audit'] = [row for source in verified for row in audit_source(query,source,self)]
            diagnostic['rejections'] = [dict(url=s.url, reason=proof.get('reason'),
                variant=proof.get('variant'),
                filter=HardFilterService().evaluate(self.candidate(proof), self.requirement).model_dump()
                    if proof.get('product_page_valid') and self.requirement else None)
                for s in verified for proof in (concrete_proofs(s.page_validation) or [s.page_validation])
                if not self.ready(proof)]
            self.batches.append((query, verified, None))
        await asyncio.gather(*(execute(query) for query in selected))

    async def run(self, queries, requirement):
        self.deadline = time.monotonic() + min(180, max(.01, self.settings.live_search_budget_seconds))
        category = (requirement.category or '').strip() if requirement else ''
        if requirement:
            values = {key: getattr(requirement, key) for key in RequirementData.model_fields
                      if getattr(requirement, key, None) is not None}
            self.requirement = RequirementData(**{**values, **stored_budget(requirement)})
        if self.requirement and (self.requirement.budget_min is not None or self.requirement.budget_max is not None):
            # Preserve saved queries, adding only any missing intent fragments.
            fragments = [category, QueryGenerator._budget_text(self.requirement),
                         ' '.join(self.requirement.purpose), QueryGenerator._requirement_text(self.requirement)]
            queries = [QueryGenerator._join(q, *(f for f in fragments if f and f not in q)) for q in queries]
        # Bound generic passes even if a legacy session saved many queries;
        # leave capacity for exact-model and merchant lookups.
        await self.pass_queries('requirement', queries[:2])
        if category and not self.enough():
            commerce = [self.category_query(), self.intent_query('mua online')]
            await self.pass_queries('commercial', commerce)
        if category and not self.enough():
            await self.pass_queries('model_discovery', [self.model_query(name,'mua') for name in self.model_hints()[:2]])
        if category and not self.enough():
            await self.pass_queries('merchant_discovery', [self.intent_query('đại lý')])
            # Re-evaluate after each query. Reserve alternating slots for new
            # sellers and models instead of queuing repetitions of a dead end.
            limit = min(24,max(1,getattr(self.settings,'live_search_max_queries',12)))
            for index in range(limit):
                if self.enough() or len(self.queries)>=limit or self.remaining()<=0: break
                query = self.continuation_query(category,prefer_domain=index%2==0)
                if query is None: break
                await self.pass_queries('merchant_products',[query])
        # Resolve images only after offers have been verified; failure is optional metadata.
        async def image(source,proof):
            if not self.eligible(proof): return
            try:
                async with asyncio.timeout(max(.001, self.remaining())):
                    for url, origin in proof.pop('image_candidates', []):
                        if await self.resolver._image_loads(url):
                            proof.update(image_url=url, image_source=origin)
                            if not source.page_validation.get('variant_offers'): source.image_url = url
                            break
            except Exception:
                pass
            proof.pop('image_candidates', None)
        await asyncio.gather(*(image(source,proof) for source in self.sources.values()
                               for proof in concrete_proofs(source.page_validation)))
        return self.batches
