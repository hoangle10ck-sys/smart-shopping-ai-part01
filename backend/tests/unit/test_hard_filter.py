"""Unit tests for deterministic hard filters."""

import pytest
from app.services.filter.hard_filter import parse_weight_grams

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


@pytest.mark.parametrize("weight, grams, accepted", [
    ("1.45kg", 1450, True), ("1,45 kg", 1450, True), ("950g", 950, True),
    ("2.2 kg", 2200, True), ("2,21 kg", 2210, False), ("2450 g", 2450, False),
    ("unknown", None, True),
])
def test_decimal_weight_and_exclusion(weight, grams, accepted):
    candidate = make_candidate(category="laptop", specifications={"weight": weight})
    requirement = make_requirement(category="laptop", excluded_requirements=["máy quá nặng"])
    assert parse_weight_grams(candidate) == grams
    decision = HardFilterService().evaluate(candidate, requirement)
    assert decision.accepted is accepted
    if not accepted:
        assert decision.rejection_stage == "exclusion"

def test_unknown_category_cannot_pass_required_category():
    decision = HardFilterService().evaluate(make_candidate(category=None), make_requirement(category="laptop"))
    assert decision.accepted is False
    assert decision.rejection_stage == "category"
