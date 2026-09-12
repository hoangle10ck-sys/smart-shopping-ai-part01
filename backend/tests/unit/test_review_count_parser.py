"""Unit tests for review-count normalization."""

from app.services.normalization.review_count_parser import (
    parse_review_count,
)


def test_plain_review_count() -> None:
    assert parse_review_count(
        "310"
    ) == 310


def test_k_review_count() -> None:
    assert parse_review_count(
        "1.2K"
    ) == 1200


def test_vietnamese_thousand_count() -> None:
    assert parse_review_count(
        "1,5 nghìn"
    ) == 1500


def test_missing_review_count() -> None:
    assert (
        parse_review_count(None)
        is None
    )