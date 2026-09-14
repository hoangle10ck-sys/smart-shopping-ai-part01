"""The three documented demo inputs must work offline on a clean test database."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.parametrize("query,category,budget,purposes", [
    ("Tôi có 500 nghìn, cần tai nghe để học online, mic tốt, pin lâu.", "tai nghe", 500000, ["học online"]),
    ("Tôi cần laptop khoảng 15 triệu để học lập trình.", "laptop", 15000000, ["học lập trình"]),
    ("Tôi có 5 triệu, cần điện thoại để chụp ảnh và chơi game, ưu tiên camera tốt, pin lâu.",
     "điện thoại", 5000000, ["chơi game", "chụp ảnh"]),
])
def test_documented_demo(query, category, budget, purposes):
    with TestClient(app) as client:
        analysis = client.post("/api/requirements/analyze", json={"raw_query": query})
        assert analysis.status_code == 200
        analyzed = analysis.json()
        requirement = analyzed["requirement"]
        assert not analyzed["needs_clarification"]
        assert requirement["category"] == category
        assert requirement["budget_max"] == budget
        assert set(requirement["purpose"]) == set(purposes)
        session_id = analyzed["session_id"]
        response = client.post("/api/search", json={"session_id": session_id})
        assert response.status_code == 200
        result = response.json()
        assert result["data_mode"] == "demo"
        assert (result["total_found"], result["total_filtered"], result["total_recommended"]) == (3, 3, 3)
        for item in result["recommendations"]:
            assert item["category"] == category and item["price"] <= budget
            assert item["explanation"]["generation_mode"] == "demo"
            assert item["evidence"]["fields"]
            assert len(item["requirement_matches"]) == len(requirement["requirements"])
        selected = [item["product_id"] for item in result["recommendations"][:2]]
        comparison = client.post("/api/comparisons", json={"session_id": session_id, "product_ids": selected})
        assert comparison.status_code == 201
        assert client.get(f"/api/products/{selected[0]}").status_code == 200
        assert client.post("/api/feedback", json={"session_id": session_id, "product_id": selected[0], "is_helpful": True}).status_code == 201
        history = client.get(f"/api/history/{session_id}")
        assert history.status_code == 200
        assert history.json()["result"]["recommendations"] == result["recommendations"]
        print(json.dumps({"category": category, "requirement": requirement,
                          "products": [{"name": p["name"], "price": p["price"], "score": p["score"]["final_score"],
                                        "matches": p["requirement_matches"]} for p in result["recommendations"]]}, ensure_ascii=False))
