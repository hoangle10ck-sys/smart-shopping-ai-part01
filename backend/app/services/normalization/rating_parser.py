"""Product-rating normalization."""

import re


def parse_rating(
    raw_value: str | None,
) -> float | None:
    """Normalize ratings to a 0-5 scale.

    Examples:
        4.6/5 -> 4.6
        4,4/5 -> 4.4
        9/10 -> 4.5
        92% -> 4.6
    """

    if raw_value is None:
        return None

    value = (
        raw_value
        .strip()
        .lower()
        .replace(",", ".")
    )

    if not value:
        return None

    fraction_match = re.search(
        r"(\d+(?:\.\d+)?)"
        r"\s*/\s*"
        r"(\d+(?:\.\d+)?)",
        value,
    )

    if fraction_match:
        score = float(
            fraction_match.group(1)
        )

        maximum = float(
            fraction_match.group(2)
        )

        if maximum <= 0:
            return None

        normalized = (
            score / maximum
        ) * 5.0

        if not 0 <= normalized <= 5:
            return None

        return round(
            normalized,
            2,
        )

    percent_match = re.search(
        r"(\d+(?:\.\d+)?)\s*%",
        value,
    )

    if percent_match:
        percent = float(
            percent_match.group(1)
        )

        if not 0 <= percent <= 100:
            return None

        return round(
            percent / 20.0,
            2,
        )

    number_match = re.search(
        r"\d+(?:\.\d+)?",
        value,
    )

    if number_match:
        number = float(
            number_match.group(0)
        )

        if 0 <= number <= 5:
            return round(
                number,
                2,
            )

    return None