"""Integration tests for requirement endpoints."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_analyze_complete_requirement() -> None:
    response = client.post(
        "/api/requirements/analyze",
        json={
            "raw_query": (
                "Tôi có 500 nghìn, "
                "cần tai nghe học online, "
                "mic tốt, pin lâu."
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["requirement"]["category"]
        == "tai nghe"
    )

    assert (
        data["requirement"]["budget_max"]
        == 500000
    )

    assert (
        data["needs_clarification"]
        is False
    )

    assert (
        1
        <= len(data["search_queries"])
        <= 4
    )


def test_analyze_then_clarify_laptop() -> None:
    first_response = client.post(
        "/api/requirements/analyze",
        json={
            "raw_query": "Tìm laptop tốt"
        },
    )

    assert (
        first_response.status_code
        == 200
    )

    first_data = first_response.json()

    assert (
        first_data["needs_clarification"]
        is True
    )

    session_id = first_data[
        "session_id"
    ]

    second_response = client.post(
        "/api/requirements/clarify",
        json={
            "session_id": session_id,
            "answer": (
                "Khoảng 15 triệu "
                "để học lập trình"
            ),
        },
    )

    assert (
        second_response.status_code
        == 200
    )

    second_data = (
        second_response.json()
    )

    assert (
        second_data[
            "requirement"
        ]["category"]
        == "laptop"
    )

    assert (
        second_data[
            "requirement"
        ]["budget_max"]
        == 15_000_000
    )

    assert (
        "học lập trình"
        in second_data[
            "requirement"
        ]["purpose"]
    )

    assert (
        second_data[
            "needs_clarification"
        ]
        is False
    )