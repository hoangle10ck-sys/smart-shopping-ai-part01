"""Source-backed model/variant hints. These never certify a sale or an offer."""
import json


def discover_child_products(parser, page_url):
    """Extract bounded same-origin links; every child still needs verification."""
    from urllib.parse import urlsplit
    import ipaddress
    from app.services.extraction.product_page_validator import http_url, possible_product_url
    found = {}
    def add(name, link):
        if not isinstance(name, str) or not name.strip(): return
        url = http_url(link, page_url)
        if not url or url == page_url or not possible_product_url(url): return
        host = urlsplit(url).hostname or ''
        if host != urlsplit(page_url).hostname or host == 'localhost' or host.endswith('.localhost'): return
        try:
            if not ipaddress.ip_address(host).is_global: return
        except ValueError:
            pass  # Runtime DNS/public-address check is still mandatory in resolver.
        if len(found) < 12:
            found.setdefault(url, {'name': name.strip(), 'url': url, 'parent_url': page_url})

    def visit(node, in_list=False):
        if isinstance(node, list):
            for item in node[:30]: visit(item, in_list)
        elif isinstance(node, dict):
            if in_list:
                item = node.get('item', node)
                if isinstance(item, dict): add(item.get('name'), item.get('url'))
            for key in ('@graph', 'mainEntity'): visit(node.get(key))
            visit(node.get('itemListElement'), True)
    for block in parser.blocks:
        try: visit(json.loads(block))
        except (ValueError, TypeError): continue
    for link in getattr(parser, 'product_links', []):
        add(' '.join(link['text']), link['href'])
    return list(found.values())


def discover_products(parser, url=''):
    from app.services.extraction.product_page_validator import same_identity, structured_price
    from app.services.extraction.product_extraction_service import infer_brand, infer_model
    heading = parser.heading
    found = []

    def visit(node, inherited=None):
        if isinstance(node, list):
            for item in node[:30]: visit(item, inherited)
        elif isinstance(node, dict):
            kind = node.get('@type')
            if kind in ('Product', 'ProductGroup'):
                name = node.get('name')
                if not isinstance(name, str) or not name.strip(): return
                # Never promote recommendation-carousel identities into page identity.
                if not inherited and heading and not same_identity(name, heading): return
                brand = node.get('brand') or (inherited or {}).get('brand')
                if isinstance(brand, dict): brand = brand.get('name')
                model = node.get('model') or (inherited or {}).get('model')
                if isinstance(model, dict): model = model.get('name')
                offers = node.get('offers') or []
                if isinstance(offers, dict): offers = [offers]
                ranges = [o for o in offers if isinstance(o, dict) and o.get('@type') == 'AggregateOffer']
                variants = {k: node[k] for k in ('sku', 'color', 'size') if isinstance(node.get(k), str)}
                brand = brand if isinstance(brand, str) else infer_brand(name)
                clean_name = heading if heading and same_identity(name,heading) else name.strip()
                if brand and brand.lower() not in clean_name.lower(): clean_name = brand + ' ' + clean_name
                hint = dict(name=clean_name, brand=brand,
                            model=model if isinstance(model, str) else infer_model(clean_name,brand), variant=variants,
                            price_type='AGGREGATE_RANGE' if ranges else 'DISCOVERY_ONLY')
                if len(ranges) == 1 and ranges[0].get('priceCurrency') == 'VND':
                    hint.update(price_min=structured_price(ranges[0].get('lowPrice')),
                                price_max=structured_price(ranges[0].get('highPrice')))
                found.append(hint)
                visit(node.get('hasVariant'), hint)
            else:
                for key in ('@graph', 'mainEntity'): visit(node.get(key))

    for block in parser.blocks:
        try: visit(json.loads(block))
        except (ValueError, TypeError): continue
    if not found and url:
        # Current breadcrumb + matching URL identify a model, not a sales offer.
        from urllib.parse import urlsplit, unquote
        from app.services.normalization.text_normalizer import normalize_product_text
        from app.services.normalization.price_parser import parse_price
        fields = parser.discovery_fields
        brand = parser.meta.get('product:brand') or infer_brand(' '.join(parser.title) + ' ' + parser.meta.get('og:title',''))
        slug = normalize_product_text(unquote(urlsplit(url).path).rsplit('/',1)[-1]) or ''
        models = [v for k,v in fields if k=='model' and normalize_product_text(v)==slug]
        if brand and len(set(models)) == 1:
            prices = [parse_price(v) for k,v in fields if k=='suggested_price' and
                      any(mark in v.upper() for mark in ('VND','VNĐ','₫'))]
            prices = [p for p in prices if p]
            hint = dict(name=f'{brand} {models[0]}',brand=brand,model=models[0],variant={},
                        price_type='SUGGESTED_RANGE',price_min=min(prices) if prices else None,
                        price_max=max(prices) if prices else None)
            found.append(hint)
            for variant in dict.fromkeys(v for k,v in fields if k=='variant' and v):
                found.append({**hint,'variant':{'version':variant},'price_min':None,'price_max':None})
    return found[:12]
