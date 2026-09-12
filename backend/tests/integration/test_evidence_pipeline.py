"""Integration tests for Evidence Validation and Explanation."""

from fastapi.testclient import (
    TestClient,
)
from sqlalchemy import select

from app.core.database import (
    SessionLocal,
)
from app.main import app
from app.models.recommendation import (
    Recommendation,
)


client = TestClient(app)


def create_completed_search() -> tuple[
    str,
    dict,
]:
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

    search = client.post(
        "/api/search",
        json={
            "session_id": session_id
        },
    )

    assert search.status_code == 200

    return (
        session_id,
        search.json(),
    )


def test_api_returns_confidence_and_explanation() -> None:
    _, data = (
        create_completed_search()
    )

    assert (
        data["total_recommended"]
        >= 1
    )

    first = (
        data["recommendations"][0]
    )

    assert (
        0
        <= first["confidence"]
        <= 100
    )

    assert (
        first["evidence"]
        is not None
    )

    assert (
        first["explanation"]
        is not None
    )

    assert (
        first["explanation"][
            "generation_mode"
        ]
        == "demo"
    )


def test_evidence_is_persisted_in_recommendation() -> None:
    session_id, _ = (
        create_completed_search()
    )

    db = SessionLocal()

    try:
        row = db.scalar(
            select(
                Recommendation
            )
            .where(
                Recommendation.session_id
                == session_id
            )
            .order_by(
                Recommendation.rank
            )
        )

        assert row is not None

        assert (
            row.confidence
            is not None
        )

        assert (
            0
            <= row.confidence
            <= 100
        )

        assert isinstance(
            row.explanation,
            dict,
        )

        assert (
            "evidence"
            in row.explanation
        )

        assert (
            "explanation"
            in row.explanation
        )

    finally:
        db.close()