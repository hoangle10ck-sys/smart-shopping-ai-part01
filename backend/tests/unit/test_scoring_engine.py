"""Unit tests for deterministic scoring."""

from app.schemas.ranking import (
    ScoringCandidate,
)
from app.schemas.requirement import (
    RequirementData,
    RequirementItem,
)
from app.services.scoring.scoring_engine import (
    ScoringEngine,
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
        "review_count": 250,
        "availability": "in_stock",
        "source_reliability": 90,
        "specifications": {
            "camera": "50MP OIS",
            "battery": "5000mAh",
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
        "purpose": [
            "chụp ảnh",
        ],
        "brands": [],
        "requirements": [
            RequirementItem(
                name="camera",
                value="tốt",
                priority=5,
            ),
            RequirementItem(
                name="battery",
                value="pin lâu",
                priority=4,
            ),
        ],
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


def test_final_score_is_between_zero_and_100() -> None:
    score = (
        ScoringEngine()
        .score(
            make_candidate(),
            make_requirement(),
        )
    )

    assert (
        0
        <= score.final_score
        <= 100
    )


def test_rating_score_normalizes_five_star_rating() -> None:
    score = (
        ScoringEngine()
        .rating_score(
            make_candidate(
                rating=4.5
            )
        )
    )

    assert score == 90.0


def test_requirement_priority_is_respected() -> None:
    engine = ScoringEngine()

    good = make_candidate(
        specifications={
            "camera": "50MP OIS",
            "battery": "5000mAh",
        }
    )

    weak = make_candidate(
        specifications={
            "battery": "5000mAh",
        }
    )

    requirement = (
        make_requirement()
    )

    good_score = (
        engine.requirement_score(
            good,
            requirement,
        )
    )

    weak_score = (
        engine.requirement_score(
            weak,
            requirement,
        )
    )

    assert good_score > weak_score


def test_missing_rating_and_reviews_score_zero() -> None:
    engine = ScoringEngine()

    candidate = make_candidate(
        rating=None,
        review_count=None,
    )

    assert (
        engine.rating_score(
            candidate
        )
        == 0
    )

    assert (
        engine.review_score(
            candidate
        )
        == 0
    )


def test_source_score_uses_reliability() -> None:
    score = (
        ScoringEngine()
        .source_score(
            make_candidate(
                source_reliability=90
            )
        )
    )

    assert score == 90.0