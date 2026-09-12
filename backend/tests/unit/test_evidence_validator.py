"""Unit tests for deterministic Data Confidence."""

from app.models.product import Product
from app.models.product_offer import (
    ProductOffer,
)
from app.schemas.ranking import (
    ScoringCandidate,
)
from app.services.recommendation.candidate_builder import (
    CandidateContext,
)
from app.services.validation.evidence_validator import (
    EvidenceValidator,
)


def make_context(
    *,
    source_scores: list[float],
    price: int | None = 449000,
) -> CandidateContext:
    product = Product(
        id=1,
        name="SoundDemo H20 Wireless",
        category="tai nghe",
        brand="SoundDemo",
        model="H20",
        normalized_name=(
            "sounddemo h20 wireless"
        ),
        rating=4.6,
        review_count=310,
        specifications={
            "microphone": "ENC",
            "battery": "40 hours",
        },
        pros=[],
        cons=[],
    )

    offers = [
        ProductOffer(
            id=index + 1,
            product_id=1,
            merchant=(
                f"shop-{index}.example"
            ),
            price=(
                price
                if price is not None
                else None
            ),
            currency="VND",
            availability="in_stock",
            source_id=index + 1,
            product_url=(
                f"https://shop-{index}.example/"
                "product"
            ),
        )
        for index
        in range(
            len(source_scores)
        )
    ]

    selected = (
        offers[0]
        if offers
        else None
    )

    candidate = ScoringCandidate(
        product_id=1,
        name="SoundDemo H20 Wireless",
        category="tai nghe",
        brand="SoundDemo",
        model="H20",
        price=price,
        currency="VND",
        rating=4.6,
        review_count=310,
        availability="in_stock",
        source_reliability=(
            source_scores[0]
            if source_scores
            else 50
        ),
        specifications={
            "microphone": "ENC",
            "battery": "40 hours",
        },
    )

    return CandidateContext(
        candidate=candidate,
        product=product,
        offer=selected,
        offers=offers,
        source_reliabilities=(
            source_scores
        ),
    )


def test_confidence_is_between_zero_and_100() -> None:
    report = (
        EvidenceValidator()
        .validate(
            make_context(
                source_scores=[90]
            )
        )
    )

    assert (
        0
        <= report.confidence
        <= 100
    )


def test_multiple_reliable_sources_improve_confidence() -> None:
    validator = EvidenceValidator()

    single = validator.validate(
        make_context(
            source_scores=[50]
        )
    )

    multiple = validator.validate(
        make_context(
            source_scores=[
                90,
                90,
                90,
            ]
        )
    )

    assert (
        multiple.confidence
        > single.confidence
    )


def test_missing_price_creates_warning() -> None:
    report = (
        EvidenceValidator()
        .validate(
            make_context(
                source_scores=[90],
                price=None,
            )
        )
    )

    assert (
        "Thiếu dữ liệu giá."
        in report.warnings
    )


def test_single_source_is_reported() -> None:
    report = (
        EvidenceValidator()
        .validate(
            make_context(
                source_scores=[90]
            )
        )
    )

    assert any(
        "một nguồn" in warning
        for warning
        in report.warnings
    )