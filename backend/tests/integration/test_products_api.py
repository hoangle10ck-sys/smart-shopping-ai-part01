"""Integration tests for product detail API."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


QUERY = (
    "Tôi có 500 nghìn, cần tai nghe học online, "
    "mic tốt, pin lâu."
)


def _create_recommended_product() -> int:
    """Create search pipeline and return one product ID."""

    analyze_response = client.post(
        "/api/requirements/analyze",
        json={
            "raw_query": QUERY,
        },
    )

    assert analyze_response.status_code == 200

    session_id = (
        analyze_response.json()["session_id"]
    )

    search_response = client.post(
        "/api/search",
        json={
            "session_id": session_id,
        },
    )

    assert search_response.status_code == 200

    recommendations = (
        search_response.json()[
            "recommendations"
        ]
    )

    assert len(recommendations) >= 1

    return recommendations[0]["product_id"]


def test_get_product_detail() -> None:
    """Recommended product should expose detail data."""

    product_id = (
        _create_recommended_product()
    )

    response = client.get(
        f"/api/products/{product_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == product_id
    assert "name" in data
    assert "category" in data
    assert "rating" in data
    assert "specifications" in data
    assert "pros" in data
    assert "cons" in data
    assert "offers" in data

    assert isinstance(
        data["offers"],
        list,
    )

    assert len(
        data["offers"]
    ) >= 1


def test_product_offer_contains_frontend_fields() -> None:
    """Offers should expose price and source information."""

    product_id = (
        _create_recommended_product()
    )

    response = client.get(
        f"/api/products/{product_id}"
    )

    assert response.status_code == 200

    offers = response.json()["offers"]

    assert len(offers) >= 1

    offer = offers[0]

    assert "merchant" in offer
    assert "price" in offer
    assert "currency" in offer
    assert "availability" in offer
    assert "product_url" in offer
    assert "source_domain" in offer


def test_missing_product_returns_404() -> None:
    """Unknown product ID should return 404."""

    response = client.get(
        "/api/products/2147483647"
    )

    assert response.status_code == 404