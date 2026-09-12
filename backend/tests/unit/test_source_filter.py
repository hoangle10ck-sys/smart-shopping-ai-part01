"""Unit tests for source validation."""

from app.services.search.base import (
    SearchResult,
)
from app.services.search.source_filter import (
    SourceFilter,
    calculate_source_reliability,
)


def test_source_filter_removes_invalid_urls() -> None:
    """Invalid non-HTTP URLs must be rejected."""

    service = SourceFilter()

    results = [
        SearchResult(
            title="Valid",
            url=(
                "https://example.com/"
                "product"
            ),
            content="Product",
        ),
        SearchResult(
            title="Invalid",
            url="javascript:alert(1)",
            content="Bad",
        ),
    ]

    filtered = (
        service.filter(
            results
        )
    )

    assert (
        len(filtered)
        == 1
    )

    assert (
        filtered[0].domain
        == "example.com"
    )


def test_source_score_for_trusted_retailer() -> None:
    """Trusted retailers should receive configured score."""

    score = (
        calculate_source_reliability(
            "cellphones.com.vn"
        )
    )

    assert score == 90.0


def test_source_filter_removes_rental_result() -> None:
    """Rental pages must not enter product purchase pipeline."""

    service = SourceFilter()

    results = [
        SearchResult(
            title=(
                "Honda Air Blade 125cc "
                "For Rent"
            ),
            url=(
                "https://example.com/"
                "motorcycle-rentals/"
                "air-blade"
            ),
            content=(
                "Honda Air Blade 125cc. "
                "Price: $8.95/Day."
            ),
        ),
        SearchResult(
            title=(
                "Honda Air Blade 125 "
                "price list"
            ),
            url=(
                "https://example.vn/"
                "air-blade-125"
            ),
            content=(
                "Honda Air Blade 125 "
                "listed price "
                "VND 43,681,000."
            ),
        ),
    ]

    filtered = (
        service.filter(
            results
        )
    )

    assert (
        len(filtered)
        == 1
    )

    assert (
        filtered[0].url
        == (
            "https://example.vn/"
            "air-blade-125"
        )
    )