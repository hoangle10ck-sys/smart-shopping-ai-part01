"""Text normalization helpers for product matching."""

import re
import unicodedata


def remove_diacritics(
    value: str,
) -> str:
    """Remove Vietnamese diacritics."""

    normalized = unicodedata.normalize(
        "NFD",
        value,
    )

    normalized = "".join(
        char
        for char in normalized
        if unicodedata.category(char)
        != "Mn"
    )

    return normalized.replace(
        "đ",
        "d",
    ).replace(
        "Đ",
        "D",
    )


def normalize_product_text(
    value: str | None,
) -> str | None:
    """Normalize product text for deterministic comparisons."""

    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    value = remove_diacritics(
        value
    ).lower()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value or None


def normalize_display_text(
    value: str | None,
) -> str | None:
    """Clean whitespace while preserving human-readable text."""

    if value is None:
        return None

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value or None