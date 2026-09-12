"""Integration tests for product comparison API."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.comparison import ComparisonSession
from app.models.product import Product
from app.models.recommendation import Recommendation


client = TestClient(app)


DEMO_QUERY = (
    "Tôi có 500 nghìn, cần tai nghe học online, "
    "mic tốt, pin lâu."
)


def _create_recommended_session(
    *,
    min_products: int = 2,
) -> tuple[str, list[int]]:
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

    assert len(product_ids) >= min_products

    return (
        session_id,
        product_ids,
    )


def test_create_and_get_comparison() -> None:
    """Two recommended products should be comparable."""

    session_id, product_ids = (
        _create_recommended_session()
    )

    selected_ids = product_ids[:2]

    create_response = client.post(
        "/api/comparisons",
        json={
            "session_id": session_id,
            "product_ids": selected_ids,
        },
    )

    assert create_response.status_code == 201

    data = create_response.json()

    assert data["id"] > 0
    assert data["session_id"] == session_id
    assert data["product_ids"] == selected_ids
    assert data["result"] is not None

    result = data["result"]

    assert (
        result["winner_product_id"]
        in selected_ids
    )

    assert len(
        result["products"]
    ) == 2

    result_product_ids = [
        item["product_id"]
        for item in result["products"]
    ]

    assert result_product_ids == selected_ids

    assert "AI score" in result["criteria"]
    assert "Price" in result["criteria"]
    assert "Rating" in result["criteria"]

    comparison_id = data["id"]

    with SessionLocal() as db:
        stored = db.get(
            ComparisonSession,
            comparison_id,
        )

        assert stored is not None
        assert stored.session_id == session_id
        assert stored.product_ids == selected_ids
        assert stored.result is not None

    get_response = client.get(
        f"/api/comparisons/{comparison_id}"
    )

    assert get_response.status_code == 200

    loaded = get_response.json()

    assert loaded["id"] == comparison_id
    assert loaded["session_id"] == session_id
    assert loaded["product_ids"] == selected_ids
    assert (
        loaded["result"]["winner_product_id"]
        == result["winner_product_id"]
    )


def test_compare_three_products() -> None:
    """Three recommended products should be comparable."""

    session_id, product_ids = (
        _create_recommended_session(
            min_products=3,
        )
    )

    selected_ids = product_ids[:3]

    response = client.post(
        "/api/comparisons",
        json={
            "session_id": session_id,
            "product_ids": selected_ids,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["product_ids"] == selected_ids
    assert len(
        data["result"]["products"]
    ) == 3

    assert (
        data["result"]["winner_product_id"]
        in selected_ids
    )


def test_comparison_requires_at_least_two_products() -> None:
    """Comparison should reject fewer than two products."""

    response = client.post(
        "/api/comparisons",
        json={
            "session_id": (
                "00000000-0000-0000-0000-000000000000"
            ),
            "product_ids": [1],
        },
    )

    assert response.status_code == 422


def test_comparison_allows_at_most_three_products() -> None:
    """Comparison should reject more than three products."""

    response = client.post(
        "/api/comparisons",
        json={
            "session_id": (
                "00000000-0000-0000-0000-000000000000"
            ),
            "product_ids": [
                1,
                2,
                3,
                4,
            ],
        },
    )

    assert response.status_code == 422


def test_comparison_rejects_duplicate_product_ids() -> None:
    """The same product cannot be selected twice."""

    response = client.post(
        "/api/comparisons",
        json={
            "session_id": (
                "00000000-0000-0000-0000-000000000000"
            ),
            "product_ids": [
                1,
                1,
            ],
        },
    )

    assert response.status_code == 422


def test_comparison_rejects_missing_session() -> None:
    """Comparison should require an existing search session."""

    response = client.post(
        "/api/comparisons",
        json={
            "session_id": (
                "00000000-0000-0000-0000-000000000000"
            ),
            "product_ids": [
                1,
                2,
            ],
        },
    )

    assert response.status_code == 404


def test_comparison_rejects_missing_product() -> None:
    """Comparison should reject an unknown product."""

    session_id, product_ids = (
        _create_recommended_session()
    )

    missing_product_id = 2_147_483_647

    response = client.post(
        "/api/comparisons",
        json={
            "session_id": session_id,
            "product_ids": [
                product_ids[0],
                missing_product_id,
            ],
        },
    )

    assert response.status_code == 404

    data = response.json()

    assert (
        missing_product_id
        in data["detail"]["product_ids"]
    )


def test_comparison_rejects_product_not_recommended() -> None:
    """Existing product must belong to session recommendations."""

    session_id, product_ids = (
        _create_recommended_session()
    )

    unrelated_product_id: int | None = None

    try:
        with SessionLocal() as db:
            unrelated_product = Product(
                name=(
                    "Unrelated integration product "
                    f"{uuid4()}"
                ),
            )

            db.add(unrelated_product)
            db.commit()
            db.refresh(unrelated_product)

            unrelated_product_id = (
                unrelated_product.id
            )

        response = client.post(
            "/api/comparisons",
            json={
                "session_id": session_id,
                "product_ids": [
                    product_ids[0],
                    unrelated_product_id,
                ],
            },
        )

        assert response.status_code == 409

        data = response.json()

        assert (
            unrelated_product_id
            in data["detail"]["product_ids"]
        )

    finally:
        if unrelated_product_id is not None:
            with SessionLocal() as db:
                product = db.get(
                    Product,
                    unrelated_product_id,
                )

                if product is not None:
                    db.delete(product)
                    db.commit()