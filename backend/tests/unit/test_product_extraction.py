"""Unit tests for raw product extraction."""

from app.schemas.search import (
    SearchSourceItem,
)
from app.services.extraction.product_extraction_service import (
    ProductExtractionService,
)


def test_extract_demo_product() -> None:
    """Extractor should preserve demo-style raw values."""

    source = SearchSourceItem(
        title=(
            "SoundDemo H20 Wireless"
        ),
        url=(
            "https://audio-demo.example/"
            "sounddemo-h20"
        ),
        domain=(
            "audio-demo.example"
        ),
        content=(
            "PRODUCT: SoundDemo H20 Wireless | "
            "BRAND: SoundDemo | "
            "MODEL: H20 | "
            "PRICE: 449.000Ä‘ | "
            "RATING: 4.6/5 | "
            "REVIEWS: 310 | "
            "AVAILABILITY: in_stock | "
            "SPECS: microphone=ENC; "
            "battery=40 hours"
        ),
        reliability_score=50,
    )

    candidate = (
        ProductExtractionService()
        .extract(
            source
        )
    )

    assert candidate is not None

    assert (
        candidate.name
        == "SoundDemo H20 Wireless"
    )

    assert (
        candidate.brand
        == "SoundDemo"
    )

    assert (
        candidate.model
        == "H20"
    )

    assert (
        candidate.price_text
        == "449.000Ä‘"
    )

    assert (
        candidate.rating_text
        == "4.6/5"
    )

    assert (
        candidate.review_count_text
        == "310"
    )

    assert (
        candidate.specifications[
            "microphone"
        ]
        == "ENC"
    )

    assert (
        candidate.specifications[
            "battery"
        ]
        == "40 hours"
    )


def test_extract_real_air_blade_product() -> None:
    """Extractor should understand natural Tavily-style text."""

    source = SearchSourceItem(
        title=(
            "Air Blade 125 price list"
        ),
        url=(
            "https://example.com/"
            "air-blade-125"
        ),
        domain="example.com",
        content=(
            "In Vietnam, the Honda "
            "Air Blade 125cc is officially "
            "distributed with four versions. "
            "The listed price is "
            "VND 43,681,000."
        ),
        reliability_score=70,
    )

    candidate = (
        ProductExtractionService()
        .extract(
            source
        )
    )

    assert candidate is not None

    assert (
        candidate.name
        == "Honda Air Blade 125"
    )

    assert (
        candidate.brand
        == "Honda"
    )

    assert (
        candidate.model
        == "Air Blade 125"
    )

    assert (
        candidate.price_text
        == "VND 43,681,000"
    )


def test_extract_rejects_rental_product() -> None:
    """Rental result must not become a purchase candidate."""

    source = SearchSourceItem(
        title=(
            "Honda Air Blade 125cc For Rent"
        ),
        url=(
            "https://example.com/"
            "motorcycle-rentals/"
            "air-blade"
        ),
        domain="example.com",
        content=(
            "Honda Air Blade 125cc. "
            "Price: $8.95/Day."
        ),
        reliability_score=50,
    )

    candidate = (
        ProductExtractionService()
        .extract(
            source
        )
    )

    assert candidate is None