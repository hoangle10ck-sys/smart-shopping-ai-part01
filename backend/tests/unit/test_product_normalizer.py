"""Unit tests for deterministic product normalization."""

from app.schemas.search import (
    RawProductCandidateData,
)
from app.services.normalization.product_normalizer import (
    ProductNormalizer,
)
from app.services.normalization.text_normalizer import (
    normalize_product_text,
)


def test_normalize_vietnamese_text() -> None:
    assert (
        normalize_product_text(
            "Điện Thoại Samsung A55 5G"
        )
        == "dien thoai samsung a55 5g"
    )


def test_normalize_raw_product_candidate() -> None:
    raw = RawProductCandidateData(
        name="SoundDemo H20 Wireless",
        brand="SoundDemo",
        model="H20",
        price_text="449.000đ",
        rating_text="4.6/5",
        review_count_text="310",
        availability="in_stock",
        product_url=(
            "https://audio-demo.example/"
            "headphones/sounddemo-h20"
        ),
        source_domain=(
            "audio-demo.example"
        ),
        specifications={
            "Microphone": "ENC",
            "Battery": "40 hours",
        },
    )

    normalized = (
        ProductNormalizer()
        .normalize(raw)
    )

    assert normalized is not None

    assert normalized.name == (
        "SoundDemo H20 Wireless"
    )

    assert normalized.normalized_name == (
        "sounddemo h20 wireless"
    )

    assert normalized.normalized_brand == (
        "sounddemo"
    )

    assert normalized.normalized_model == (
        "h20"
    )

    assert normalized.price == 449000
    assert normalized.rating == 4.6
    assert normalized.review_count == 310

    assert (
        normalized.specifications[
            "microphone"
        ]
        == "ENC"
    )

    assert (
        normalized.specifications[
            "battery"
        ]
        == "40 hours"
    )