"""Bounded Live retrieval: requirements, commerce, then discovered merchants.

No persistence here. A failed retrieval cannot delete any previous session data.
"""
import asyncio
import time
import re
from collections import Counter
from contextlib import AsyncExitStack
from urllib.parse import urlsplit

from app.services.extraction.product_page_validator import classify_source, identity_tokens, same_identity
from app.services.extraction.search_metadata_validator import verify_search_metadata
from app.services.search.source_filter import SourceFilter, normalize_domain
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
from app.services.search.retrieval_relevance import (irrelevant_reason, hint_budget_rank,
    category_compatible, source_category, source_category_compatible)
from app.services.performance import current_trace, measure, timed
from app.services.search.retrieval_diagnostics import source_plan, conversion_stats, rejection_reason, source_filter_reasons


class ProgressiveRetriever:
    def __init__(self, provider, resolver, settings):
        self.provider, self.resolver, self.settings = provider, resolver, settings
        self.diagnostics = []
        self.sources = {}
        self.batches = []
        self.queries = set()
        self.deadline = 0.0
        self.deadline_exhausted = False
        self.requirement = None
        self.pending = {}
        self.source_queries = {}
        self.candidate_urls = set()
        self.duplicate_urls = 0
        self.stop_reason = 'query_budget'
        self.page_concurrency = min(8, max(1, getattr(settings, 'live_search_page_concurrency', 4)))
        self.query_concurrency = min(4, max(1, getattr(settings, 'live_search_query_concurrency', 2)))
        self.page_slots = asyncio.Semaphore(self.page_concurrency)
        self.query_slots = asyncio.Semaphore(self.query_concurrency)
        self.domain_slots = {}
        self.initial_cap = min(40, max(1, getattr(settings, 'live_search_initial_candidates', 10)))
        self.max_cap = min(40, max(self.initial_cap, getattr(settings, 'live_search_max_candidates', 20)))
        self.candidate_cap = self.initial_cap
        self.discovery_cap = min(8, max(0, getattr(settings, 'live_search_discovery_pages', 4)))
        self.max_page_requests = self.max_cap + self.discovery_cap
        self.product_attempts, self.discovery_attempts, self.inspected_urls = set(), set(), set()
        self.plans = {}
        self.rounds = []
        self.no_progress_rounds = 0
        self.observed_product_identities = set()
        self.observed_model_keys, self.observed_merchant_domains = set(), set()
        self.model_price_ranks = {}
        self.incompatible_model_keys = set()
        self.page_metrics = []
        self.child_urls = set()
        self.domain_work = {}
        self.page_budget = min(12., max(.01, getattr(settings, 'live_search_page_budget_seconds', 4.)))
        self.domain_budget = min(30., max(.01, getattr(settings, 'live_search_domain_budget_seconds', 6.)))
        # Reuse remaining global slots; only the exhausted domain gets a small,
        # separately bounded opportunity for an unrequested direct product.
        self.recovery_limit = min(2, self.max_cap)
        self.recovery_timeout = min(2., self.page_budget, self.domain_budget)
        self.recovery_urls = []
        self.recovery_work = {}

    def remaining(self):
        if self.deadline_exhausted:
            return 0
        return max(0, self.deadline - time.monotonic())

    def enough(self):
        names = {tuple(sorted(identity_tokens(proof.get('name'))))
                 for s in self.sources.values() for proof in concrete_proofs(s.page_validation) if self.ready(proof)}
        return len(names) >= max(1, self.settings.live_search_target_products)

    def can_continue(self):
        satisfaction = self.satisfaction()
        if self.requirement and self.requirement.budget_mode == 'FLEXIBLE_TARGET':
            offers = [p for s in self.sources.values() for p in concrete_proofs(s.page_validation) if self.eligible(p)]
            identities = {tuple(sorted(identity_tokens(p.get('name')))) for p in offers}
            if (len(identities) >= max(3,getattr(self.settings,'live_search_min_products',3))
                    and all(ScoringEngine().budget_score(self.candidate(p),self.requirement)==0 for p in offers)):
                hints = self.model_hints()
                near_unsearched = any(self.model_price_ranks.get(lookup_key(n))==0
                    and self.model_progress(n)['state']=='unsearched' for n in hints)
                if not near_unsearched:
                    self.stop_reason = 'fallback_minimum_no_near_evidence'
                    return False
        if (satisfaction['strong_models'] >= 2 and self.no_progress_rounds >= 1
                and not any(self.model_progress(n)['state']=='unsearched' for n in self.model_hints())):
            self.stop_reason = 'strong_fit_no_progress'
            return False
        # Allow initial requirement/model/commerce discovery and one targeted
        # merchant attempts before stopping repeated unproductive continuation.
        if (self.no_progress_rounds >= 3 and self.rounds
                and sum(r['kind'] in {'merchant_products','alternative_model'} for r in self.rounds) >= 2):
            # Give an observed alternative one bounded chance after exhausted
            # out-of-stock recovery. Repeated evidence cannot extend this again.
            progress = [self.model_progress(name) for name in self.model_hints()]
            alternative = (not any(r['kind']=='alternative_model' for r in self.rounds)
                and any(p['state']=='unavailable' for p in progress)
                and any(not p['attempts'] and p['state']=='unsearched' for p in progress))
            if not alternative:
                self.stop_reason = 'no_progress'
                return False
        return (not self.enough() and self.remaining() > 0 and len(self.product_attempts) < self.max_cap
                and len(self.inspected_urls) < self.max_page_requests
                and len(self.queries) < min(24, max(1, getattr(self.settings, 'live_search_max_queries', 12))))

    def domain_slot(self, url):
        domain = (urlsplit(url).hostname or '').removeprefix('www.')
        return self.domain_slots.setdefault(domain, asyncio.Semaphore(
            min(4, max(1, getattr(self.settings, 'live_search_per_domain_concurrency', 2)))))

    def recovery_needed(self):
        # ready() includes all unchanged hard filters: category, stock, budget,
        # brand and exclusions. All-rejected sets qualify just like empty/OOS.
        return not any(self.ready(p) for s in self.sources.values()
                       for p in concrete_proofs(s.page_validation))

    def recovery_candidate(self, source):
        """Scheduling evidence only: still requires the unchanged page validator."""
        if (source_plan(source) != 'product' or irrelevant_reason(source, self.requirement)
                or not source_category_compatible(source, self.requirement)
                or self.unavailable_duplicate(source)):
            return False
        path = urlsplit(source.url).path.lower()
        # A generic store/brand landing page is not a reserved opportunity.
        slug = re.sub(r'\.(html?|aspx)$', '', path.rsplit('/', 1)[-1]).replace('-', ' ')
        shared = identity_tokens(slug) & identity_tokens(source.title or '')
        return (any(any(c.isdigit() for c in token) for token in shared)
                and bool(source_category(source) or observed_models(source.title or '') or
                         re.search(r'/(?:products?|dtdd|dien-thoai|san-pham)/[^/]+', path)))

    def recovery_priority(self, source):
        names = observed_models(source.title or '')
        keys = {lookup_key(n) for n in names}
        known = {lookup_key(p.get('name', '')) for s in self.sources.values()
                 for p in concrete_proofs(s.page_validation) if p.get('product_page_valid')}
        price_rank = min((self.model_price_ranks.get(k, hint_budget_rank(source, self.requirement))
                          for k in keys), default=1)
        old_domains = {normalize_domain(s.url) for s in self.sources.values()
                       if any(is_unavailable(p.get('availability')) for p in concrete_proofs(s.page_validation))}
        return (source_category(source) is None, price_rank, bool(keys & known),
                normalize_domain(source.url) in old_domains, self.fetch_priority(source), source.url)

    async def recover_direct(self):
        """No new provider call or retry: at most two previously unrequested URLs.

        Each domain gets at most one reserved probe. Global deadline/page/candidate
        caps and the existing direct-fetch failure circuit remain mandatory.
        """
        if self.enough() or not self.recovery_needed():
            return
        self.model_hints()
        candidates = {**self.pending, **{url: s for url, s in self.sources.items()
            if (s.page_validation or {}).get('rejection_code') == 'resource_budget'}}
        candidates = [s for s in candidates.values() if s.url not in self.inspected_urls
                      and s.url not in self.recovery_urls and self.recovery_candidate(s)]
        for source in sorted(candidates, key=self.recovery_priority):
            if (self.enough() or not self.recovery_needed() or self.remaining() <= 0
                    or len(self.recovery_urls) >= self.recovery_limit
                    or len(self.inspected_urls) >= self.max_page_requests
                    or len(self.product_attempts) >= self.max_cap):
                break
            domain = normalize_domain(source.url)
            normal = self.domain_work.get(domain, {})
            if domain in self.recovery_work or normal.get('direct_failures', 0) >= 2:
                continue
            self.pending.pop(source.url, None)
            timeout = asyncio.timeout(max(.001, self.remaining()))
            try:
                async with timeout:
                    async with self.domain_slot(source.url), self.page_slots:
                        self.recovery_urls.append(source.url)
                        await self.verify(source, recovery=True)
            except TimeoutError:
                if timeout.expired():
                    self.deadline_exhausted = True
                self.stop_reason = 'time_budget'
                break

    def skip_page(self, source, reason):
        source.page_validation = dict(product_page_valid=False, page_requested=False, page_fetched=False,
            fetch_blocked=False, verification_level='UNVERIFIED', product_page_confidence=0,
            evidence_url=source.url, rejection_code='resource_budget', reason=reason, image_url=None)
        source.image_url = None
        self.sources[source.url] = source
        return source

    def candidate(self, proof):
        return ScoringCandidate(product_id=0, **{key: proof[key] for key in
            ('name', 'category', 'brand', 'model', 'price', 'availability', 'specifications') if key in proof})

    def eligible(self, proof):
        if proof.get('variant_offers'): return any(self.eligible(p) for p in concrete_proofs(proof))
        if not proof.get('product_page_valid'): return False
        if is_unavailable(proof.get('availability')): return False
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

    def satisfaction(self):
        proofs = [p for s in self.sources.values() for p in concrete_proofs(s.page_validation)]
        return {'eligible_offers': sum(self.eligible(p) for p in proofs),
                'strong_models': len({lookup_key(p.get('name','')) for p in proofs if self.ready(p)}),
                'target_reached': self.enough()}

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
        attempted_domains = {query.split()[0][5:] for query in self.queries if query.startswith('site:')
            and any(lookup_key(n)==key for n in re.findall(r'"([^"]+)"',query))}
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
                'attempted_domains':sorted(attempted_domains),
                'unscoped_exhausted':attempts>0,'exhausted':attempts>=2}

    def continuation_query(self, category, prefer_domain):
        models = self.model_hints()
        progress = [self.model_progress(name) for name in models]
        unsearched = [p for p in progress if not p['attempts']]
        plain = [self.model_query(p['model'],'giá') for p in unsearched]
        used = Counter(query.split()[0][5:] for query in self.queries if query.startswith('site:'))
        relevant = [s for s in self.sources.values() if not irrelevant_reason(s,self.requirement)]
        domains = list(dict.fromkeys([*MerchantQualityService().discover(relevant,category),
                                     *SourceStrategy().preferred_domains(category)]))
        failed = {domain for p in progress for domain in p['failed_domains']}
        domains = sorted(domains,key=lambda domain:(used[domain],domain in failed,domains.index(domain)))
        scoped = []
        unavailable = [p for p in progress if p['state'] == 'unavailable' and not p['exhausted']]
        # Each known unavailable model gets a different seller first. Then
        # reserve discovery for another observed model, not another old SKU loop.
        recovery = []
        for p in unavailable:
            if p['attempted_domains']: continue
            domain = next((d for d in domains if used[d]<2 and d not in p['failed_domains']),None)
            if domain: recovery.append(self.model_query(p['model'],'giá bán',domain))
        alternatives = [self.model_query(p['model'],'giá') for p in unsearched if p['state']=='unsearched']
        near = [p for p in unsearched if p['state']=='unsearched'
                and self.model_price_ranks.get(lookup_key(p['model']))==0]
        if near and (self.satisfaction()['eligible_offers'] or self.recovery_needed()):
            return self.model_query(near[0]['model'],'giá')
        if recovery: return next((q for q in recovery if q not in self.queries),None)
        # Existing weak offers are useful fallbacks, not evidence of search
        # satisfaction. Spend the next slot on an observed alternative first.
        if alternatives and self.satisfaction()['eligible_offers'] and not self.enough():
            return alternatives[0]
        if any(p['state']=='unavailable' for p in progress):
            # Retain one category/budget recall slot at a new merchant after
            # direct recovery. It must not become a series of generic articles.
            broad_used = any(q.startswith('site:') and q == self.category_query(domain=q.split()[0][5:])
                             for q in self.queries)
            domain = next((d for d in domains if not used[d] and d not in failed),None)
            if not broad_used and domain:
                return self.category_query(domain=domain)
        if any(p['state']=='unavailable' for p in progress) and alternatives:
            return alternatives[0]
        for domain in domains:
            if used[domain]>=2: continue
            # First scoped slot can try the observed model at another seller.
            # Subsequent domains get broad budget recall, not the same old SKU.
            if unavailable or not used:
                for p in unavailable or progress:
                    if not p['exhausted'] and domain not in {*p['failed_domains'],*p['attempted_domains']}:
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

    def verification_tier(self, source):
        """Schedule observed URLs only; a high priority never certifies a page."""
        if source.url in self.child_urls: return 2
        if self.plans[source.url] != 'product': return 3
        path = urlsplit(source.url).path.lower()
        slug = re.sub(r'\.(html?|aspx)$','',path.rsplit('/',1)[-1]).replace('-',' ')
        model_tokens = identity_tokens(slug) & identity_tokens(source.title or '')
        direct = (re.search(r'/(?:products?|dtdd|dien-thoai)/[^/]+',path)
                  or any(any(c.isdigit() for c in token) for token in model_tokens))
        if direct: return 0
        # A generic commerce landing page has no model identity. Do not let its
        # purchase keywords outrank an actual extracted child product link.
        return 1 if observed_models(source.title or '') else 3

    @timed('product_discovery_ms')
    def model_hints(self):
        hints = []
        self.model_price_ranks = {}
        self.incompatible_model_keys = set()
        for source in self.sources.values():
            if irrelevant_reason(source,self.requirement): continue
            if not source_category_compatible(source, self.requirement):
                self.incompatible_model_keys.update(lookup_key(n) for n in observed_models(source.title or ''))
            for proof in concrete_proofs(source.page_validation):
                if not category_compatible(proof.get('name', ''), self.requirement, proof.get('category')):
                    self.incompatible_model_keys.update(lookup_key(n) for n in observed_models(proof.get('name', '')))
            for hint in (source.page_validation or {}).get('discovery', []):
                if not hint.get('brand'): continue
                if not category_compatible(hint['name'], self.requirement, hint.get('category')):
                    self.incompatible_model_keys.update(lookup_key(n) for n in
                        observed_models(hint['name'], extra_brands=(hint['brand'],)))
                    continue
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
                priced = hint.get('price_min') is not None or hint.get('price_max') is not None
                rank = 2 if outside else (0 if priced else 1)
                # Preserve official family discovery priority: the selected
                # version's MSRP cannot exclude the rest of the family. It
                # also cannot establish a near-budget concrete offer.
                if hint.get('price_type') == 'SUGGESTED_RANGE': rank = 0
                if priced and rank != 1 and hint.get('price_type') != 'SUGGESTED_RANGE':
                    key = lookup_key(base_name)
                    self.model_price_ranks[key] = min(rank,self.model_price_ranks.get(key,rank))
                hints.append((rank, base_name, False, False))
                if extra: hints.append((rank, name, True, False))
            if source.result_type not in {'HOMEPAGE', 'CATEGORY', 'SEARCH_PAGE'}:
                # Editorial mentions can seed lookups, never verified offers.
                for name in observed_models((source.title or '')+'\n'+source.content):
                    if not category_compatible(name, self.requirement): continue
                    editorial = MerchantQualityService().assess(source)['kind']=='editorial_news'
                    hints.append((hint_budget_rank(source,self.requirement),name,False,editorial))
        names = {}
        # A verified offer's price applies only to its own model. Never attach
        # it to another model mentioned in the page's navigation or article.
        low, high = bounds(self.requirement) if self.requirement else (None,None)
        for source in self.sources.values():
            for proof in concrete_proofs(source.page_validation):
                price = proof.get('price')
                if not proof.get('product_page_valid') or price is None: continue
                rank = 2 if ((low is not None and price < low) or (high is not None and price > high)) else 0
                for name in observed_models(proof.get('name','')):
                    if not category_compatible(name, self.requirement, proof.get('category')): continue
                    key = lookup_key(name)
                    self.model_price_ranks[key] = min(rank,self.model_price_ranks.get(key,rank))
        hints = [(self.model_price_ranks.get(lookup_key(n),rank),n,variant,editorial)
                 for rank,n,variant,editorial in hints]
        for entry in sorted(hints, key=lambda x: (x[2],x[0],x[3])):
            if lookup_key(entry[1]) in self.incompatible_model_keys: continue
            if not category_compatible(entry[1], self.requirement): continue
            if self.requirement and normalized(self.requirement.category or '') in {'dien thoai', 'phone', 'smartphone'}:
                # A family heading or a sensor model is not an observed phone.
                if not any(c.isdigit() for c in entry[1]) or re.search(r'\b(?:LYT[- ]?\d|IMX\d)', entry[1], re.I):
                    continue
            names.setdefault(lookup_key(entry[1]), entry[1])
        return list(names.values())

    def model_query(self, name, action='giá bán', domain=None):
        # Exact model lookup avoids drifting back into generic fuel/budget articles.
        # Full requirements remain attached to diagnostics and eligibility/scoring.
        name = name.replace('"',' ').strip()
        if lookup_key(name) in self.incompatible_model_keys or not category_compatible(name, self.requirement):
            return self.category_query(domain=domain)
        if normalized(name) in {'4g','5g','6g','vnd','usd'}: return ''
        market = ('Việt Nam VND' if self.requirement and self.requirement.currency == 'VND'
                  and any(getattr(self.requirement, k) is not None for k in ('budget_target','budget_min','budget_max')) else '')
        return QueryGenerator._join(f'site:{domain}' if domain else '', f'"{name}"', action, market)

    async def verify(self, source, *, recovery=False):
        if source.url in self.sources and not recovery:
            return self.sources[source.url]
        domain = (urlsplit(source.url).hostname or '').removeprefix('www.')
        ledger = self.recovery_work if recovery else self.domain_work
        work = ledger.setdefault(domain, dict(active=0, spent=0., since=0., attempts=0,
                                              failures=0, direct_failures=0, skipped=0))
        budget = self.recovery_timeout if recovery else self.domain_budget
        allowance = budget - work['spent'] - (time.monotonic()-work['since'] if work['active'] else 0)
        # After a failure, in-flight probes reserve the remaining retry slots.
        # Otherwise staggered timeouts can keep admitting another request just
        # before its sibling records the second failure.
        failure_budget_used = work['failures'] and work['failures'] + work['active'] >= 2
        if allowance <= 0 or failure_budget_used:
            work['skipped'] += 1
            return self.skip_page(source, 'Per-domain time/failure budget exhausted; source remains unverified.')
        if not work['active']: work['since'] = time.monotonic()
        work['active'] += 1
        work['attempts'] += 1
        source.image_url = None  # Query images do not certify product identity.
        self.inspected_urls.add(source.url)
        plan = self.plans.get(source.url, source_plan(source))
        started = time.perf_counter()
        (self.product_attempts if plan == 'product' else self.discovery_attempts).add(source.url)
        remaining = self.remaining()
        timeout_seconds = max(.001, min(remaining, self.page_budget, allowance))
        deadline_limited = remaining <= self.page_budget and remaining <= allowance
        timeout = asyncio.timeout(timeout_seconds)
        try:
            async with timeout:
                proof = await self.resolver.inspect(source.url, resolve_images=False)
        except TimeoutError:
            if timeout.expired() and deadline_limited:
                self.deadline_exhausted = True
            proof = {'product_page_valid': False, 'fetch_blocked': True,
                     'page_fetched': False, 'fetch_failure': 'timeout',
                     'reason': 'Page/domain/retrieval time budget reached.', 'evidence_url': source.url}
        except Exception:
            proof = {'product_page_valid': False, 'fetch_blocked': False,
                     'page_fetched': False, 'fetch_failure': 'invalid_metadata',
                     'reason': 'Malformed page metadata; source remains unverified.', 'evidence_url': source.url}
        finally:
            work['active'] -= 1
            if not work['active']:
                work['spent'] += time.monotonic() - work['since']
            self.page_metrics.append({'url': source.url, 'domain': urlsplit(source.url).hostname,
                                      'inspection_ms': round((time.perf_counter()-started)*1000, 3)})
        if not proof.get('page_fetched', not proof.get('fetch_blocked', False)) and proof.get('fetch_blocked'):
            work['failures'] += 1
            if self.recovery_candidate(source): work['direct_failures'] += 1
        else:
            work['failures'] = 0
            if self.recovery_candidate(source): work['direct_failures'] = 0
        fetched = proof.get('page_fetched', not proof.get('fetch_blocked', False))
        if not proof.get('product_page_valid') and proof.get('fetch_blocked'):
            with measure('verification_ms'):
                proof = {**proof, **verify_search_metadata(source, proof)}
        proof.update(page_requested=True, page_fetched=fetched)
        proof.setdefault('verification_level', 'UNVERIFIED')
        proof.setdefault('product_page_confidence', 0)
        source.page_validation = proof
        source.result_type = proof.get('result_type') or classify_source(source.url)
        if source.result_type in {'ARTICLE', 'NEWS', 'REVIEW', 'HOMEPAGE', 'CATEGORY', 'SEARCH_PAGE'}:
            # An UNKNOWN URL can turn out to be editorial content. It consumed
            # bounded HTTP work, but must not spend a product-candidate slot.
            self.product_attempts.discard(source.url)
            self.discovery_attempts.add(source.url)
        self.sources[source.url] = source
        return source

    def retain_metadata(self, source, reason='Non-product source retained for model/merchant discovery.'):
        source.image_url = None
        source.page_validation = dict(product_page_valid=False, page_requested=False, page_fetched=False,
            fetch_blocked=False, verification_level='REJECTED', product_page_confidence=0,
            result_type=source.result_type, evidence_url=source.url, image_url=None,
            rejection_code='non_product_page', reason=reason)
        self.sources[source.url] = source

    def unavailable_duplicate(self, source):
        """Only a verified same-variant observation can suppress seller repeats."""
        domain = normalize_domain(source.url)
        return any(normalize_domain(old.url)==domain and p.get('product_page_valid')
            and is_unavailable(p.get('availability')) and same_identity(source.title or '',p.get('name',''))
            for old in self.sources.values() for p in concrete_proofs(old.page_validation))

    def enqueue_children(self, parent):
        from app.services.search.base import SearchResult
        for child in (parent.page_validation or {}).get('child_products', [])[:12]:
            if len(self.child_urls) >= self.max_cap: break
            if not category_compatible(child['name'], self.requirement, child.get('category')): continue
            rows = SourceFilter().filter([SearchResult(url=child['url'], title=child['name'], content='')])
            if not rows: continue
            source = rows[0]
            if not source_category_compatible(source, self.requirement): continue
            if source.url in self.candidate_urls or source_plan(source) != 'product': continue
            self.child_urls.add(source.url)
            self.candidate_urls.add(source.url)
            self.source_queries[source.url] = self.source_queries[parent.url]
            self.plans[source.url] = 'product'
            self.pending[source.url] = source

    def summary(self):
        """Mutually exclusive first rejection per observed offer (pages can have variants)."""
        counts = dict.fromkeys(('rejected_wrong_category', 'rejected_non_product_page',
            'rejected_missing_price', 'rejected_missing_identity', 'rejected_http_network_failure',
            'rejected_out_of_stock', 'rejected_duplicate', 'rejected_other'), 0)
        counts['rejected_duplicate'] = self.duplicate_urls
        valid = set()
        for source in self.sources.values():
            page = source.page_validation or {}
            for proof in concrete_proofs(page) or [page]:
                reason = rejection_reason(proof, self)
                if reason:
                    key = 'rejected_' + reason
                else:
                    identity = tuple(sorted(identity_tokens(proof.get('name'))))
                    if identity not in valid:
                        valid.add(identity)
                        continue
                    key = 'rejected_duplicate'
                counts[key] += 1
        return {**counts, 'generated_queries': [q for q, _, _ in self.batches],
                'candidates_found': len(self.candidate_urls), 'unique_candidate_urls': sorted(self.candidate_urls),
                'pages_verified': len(self.inspected_urls), 'valid_offers': len(valid),
                'candidate_cap': self.candidate_cap, 'unverified_candidates': len(self.pending),
                'product_attempts': len(self.product_attempts), 'discovery_attempts': len(self.discovery_attempts),
                'max_page_requests': self.max_page_requests, 'rounds': self.rounds,
                'page_timings': sorted(self.page_metrics, key=lambda p: p['url']),
                'provider_calls': len(self.queries), 'page_attempts': len(self.inspected_urls), 'round_count': len(self.rounds),
                'domain_budgets': {domain: dict(attempts=w['attempts'], failures=w['failures'], skipped=w['skipped'],
                    active_ms=round(w['spent']*1000, 3), budget_ms=self.domain_budget*1000)
                    for domain, w in sorted(self.domain_work.items())},
                'child_product_urls': sorted(self.child_urls),
                'direct_recovery': dict(limit=self.recovery_limit, timeout_seconds=self.recovery_timeout,
                    attempted_urls=list(self.recovery_urls),
                    domains={d: dict(attempts=w['attempts'], active_ms=round(w['spent']*1000, 3))
                             for d, w in sorted(self.recovery_work.items())}),
                'search_satisfaction': self.satisfaction(),
                'conversion': conversion_stats(self.sources.values(), self), 'stop_reason': self.stop_reason}

    async def pass_queries(self, label, queries):
        round_started = time.perf_counter()
        generated = [' '.join(q.split()) for q in queries if q.strip()]
        requested_before = set(self.inspected_urls)
        candidates_before = set(self.candidate_urls)
        children_before = set(self.child_urls)
        limit = min(24, max(1, self.settings.live_search_max_queries))
        selected = []
        for query in queries:
            query = ' '.join(query.split())
            if query and query not in self.queries and len(self.queries) < limit and self.remaining() > 0:
                self.queries.add(query)
                selected.append(query)
        async def execute(query):
            query_started = time.perf_counter()
            diagnostic = {'pass': label, 'query': query, 'result_count': 0, 'source_filter_rejected': 0,
                          'requirement_context':self.requirement.model_dump() if self.requirement else None}
            timeout = asyncio.timeout(max(.001, self.remaining()))
            try:
                async with timeout:
                    async with self.query_slots:
                        rows = await self.provider.search(query, self.settings.max_results_per_query)
                filtered = SourceFilter().filter(rows)
                diagnostic.update(result_count=len(rows), source_filter_rejected=len(rows) - len(filtered))
                diagnostic['result_domains'] = sorted({domain for row in rows if (domain := normalize_domain(row.url))})
                diagnostic['source_filter_reason_counts'] = source_filter_reasons(rows)
            except Exception as exc:
                if isinstance(exc, TimeoutError) and timeout.expired():
                    self.deadline_exhausted = True
                kind = getattr(exc, 'kind', 'timeout' if isinstance(exc, TimeoutError) else 'unexpected_error')
                diagnostic['error_kind'] = kind
                return query, [], f"Query '{query}' [{kind}]: search provider unavailable", diagnostic
            finally:
                diagnostic['provider_wait_ms'] = round((time.perf_counter()-query_started)*1000, 3)
            return query, filtered, None, diagnostic

        # Merge by requested query order, never network completion order. URL
        # dedup happens BEFORE fetch: shared URLs cannot race or exhaust the cap.
        with measure('search_provider_ms'):
            results = await asyncio.gather(*(execute(query) for query in selected))
        for query, filtered, _, _ in results:
            for source in filtered:
                if source.url in self.candidate_urls:
                    self.duplicate_urls += 1
                    continue
                self.candidate_urls.add(source.url)
                self.source_queries[source.url] = query
                irrelevant = irrelevant_reason(source,self.requirement)
                if not source_category_compatible(source, self.requirement):
                    self.plans[source.url] = 'metadata'
                    self.retain_metadata(source, 'Observed product category conflicts with requested category.')
                    source.page_validation['rejection_code'] = 'category_mismatch'
                    continue
                if irrelevant:
                    self.plans[source.url] = 'metadata'
                    self.retain_metadata(source,irrelevant)
                    source.page_validation['rejection_code'] = 'irrelevant_intent'
                    continue
                self.plans[source.url] = source_plan(source)
                if self.plans[source.url] == 'metadata':
                    self.retain_metadata(source)
                else:
                    self.pending[source.url] = source

        async def inspect(source):
            async with AsyncExitStack() as slots:
                timeout = asyncio.timeout(max(.001, self.remaining()))
                try:
                    async with timeout:
                        await slots.enter_async_context(self.domain_slot(source.url))
                        await slots.enter_async_context(self.page_slots)
                except TimeoutError:
                    if timeout.expired():
                        self.deadline_exhausted = True
                    return self.skip_page(source, 'Retrieval deadline reached while waiting for page slots.')
                return await self.verify(source)

        with measure('product_verification_ms'):
            while self.pending and self.remaining() > 0 and not self.enough():
                if len(self.inspected_urls) >= self.max_page_requests:
                    self.stop_reason = 'page_budget'
                    break
                if len(self.product_attempts) >= self.candidate_cap:
                    if self.candidate_cap >= self.max_cap:
                        self.stop_reason = 'candidate_budget'
                        break
                    # Expand only when verified candidates still do not meet
                    # the existing requirement-aware readiness test.
                    valid = self.summary()['valid_offers']
                    step = self.initial_cap if valid < getattr(self.settings, 'live_search_min_products', 3) else self.page_concurrency
                    self.candidate_cap = min(self.max_cap, self.candidate_cap + step)
                for source in list(self.pending.values()):
                    if self.unavailable_duplicate(source):
                        self.pending.pop(source.url)
                        self.retain_metadata(source,'Same merchant/variant already verified unavailable in this retrieval.')
                        source.page_validation['rejection_code']='unavailable_duplicate'
                ordered = sorted(self.pending.values(), key=lambda s: (self.verification_tier(s), self.fetch_priority(s)))
                if not ordered: break
                # Diversity applies within a tier, never ahead of direct URLs.
                tier = self.verification_tier(ordered[0])
                ordered = [s for s in ordered if self.verification_tier(s)==tier]
                # Interleave merchants/models instead of fetching one seller's
                # repeated SKU first. Quality remains a signal, not a whitelist.
                domains, models, diverse = set(), set(), []
                for source in ordered:
                    domain = urlsplit(source.url).hostname
                    model = tuple(observed_models(source.title or '')) or (source.title,)
                    if domain not in domains and model not in models:
                        diverse.append(source); domains.add(domain); models.add(model)
                ordered = diverse + [s for s in ordered if s not in diverse]
                take = min(self.page_concurrency, self.candidate_cap - len(self.product_attempts),
                           self.max_page_requests - len(self.inspected_urls))
                chosen = []
                discovery_left = max(0, self.discovery_cap - len(self.discovery_attempts))
                for source in ordered:
                    # Low-value work must leave room for later direct discoveries.
                    # A direct-looking page can still prove editorial after fetch;
                    # its real HTTP work continues to count toward the global cap.
                    if (self.recovery_needed() and not self.recovery_candidate(source)
                            and (len(self.inspected_urls) + len(chosen) >= self.max_page_requests - self.recovery_limit
                                 or (self.plans[source.url] == 'product' and len(self.product_attempts)
                                     + sum(self.plans[s.url] == 'product' for s in chosen)
                                     >= self.max_cap - self.recovery_limit))):
                        self.pending.pop(source.url)
                        self.skip_page(source, 'Remaining page/product slots reserved for direct product recovery.')
                        continue
                    if self.plans[source.url] == 'discovery':
                        if discovery_left == 0:
                            self.pending.pop(source.url)
                            self.retain_metadata(source, 'Discovery HTTP budget exhausted; metadata retained.')
                            continue
                        discovery_left -= 1
                    chosen.append(source)
                    if len(chosen) >= take: break
                if not chosen: break
                for source in chosen:
                    self.pending.pop(source.url)
                fetched = await asyncio.gather(*(inspect(source) for source in chosen))
                # verify() also caches results; restore canonical insertion order.
                for source in chosen:
                    self.sources.pop(source.url, None)
                for source in fetched:
                    self.sources[source.url] = source
                    self.enqueue_children(source)

        with measure('product_verification_ms'):
            await self.recover_direct()

        for query, filtered, warning, diagnostic in results:
            verified = [self.sources[s.url] for s in filtered if s.url in self.sources]
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
            diagnostic['unverified_due_to_budget_or_target'] = len(filtered) - len(verified)
            diagnostic['round'] = len(self.rounds) + 1
            diagnostic['provider_limit'] = self.settings.max_results_per_query
            requested_here = (self.inspected_urls - requested_before) & {
                url for url, owner in self.source_queries.items() if owner == query}
            diagnostic['conversion'] = conversion_stats(filtered, self, requested_urls=requested_here)
            diagnostic['conversion']['rejected_before_fetch'] += diagnostic['source_filter_rejected']
            self.diagnostics.append(diagnostic)
            self.batches.append((query, verified, warning))
        if selected:
            round_sources = {s.url:s for _, rows, _, _ in results for s in rows}
            stats = conversion_stats(round_sources.values(), self,
                                     requested_urls=self.inspected_urls - requested_before)
            stats['rejected_before_fetch'] += sum(d['source_filter_rejected'] for _, _, _, d in results)
            identities = {tuple(sorted(identity_tokens(p.get('name')))) for s in self.sources.values()
                          for p in concrete_proofs(s.page_validation) if p.get('product_page_valid')}
            new_products = len(identities - self.observed_product_identities)
            self.observed_product_identities.update(identities)
            model_keys = {lookup_key(name) for name in self.model_hints()}
            merchants = {normalize_domain(s.url) for s in self.sources.values()
                         if self.plans.get(s.url)=='product' and MerchantQualityService().assess(s)['commercial']}
            new_models = len(model_keys-self.observed_model_keys)
            new_merchants = len(merchants-self.observed_merchant_domains)
            new_direct = sum(self.plans.get(url)=='product' and self.verification_tier(self.sources[url])<=2
                             and not self.unavailable_duplicate(self.sources[url])
                             for url in self.sources.keys()-candidates_before)
            new_children = len(self.child_urls-children_before)
            self.observed_model_keys.update(model_keys)
            self.observed_merchant_domains.update(merchants)
            self.no_progress_rounds = 0 if any((new_products,new_models,new_merchants,new_direct,new_children)) else self.no_progress_rounds + 1
            self.rounds.append(dict(round=len(self.rounds)+1, kind=label,
                duration_ms=round((time.perf_counter()-round_started)*1000, 3),
                new_verified_products=new_products, no_progress_rounds=self.no_progress_rounds,
                new_model_hints=new_models,new_merchant_domains=new_merchants,new_direct_urls=new_direct,new_child_urls=new_children,
                queries_generated=generated, queries_executed=selected,
                raw_search_results_per_query={q:d['result_count'] for q, _, _, d in results},
                unique_search_results=len(round_sources),
                result_domains=sorted({domain for _, _, _, d in results for domain in d.get('result_domains', [])}),
                conversion=stats, cumulative_product_attempts=len(self.product_attempts),
                cumulative_pages_requested=len(self.inspected_urls), cumulative_valid_offers=self.summary()['valid_offers']))

    async def run(self, queries, requirement):
        # One pool per retrieval, closed even on cancellation; no process-global
        # client tied to another event loop and no cross-session stale prices.
        async with AsyncExitStack() as stack:
            if hasattr(self.resolver, 'session'):
                await stack.enter_async_context(self.resolver.session())
            return await self._run(queries, requirement)

    async def _run(self, queries, requirement):
        self.deadline_exhausted = False
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
        if category and self.can_continue():
            hints = self.model_hints()
            if self.satisfaction()['eligible_offers']:
                # Do not re-query known weak/ready offers ahead of genuinely
                # unseen alternatives. Unavailable recovery remains separate.
                hints = sorted(hints,key=lambda n:self.model_progress(n)['state']!='unsearched')
            await self.pass_queries('model_discovery', [self.model_query(name,'mua') for name in hints[:2]])
        # Once verified offers are unavailable, spend the remaining query budget
        # on sellers/models rather than repeating broad editorial discovery.
        recovering_stock = any(p.get('product_page_valid') and is_unavailable(p.get('availability'))
            for source in self.sources.values() for p in concrete_proofs(source.page_validation))
        useful_alternatives = any(self.model_progress(n)['state']=='unsearched' for n in self.model_hints())
        if category and not recovering_stock and not useful_alternatives and self.can_continue():
            commerce = [self.category_query(), self.intent_query('mua online')]
            await self.pass_queries('commercial', commerce)
        if category and self.can_continue():
            if not recovering_stock and not useful_alternatives:
                await self.pass_queries('merchant_discovery', [self.intent_query('đại lý')])
            # Re-evaluate after each query. Reserve alternating slots for new
            # sellers and models instead of queuing repetitions of a dead end.
            limit = min(24,max(1,getattr(self.settings,'live_search_max_queries',12)))
            for index in range(limit):
                if not self.can_continue(): break
                query = self.continuation_query(category,prefer_domain=index%2==0 or self.no_progress_rounds >= 3)
                if query is None: break
                names = re.findall(r'"([^"]+)"',query)
                alternative = (names and self.model_progress(names[0])['state']=='unsearched'
                    and any(self.model_progress(name)['state']=='unavailable' for name in self.model_hints()))
                await self.pass_queries('alternative_model' if alternative else 'merchant_products',[query])
        # Query/no-progress exhaustion must not hide an already discovered URL.
        with measure('product_verification_ms'):
            await self.recover_direct()
        # Resolve images only after offers have been verified; failure is optional metadata.
        async def image(source,proof):
            if not self.eligible(proof): return
            try:
                async with asyncio.timeout(max(.001, self.remaining())), self.page_slots:
                    for url, origin in proof.pop('image_candidates', []):
                        async with self.domain_slot(url):
                            loaded = await self.resolver._image_loads(url)
                        if loaded:
                            proof.update(image_url=url, image_source=origin)
                            if not source.page_validation.get('variant_offers'): source.image_url = url
                            break
            except Exception:
                pass
            proof.pop('image_candidates', None)
        image_jobs = [(source, proof) for source in self.sources.values()
                      for proof in concrete_proofs(source.page_validation)]
        for start in range(0, len(image_jobs), self.page_concurrency):
            await asyncio.gather(*(image(source, proof) for source, proof
                                   in image_jobs[start:start + self.page_concurrency]))
        if self.enough(): self.stop_reason = 'target_reached'
        elif self.remaining() <= 0: self.stop_reason = 'time_budget'
        elif len(self.product_attempts) >= self.max_cap: self.stop_reason = 'candidate_budget'
        elif len(self.inspected_urls) >= self.max_page_requests: self.stop_reason = 'page_budget'
        elif self.recovery_needed() and self.recovery_urls:
            unresolved = any(s.url not in self.inspected_urls and self.recovery_candidate(s)
                for s in [*self.pending.values(), *self.sources.values()]
                if s.url in self.pending or (s.page_validation or {}).get('rejection_code') == 'resource_budget')
            self.stop_reason = 'recovery_budget' if unresolved else 'recovery_opportunities_exhausted'
        trace = current_trace.get()
        # A page queued in an earlier round may be verified by a later round.
        # Attach it to its original query so extraction cannot lose that offer.
        for query, sources, _ in self.batches:
            attached = {s.url for s in sources}
            sources.extend(s for url, s in self.sources.items()
                           if self.source_queries.get(url) == query and url not in attached)
        if trace is not None:
            trace.diagnostics.update(self.summary())
        return self.batches
