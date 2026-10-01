"""Audit observations without upgrading discovery hints to verified offers."""
from urllib.parse import urlsplit
from app.services.extraction.dealer_offers import concrete_proofs
from app.services.filter.hard_filter import category_matches, is_unavailable, normalized


def source_filter_reasons(rows):
    """Explain the existing SourceFilter gates without changing eligibility."""
    from collections import Counter
    from app.services.search.source_filter import normalize_domain, is_rental_result
    reasons, seen = Counter(), set()
    for row in rows:
        url = row.url.strip()
        if not url: reasons['missing_url'] += 1
        elif url in seen: reasons['duplicate_url'] += 1
        elif normalize_domain(url) is None: reasons['invalid_url'] += 1
        elif is_rental_result(row): reasons['rental_service'] += 1
        else: seen.add(url)
    return dict(reasons)


def source_plan(source):
    """Allocate HTTP work, never certify a product from URL/snippet alone."""
    import re
    from app.services.extraction.product_page_validator import classify_source, possible_product_url
    from app.services.search.merchant_quality import MerchantQualityService
    kind = classify_source(source.url)
    path = urlsplit(source.url).path.lower()
    if (kind in {'ARTICLE', 'NEWS', 'REVIEW'}
            or re.search(r'/(?:tags?|feed|support|sforum|forums?|thread|hoi-dap|kinh-nghiem-mua-sam|newsroom|press|events?)(?:/|$)', path)
            or re.search(r'/(?:top-|so-sanh-|danh-gia-)|_vs_',path)
            or (urlsplit(source.url).hostname or '').removeprefix('www.') == 'devicespecifications.com'
            or MerchantQualityService().assess(source)['kind'] == 'editorial_news'):
        return 'metadata'
    if (kind in {'HOMEPAGE', 'CATEGORY', 'SEARCH_PAGE'} or not possible_product_url(source.url)
            or re.search(r'^/(?:bo-loc|danh-muc|clp|b)/', path)
            or ((urlsplit(source.url).hostname or '').removeprefix('www.') == 'cellphones.com.vn'
                and path.startswith('/mobile/'))):
        return 'discovery'
    return 'product'


def rejection_reason(proof, retriever):
    from app.services.filter.hard_filter import HardFilterService
    if not proof.get('product_page_valid'):
        code = proof.get('rejection_code')
        if (proof.get('category_evidence') or {}).get('conflict'): return 'wrong_category'
        if code in {'missing_price', 'missing_identity', 'non_product_page'}: return code
        if proof.get('result_type') in {'ARTICLE', 'NEWS', 'REVIEW', 'CATEGORY', 'HOMEPAGE', 'SEARCH_PAGE'}:
            return 'non_product_page'
        if proof.get('page_requested') and not proof.get('page_fetched') and proof.get('fetch_blocked'):
            return 'http_network_failure'
        reason = str(proof.get('reason', '')).lower()
        if 'price' in reason or 'giá' in reason: return 'missing_price'
        return 'other'
    if proof.get('price') is None: return 'missing_price'
    if retriever.requirement:
        decision = HardFilterService().evaluate(retriever.candidate(proof), retriever.requirement)
        if not decision.accepted:
            return {'category':'wrong_category', 'availability':'out_of_stock'}.get(decision.rejection_stage, 'other')
    if is_unavailable(proof.get('availability')): return 'out_of_stock'
    return None


def conversion_stats(sources, retriever, requested_urls=None):
    """Counts scoped to unique URLs in this query/round, at completion time.

    Page counters count URLs; candidate/reason counters count concrete offers.
    A metadata fallback can verify an offer even though no page was fetched.
    """
    from collections import Counter
    from app.services.extraction.product_page_validator import identity_tokens
    sources = list({s.url:retriever.sources.get(s.url, s) for s in sources}.values())
    stats = dict.fromkeys(('potential_product_urls', 'direct_product_candidates', 'evidence_only_results',
        'rejected_before_fetch', 'pages_requested', 'pages_fetched', 'pages_verified', 'verification_failed',
        'wrong_category', 'non_product_page', 'missing_price', 'missing_identity', 'out_of_stock',
        'duplicate', 'http_network_failure', 'other', 'valid_candidates', 'eligible_offers', 'reused_pages'), 0)
    eligible = set()
    reasons = Counter()
    for source in sources:
        page = source.page_validation or {}
        if (retriever.plans.get(source.url) or source_plan(source)) == 'product':
            stats['potential_product_urls'] += 1
        if not page: continue  # Pending, never pretend an unrequested page failed verification.
        requested = page.get('page_requested', False)
        new_request = requested and (requested_urls is None or source.url in requested_urls)
        stats['reused_pages'] += bool(requested and not new_request)
        stats['pages_requested'] += bool(new_request)
        stats['pages_fetched'] += bool(new_request and page.get('page_fetched'))
        stats['pages_verified'] += bool(new_request and page.get('product_page_valid'))
        stats['verification_failed'] += bool(new_request and not page.get('product_page_valid'))
        stats['rejected_before_fetch'] += not requested
        stats['evidence_only_results'] += not page.get('product_page_valid')
        if new_request and not page.get('page_fetched') and page.get('fetch_blocked'):
            stats['http_network_failure'] += 1
        for proof in concrete_proofs(page) or [page]:
            stats['direct_product_candidates'] += bool(proof.get('product_page_valid'))
            reason = rejection_reason(proof, retriever)
            if reason:
                reasons[reason] += 1
                if reason != 'http_network_failure': stats[reason] += 1
                continue
            stats['valid_candidates'] += 1
            identity = tuple(sorted(identity_tokens(proof.get('name'))))
            if identity in eligible:
                stats['duplicate'] += 1
                reasons['duplicate'] += 1
            eligible.add(identity)
    stats['eligible_offers'] = len(eligible)
    stats['reason_counts'] = dict(reasons)
    return stats


def audit_source(query,source,retriever):
    page=source.page_validation or {}
    offers=concrete_proofs(page)
    observations=offers or page.get('discovery') or [{}]
    rows=[]
    for item in observations:
        verified=bool(item.get('product_page_valid'))
        decision=None
        if verified and retriever.requirement:
            from app.services.filter.hard_filter import HardFilterService
            decision=HardFilterService().evaluate(retriever.candidate(item),retriever.requirement)
        availability=item.get('availability')
        available_key=normalized((availability or '').rsplit('/',1)[-1])
        category=item.get('category')
        evidence=item.get('category_evidence') or page.get('category_evidence') or {}
        observed=evidence.get('observations') or {}
        category_status='UNKNOWN' if not category else ('MATCHED' if not retriever.requirement or
            not retriever.requirement.category or category_matches(retriever.requirement.category,category) else 'MISMATCH')
        if verified:
            stage=decision.rejection_stage if decision else None
            reason='; '.join(decision.reasons) if decision and not decision.accepted else None
        elif item:
            stage,reason='concrete_offer','Model/variant discovery only; no verified concrete seller price.'
        else:
            stage=('source_type' if page.get('verification_level')=='REJECTED' else
                   'fetch_or_metadata' if page.get('fetch_blocked') else 'page_identity_or_price')
            reason=page.get('reason')
        rows.append(dict(QUERY=query,TITLE=source.title,SNIPPET=source.content,DOMAIN=urlsplit(source.url).hostname,URL=source.url,
            CATEGORY_EVIDENCE=evidence or None,CATEGORY_EVIDENCE_SOURCE=evidence.get('source'),
            CATEGORY_DECISION=category,H1=observed.get('h1',page.get('page_heading')),
            JSON_LD_TYPE=observed.get('json_ld_type'),JSON_LD_CATEGORY=observed.get('json_ld_category'),
            BREADCRUMB=observed.get('breadcrumbs'),URL_PATH=urlsplit(source.url).path,
            PRODUCT_IDENTITY=item.get('name'),PRODUCT_PAGE_VALID=verified,
            VERIFICATION_LEVEL=page.get('verification_level','UNVERIFIED'),
            SOURCE_TYPE=source.result_type,BRAND=item.get('brand'),MODEL=item.get('model'),
            CATEGORY=category,MERCHANT=item.get('merchant'),AVAILABILITY=availability,
            VARIANT=item.get('variant'),NAME=item.get('name'),PRICE_TYPE=item.get('price_type','UNKNOWN'),
            PRICE=item.get('price') if verified else None,PRICE_MIN=item.get('price_min'),PRICE_MAX=item.get('price_max'),
            PAGE_VERIFICATION=page.get('verification_level','UNVERIFIED'),
            IDENTITY_STATUS='MATCHED' if verified else 'DISCOVERY_ONLY' if item else 'UNKNOWN',
            CATEGORY_STATUS=category_status,AVAILABILITY_STATUS='UNAVAILABLE' if is_unavailable(availability) else
                'AVAILABLE' if available_key in {'in stock','instock','available','con hang'} else 'UNKNOWN',
            REJECT_STAGE=stage,REJECT_REASON=reason,STOP_READY=retriever.ready(item) if verified else False))
    return rows
