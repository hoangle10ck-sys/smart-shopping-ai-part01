"""Integration tests for recommendation feedback API."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.feedback import Feedback
from app.models.recommendation import Recommendation


client = TestClient(app)


DEMO_QUERY = (
    "Tôi có 500 nghìn, cần tai nghe học online, "
    "mic tốt, pin lâu."
)


def _create_recommended_session() -> tuple[
    str,
    list[int],
]:
    """Create a real search session with recommendations."""

    analyze_response = client.post(
        "/api/requirements/analyze",
        json={
            "raw_query": DEMO_QUERY,
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

    with SessionLocal() as db:
        recommendation_product_ids = list(
            db.scalars(
                select(
                    Recommendation.product_id
                )
                .where(
                    Recommendation.session_id
                    == session_id
                )
                .order_by(
                    Recommendation.id
                )
            )
        )

    product_ids = list(
        dict.fromkeys(
            product_id
            for product_id
            in recommendation_product_ids
            if product_id is not None
        )
    )

    assert len(product_ids) >= 1

    return (
        session_id,
        product_ids,
    )


def test_create_helpful_feedback_for_product() -> None:
    """Helpful product feedback should be persisted."""

    session_id, product_ids = (
        _create_recommended_session()
    )

    response = client.post(
        "/api/feedback",
        json={
            "session_id": session_id,
            "product_id": product_ids[0],
            "is_helpful": True,
            "reason": "Phù hợp nhu cầu",
            "comment": (
                "Sản phẩm được đề xuất khá phù hợp."
            ),
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] > 0
    assert data["session_id"] == session_id
    assert data["product_id"] == product_ids[0]
    assert data["is_helpful"] is True
    assert data["reason"] == "Phù hợp nhu cầu"
    assert (
        data["comment"]
        == "Sản phẩm được đề xuất khá phù hợp."
    )

    with SessionLocal() as db:
        stored = db.get(
            Feedback,
            data["id"],
        )

        assert stored is not None
        assert stored.session_id == session_id
        assert stored.product_id == product_ids[0]
        assert stored.is_helpful is True


def test_feedback_without_product_is_allowed() -> None:
    """Feedback may describe the whole recommendation session."""

    session_id, _ = (
        _create_recommended_session()
    )

    response = client.post(
        "/api/feedback",
        json={
            "session_id": session_id,
            "product_id": None,
            "is_helpful": True,
            "reason": "   ",
            "comment": "   ",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["session_id"] == session_id
    assert data["product_id"] is None
    assert data["is_helpful"] is True

    # Blank optional strings are normalized by
    # FeedbackCreateRequest.
    assert data["reason"] is None
    assert data["comment"] is None


def test_get_feedback_for_session() -> None:
    """Session feedback endpoint should return persisted entries."""

    session_id, product_ids = (
        _create_recommended_session()
    )

    first_response = client.post(
        "/api/feedback",
        json={
            "session_id": session_id,
            "product_id": product_ids[0],
            "is_helpful": True,
            "reason": "Phù hợp",
            "comment": "Đề xuất tốt.",
        },
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/api/feedback",
        json={
            "session_id": session_id,
            "product_id": None,
            "is_helpful": False,
            "reason": "Giá cao",
            "comment": (
                "Tôi muốn có thêm lựa chọn rẻ hơn."
            ),
        },
    )

    assert second_response.status_code == 201

    first_id = first_response.json()["id"]
    second_id = second_response.json()["id"]

    get_response = client.get(
        f"/api/feedback/session/{session_id}"
    )

    assert get_response.status_code == 200

    data = get_response.json()

    assert data["session_id"] == session_id
    assert data["total"] == 2
    assert len(data["items"]) == 2

    returned_ids = {
        item["id"]
        for item in data["items"]
    }

    assert returned_ids == {
        first_id,
        second_id,
    }

    second_item = next(
        item
        for item in data["items"]
        if item["id"] == second_id
    )

    assert second_item["is_helpful"] is False
    assert second_item["reason"] == "Giá cao"


def test_feedback_rejects_missing_session() -> None:
    """Feedback should require an existing search session."""

    response = client.post(
        "/api/feedback",
        json={
            "session_id": (
                "00000000-0000-0000-0000-000000000000"
            ),
            "product_id": None,
            "is_helpful": True,
        },
    )

    assert response.status_code == 404


def test_feedback_rejects_missing_product() -> None:
    """Feedback should reject unknown product IDs."""

    session_id, _ = (
        _create_recommended_session()
    )

    response = client.post(
        "/api/feedback",
        json={
            "session_id": session_id,
            "product_id": 2_147_483_647,
            "is_helpful": False,
            "reason": "Sai sản phẩm",
        },
    )

    assert response.status_code == 404


def test_feedback_rejects_invalid_product_id() -> None:
    """Product ID must be greater than zero."""

    response = client.post(
        "/api/feedback",
        json={
            "session_id": (
                "00000000-0000-0000-0000-000000000000"
            ),
            "product_id": 0,
            "is_helpful": False,
        },
    )

    assert response.status_code == 422