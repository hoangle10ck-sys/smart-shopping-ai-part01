"""Unit tests for deterministic scoring."""

import pytest

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


@pytest.mark.parametrize("specs, required, expected", [
    ({"ram": "8GB"}, "16GB", 0),
    ({"ram": "16GB"}, "16GB", 100),
    ({"ram": "32 GB"}, "16GB", 100),
    ({"ram": "8 GB, nâng cấp tối đa 32GB"}, "16GB", 0),
    ({"ram": "16GB"}, "tối đa 8GB", 0),
    ({"RAM": "16384 MB"}, "16GB", 100),
    ({"storage": "16GB"}, "16GB", 0),
    ({}, "16GB", 0),
    ({"ram": "unknown"}, "16GB", 0),
])
def test_ram_value_is_verified(specs, required, expected):
    candidate = make_candidate(name="Laptop RAM 16GB", specifications=specs)
    requirement = make_requirement(requirements=[RequirementItem(name="RAM", value=required, priority=5)])
    assert ScoringEngine().requirement_score(candidate, requirement) == expected

@pytest.mark.parametrize("specs, name, value, expected", [
    ({"color": "trắng"}, "color", "đen", 0),
    ({"color": "đen"}, "color", "đen", 100),
    ({"microphone": "không có"}, "microphone", "tốt", 0),
    ({"microphone": "không tốt"}, "microphone", "tốt", 0),
    ({"microphone": "N/A"}, "microphone", "tốt", 0),
    ({"microphone": "ENC"}, "microphone", "tốt", 100),
    ({"battery": "1 hour"}, "battery", "pin lâu", 0),
    ({"battery": "40 hours"}, "battery", "pin lâu", 100),
    ({}, "battery", "pin lâu", 0),
    ({"storage": "512GB SSD"}, "storage", "1TB", 0),
    ({"storage": "1TB SSD"}, "storage", "512GB", 100),
])
def test_requirement_values_and_missing_evidence(specs, name, value, expected):
    candidate = make_candidate(category="tai nghe", specifications=specs)
    requirement = make_requirement(requirements=[RequirementItem(name=name, value=value, priority=5)])
    assert ScoringEngine().requirement_score(candidate, requirement) == expected

def test_value_matching_keeps_priority_and_final_weights():
    candidate = make_candidate(specifications={"ram": "8GB", "color": "đen"})
    requirement = make_requirement(requirements=[
        RequirementItem(name="ram", value="16GB", priority=5),
        RequirementItem(name="color", value="đen", priority=1),
    ])
    engine = ScoringEngine()
    assert engine.requirement_score(candidate, requirement) == pytest.approx(100 / 6)
    score = engine.score(candidate, requirement)
    expected = sum(weight * value for weight, value in [
        (.25, engine.budget_score(candidate, requirement)),
        (.30, engine.requirement_score(candidate, requirement)),
        (.20, engine.purpose_score(candidate, requirement)),
        (.10, engine.rating_score(candidate)), (.05, engine.review_score(candidate)),
        (.10, engine.source_score(candidate)),
    ])
    assert score.final_score == round(expected, 2)
