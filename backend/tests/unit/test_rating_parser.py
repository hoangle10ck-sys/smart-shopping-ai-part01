"""Unit tests for rating normalization."""

from app.services.normalization.rating_parser import (
    parse_rating,
)


def test_parse_rating_dot() -> None:
    assert parse_rating(
        "4.6/5"
    ) == 4.6


def test_parse_rating_comma() -> None:
    assert parse_rating(
        "4,4/5"
    ) == 4.4


def test_parse_rating_out_of_ten() -> None:
    assert parse_rating(
        "9/10"
    ) == 4.5


def test_parse_rating_percentage() -> None:
    assert parse_rating(
        "92%"
    ) == 4.6


def test_invalid_rating() -> None:
    assert parse_rating(
        "không có đánh giá"
    ) is None