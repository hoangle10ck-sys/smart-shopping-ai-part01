"""Conservative retrieval hints, never product evidence or hard-filter policy."""
import re

from app.services.budget import bounds
from app.services.normalization.product_normalizer import infer_product_category
from app.services.search.model_hints import observed_models
from app.services.scoring.scoring_engine import normalized


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
