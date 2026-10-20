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

    assert result.clarification_question == "Bạn dự kiến ngân sách khoảng bao nhiêu?"


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

@pytest.mark.asyncio
@pytest.mark.parametrize("category_text", ["Tai nghe microphone tốt", "Headphones microphone tốt", "Headset microphone tốt"])
async def test_microphone_does_not_imply_phone(category_text):
    result = await RequirementAnalyzer(client=MockLLMClient()).analyze(f"{category_text}, 500 nghìn để học online")
    assert result.requirement.category == "tai nghe"
    assert result.needs_clarification is False

@pytest.mark.asyncio
@pytest.mark.parametrize("budget, minimum, maximum", [
    ("15.000.000 VND", None, 15000000), ("15,000,000 VND", None, 15000000),
    ("VND 15.000.000", None, 15000000), ("15000000đ", None, 15000000),
    ("15 triệu", None, 15000000), ("15 tr", None, 15000000),
    ("1,5 triệu", None, 1500000), ("500 nghìn", None, 500000),
    ("500 ngàn", None, 500000), ("500K", None, 500000), ("1 tỷ", None, 1000000000),
    ("từ 10 đến 15 triệu", 10000000, 15000000),
    ("tu 10 den 15 trieu", 10000000, 15000000),
    ("từ 10 triệu đến 15 triệu", 10000000, 15000000),
    ("từ 10.000.000 đến 15.000.000 VND", 10000000, 15000000),
    ("từ 500 nghìn đến 1,5 triệu", 500000, 1500000),
])
async def test_local_budget_formats(budget, minimum, maximum):
    result = await RequirementAnalyzer(client=MockLLMClient()).analyze(f"Laptop {budget} để học lập trình, RAM 16GB")
    assert result.requirement.budget_min == minimum
    assert result.requirement.budget_max == maximum
    assert result.needs_clarification is False
