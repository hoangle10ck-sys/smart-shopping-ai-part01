"""Audit observations without upgrading discovery hints to verified offers."""
from urllib.parse import urlsplit
from app.services.extraction.dealer_offers import concrete_proofs
from app.services.filter.hard_filter import category_matches, is_unavailable, normalized


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
