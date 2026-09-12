"""Unit tests for deterministic hard filters."""

from app.schemas.ranking import (
    ScoringCandidate,
)
from app.schemas.requirement import (
    RequirementData,
)
from app.services.filter.hard_filter import (
    HardFilterService,
)


def make_candidate(
    **overrides,
) -> ScoringCandidate:
    data = {
        "product_id": 1,
        "name": "Demo Phone X5",
        "category": "điện thoại",
        "brand": "Demo",
        "model": "X5",
        "price": 4_500_000,
        "rating": 4.5,
        "review_count": 200,
        "availability": "in_stock",
        "source_reliability": 90,
        "specifications": {
            "camera": "50MP OIS",
            "battery": "5000mAh",
            "weight": "188g",
        },
    }

    data.update(
        overrides
    )

    return ScoringCandidate(
        **data
    )


def make_requirement(
    **overrides,
) -> RequirementData:
    data = {
        "category": "điện thoại",
        "budget_max": 5_000_000,
        "currency": "VND",
        "purpose": ["chụp ảnh"],
        "brands": [],
        "requirements": [],
        "excluded_requirements": [],
        "sort_preference": "best_match",
        "confidence": 1.0,
    }

    data.update(
        overrides
    )

    return RequirementData(
        **data
    )


def test_valid_candidate_passes() -> None:
    decision = (
        HardFilterService()
        .evaluate(
            make_candidate(),
            make_requirement(),
        )
    )

    assert decision.accepted is True


def test_wrong_category_rejected_first() -> None:
    decision = (
        HardFilterService()
        .evaluate(
            make_candidate(
                category="laptop",
                price=20_000_000,
            ),
            make_requirement(),
        )
    )

    assert decision.accepted is False
    assert (
        decision.rejection_stage
        == "category"
    )


def test_over_budget_is_rejected() -> None:
    decision = (
        HardFilterService()
        .evaluate(
            make_candidate(
                price=5_500_000,
            ),
            make_requirement(),
        )
    )

    assert decision.accepted is False

    assert (
        decision.rejection_stage
        == "budget"
    )


def test_missing_price_rejected_when_budget_exists() -> None:
    decision = (
        HardFilterService()
        .evaluate(
            make_candidate(
                price=None,
            ),
            make_requirement(),
        )
    )

    assert decision.accepted is False

    assert (
        decision.rejection_stage
        == "budget"
    )


def test_brand_filter_rejects_wrong_brand() -> None:
    decision = (
        HardFilterService()
        .evaluate(
            make_candidate(
                brand="Demo",
            ),
            make_requirement(
                brands=["Samsung"],
            ),
        )
    )

    assert decision.accepted is False

    assert (
        decision.rejection_stage
        == "brand"
    )


def test_heavy_product_is_excluded() -> None:
    decision = (
        HardFilterService()
        .evaluate(
            make_candidate(
                specifications={
                    "weight": "245g",
                },
            ),
            make_requirement(
                excluded_requirements=[
                    "máy quá nặng"
                ],
            ),
        )
    )

    assert decision.accepted is False

    assert (
        decision.rejection_stage
        == "exclusion"
    )


def test_out_of_stock_is_rejected() -> None:
    decision = (
        HardFilterService()
        .evaluate(
            make_candidate(
                availability=(
                    "out_of_stock"
                ),
            ),
            make_requirement(),
        )
    )

    assert decision.accepted is False

    assert (
        decision.rejection_stage
        == "availability"
    )