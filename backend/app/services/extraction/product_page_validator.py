"""Conservative, deterministic sales-page and product identity checks.

No URL is constructed from a product name. A product path alone is not proof.
"""
import json
import re
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit

from app.services.normalization.text_normalizer import normalize_product_text
from app.services.normalization.price_parser import parse_price


BAD_PATH = re.compile(r"(?:^|/)(?:category|categories|collections?|search|tim-kiem|blog|news|tin-tuc|review|reviews|bai-viet|thuong-hieu|brands?|tags?|bang-gia|so-sanh)(?:/|$)")
CATEGORY_PATHS = {"xe-may", "dien-thoai", "laptop", "tivi", "tv", "tai-nghe", "san-pham", "products", "product", "shop"}
BAD_IMAGES = re.compile(r"logo|favicon|icon|banner|category|danh-muc|advert|quang-cao|placeholder|placehoder|sprite|tracking|avatar|no[-_]image", re.I)
VARIANTS = {"pro", "max", "plus", "ultra", "mini", "lite", "alpha", "rsx"}
NOISE = {"chinh", "hang", "gia", "ban", "mua", "san", "pham", "dien", "thoai", "xe", "may", "tivi", "tv", "smart", "laptop", "moi", "nhat", "chiec"}


def http_url(value, base=None):
    if not isinstance(value, str) or not value.strip():
        return None
    value = urljoin(base, value.strip()) if base else value.strip()
    try:
        p = urlsplit(value)
        if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
            return None
        if p.port not in {None, 80, 443}:
            return None
    except ValueError:
        return None
    return value


def possible_product_url(url):
    """Reject known nonsales routes; acceptance still needs page evidence."""
    if not http_url(url):
        return False
    p = urlsplit(url)
    path = unquote(p.path).lower().strip('/')
    if not path or path in CATEGORY_PATHS or BAD_PATH.search(path):
        return False
    if re.search(r"(?:^|&)(?:q|query|search|s)=", p.query, re.I):
        return False
    return not re.search(r"(?:^|[-/])(?:review|tin-tuc|blog|news)(?:[-/]|$)", path)


def identity_tokens(name):
    text = normalize_product_text(name) or ''
    text = re.sub(r"(\d+)\s+(gb|tb|cc)\b", r"\1\2", text)
    return set(re.findall(r"[a-z0-9]+", text)) - NOISE


def structured_price(value):
    """Schema.org/OG use decimal numbers, unlike grouped display-price text."""
    text = str(value).strip()
    if re.fullmatch(r'\d+(?:\.\d{1,2})?', text):
        try:
            number = Decimal(text)
            return int(number) if number > 0 and number == int(number) else None
        except (InvalidOperation, ValueError):
            return None
    return parse_price(text + ' VND') if re.fullmatch(r'\d{1,3}(?:[.,]\d{3})+', text) else None


def same_identity(left, right):
    """Require model/version/capacity agreement, allowing descriptive suffixes."""
    a, b = identity_tokens(left), identity_tokens(right)
    if not a or not b:
        return False
    if (a & VARIANTS) != (b & VARIANTS):
        return False
    ids_a = {t for t in a if any(c.isdigit() for c in t)}
    ids_b = {t for t in b if any(c.isdigit() for c in t)}
    if ids_a != ids_b:
        return False
    return min(len(a), len(b)) >= 2 and (a <= b or b <= a)


def main_product_identity(product, heading, url):
    """Reconcile source formatting only with an explicit same-page binding."""
    name = product.get('name')
    if not isinstance(name, str): return False
    if same_identity(name, heading): return True
    from urllib.parse import unquote, urldefrag
    from app.services.extraction.dealer_offers import same_page
    entity = product.get('mainEntityOfPage')
    reference = entity.get('@id') if isinstance(entity, dict) else entity
    if not isinstance(reference, str) or not same_page(urldefrag(reference)[0], url): return False
    path = unquote(urlsplit(url).path).replace('-', ' ')
    def formatted(value):
        # FI can be attached to displacement in H1 but separated in the URL.
        return re.sub(r'(\d+)\s+fi\b', r'\1FI', value, flags=re.I)
    if not same_identity(formatted(heading), formatted(path)): return False
    # Explicit zero-interest financing is not a model number. Other numeric
    # differences remain identity conflicts, including price/capacity/version.
    cleaned = re.sub(r'\b(?:trả\s+góp|tra\s+gop|installments?)\s+0\s*%', '', name, flags=re.I)
    if cleaned != name and same_identity(formatted(cleaned), formatted(heading)): return True
    if re.search(r'\b(?:19|20)\d{2}\b', heading + ' ' + path): return False
    # Never strip capacity/model digits or reconcile conflicting explicit years.
    years = re.findall(r'\b(?:19|20)\d{2}\b', name)
    return len(set(years)) == 1 and same_identity(re.sub(r'\b(?:19|20)\d{2}\b', '', name), heading)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.blocks, self.images = {}, [], []
        self.title, self.h1, self.text = [], [], []
        self.headings, self.current_heading = [], None
        self.script = None
        self.in_title = self.in_h1 = False
        self.property_tag = None
        self.property_name = None
        self.properties = {}
        self.discovery_fields = []
        self.discovery_capture = None
        self.select_kind = None
        self.breadcrumbs = []
        self.breadcrumb_capture = None
        self.breadcrumb_depth = 0
        self.product_links = []
        self.product_link = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        css = a.get('class', '').lower()
        if tag == 'a' and a.get('href') and ('product' in css or a.get('itemprop') == 'url'):
            self.product_link = {'href': a['href'], 'text': []}
        void = tag in {'meta','img','br','hr','input','link','source','wbr'}
        if self.breadcrumb_capture is not None and not void:
            self.breadcrumb_depth += 1
        elif not void and ('breadcrumb' in css or 'breadcrumb' in a.get('aria-label','').lower()):
            self.breadcrumb_capture = []
            self.breadcrumb_depth = 1
        if ('crumb' in css and 'current' in css) or a.get('aria-current') == 'page':
            self.discovery_capture = ['model', tag, []]
        if any(marker in css for marker in ('proposal-price', 'suggested-price', 'recommended-price')):
            self.discovery_capture = ['suggested_price', tag, []]
        if tag == 'select':
            self.select_kind = 'variant' if re.search(r'version|variant', a.get('name', ''), re.I) else None
        if tag == 'option' and self.select_kind and a.get('value'):
            self.discovery_capture = ['variant', tag, []]
        if tag == 'script':
            self.script = [] if a.get('type', '').lower() == 'application/ld+json' else False
        if tag == 'title': self.in_title = True
        if tag == 'h1':
            self.in_h1 = True
            self.current_heading = []
        if tag == 'meta':
            self.meta[(a.get('property') or a.get('name') or a.get('itemprop') or '').lower()] = a.get('content') or ''
        if tag == 'img':
            self.images.append(a)
        if 'ProductPrice' in a.get('class', '').split() or a.get('id') == 'ProductPrice':
            # Explicit main-product price marker, not generic related-card "price".
            self.property_tag, self.property_name = tag, 'price'
            self.properties['price'] = a.get('content') or ''
        if a.get('itemprop') in {'price', 'priceCurrency'}:
            self.property_tag, self.property_name = tag, a['itemprop']
            self.properties[a['itemprop']] = a.get('content') or ''
            if tag == 'meta': self.property_tag = self.property_name = None

    def handle_data(self, data):
        if isinstance(self.script, list): self.script.append(data)
        if self.script is not None: return
        if self.product_link is not None: self.product_link['text'].append(data)
        if self.breadcrumb_capture is not None: self.breadcrumb_capture.append(data)
        if self.discovery_capture: self.discovery_capture[2].append(data)
        if self.in_title: self.title.append(data)
        if self.in_h1: self.h1.append(data)
        if self.current_heading is not None: self.current_heading.append(data)
        if self.property_name:
            self.properties[self.property_name] += data
        self.text.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.product_link is not None:
            if len(self.product_links) < 30: self.product_links.append(self.product_link)
            self.product_link = None
        if self.breadcrumb_capture is not None and tag not in {'meta','img','br','hr','input','link','source','wbr'}:
            self.breadcrumb_depth -= 1
            if self.breadcrumb_depth <= 0:
                self.breadcrumbs.append(' > '.join(s.strip() for s in self.breadcrumb_capture if s.strip()))
                self.breadcrumb_capture = None
        if self.discovery_capture and self.discovery_capture[1] == tag:
            kind, _, values = self.discovery_capture
            self.discovery_fields.append((kind, ' '.join(values).strip()))
            self.discovery_capture = None
        if tag == 'select': self.select_kind = None
        if tag == 'script':
            if isinstance(self.script, list): self.blocks.append(''.join(self.script))
            self.script = None
        if tag == 'title': self.in_title = False
        if tag == 'h1':
            self.in_h1 = False
            if self.current_heading is not None:
                self.headings.append(' '.join(self.current_heading).strip())
                self.current_heading = None
        if tag == self.property_tag:
            self.property_tag = self.property_name = None

    @property
    def heading(self):
        return next((h for h in self.headings if h), ' '.join(self.title).strip())


def products_in(value):
    if isinstance(value, list):
        for child in value: yield from products_in(child)
    elif isinstance(value, dict):
        types = value.get('@type', [])
        types = [types] if isinstance(types, str) else types
        if any(str(t).rstrip('/').split('/')[-1].lower() == 'product' for t in types):
            yield value
            return
        # ItemList/recommendation carousels are not the page's main product.
        for key in ('@graph', 'mainEntity'):
            if key in value: yield from products_in(value[key])


def declared_page_kind(parser):
    """Inspect page-level structured types, not nested related products."""
    kinds = {'newsarticle': 'NEWS', 'article': 'ARTICLE', 'blogposting': 'ARTICLE',
             'review': 'REVIEW', 'collectionpage': 'CATEGORY', 'itemlist': 'CATEGORY',
             'searchresultspage': 'SEARCH_PAGE'}
    def types(value):
        if isinstance(value, list):
            for child in value: yield from types(child)
        elif isinstance(value, dict):
            value_types = value.get('@type', [])
            if isinstance(value_types, str): value_types = [value_types]
            yield from (str(t).rstrip('/').split('/')[-1].lower() for t in value_types)
            yield from types(value.get('@graph'))
    for block in parser.blocks:
        try:
            for kind in types(json.loads(block)):
                if kind in kinds: return kinds[kind]
        except (ValueError, TypeError): continue
    if parser.meta.get('og:type', '').lower() == 'article': return 'ARTICLE'
    return None


def classify_source(url, *, parser=None, proof=None):
    """DIRECT_PRODUCT requires content validation; a suggestive URL is UNKNOWN."""
    if not http_url(url): return 'UNKNOWN'
    parsed = urlsplit(url)
    path = unquote(parsed.path).strip('/').lower()
    if re.search(r'(?:^|&)(?:q|query|search|s)=', parsed.query, re.I) or re.search(r'(^|/)(search|tim-kiem)(/|$)', path):
        return 'SEARCH_PAGE'
    if not path: return 'HOMEPAGE'
    if re.search(r'(^|[-/])(reviews?)([-/]|$)', path): return 'REVIEW'
    if re.search(r'(^|/)(news|tin-tuc)(/|$)', path): return 'NEWS'
    if re.search(r'(^|/)(blog|bai-viet|kinh-nghiem-hay)(/|$)', path): return 'ARTICLE'
    if path.removesuffix('.html') in CATEGORY_PATHS or re.search(r'(^|/)(category|categories|collections?|tags?|brands?|thuong-hieu)(/|$)', path):
        return 'CATEGORY'
    if parser:
        declared = declared_page_kind(parser)
        if declared: return declared
    if proof and proof.get('product_page_valid') and possible_product_url(url):
        return 'DIRECT_PRODUCT'
    return 'UNKNOWN'


def image_values(value):
    if isinstance(value, str): yield value
    elif isinstance(value, list):
        for item in value: yield from image_values(item)
    elif isinstance(value, dict):
        yield from image_values(value.get('url') or value.get('contentUrl'))


def inspect_page(url, html, expected_name=''):
    """Return evidence plus image candidates; network validation is a separate step."""
    result = dict(product_page_valid=False, evidence_url=url, image_url=None, image_source=None,
                  verification_level='UNVERIFIED', product_page_confidence=0, fetch_blocked=False,
                  reason='Chưa xác minh được trang bán sản phẩm cụ thể.')
    result['result_type'] = classify_source(url)
    parser = PageParser()
    parser.feed(html)
    result['page_heading'] = parser.heading
    from app.services.extraction.product_discovery import discover_products
    result['discovery'] = discover_products(parser, url)
    kind = classify_source(url, parser=parser)
    if kind in {'CATEGORY', 'SEARCH_PAGE', 'HOMEPAGE'}:
        from app.services.extraction.product_discovery import discover_child_products
        result['child_products'] = discover_child_products(parser, url)
    if not possible_product_url(url):
        result['verification_level'] = 'REJECTED'
        result['reason'] = 'URL là trang chủ/danh mục/tìm kiếm/bài viết hoặc không an toàn.'
        return result
    kind = classify_source(url, parser=parser)
    result['result_type'] = kind
    if kind in {'ARTICLE', 'NEWS', 'REVIEW', 'CATEGORY', 'HOMEPAGE', 'SEARCH_PAGE'}:
        result['verification_level'] = 'REJECTED'
        result['reason'] = 'Trang không phải trang bán sản phẩm: ' + kind
        return result
    heading = parser.heading
    # An interstitial or a JS-only shell is unavailable content, not contrary
    # product evidence. Search-metadata verification still has its own hard gates.
    visible = normalize_product_text(' '.join(parser.text)) or ''
    blocked = any(marker in visible for marker in ('just a moment', 'verify you are human',
        'access denied', 'enable javascript', 'checking your browser', 'captcha'))
    js_shell = not parser.h1 and not parser.blocks and bool(re.search(r'id=["\x27](?:root|app|__next)["\x27]', html))
    if blocked or js_shell:
        result.update(fetch_blocked=True, reason='Page requires browser/JS or access verification.')
        return result
    nodes = []
    for block in parser.blocks:
        try: nodes.extend(products_in(json.loads(block)))
        except (ValueError, TypeError): continue
    nodes = [n for n in nodes if isinstance(n.get('name'), str) and
             (not heading or main_product_identity(n, heading, url))]
    unique = {tuple(sorted(identity_tokens(n['name']))) for n in nodes}
    product = nodes[0] if len(unique) == 1 else None
    name = product['name'] if product else heading
    from app.services.extraction.dealer_offers import dealer_variant_proofs
    variants = dealer_variant_proofs(parser, html, url, product)
    if variants:
        # Concrete variants have already passed identity/price validation.
        # Apply the same page taxonomy as single offers before returning them.
        from app.services.extraction.category_evidence import category_evidence, variant_category_evidence
        from html import unescape
        schema_taxonomy = (product or {}).get('category')
        normalized_taxonomy = (variants[0].get('category') if isinstance(schema_taxonomy,str)
                               and '>' in unescape(schema_taxonomy) else None)
        category_proof = category_evidence(parser, product, url, verified=True,
                                          normalized_schema_category=normalized_taxonomy)
        if category_proof['conflict']:
            result.update(category_evidence=category_proof, reason=category_proof['reason'])
            return result
        accepted = []
        rejected = []
        for variant in variants:
            inherited = variant_category_evidence(category_proof, variant)
            if inherited['conflict']:
                rejected.append({'name':variant['name'], 'category_evidence':inherited})
                continue
            # Preserve the parser's existing explicit taxonomy normalization;
            # fill only missing category from the shared page evidence.
            variant.update(category=variant.get('category') or inherited['category'],
                           category_evidence=inherited)
            accepted.append(variant)
        if rejected: result['rejected_variants'] = rejected
        if not accepted:
            result.update(category_evidence=rejected[0]['category_evidence'],
                          reason=rejected[0]['category_evidence']['reason'])
            return result
        variants = accepted
        if expected_name:
            selected = [v for v in variants if identity_tokens(v['name']) == identity_tokens(expected_name)]
            if len(selected) == 1: return {**result, **selected[0]}
            result['reason'] = 'Requested variant does not match one explicit seller price row.'
            return result
        result.update(product_page_valid=True,result_type='DIRECT_PRODUCT',verification_level='VERIFIED_CONTENT',
                      product_page_confidence=95,name=name,price_type='VARIANT_OFFERS',variant_offers=variants,
                      reason='Verified explicit variants; no single price is assigned to the base model.')
        return result
    if not name or (expected_name and not same_identity(name, expected_name)):
        result['rejection_code'] = 'missing_identity'
        return result
    offer = None
    if product:
        offers = product.get('offers', [])
        offers = [offers] if isinstance(offers, dict) else offers
        # Aggregate/range prices cannot identify a purchasable variant.
        valid = [o for o in offers if isinstance(o, dict) and o.get('@type') != 'AggregateOffer' and o.get('price') is not None and
                 o.get('priceCurrency', '').upper() == 'VND' and
                 (not o.get('url') or http_url(o['url'], url) == url)]
        prices = {str(o['price']) for o in valid}
        if len(prices) == 1: offer = valid[0]
    text = normalize_product_text(' '.join(parser.text)) or ''
    buy = any(x in text for x in ('them vao gio', 'mua ngay', 'dat hang', 'dat xe', 'dang ky mua', 'lien he mua', 'add to cart', 'buy now'))
    og_product = 'product' in parser.meta.get('og:type', '').lower()
    price = structured_price(offer['price']) if offer else None
    micro_price = parser.properties.get('price', '')
    micro_currency = parser.properties.get('priceCurrency', '').strip().upper()
    explicit_html_price = bool(micro_price and (micro_currency == 'VND' or re.search(r'VND|₫|đ', micro_price)))
    if price is None and buy and parser.h1 and explicit_html_price:
        price = parse_price(micro_price + ' VND')
    if price is None and og_product and buy and parser.meta.get('product:price:currency', '').upper() == 'VND':
        price = structured_price(parser.meta.get('product:price:amount', ''))
    if not price or not (offer or ((og_product or explicit_html_price) and buy)) or len(identity_tokens(name)) < 2:
        if not price and product and buy and len(identity_tokens(name)) >= 2:
            # Diagnostics only; keep the same rejection gate and evidence.
            result['rejection_code'] = 'missing_price'
        elif len(identity_tokens(name)) < 2:
            result['rejection_code'] = 'missing_identity'
        return result
    if not product and nodes: return result
    seller = offer.get('seller') if offer else None
    merchant = seller.get('name') if isinstance(seller, dict) else None
    brand = product.get('brand') if product else None
    brand = brand.get('name') if isinstance(brand, dict) else brand
    # Brand catalog/MSRP pages must also expose a purchase action.
    host = urlsplit(url).hostname or ''
    brand_key = re.sub('[^a-z0-9]', '', normalize_product_text(brand) or '')
    if brand_key and host.removeprefix('www.').split('.')[0] == brand_key and not buy:
        return result
    aggregate = product.get('aggregateRating') or {} if product else {}
    if not isinstance(aggregate, dict): aggregate = {}
    specs = {}
    from app.services.extraction.category_evidence import category_evidence
    category_proof = category_evidence(parser, product, url, verified=True)
    if category_proof['conflict']:
        result.update(category_evidence=category_proof, reason=category_proof['reason'])
        return result
    category = category_proof['category']
    for prop in (product.get('additionalProperty') or []) if product else []:
        if isinstance(prop, dict) and prop.get('name') and prop.get('value') is not None:
            specs[str(prop['name']).lower()] = str(prop['value'])
    result.update(product_page_valid=True, result_type='DIRECT_PRODUCT', product_url=url, name=name.strip(), brand=brand,
                  price_type='CONCRETE',
                  variant={key: product[key] for key in ('sku', 'color', 'size') if isinstance(product.get(key), str)} if product else None,
                  category=category, category_evidence=category_proof,
                  verification_level='VERIFIED_CONTENT', product_page_confidence=95,
                  confidence_signals={'page_identity': 30, 'same_page_price': 25, 'product_metadata_or_buy_action': 30, 'direct_path': 10},
                  model=product.get('model') if product else None, price=price,
                  merchant=merchant or urlsplit(url).hostname, specifications=specs,
                  rating=aggregate.get('ratingValue'), review_count=aggregate.get('reviewCount'),
                  availability=offer.get('availability') if offer else None,
                  reason='Trang chi tiết có identity và giá bán cụ thể cùng nguồn.')
    from app.services.extraction.product_image_candidates import collect_product_images
    result['image_diagnostics'] = {}
    result['image_candidates'] = collect_product_images(parser, product, url=url, name=name, brand=brand,
                                                       html=html, diagnostics=result['image_diagnostics'])
    return result
