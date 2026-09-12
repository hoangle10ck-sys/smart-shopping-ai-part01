"""Unit tests for price normalization."""

from app.services.normalization.price_parser import (
    parse_price,
)


def test_parse_vnd_dot_separator() -> None:
    assert (
        parse_price(
            "449.000Ä‘"
        )
        == 449000
    )


def test_parse_k_suffix() -> None:
    assert (
        parse_price(
            "399K"
        )
        == 399000
    )


def test_parse_vnd_text() -> None:
    assert (
        parse_price(
            "499.000 VND"
        )
        == 499000
    )


def test_parse_million_decimal() -> None:
    assert (
        parse_price(
            "4,5 triá»‡u"
        )
        == 4500000
    )


def test_parse_million_short() -> None:
    assert (
        parse_price(
            "15 tr"
        )
        == 15000000
    )


def test_parse_missing_price() -> None:
    assert (
        parse_price(
            None
        )
        is None
    )

    assert (
        parse_price(
            ""
        )
        is None
    )


def test_parse_vnd_prefix() -> None:
    assert (
        parse_price(
            "VND 43,681,000"
        )
        == 43681000
    )


def test_parse_vnd_large_price() -> None:
    assert (
        parse_price(
            "43.681.000 VND"
        )
        == 43681000
    )


def test_parse_proper_unicode_million() -> None:
    assert (
        parse_price(
            "43,5 triệu"
        )
        == 43500000
    )


def test_parse_english_million_vnd() -> None:
    assert (
        parse_price(
            "40 million VND"
        )
        == 40000000
    )


def test_reject_rental_price() -> None:
    assert (
        parse_price(
            "$8.95/Day"
        )
        is None
    )


def test_reject_usd_price() -> None:
    assert (
        parse_price(
            "20 USD"
        )
        is None
    )