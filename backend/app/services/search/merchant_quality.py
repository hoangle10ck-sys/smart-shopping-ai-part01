"""Merchant hints boost retrieval; they never certify a product or dealership."""
import re
from urllib.parse import urlsplit

from app.core.constants import (OFFICIAL_BRAND_DOMAINS, TRUSTED_RETAILER_DOMAINS,
                                MARKETPLACE_DOMAINS, REVIEW_DOMAINS)
from app.services.search.source_strategy import normalize_text


def matches(domain, registry):
    return any(domain == item or domain.endswith('.' + item) for item in registry)


class MerchantQualityService:
    def assess(self, source):
        domain = (urlsplit(source.url).hostname or '').removeprefix('www.')
        if matches(domain, {'facebook.com', 'youtube.com', 'tiktok.com', 'instagram.com',
                            'wikipedia.org', 'vnexpress.net', 'vietnamnet.vn', 'dantri.com.vn'}):
            return {'domain': domain, 'kind': 'editorial_news', 'boost': 0, 'commercial': False}
        text = normalize_text((source.title or '') + ' ' + source.content)
        editorial = source.result_type in {'ARTICLE', 'NEWS', 'REVIEW'} or matches(domain, REVIEW_DOMAINS)
        if editorial:
            return {'domain': domain, 'kind': 'editorial_news', 'boost': 0, 'commercial': False}
        if matches(domain, TRUSTED_RETAILER_DOMAINS): kind, boost = 'known_retailer', 15
        elif matches(domain, MARKETPLACE_DOMAINS): kind, boost = 'ecommerce_marketplace', 10
        elif matches(domain, OFFICIAL_BRAND_DOMAINS): kind, boost = 'official_manufacturer', 10
        else: kind, boost = 'unknown_merchant', 0
        # "Authorized dealer" is deliberately not inferred from self-described snippets.
        commercial = bool(re.search(r'\b(cua hang|dai ly|mua ngay|dat hang|gio hang|gia ban|retailer|buy now|add to cart)\b', text))
        return {'domain': domain, 'kind': kind, 'boost': boost,
                'commercial': commercial or kind in {'known_retailer', 'ecommerce_marketplace'}}

    def discover(self, sources, category):
        from app.services.normalization.product_normalizer import infer_product_category
        category = infer_product_category(category) or category
        terms = set(normalize_text(category).split())
        ranked = {}
        for source in sources:
            quality = self.assess(source)
            text = normalize_text((source.title or '') + ' ' + source.content)
            discovery = bool((source.page_validation or {}).get('discovery'))
            # Tag/news indexes are not merchant discovery, even if their snippet
            # discusses prices/dealers. They must not consume dealer-site queries.
            path = urlsplit(source.url).path.lower()
            if re.search(r'/(?:tags?|news|tin-tuc)(?:/|$)',path): continue
            if ((quality['commercial'] or discovery) and quality['domain']
                    and (terms <= set(text.split()) or infer_product_category(text)==category or discovery)
                    and source.result_type not in {'ARTICLE', 'NEWS', 'REVIEW', 'SEARCH_PAGE'}):
                ranked[quality['domain']] = max(ranked.get(quality['domain'], 0), quality['boost'])
        return sorted(ranked, key=lambda domain: (-ranked[domain], domain))
