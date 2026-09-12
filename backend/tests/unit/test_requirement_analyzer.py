"""Unit tests for requirement analysis."""

import pytest

from app.services.llm.client import (
    MockLLMClient,
)
from app.services.llm.requirement_analyzer import (
    RequirementAnalyzer,
)


@pytest.mark.asyncio
async def test_complete_headphone_requirement() -> None:
    analyzer = RequirementAnalyzer(
        client=MockLLMClient()
    )

    result = await analyzer.analyze(
        "Tôi có 500 nghìn, cần tai nghe "
        "để học online, mic tốt, pin lâu."
    )

    requirement = result.requirement

    assert requirement.category == "tai nghe"

    assert (
        requirement.budget_max
        == 500_000
    )

    assert "học online" in requirement.purpose

    assert result.needs_clarification is False

    assert result.clarification_question is None


@pytest.mark.asyncio
async def test_laptop_without_budget_requires_clarification() -> None:
    analyzer = RequirementAnalyzer(
        client=MockLLMClient()
    )

    result = await analyzer.analyze(
        "Tìm laptop tốt"
    )

    assert (
        result.requirement.category
        == "laptop"
    )

    assert result.needs_clarification is True

    assert "budget" in result.missing_fields

    assert (
        result.clarification_question
        == "Bạn dự kiến ngân sách khoảng bao nhiêu?"
    )


@pytest.mark.asyncio
async def test_vietnamese_without_accents() -> None:
    analyzer = RequirementAnalyzer(
        client=MockLLMClient()
    )

    result = await analyzer.analyze(
        "Toi co 500 nghin can tai nghe "
        "hoc online mic tot pin lau"
    )

    requirement = result.requirement

    assert requirement.category == "tai nghe"

    assert (
        requirement.budget_max
        == 500_000
    )

    assert "học online" in requirement.purpose

    assert result.needs_clarification is False