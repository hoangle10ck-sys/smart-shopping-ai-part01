"""Deterministic category evidence on an already verified product page."""
import json
import re
from html import unescape
from urllib.parse import unquote, urlsplit

from app.services.normalization.product_normalizer import infer_product_category
from app.services.normalization.text_normalizer import normalize_product_text


def verified_category(value):
    """Main-page family evidence, after explicit object/accessory taxonomy."""
    explicit = infer_product_category(value)
    if explicit:
        return explicit
    text = normalize_product_text(value) or ''
    if re.match(r'^(?:xiaomi\s+)?redmi note \d+\b', text):
        return 'điện thoại'
    return None


def breadcrumb_taxonomy(parser):
    """Read page BreadcrumbList, never a related product's nested taxonomy."""
    found = []
    def visit(node):
        if isinstance(node, list):
            for child in node: visit(child)
        elif isinstance(node, dict):
            kinds = node.get('@type', [])
            if isinstance(kinds, str): kinds = [kinds]
            if 'BreadcrumbList' in kinds:
                names = []
                for entry in node.get('itemListElement', []):
                    if not isinstance(entry, dict): continue
                    item = entry.get('item')
                    name = entry.get('name') or (item.get('name') if isinstance(item, dict) else None)
                    if isinstance(name, str): names.append(unescape(name))
                if names: found.append(names)
            for key in ('@graph', 'breadcrumb'): visit(node.get(key))
    for block in parser.blocks:
        try: visit(json.loads(block))
        except (ValueError, TypeError): continue
    found.extend([re.split(r'[>»›]',s) for s in getattr(parser, 'breadcrumbs', []) if s])
    return found


def category_evidence(parser, product, url, *, verified, normalized_schema_category=None):
    result = dict(category=None, source=None, confidence=0, reason='Page is not verified.', conflict=False)
    if not verified: return result
    schema = (product or {}).get('category')
    if not isinstance(schema, str): schema = None
    breadcrumbs = breadcrumb_taxonomy(parser)
    def taxonomy(values):
        # The deepest recognized category wins over a broad ancestor.
        return next((c for value in reversed(values) if (c := verified_category(value))), None)
    breadcrumb_categories = {c for path in breadcrumbs if (c := taxonomy(path))}
    # Reuse a verified parser's explicit taxonomy normalization where supplied;
    # retain the raw schema in observations for provenance/conflict auditing.
    schema_category = (normalized_schema_category or infer_product_category('', unescape(schema))) if schema else None
    h1_category = verified_category(parser.heading)
    title_category = verified_category(' '.join(parser.title))
    heading_category = h1_category or title_category
    path = unquote(urlsplit(url).path).strip('/')
    path_category = verified_category(path.rsplit('/',1)[-1]) or infer_product_category(path)
    accessories = {'ốp lưng','bao da','miếng dán','giá treo','remote','kệ tivi','chân đế','phụ kiện'}
    strong = {c for c in (schema_category, *breadcrumb_categories, heading_category) if c}
    if path_category in accessories: strong.add(path_category)
    observations = dict(json_ld_category=schema, json_ld_type=(product or {}).get('@type'), breadcrumbs=breadcrumbs, h1=parser.heading,
                        title=' '.join(parser.title), url_path=unquote(urlsplit(url).path))
    if len(strong) > 1:
        return {**result, 'reason':'Conflicting product schema, breadcrumb or heading categories.',
                'conflict':True, 'observations':observations}
    for category, source, confidence in (
        (schema_category, 'product_schema', 95),
        (next(iter(breadcrumb_categories), None), 'breadcrumb', 90),
        (heading_category, 'h1' if h1_category else 'title', 85),
        (path_category, 'verified_url_path', 80),
    ):
        if category:
            return dict(category=category, source=source, confidence=confidence, conflict=False,
                        reason='Category observed on the verified main product page.', observations=observations)
    return {**result, 'reason':'No explicit category evidence on the verified page.', 'observations':observations}


def variant_category_evidence(parent, variant):
    """Inherit page taxonomy only without contrary variant-type evidence."""
    observed = {c for value in (variant.get('variant') or {}).values()
                if isinstance(value, str) and (c := infer_product_category(value))}
    category = parent.get('category')
    if category and any(c != category for c in observed):
        return {**parent, 'category':None, 'source':None, 'confidence':0, 'conflict':True,
                'reason':'Variant type conflicts with the verified parent category.',
                'variant_categories':sorted(observed)}
    return parent
