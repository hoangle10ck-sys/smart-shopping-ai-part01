"""Unit tests for universal query generation."""

from app.schemas.requirement import (
    RequirementData,
    RequirementItem,
)
from app.services.llm.query_generator import (
    QueryGenerator,
)


def test_generate_queries() -> None:
    requirement = RequirementData(
        category="tai nghe",
        budget_min=None,
        budget_max=500000,
        currency="VND",
        purpose=[
            "học online",
        ],
        brands=[],
        requirements=[
            RequirementItem(
                name="microphone",
                value="tốt",
                priority=5,
            ),
            RequirementItem(
                name="battery",
                value="pin lâu",
                priority=4,
            ),
        ],
        excluded_requirements=[],
        sort_preference=(
            "best_match"
        ),
        confidence=0.95,
    )

    queries = (
        QueryGenerator(
            max_queries=4
        )
        .generate(
            requirement
        )
    )

    assert queries

    assert len(
        queries
    ) <= 4

    combined = " ".join(
        queries
    ).lower()

    assert "tai nghe" in combined
    assert "500000" in combined
    assert (
        "mua" in combined
        or "giá" in combined
    )


def test_generate_queries_without_category() -> None:
    requirement = RequirementData(
        category=None,
        budget_min=None,
        budget_max=500000,
        currency="VND",
        purpose=[],
        brands=[],
        requirements=[],
        excluded_requirements=[],
        sort_preference=(
            "best_match"
        ),
        confidence=0.3,
    )

    queries = (
        QueryGenerator()
        .generate(
            requirement
        )
    )

    assert queries == []


def test_unknown_product_category_is_supported() -> None:
    """Unknown categories must still receive commerce queries."""

    requirement = RequirementData(
        category=(
            "máy đóng đai thùng carton"
        ),
        budget_min=None,
        budget_max=20000000,
        currency="VND",
        purpose=[
            "đóng gói hàng hóa",
        ],
        brands=[],
        requirements=[],
        excluded_requirements=[],
        sort_preference=(
            "best_match"
        ),
        confidence=0.9,
    )

    queries = (
        QueryGenerator(
            max_queries=4
        )
        .generate(
            requirement
        )
    )

    assert queries

    combined = " ".join(
        queries
    ).lower()

    assert (
        "máy đóng đai thùng carton"
        in combined
    )

    assert (
        "mua"
        in combined
    )

    assert (
        "việt nam"
        in combined
    )


def test_fashion_gets_preferred_marketplace_query() -> None:
    requirement = RequirementData(
        category="áo khoác nam",
        budget_min=None,
        budget_max=500000,
        currency="VND",
        purpose=[],
        brands=[],
        requirements=[
            RequirementItem(
                name="color",
                value="đen",
                priority=3,
            )
        ],
        excluded_requirements=[],
        sort_preference=(
            "best_match"
        ),
        confidence=0.9,
    )

    queries = (
        QueryGenerator(
            max_queries=6
        )
        .generate(
            requirement
        )
    )

    combined = " ".join(
        queries
    ).lower()

    assert (
        "shopee.vn"
        in combined
        or "lazada.vn"
        in combined
        or "tiki.vn"
        in combined
    )