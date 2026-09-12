"""Review-count normalization."""

import re
import unicodedata


def normalize_text(
    value: str,
) -> str:
    """Normalize Vietnamese text."""

    value = (
        value
        .strip()
        .lower()
    )

    value = unicodedata.normalize(
        "NFD",
        value,
    )

    value = "".join(
        char
        for char in value
        if unicodedata.category(char) != "Mn"
    )

    return value.replace("đ", "d")


def parse_decimal(
    value: str,
) -> float | None:
    """Parse comma/dot decimal numbers."""

    try:
        return float(
            value.replace(",", ".")
        )

    except ValueError:
        return None


def parse_review_count(
    raw_value: str | None,
) -> int | None:
    """Convert review-count strings to integers.

    Examples:
        310 -> 310
        1.2K -> 1200
        1,5 nghìn -> 1500
    """

    if raw_value is None:
        return None

    value = normalize_text(
        raw_value
    )

    if not value:
        return None

    multiplier_match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*"
        r"(k|nghin|ngan|trieu)",
        value,
    )

    if multiplier_match:
        number = parse_decimal(
            multiplier_match.group(1)
        )

        if number is None:
            return None

        unit = multiplier_match.group(2)

        multiplier = (
            1_000_000
            if unit == "trieu"
            else 1_000
        )

        return round(
            number * multiplier
        )

    digits = re.sub(
        r"[^\d]",
        "",
        value,
    )

    if not digits:
        return None

    return int(digits)