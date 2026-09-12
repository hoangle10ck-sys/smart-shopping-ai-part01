"""Vietnamese product-price normalization."""

from __future__ import annotations

import re
import unicodedata


# =============================================================
# CONSTANTS
# =============================================================


FOREIGN_CURRENCY_MARKERS = {
    "$",
    "usd",
    "eur",
    "gbp",
    "jpy",
    "cny",
}


RENTAL_MARKERS = {
    "/day",
    "per day",
    "daily",
    "rental",
    "for rent",

    "cho thue",
    "gia thue",

    "cho thuê",
    "giá thuê",
}


# =============================================================
# ENCODING REPAIR
# =============================================================


def repair_common_mojibake(
    value: str,
) -> str:
    """
    Repair common UTF-8 mojibake found in search snippets.

    Examples:
        triá»‡u -> triệu
        Ä‘      -> đ
        â‚«     -> ₫
        nghĂ¬n  -> nghìn
    """

    replacements = (
        (
            "triá»‡u",
            "triệu",
        ),
        (
            "triĂ¡Â»â€¡u",
            "triệu",
        ),
        (
            "nghĂ¬n",
            "nghìn",
        ),
        (
            "nghÄ‚Â¬n",
            "nghìn",
        ),
        (
            "Ä‘",
            "đ",
        ),
        (
            "Ă„â€˜",
            "đ",
        ),
        (
            "â‚«",
            "₫",
        ),
        (
            "Ă¢â€Â«",
            "₫",
        ),
    )

    for (
        source,
        target,
    ) in replacements:
        value = value.replace(
            source,
            target,
        )

    return value


# =============================================================
# TEXT NORMALIZATION
# =============================================================


def normalize_text(
    value: str,
) -> str:
    """
    Normalize text for price matching.

    Vietnamese:
        triệu -> trieu
        nghìn -> nghin
        tỷ    -> ty
    """

    value = (
        repair_common_mojibake(
            value
        )
        .strip()
        .lower()
    )

    value = value.replace(
        "₫",
        " vnd ",
    )

    value = value.replace(
        "vnđ",
        " vnd ",
    )

    value = unicodedata.normalize(
        "NFD",
        value,
    )

    value = "".join(
        char
        for char in value
        if unicodedata.category(
            char
        )
        != "Mn"
    )

    value = value.replace(
        "đ",
        "d",
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


# =============================================================
# NUMBER HELPERS
# =============================================================


def parse_decimal_number(
    value: str,
) -> float | None:
    """Parse decimal value such as 4,5 or 4.5."""

    value = (
        value
        .strip()
        .replace(
            ",",
            ".",
        )
    )

    try:
        return float(
            value
        )

    except ValueError:
        return None


def parse_integer_price(
    value: str,
) -> int | None:
    """
    Parse formatted integer VND value.

    Examples:
        43.681.000 -> 43681000
        43,681,000 -> 43681000
        499000     -> 499000
    """

    digits = re.sub(
        r"[^\d]",
        "",
        value,
    )

    if not digits:
        return None

    try:
        return int(
            digits
        )

    except ValueError:
        return None


# =============================================================
# PRICE PARSER
# =============================================================


def parse_price(
    raw_value: str | None,
) -> int | None:
    """Convert raw purchase price into integer VND."""

    if raw_value is None:
        return None

    original = (
        raw_value.strip()
    )

    if not original:
        return None

    value = (
        normalize_text(
            original
        )
    )

    if not value:
        return None


    # =========================================================
    # FOREIGN CURRENCY
    # =========================================================

    if any(
        marker in value
        for marker
        in FOREIGN_CURRENCY_MARKERS
    ):
        return None


    # =========================================================
    # RENTAL PRICE
    # =========================================================

    if any(
        marker in value
        for marker
        in RENTAL_MARKERS
    ):
        return None


    # =========================================================
    # BILLION
    #
    # 1,2 tỷ
    # 1.2 billion
    # =========================================================

    billion_match = re.search(
        r"""
        (?<!\d)
        (\d+(?:[.,]\d+)?)
        \s*
        (?:
            ty
            |
            billion
        )
        \b
        """,
        value,
        re.IGNORECASE
        | re.VERBOSE,
    )

    if billion_match:
        number = (
            parse_decimal_number(
                billion_match.group(
                    1
                )
            )
        )

        if number is None:
            return None

        return round(
            number
            * 1_000_000_000
        )


    # =========================================================
    # MILLION
    #
    # 4,5 triệu
    # 4,5 triá»‡u
    # 15 tr
    # 40 million VND
    # =========================================================

    million_match = re.search(
        r"""
        (?<!\d)
        (\d+(?:[.,]\d+)?)
        \s*
        (?:
            trieu
            |
            million
            |
            tr
        )
        \b
        """,
        value,
        re.IGNORECASE
        | re.VERBOSE,
    )

    if million_match:
        number = (
            parse_decimal_number(
                million_match.group(
                    1
                )
            )
        )

        if number is None:
            return None

        return round(
            number
            * 1_000_000
        )


    # =========================================================
    # THOUSAND
    #
    # 399K
    # 500 nghìn
    # 500 ngan
    # =========================================================

    thousand_match = re.search(
        r"""
        (?<!\d)
        (\d+(?:[.,]\d+)?)
        \s*
        (?:
            k
            |
            nghin
            |
            ngan
            |
            thousand
        )
        \b
        """,
        value,
        re.IGNORECASE
        | re.VERBOSE,
    )

    if thousand_match:
        number = (
            parse_decimal_number(
                thousand_match.group(
                    1
                )
            )
        )

        if number is None:
            return None

        return round(
            number
            * 1_000
        )


    # =========================================================
    # NORMAL VND
    #
    # 43.681.000 VND
    # VND 43,681,000
    # 499.000đ
    # =========================================================

    grouped_match = re.search(
        r"""
        (?:
            vnd
            \s*
        )?
        (
            \d{1,3}
            (?:
                [.,]\d{3}
            )+
        )
        (?:
            \s*
            (?:
                vnd
                |
                d
            )
        )?
        """,
        value,
        re.IGNORECASE
        | re.VERBOSE,
    )

    if grouped_match:
        return (
            parse_integer_price(
                grouped_match.group(
                    1
                )
            )
        )


    # =========================================================
    # PLAIN INTEGER VND
    #
    # 20000000 VND
    # VND 20000000
    # =========================================================

    plain_vnd_match = re.search(
        r"""
        (?:
            vnd
            \s*
            (\d+)
        )
        |
        (?:
            (\d+)
            \s*
            (?:
                vnd
                |
                d
            )
        )
        """,
        value,
        re.IGNORECASE
        | re.VERBOSE,
    )

    if plain_vnd_match:
        raw_number = (
            plain_vnd_match.group(
                1
            )
            or plain_vnd_match.group(
                2
            )
        )

        return (
            parse_integer_price(
                raw_number
            )
        )


    # =========================================================
    # BACKWARD-COMPATIBLE FALLBACK
    #
    # Existing unit tests and demo data may contain raw numeric
    # prices without an explicit VND suffix.
    # =========================================================

    return (
        parse_integer_price(
            value
        )
    )