"""Explicit main-product variant/price mappings; never derive an offer from a range."""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit


class DealerParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms, self.tables = [], []
        self.table = self.row = self.cell = None
        self.caption = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form' and 'data-product_variations' in attrs:
            try:
                values = json.loads(attrs['data-product_variations'])
                if isinstance(values, list): self.forms.append((attrs, values[:100]))
            except (ValueError, TypeError): pass
        if tag == 'table':
            self.table = {'product': attrs.get('data-product'), 'caption': '', 'rows': []}
        if tag == 'caption' and self.table is not None: self.caption = True
        if tag == 'tr' and self.table is not None: self.row = []
        if tag in {'td', 'th'} and self.row is not None: self.cell = ''

    def handle_data(self, value):
        if self.caption and self.table is not None: self.table['caption'] += value
        if self.cell is not None: self.cell += value

    def handle_endtag(self, tag):
        if tag in {'td', 'th'} and self.cell is not None:
            self.row.append(self.cell.strip()); self.cell = None
        if tag == 'tr' and self.row is not None:
            self.table['rows'].append(self.row); self.row = None
        if tag == 'caption': self.caption = False
        if tag == 'table' and self.table is not None:
            self.tables.append(self.table); self.table = self.row = self.cell = None


def same_page(left, right):
    a, b = urlsplit(left), urlsplit(right)
    return (a.scheme, a.netloc, a.path.rstrip('/'), a.query) == (b.scheme, b.netloc, b.path.rstrip('/'), b.query)


def variant_mappings(html, url, name, *, currency=None):
    """Return only explicit, unique variant -> price associations for this page."""
    from app.services.extraction.product_page_validator import http_url, same_identity, structured_price
    from app.services.normalization.price_parser import parse_price
    from app.services.normalization.text_normalizer import normalize_product_text
    parser = DealerParser(); parser.feed(html)
    mappings = []
    for form, rows in parser.forms:
        action = http_url(form.get('action') or url, url)
        if not action or not same_page(action, url) or not form.get('data-product_id'): continue
        if 'variations_form' not in form.get('class', '').split(): continue
        for row in rows:
            if not isinstance(row, dict): continue
            attributes = row.get('attributes')
            if not isinstance(attributes, dict) or not attributes or any(not isinstance(v,str) or not v.strip() for v in attributes.values()): continue
            if row.get('is_purchasable') is not True or row.get('variation_is_active') is not True: continue
            price = structured_price(row.get('display_price'))
            price_html = row.get('price_html') or ''
            if currency != 'VND' and not re.search(r'VND|VNĐ|₫|&#8363;',price_html,re.I): continue
            if not price: continue
            mappings.append({'variant': {str(k):v for k,v in attributes.items()}, 'price':price,
                'availability': 'in_stock' if row.get('is_in_stock') is True else
                                'out_of_stock' if row.get('is_in_stock') is False else None,
                'mapping_source':'product_variation_form', 'variation_id':row.get('variation_id'),
                'image':row.get('image') if isinstance(row.get('image'),dict) else None})
    for table in parser.tables:
        # A table must name this product, not just appear somewhere on its page.
        label = table['product'] or table['caption']
        if not label or not same_identity(name,label) or not table['rows']: continue
        header = [normalize_product_text(c) or '' for c in table['rows'][0]]
        if any(c in {'model','product','san pham','mau xe','dong xe'} for c in header): continue
        variant_cols = [i for i,c in enumerate(header) if c in {'phien ban','variant','version','mau sac','color'}]
        price_cols = [i for i,c in enumerate(header) if re.fullmatch(r'(?:gia ban|price)(?: vnd)?',c)]
        if not variant_cols or len(price_cols)!=1: continue
        price_col=price_cols[0]
        for row in table['rows'][1:]:
            if len(row)!=len(header) or any(not row[i] for i in variant_cols): continue
            value=row[price_col]
            if re.search(r'\d\s*[-–—]\s*\d|\b(?:từ|from)\b',value,re.I): continue
            if 'vnd' not in header[price_col] and not re.search(r'VND|VNĐ|₫|đ',value,re.I): continue
            # One amount per cell; an old/new price pair is ambiguous here.
            amounts=re.findall(r'\d+(?:[.,]\d+)*',value)
            if len(amounts)!=1: continue
            price=parse_price(value + ' VND')
            if price:
                mappings.append({'variant':{header[i]:row[i] for i in variant_cols},'price':price,
                                 'availability':None,'mapping_source':'variant_price_table'})
    unique={}
    conflicts=set()
    for item in mappings:
        key=tuple(sorted(item['variant'].items()))
        if key in unique and unique[key]['price']!=item['price']: conflicts.add(key)
        unique[key]=item
    return [item for key,item in unique.items() if key not in conflicts][:30]


def concrete_proofs(proof):
    """Page proof can contain several variant offers, never a made-up base price."""
    if not proof: return []
    if proof.get('variant_offers'): return proof['variant_offers']
    return [proof] if proof.get('product_page_valid') else []


def commercial_variants(mappings):
    """Coalesce equivalent colors; retain independently priced color variants."""
    from app.services.normalization.text_normalizer import normalize_product_text
    def color(key):
        key = normalize_product_text(key) or ''
        return key in {'color','colour','mau sac','attribute pa mau sac','attribute pa color','attribute color'}
    groups = {}
    for item in mappings:
        key = tuple(sorted((k,v) for k,v in item['variant'].items() if not color(k)))
        groups.setdefault(key,[]).append(item)
    result = []
    for key, rows in groups.items():
        if len({r['price'] for r in rows})>1:
            result.extend(rows)
            continue
        # A sold-out color must not hide an available color or claim it is available.
        rank = {'in_stock':0, None:1, 'out_of_stock':2}
        chosen = min(rows,key=lambda r:rank[r['availability']])
        colors = sorted({v for r in rows if r['availability']==chosen['availability']
                         for k,v in r['variant'].items() if color(k)})
        variant = dict(key)
        if colors: variant['color_options'] = ' / '.join(colors)
        result.append({**chosen,'variant':variant,'image_variant':chosen['variant']})
    return result


def dealer_variant_proofs(parser, html, url, product):
    """Bind variant mappings to the main page identity and an actual seller action."""
    from urllib.parse import unquote
    from app.services.extraction.product_page_validator import same_identity, identity_tokens
    from app.services.extraction.product_extraction_service import infer_brand, infer_model
    from app.services.normalization.product_normalizer import infer_product_category
    from app.services.normalization.text_normalizer import normalize_product_text
    heading=parser.heading if parser.h1 else ''
    if not heading: return []
    title=parser.meta.get('og:title') or ' '.join(parser.title)
    data=product or {}
    brand=data.get('brand')
    if isinstance(brand,dict): brand=brand.get('name')
    brand=brand or infer_brand(data.get('name','')+' '+heading+' '+title)
    name=heading if not brand or brand.lower() in heading.lower() else brand+' '+heading
    if len(identity_tokens(name))<2: return []
    if product is None and (not same_identity(name,title) or
                            not same_identity(name,unquote(urlsplit(url).path).replace('-',' '))): return []
    offers=data.get('offers') or []
    if isinstance(offers,dict): offers=[offers]
    offers=[o for o in offers if isinstance(o,dict) and (not o.get('url') or same_page(o['url'],url))]
    currency='VND' if any(o.get('priceCurrency')=='VND' for o in offers) else None
    mappings=variant_mappings(html,url,name,currency=currency)
    text=normalize_product_text(' '.join(parser.text)) or ''
    buy=any(x in text for x in ('mua ngay','dat xe','dat hang','lien he mua','dang ky mua','buy now','add to cart'))
    # Purchasable, active WooCommerce variants are explicit sale actions too.
    mappings=[m for m in mappings if buy or m['mapping_source']=='product_variation_form']
    sellers={o['seller']['name'] for o in offers if isinstance(o.get('seller'),dict) and isinstance(o['seller'].get('name'),str)}
    merchant=next(iter(sellers)) if len(sellers)==1 else urlsplit(url).hostname
    model=data.get('model')
    if isinstance(model,dict): model=model.get('name')
    model=model or infer_model(name,brand)
    category=infer_product_category(name,data.get('category') if isinstance(data.get('category'),str) else None)
    # Verified dealer taxonomy may encode a motorcycle subtype as HTML entities.
    # Do not map arbitrary descendants (e.g. accessories) to their broad parent.
    if isinstance(data.get('category'),str):
        from html import unescape
        taxonomy=[normalize_product_text(p.strip()) for p in unescape(data['category']).split('>')]
        if len(taxonomy)==2 and taxonomy[0]=='xe may' and taxonomy[1] in {'xe ga','xe so','xe con tay'}:
            category='xe máy'
    category=category or infer_product_category(unquote(urlsplit(url).path))
    specs={str(p['name']).lower():str(p['value']) for p in (data.get('additionalProperty') or []) if
           isinstance(p,dict) and p.get('name') and p.get('value') is not None}
    result=[]
    for item in commercial_variants(mappings):
        identity={k:v for k,v in item['variant'].items() if k!='color_options'}
        label=' / '.join(value.replace('-',' ') for key,value in sorted(identity.items()))
        signature='; '.join(f'{key}={value}' for key,value in sorted(identity.items()))
        images=[]
        image=item.get('image') or {}
        if image:
            from app.services.extraction.product_page_validator import http_url, BAD_IMAGES
            address=http_url(image.get('url') or image.get('src'),url)
            description=' '.join(str(image.get(k) or '') for k in ('alt','title'))
            if address:
                description+=' '+unquote(urlsplit(address).path.rsplit('/',1)[-1]).replace('-',' ')
            image_tokens=identity_tokens(description)
            attrs=item.get('image_variant',item['variant'])
            matches=identity_tokens(name)<=image_tokens and all(
                identity_tokens(v)<=image_tokens for k,v in attrs.items() if k!='color_options')
            if address and matches and not BAD_IMAGES.search(address):
                images=[(address,'product_variation_image')]
        result.append(dict(product_page_valid=True,verification_level='VERIFIED_CONTENT',product_page_confidence=95,
            result_type='DIRECT_PRODUCT',name=name+(' - '+label if label else ''),brand=brand,model=model,category=category,
            variant=item['variant'],price=item['price'],price_type='CONCRETE',availability=item['availability'],
            merchant=merchant,product_url=url,evidence_url=url,image_url=None,image_source=None,image_candidates=images,
            specifications={**specs,'variant':signature},mapping_source=item['mapping_source'],
            identity_status='MATCHED',reason='Explicit main-product variant mapped to its own advertised seller price.'))
    return result
