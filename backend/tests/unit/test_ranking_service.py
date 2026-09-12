"""Unit tests for deterministic product ranking."""

from app.schemas.ranking import (
    ScoringCandidate,
)
from app.schemas.requirement import (
    RequirementData,
)
from app.services.recommendation.ranking_service import (
    RankingService,
)


def make_requirement() -> RequirementData:
    return RequirementData(
        category="tai nghe",
        budget_max=500_000,
        currency="VND",
        purpose=[],
        brands=[],
        requirements=[],
        excluded_requirements=[],
        sort_preference="best_match",
        confidence=1.0,
    )


def test_higher_scoring_product_ranks_first() -> None:
    candidates = [
        ScoringCandidate(
            product_id=1,
            name="Weak Headphone",
            category="tai nghe",
            price=300_000,
            rating=3.0,
            review_count=10,
            source_reliability=50,
        ),
        ScoringCandidate(
            product_id=2,
            name="Better Headphone",
            category="tai nghe",
            price=480_000,
            rating=4.8,
            review_count=500,
            source_reliability=90,
        ),
    ]

    ranked = (
        RankingService()
        .rank(
            candidates,
            make_requirement(),
            top_k=5,
        )
    )

    assert (
        ranked[0]
        .candidate
        .product_id
        == 2
    )

    assert ranked[0].rank == 1


def test_top_k_is_respected() -> None:
    candidates = [
        ScoringCandidate(
            product_id=index,
            name=f"Product {index}",
            category="tai nghe",
            price=400_000,
            rating=4.0,
            review_count=100,
            source_reliability=80,
        )
        for index
        in range(1, 11)
    ]

    ranked = (
        RankingService()
        .rank(
            candidates,
            make_requirement(),
            top_k=5,
        )
    )

    assert len(ranked) == 5

    assert [
        item.rank
        for item in ranked
    ] == [
        1,
        2,
        3,
        4,
        5,
    ]