"""Conservative retrieval hints, never product evidence or hard-filter policy."""
import re
from urllib.parse import unquote, urlsplit

from app.services.budget import bounds
from app.services.normalization.product_normalizer import infer_product_category
from app.services.search.model_hints import observed_models
from app.services.scoring.scoring_engine import normalized
from app.services.filter.hard_filter import category_matches


def hint_category(name, explicit=None):
    """Scheduling evidence only; never assign this category to an offer."""
    category = infer_product_category(name, explicit)
    if category and (explicit or category not in {'máy ảnh', 'màn hình'}):
        return category
    text = normalized(name or '')
    families = {
        'máy tính bảng': r'\b(?:galaxy tab|(?:redmi|xiaomi|oppo|oneplus|honor) pad|lenovo tab)\b',
        'điện thoại': r'\b(?:galaxy (?:[asmf]\d|z (?:fold|flip))|redmi note \d)\w*',
        'tai nghe': r'\b(?:airpods|galaxy buds)\b',
    }
    # A known device family may describe its camera/screen; these feature words
    # do not turn it into a standalone camera/monitor. Explicit taxonomy wins.
    return next((c for c, pattern in families.items() if re.search(pattern, text)), category)


def category_compatible(name, requirement, explicit=None):
    if requirement is None or not requirement.category:
        return True
    required = infer_product_category('', requirement.category)
    observed = hint_category(name, explicit)
    # Unknown remains discoverable; only positive conflicting evidence rejects.
    return observed is None or category_matches(required, observed)


def source_category(source):
    proof = source.page_validation or {}
    explicit = proof.get('category') if proof.get('product_page_valid') else None
    return (hint_category(source.title, explicit)
            or hint_category(unquote(urlsplit(source.url).path).rsplit('/', 1)[-1]))


def source_category_compatible(source, requirement):
    return category_compatible('', requirement, source_category(source))


def irrelevant_reason(source, requirement):
    if requirement is None or not requirement.category:
        return None
    category = infer_product_category(requirement.category)
    title = normalized(source.title or '')
    # Only explicit different intents are rejected. Missing category/model data
    # stays discoverable, including unknown brands and merchant landing pages.
    text = normalized((source.title or '') + '\n' + source.content[:2000])
    digital = re.search(r'\b(the game|the qua tang|gift card|nap the|nap tien vao vi)\b', text)
    currency = re.search(r'\b(btc|bitcoin|crypto|ethereum|exchange rate|ty gia)\b', title)
    if category in {'điện thoại', 'laptop', 'tivi', 'tai nghe', 'xe máy'} and (digital or currency):
        if not observed_models(source.title or '') and infer_product_category(source.title) != category:
            return 'Non-hardware currency or digital-credit intent.'
    if category == 'điện thoại' and not observed_models(source.title or ''):
        if re.search(r'^(?:what is |tim hieu |mang |cong nghe )?[456]g(?:\b|$)', title):
            return 'Generic network information without a product identity.'
    return None


def hint_budget_rank(source, requirement):
    """Rank the article's explicit budget topic, not a model's offer price.

    Only the title is used: an unrelated price in a multi-product snippet must
    never become the named model's price or verified requirement evidence.
    """
    if requirement is None:
        return 1
    low, high = bounds(requirement)
    if low is None and high is None:
        return 1
    title = normalized(source.title or '')
    values = [float(m.replace(',', '.')) * 1_000_000
              for m in re.findall(r'\b(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:trieu|million)\b', title)]
    if not values:
        return 1
    if any((low is None or v >= low) and (high is None or v <= high) for v in values):
        return 0
    return 2
