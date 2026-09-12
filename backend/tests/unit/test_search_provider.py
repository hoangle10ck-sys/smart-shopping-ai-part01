"""Unit tests for MockSearchProvider."""

import pytest

from app.services.search.mock_provider import MockSearchProvider


@pytest.mark.asyncio
async def test_mock_search_headphones() -> None:
    """Mock provider should return headphone demo products."""

    provider = MockSearchProvider()

    results = await provider.search(
        "tai nghe dưới 500000 VND học online",
        max_results=5,
    )

    assert len(results) >= 1
    assert "SoundDemo" in results[0].title


@pytest.mark.asyncio
async def test_mock_search_unknown_category() -> None:
    """Unknown categories should return no demo products."""

    provider = MockSearchProvider()

    results = await provider.search(
        "một loại sản phẩm không xác định",
        max_results=5,
    )

    assert results == []