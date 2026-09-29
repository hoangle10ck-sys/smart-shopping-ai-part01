"""Image-only selection from an already verified main product page.

Never constructs an image URL from a model, or promotes another JSON-LD Product.
Network/raster validation remains the resolver's responsibility.
"""
import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import unquote, urldefrag, urlsplit

from app.services.extraction.product_page_validator import (
    BAD_IMAGES, VARIANTS, http_url, identity_tokens, same_identity,
)

DECORATIVE = re.compile(r'transparent|(?:^|[/_.-])(?:pixel|1x1|blank|loading|spinner)(?:[_.-]|$)', re.I)
ATTRIBUTES = ('data-zoom-image', 'data-original', 'data-src', 'data-lazy-src', 'data-image', 'src')


class ImageContextParser(HTMLParser):
    """Keep explicit Product ownership and picture siblings; CSS alone is not proof."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.frames, self.images = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'source':
            picture = next((f for f in reversed(self.frames) if f['tag'] == 'picture'), None)
            if picture is not None and len(picture['sources']) < 8:
                picture['sources'].append(a)
        if tag == 'img' and len(self.images) < 512:
            picture = next((f for f in reversed(self.frames) if f['tag'] == 'picture'), None)
            self.images.append({**a, '_ancestors': [f['attrs'] for f in self.frames],
                                '_picture_sources': list(picture['sources']) if picture else []})
        if tag not in {'img', 'meta', 'link', 'source', 'br', 'hr', 'input', 'wbr', 'area', 'base', 'embed', 'param', 'col'}:
            self.frames.append({'tag': tag, 'attrs': a, 'sources': []})

    def handle_endtag(self, tag):
        for i in range(len(self.frames) - 1, -1, -1):
            if self.frames[i]['tag'] == tag:
                del self.frames[i:]
                break


def gallery_scope(img, *, url, name, product):
    """True=explicit same owner, False=other/excluded, None=unknown ownership."""
    ancestors = img.get('_ancestors', [])
    for a in ancestors:
        marker = ' '.join(a.get(k) or '' for k in ('class', 'id', 'role'))
        if re.search(r'related|recommend|upsell|cross.?sell|suggest|product.?card|product.?list|banner', marker, re.I):
            return False
    for a in reversed(ancestors):
        owner = a.get('data-product-url') or (a.get('itemid') if str(a.get('itemtype', '')).rstrip('/').endswith('/Product') else None)
        owner_name, sku = a.get('data-product-name'), a.get('data-product-sku')
        declared = str(a.get('itemtype', '')).rstrip('/').endswith('/Product')
        if owner or owner_name or sku or declared:
            # The nearest Product boundary wins; never inherit an outer owner
            # through an unrelated or unidentified nested Product.
            if owner and urldefrag(http_url(owner, url) or '')[0] != urldefrag(url)[0]: return False
            if owner_name and not same_identity(owner_name, name): return False
            if sku and sku != (product or {}).get('sku'): return False
            return bool(owner or owner_name or sku)
    return None


def bad_image(value):
    return bool(BAD_IMAGES.search(value) or DECORATIVE.search(value))


def image_label(url):
    filename = unquote(urlsplit(url).path.rsplit('/', 1)[-1]).rsplit('.', 1)[0]
    return re.sub(r'(?:[-_]\d{2,4}x\d{2,4})$', '', filename, flags=re.I)


def tiny_raster(raw):
    """Reject common transparent tracking pixels without adding a decoder dependency."""
    if raw.startswith(b'GIF8') and len(raw) >= 10:
        return int.from_bytes(raw[6:8], 'little') <= 1 or int.from_bytes(raw[8:10], 'little') <= 1
    if raw.startswith(b'\x89PNG\r\n\x1a\n') and len(raw) >= 24 and raw[12:16] == b'IHDR':
        return int.from_bytes(raw[16:20], 'big') <= 1 or int.from_bytes(raw[20:24], 'big') <= 1
    return False


def raster_prefix(raw):
    """Validate the bounded raster prefix consumed by the image probe."""
    if len(raw) <= 32 or tiny_raster(raw):
        return False
    if raw.startswith((b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n', b'GIF8')):
        return True
    if raw.startswith(b'RIFF') and raw[8:12] == b'WEBP':
        return True
    # AVIF may use mif1/msf1 as its major brand and avif/avis as a
    # compatible brand. Never inspect past the supplied prefix/ftyp box.
    if raw[4:8] == b'ftyp':
        end = min(len(raw), int.from_bytes(raw[:4], 'big'))
        brands = [raw[8:12], *(raw[i:i+4] for i in range(16, end, 4))]
        return end >= 16 and any(b in {b'avif', b'avis'} for b in brands)
    return False


def normalized_image_url(raw, page_url):
    if not isinstance(raw, str):
        return None
    value = unescape(raw).replace('\\/', '/')
    # Decode escaped URL delimiters only, not arbitrary text/percent-encoded paths.
    for code, replacement in (('002f', '/'), ('003a', ':'), ('0026', '&')):
        value = re.sub(r'\\u' + code, lambda _: replacement, value, flags=re.I)
    if value.startswith('//'):
        value = 'https:' + value
    url = http_url(value, page_url)
    if not url or bad_image(unquote(url)) or urlsplit(url).path.lower().endswith(('.svg', '.ico')):
        return None
    return urldefrag(url)[0]


def conflicts(label, name, brand=None):
    """Reject explicit contradictory identity, keeping unknown opaque IDs neutral."""
    from app.services.extraction.product_extraction_service import infer_brand
    from app.services.normalization.text_normalizer import normalize_product_text
    if not label:
        return False
    if bad_image(label):
        return True
    label_brand = infer_brand(label.replace('-', ' '))
    if label_brand and normalize_product_text(label_brand) not in normalize_product_text(name + ' ' + (brand or '')):
        return True
    page, tokens = identity_tokens(name), identity_tokens(label)
    ids = {t for t in tokens if any(c.isdigit() for c in t)}
    page_ids = {t for t in page if any(c.isdigit() for c in t)}
    descriptive = bool(tokens & page)
    if descriptive and ids and page_ids and not ids <= page_ids:
        return True
    if (tokens & VARIANTS) - (page & VARIANTS):
        return True
    # Explicit same-family model without the required Pro/Max/etc is another model.
    if descriptive and ids & page_ids and (tokens & VARIANTS) != (page & VARIANTS):
        return True
    return False


def image_values(value, *, name, brand):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from image_values(item, name=name, brand=brand)
    elif isinstance(value, dict):
        if any(conflicts(str(value.get(key) or ''), name, brand) for key in ('name', 'caption', 'description')):
            return
        # A broken/placeholder url must not suppress a valid contentUrl.
        for key in ('url', 'contentUrl'):
            yield from image_values(value.get(key), name=name, brand=brand)


def srcset_values(value):
    # Data URLs contain commas; omit the entire untrusted set rather than treating
    # a base64 tail as a relative path. Regular HTTP/relative srcsets are supported.
    if not isinstance(value, str) or 'data:' in value.lower():
        return
    for part in value.split(','):
        fields = part.strip().split()
        if len(fields) == 1 or (len(fields) == 2 and re.fullmatch(r'\d+(?:\.\d+)?[wx]', fields[1])):
            yield fields[0]


def collect_product_images(parser, product, *, url, name, brand=None, html=None, diagnostics=None):
    """Priority: bound JSON-LD, bound structured media, social meta, bound img.

    Called only after the existing direct-product validator accepts the offer.
    Unknown gallery membership is not identity proof. An explicit same Product
    owner can bind opaque gallery URLs without requiring model text in filenames.
    """
    images = parser.images
    if html is not None:
        context = ImageContextParser()
        context.feed(html)
        images = context.images
    audit = diagnostics if diagnostics is not None else {}
    audit.update(accepted_count=0, rejections=[], candidate_count=0,
                 has_product_image=bool((product or {}).get('image')),
                 has_social_image=any(parser.meta.get(k) for k in ('og:image', 'og:image:secure_url', 'twitter:image', 'twitter:image:src')),
                 html_image_count=len(images))
    def reject(origin, reason):
        if len(audit['rejections']) < 20:
            audit['rejections'].append({'source': origin, 'reason': reason})
    candidates = []
    if product:
        candidates.extend((v, 'json_ld_product') for v in image_values(product.get('image'), name=name, brand=brand))
        media = product.get('associatedMedia') or []
        media = [media] if isinstance(media, dict) else media
        if isinstance(media, list):
            for item in media:
                if isinstance(item, dict) and item.get('@type') == 'ImageObject':
                    candidates.extend((v, 'structured_product_media') for v in image_values(item, name=name, brand=brand))
    # Explicitly labelled itemprop images are product-specific structured media.
    for img in images:
        if gallery_scope(img, url=url, name=name, product=product) is False:
            continue
        if (img.get('itemprop') == 'image' and same_identity(name, img.get('alt') or img.get('title') or '')
                and not any(conflicts(img.get(k) or '', name, brand) for k in ('alt', 'title'))):
            for attr in ATTRIBUTES:
                if img.get(attr): candidates.append((img[attr], 'structured_product_media'))
    for key in ('og:image:secure_url', 'og:image', 'twitter:image', 'twitter:image:src'):
        alt = parser.meta.get(key.split(':')[0] + ':image:alt', '')
        if parser.meta.get(key) and not conflicts(alt, name, brand):
            candidates.append((parser.meta[key], key))
    for img in images:
        scope = gallery_scope(img, url=url, name=name, product=product)
        if scope is False:
            reject('html_product_image', 'unrelated_gallery')
            continue
        labels = [img.get('alt') or '', img.get('title') or '']
        if any(conflicts(label, name, brand) for label in labels):
            reject('html_product_image', 'identity_conflict')
            continue
        if any(str(img.get(d, '')).strip() in {'0', '1', '1px'} for d in ('width', 'height')):
            continue
        values = [img[a] for a in ATTRIBUTES if img.get(a)]
        for attr in ('data-srcset', 'srcset'):
            values.extend(srcset_values(img.get(attr)))
        for source in img.get('_picture_sources', []):
            for attr in ('data-srcset', 'srcset'):
                values.extend(srcset_values(source.get(attr)))
        for value in values:
            parsed = normalized_image_url(value, url)
            if not parsed:
                continue
            filename = image_label(parsed)
            if scope is True or any(same_identity(name, label) for label in labels) or same_identity(name, filename):
                candidates.append((parsed, 'html_product_image'))
            else:
                reject('html_product_image', 'unbound_gallery')
    audit['candidate_count'] = len(candidates)
    safe, seen = [], set()
    for value, origin in candidates:
        image = normalized_image_url(value, url)
        if not image:
            reject(origin, 'unsafe_or_decorative_url')
            continue
        if image in seen:
            continue
        # Only explicit width x height transform suffixes are neutral. Do not
        # strip arbitrary numbers that could be a model/capacity/year conflict.
        filename = image_label(image)
        if conflicts(filename, name, brand):
            reject(origin, 'identity_conflict')
            continue
        seen.add(image)
        safe.append((image, origin))
        if len(safe) == 5:
            break
    audit['accepted_count'] = len(safe)
    return safe
