"""Integration tests for filtering, scoring and ranking."""

from sqlalchemy import (
    func,
    select,
)
from fastapi.testclient import TestClient

from app.core.database import (
    SessionLocal,
)
from app.main import app
from app.models.recommendation import (
    Recommendation,
)


client = TestClient(app)


def test_search_returns_ranked_recommendations() -> None:
    analyze = client.post(
        "/api/requirements/analyze",
        json={
            "raw_query": (
                "Tôi có 500 nghìn, "
                "cần tai nghe để học online, "
                "mic tốt, pin lâu."
            )
        },
    )

    assert analyze.status_code == 200

    session_id = (
        analyze.json()["session_id"]
    )

    response = client.post(
        "/api/search",
        json={
            "session_id": session_id
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["requirement"]["category"]
        == "tai nghe"
    )

    assert data["total_found"] == 3

    assert data["total_filtered"] == 3

    assert data["total_recommended"] >= 1

    assert (
        len(data["recommendations"])
        == data["total_recommended"]
    )

    first = data["recommendations"][0]

    assert first["rank"] == 1

    assert (
        0
        <= first["score"]["final_score"]
        <= 100
    )


def test_budget_filter_removes_over_budget_products() -> None:
    analyze = client.post(
        "/api/requirements/analyze",
        json={
            "raw_query": (
                "Tôi có 400 nghìn, "
                "cần tai nghe để học online, "
                "mic tốt, pin lâu."
            )
        },
    )

    assert analyze.status_code == 200

    session_id = (
        analyze.json()["session_id"]
    )

    response = client.post(
        "/api/search",
        json={
            "session_id": session_id
        },
    )

    assert response.status_code == 200

    data = response.json()

    names = [
        item["name"]
        for item
        in data["recommendations"]
    ]

    assert names == [
        "StudyBeat M5"
    ]

    assert (
        data["total_filtered"]
        == 1
    )


def test_recommendations_are_not_duplicated_on_rerun() -> None:
    analyze = client.post(
        "/api/requirements/analyze",
        json={
            "raw_query": (
                "Tôi có 500 nghìn, "
                "cần tai nghe học online, "
                "mic tốt, pin lâu."
            )
        },
    )

    session_id = (
        analyze.json()["session_id"]
    )

    first = client.post(
        "/api/search",
        json={
            "session_id": session_id
        },
    )

    second = client.post(
        "/api/search",
        json={
            "session_id": session_id
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200

    expected = (
        second.json()[
            "total_recommended"
        ]
    )

    db = SessionLocal()

    try:
        count = db.scalar(
            select(
                func.count(
                    Recommendation.id
                )
            ).where(
                Recommendation.session_id
                == session_id
            )
        )

        assert count == expected

    finally:
        db.close()