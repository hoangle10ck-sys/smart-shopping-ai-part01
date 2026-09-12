"""Integration tests for recommendation read APIs."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.recommendation import (
    Recommendation,
)


client = TestClient(app)


QUERY = (
    "Tôi có 500 nghìn, cần tai nghe học online, "
    "mic tốt, pin lâu."
)


def _create_session() -> str:
    """Create a completed recommendation session."""

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

    assert len(
        search_response.json()[
            "recommendations"
        ]
    ) >= 1

    return session_id


def test_get_session_recommendations() -> None:
    """Completed session should expose recommendation cards."""

    session_id = _create_session()

    response = client.get(
        (
            "/api/recommendations/"
            f"session/{session_id}"
        )
    )

    assert response.status_code == 200

    data = response.json()

    assert data["session_id"] == session_id
    assert data["total"] >= 1
    assert len(data["items"]) == data["total"]

    item = data["items"][0]

    assert item["product_id"] > 0
    assert item["rank"] >= 1

    assert "image_url" in item
    assert "price" in item
    assert "rating" in item
    assert "score" in item
    assert "confidence" in item
    assert "evidence" in item
    assert "explanation" in item


def test_get_single_recommendation() -> None:
    """Persisted recommendation should be readable by ID."""

    session_id = _create_session()

    with SessionLocal() as db:
        recommendation = db.scalar(
            select(Recommendation)
            .where(
                Recommendation.session_id
                == session_id
            )
            .order_by(
                Recommendation.rank
            )
        )

        assert recommendation is not None

        recommendation_id = (
            recommendation.id
        )

        product_id = (
            recommendation.product_id
        )

    response = client.get(
        (
            "/api/recommendations/"
            f"{recommendation_id}"
        )
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == recommendation_id
    assert data["session_id"] == session_id
    assert data["product_id"] == product_id

    assert (
        data["item"]["product_id"]
        == product_id
    )


def test_missing_recommendation_session_returns_404() -> None:
    """Unknown search session should return 404."""

    response = client.get(
        (
            "/api/recommendations/session/"
            "00000000-0000-0000-0000-000000000000"
        )
    )

    assert response.status_code == 404


def test_missing_recommendation_returns_404() -> None:
    """Unknown recommendation ID should return 404."""

    response = client.get(
        "/api/recommendations/2147483647"
    )

    assert response.status_code == 404