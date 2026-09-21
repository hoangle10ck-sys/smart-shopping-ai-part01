"""Conservative fallback only when fetching a direct page was blocked/failed."""
import re
from urllib.parse import unquote, urlsplit

from app.services.extraction.product_page_validator import (classify_source, possible_product_url,
    identity_tokens, same_identity, VARIANTS)
from app.services.extraction.product_extraction_service import (PRICE_PATTERNS, infer_brand,
    infer_model, extract_basic_specs)
from app.services.normalization.price_parser import parse_price
from app.services.normalization.product_normalizer import infer_product_category
from app.services.search.merchant_quality import MerchantQualityService
from app.services.search.source_strategy import normalize_text

METADATA_THRESHOLD = 90


def verify_search_metadata(source, fetched):
    result = {**fetched, 'verification_level': 'UNVERIFIED', 'product_page_confidence': 0,
              'product_page_valid': False, 'image_url': None, 'image_source': None}
    kind = classify_source(source.url)
    if not possible_product_url(source.url) or kind != 'UNKNOWN':
        result.update(verification_level='REJECTED', reason='Non-product URL cannot use metadata fallback.')
        return result
    if not fetched.get('fetch_blocked'):
        return result
    title, snippet = source.title or '', source.content or ''
    editorial = r'\b(top\s+\d|so sanh|danh gia|review|bang gia|danh sach|nen mua|tot nhat|cac mau)\b'
    if re.search(editorial, normalize_text(title + ' ' + snippet)):
        result.update(verification_level='REJECTED', reason='Editorial/multiple-product search metadata.')
        return result
    name = re.split(r'\s[|–—]\s|\s-\s|,|\bgiá\b|\bGiá\b', title)[0].strip()
    name = re.sub(r'\s+(chính hãng|Chính hãng).*$', '', name).strip()
    slug = unquote(urlsplit(source.url).path.rstrip('/').rsplit('/', 1)[-1])
    slug = re.sub(r'\.(html?|aspx)$', '', slug, flags=re.I).replace('-', ' ')
    tokens = identity_tokens(name)
    if len(tokens) < 2 or not same_identity(name, slug):
        result['reason'] = 'Title and direct URL must identify the same model/variant.'
        return result
    if not any(any(char.isdigit() for char in token) for token in tokens) and len(tokens) < 3:
        result['reason'] = 'Insufficient model specificity for metadata-only verification.'
        return result
    normalized_name = normalize_text(name)
    normalized_snippet = normalize_text(snippet)
    if normalized_name not in normalized_snippet:
        result['reason'] = 'Exact product identity is missing from snippet.'
        return result
    # Do not treat a base model prefix in a Pro/Max/etc snippet as the base model.
    for occurrence in re.finditer(re.escape(normalized_name), normalized_snippet):
        suffix = normalized_snippet[occurrence.end():].strip().split()[:1]
        if suffix and suffix[0] in VARIANTS and suffix[0] not in tokens:
            result.update(verification_level='REJECTED', reason='Snippet variant contradicts title.')
            return result
    quality = MerchantQualityService().assess(source)
    prices = {parse_price(match.group()) for pattern in PRICE_PATTERNS for match in pattern.finditer(snippet)} - {None}
    if len(prices) != 1 or not quality['commercial']:
        result['reason'] = 'Need one unambiguous same-source price and commercial merchant signals.'
        return result
    price = next(iter(prices))
    signals = {'title_identity': 25, 'url_identity': 30, 'snippet_identity': 20,
               'same_source_price': 15, 'merchant': 5}
    confidence = sum(signals.values())
    if confidence < METADATA_THRESHOLD: return result
    brand = infer_brand(name)
    result.update(product_page_valid=True, result_type='DIRECT_PRODUCT',
        verification_level='VERIFIED_SEARCH_METADATA', product_page_confidence=confidence,
        confidence_signals=signals, name=name, brand=brand, model=infer_model(name, brand),
        price=price, price_type='CONCRETE', product_url=source.url, evidence_url=source.url, merchant=quality['domain'],
        category=(infer_product_category(name) or infer_product_category(title + ' ' + snippet)
                  or infer_product_category(unquote(urlsplit(source.url).path))),
        merchant_quality=quality, specifications=extract_basic_specs(snippet),
        reason='Strong same-source title/slug/snippet/price; HTML fetch unavailable. Not content-verified.')
    return result
