"""Deterministic budget semantics shared by filtering, queries and persistence."""
from decimal import Decimal, ROUND_HALF_UP

BUDGET_FIELDS = ('budget_mode', 'budget_target', 'preferred_min', 'preferred_max')


def tolerance(target: int) -> int:
    """6%, rounded to 10k (100k above 1m); floor 20k, cap 5m and target."""
    scaled = int((Decimal(target) * Decimal('.06') / 10000).quantize(
        Decimal('1'), rounding=ROUND_HALF_UP)) * 10000
    if scaled >= 1_000_000:
        scaled = int((Decimal(scaled) / 100000).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP)) * 100000
    return min(target, max(20_000, min(5_000_000, scaled)))


def apply_budget_semantics(requirement, raw_query):
    from app.services.llm.client import normalize_text, parse_budget_range
    import re
    minimum, maximum = parse_budget_range(raw_query)
    if maximum is not None:
        requirement.budget_min, requirement.budget_max = minimum, maximum
    requirement.budget_target = requirement.preferred_min = requirement.preferred_max = None
    text = normalize_text(raw_query)
    if requirement.budget_min is not None and requirement.budget_max is not None:
        requirement.budget_mode = 'RANGE'
    elif re.search(r'\b(?:toi da|khong qua|duoi|at most|under)\b', text):
        requirement.budget_mode = 'HARD_MAX'
    elif maximum is not None and re.search(r'\b(?:khoang|tam|around|about)\b', text):
        requirement.budget_mode = 'FLEXIBLE_TARGET'
        requirement.budget_target = maximum
        delta = tolerance(maximum)
        requirement.preferred_min = maximum - delta
        requirement.preferred_max = maximum + delta
    else:
        # Bare amounts retain the established parser's maximum semantics.
        requirement.budget_mode = 'HARD_MAX'
    return requirement


def bounds(requirement):
    if requirement.budget_mode == 'FLEXIBLE_TARGET':
        return requirement.preferred_min, requirement.preferred_max
    return requirement.budget_min, requirement.budget_max


def stored_budget(model):
    metadata = getattr(model, 'budget_metadata', None)
    return metadata.values if metadata else {}
