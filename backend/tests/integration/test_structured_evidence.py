"""Field provenance and matches remain part of the immutable session result."""

from fastapi.testclient import TestClient
import pytest
import re
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.raw_product_candidate import RawProductCandidate
from app.models.recommendation_snapshot import RecommendationSnapshot
from app.services.recommendation.recommendation_service import RecommendationService
from app.services.search.base import SearchResult
from app.services.search.multi_provider import MultiSearchProvider
from app.services.search.unified.external_sources import LiveProductSource
from app.services.extraction.product_image_resolver import ProductImageResolver
from tests.fixtures.sales_pages import sales_page


def patch_live_provider(monkeypatch, provider):
    observations = {}

    class Provider:
        async def search(self, query, max_results):
            results = await provider(self, query, max_results)
            for result in results:
                observations[result.url] = result
            return results

    async def fetch_page(self, url):
        result = observations[url]
        content = result.content
        name = re.search(r"PRODUCT:\s*(.*?)\s*\|", content)
        price = re.search(r"PRICE:\s*(\d+)", content)
        rating = re.search(r"RATING:\s*([\d.]+)", content)
        reviews = re.search(r"REVIEWS:\s*(\d+)", content)
        specifications = re.search(r"SPECS:\s*(.*)$", content)
        props = []
        if specifications:
            for item in specifications.group(1).split(";"):
                key, separator, value = item.partition("=")
                if separator:
                    props.append({"name": key.strip(), "value": value.strip()})
        extra = {"additionalProperty": props}
        if rating:
            extra["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": rating.group(1),
                                        "reviewCount": reviews.group(1) if reviews else None}
        return url, sales_page(name=name.group(1) if name else result.title,
                               price=int(price.group(1)) if price else 1,
                               image="https://evidence.example/images/laptop-x1.jpg", **extra)

    monkeypatch.setattr(MultiSearchProvider, "__init__", lambda self, **kwargs: setattr(self, "providers", [Provider()]))
    monkeypatch.setattr(LiveProductSource, "is_available", lambda self, db: True)
    monkeypatch.setattr(ProductImageResolver, "_fetch_html", fetch_page)


def search(client):
    response = client.post("/api/requirements/analyze", json={"raw_query": "Laptop 25 triệu học lập trình RAM 16GB"})
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    response = client.post("/api/search", json={"session_id": session_id})
    assert response.status_code == 200
    assert response.json()["recommendations"], [(row.get("TITLE"), row.get("SOURCE_TYPE"), row.get("VERIFICATION_LEVEL"), row.get("REJECT_REASON"), row.get("PRODUCT_PAGE_VALID")) for diagnostic in response.json()["retrieval_diagnostics"] for row in diagnostic.get("source_audit", [])]
    return session_id, response.json()["recommendations"][0]


def test_fields_reference_observed_values_and_survive_catalog_changes(monkeypatch):
    state = {"price": 15000000, "ram": "16GB", "rating": "4.5", "reviews": 120}

    async def provider(self, query, max_results):
        return [SearchResult(title="Laptop Evidence X1", url="https://evidence.example/products/laptop", content=(
            f"PRODUCT: Laptop Evidence X1 | PRICE: {state['price']} VND | RATING: {state['rating']}/5 | "
            f"REVIEWS: {state['reviews']} | SPECS: ram={state['ram']}; storage=512GB"
        ))]

    patch_live_provider(monkeypatch, provider)
    with TestClient(app) as client:
        session_a, original = search(client)
        fields = {field["field"]: field for field in original["evidence"]["fields"]}
        assert {key: field["value"] for key, field in fields.items()} == {
            "price": 15000000, "rating": 4.5, "review_count": 120,
            "specifications.ram": "16GB", "specifications.storage": "512GB",
        }
        for field in fields.values():
            assert field["url"] == "https://evidence.example/products/laptop"
            assert field["domain"] == "evidence.example"
            assert field["retrieved_at"]
        assert original["requirement_matches"][0]["status"] == "matched"
        state.update(price=20000000, ram="8GB", rating="3.5", reviews=140)
        _, newer = search(client)
        assert newer["price"] == 20000000
        # Existing dedup semantics retain the original RAM specification. The
        # new 8GB observation cannot be cited as evidence for that retained 16GB.
        assert newer["specifications"]["ram"] == "16GB"
        assert newer["requirement_matches"][0]["product_value"] == "16GB"
        assert newer["requirement_matches"][0]["status"] == "matched"
        newer_fields = {field["field"]: field["value"] for field in newer["evidence"]["fields"]}
        assert newer_fields == {"price": 20000000, "rating": 3.5, "review_count": 140,
                                "specifications.storage": "512GB"}
        loaded = client.get(f"/api/search/{session_a}").json()["recommendations"][0]
        assert loaded == original


@pytest.mark.parametrize("raw_change", [
    {"price_text": "9000000 VND"},
    {"name": "Different laptop"},
    {"product_url": "https://unrelated.example/product"},
])
def test_unknown_evidence_is_not_attributed_to_another_source(monkeypatch, raw_change):
    async def provider(self, query, max_results):
        return [SearchResult(title="Laptop Sparse X1", url="https://sparse.example/products/laptop",
                             content="PRODUCT: Laptop Sparse X1 | PRICE: 15000000 VND")]

    patch_live_provider(monkeypatch, provider)
    with TestClient(app) as client:
        session_id, original = search(client)
        assert original["requirement_matches"][0]["status"] == "unknown"
        assert original["requirement_matches"][0]["product_value"] is None
        assert [field["field"] for field in original["evidence"]["fields"]] == ["price"]
        with SessionLocal() as db:
            # A staging observation for a different product or conflicting price
            # must not substantiate the consolidated candidate's price.
            for raw in db.scalars(select(RawProductCandidate).where(RawProductCandidate.session_id == session_id)):
                raw.payload = {**raw.payload, **raw_change}
            db.flush()
            recomputed = RecommendationService().run(db=db, session_id=session_id)
            assert not recomputed.recommendations or all(
                item.evidence.fields == [] for item in recomputed.recommendations
            )
            db.rollback()


def test_actual_8gb_product_is_unmet_in_api_and_snapshot(monkeypatch):
    async def provider(self, query, max_results):
        return [SearchResult(title="Laptop Small X1", url="https://small.example/products/laptop",
                             content="PRODUCT: Laptop Small X1 | PRICE: 15000000 VND | SPECS: ram=8GB")]
    patch_live_provider(monkeypatch, provider)
    with TestClient(app) as client:
        session_id, original = search(client)
        match, = original["requirement_matches"]
        assert match["requested_value"] == "16GB"
        assert match["product_value"] == "8GB"
        assert match["status"] == "unmet"
        assert original["score"]["requirement_score"] == 0
        assert client.get(f"/api/search/{session_id}").json()["recommendations"][0] == original


def test_product_fields_are_not_assigned_to_the_cheapest_offer_source(monkeypatch):
    async def provider(self, query, max_results):
        return [
            SearchResult(title="Cheap offer", url="https://cheap.example/products/laptop",
                         content="PRODUCT: Laptop Multi X1 | PRICE: 15000000 VND"),
            SearchResult(title="Detailed offer", url="https://details.example/products/laptop",
                         content="PRODUCT: Laptop Multi X1 | PRICE: 16000000 VND | RATING: 4.7/5 | REVIEWS: 200 | SPECS: ram=16GB"),
        ]
    patch_live_provider(monkeypatch, provider)
    with TestClient(app) as client:
        _, item = search(client)
        fields = {field["field"]: field for field in item["evidence"]["fields"]}
        assert fields["price"]["value"] == item["price"]
        assert fields["price"]["domain"] in {"cheap.example", "details.example"}
        assert fields["price"]["domain"] in item["product_url"]
        for name in ("rating", "review_count", "specifications.ram"):
            assert fields[name]["domain"] == "details.example"
            assert fields[name]["url"] == "https://details.example/products/laptop"


def test_missing_current_observations_do_not_reuse_another_sessions_evidence(monkeypatch):
    state = {"details": " | RATING: 4.7/5 | REVIEWS: 200 | SPECS: ram=16GB"}
    async def provider(self, query, max_results):
        return [SearchResult(title="Laptop Retained X1", url="https://retained.example/products/laptop",
                             content=f"PRODUCT: Laptop Retained X1 | PRICE: 15000000 VND{state['details']}")]
    patch_live_provider(monkeypatch, provider)
    with TestClient(app) as client:
        old_session, old = search(client)
        assert len(old["evidence"]["fields"]) == 4
        state["details"] = ""
        _, new = search(client)
        assert new["rating"] == 4.7
        assert new["specifications"]["ram"] == "16GB"
        assert [field["field"] for field in new["evidence"]["fields"]] == ["price"]
        assert client.get(f"/api/search/{old_session}").json()["recommendations"][0] == old


def test_old_snapshot_defaults_empty_without_backfill(monkeypatch):
    async def provider(self, query, max_results):
        return [SearchResult(title="Laptop Old Snapshot X1", url="https://old.example/products/laptop",
                             content="PRODUCT: Laptop Old Snapshot X1 | PRICE: 15000000 VND | SPECS: ram=16GB")]
    patch_live_provider(monkeypatch, provider)
    with TestClient(app) as client:
        session_id, _ = search(client)
        with SessionLocal() as db:
            snapshot = db.get(RecommendationSnapshot, session_id)
            payload = dict(snapshot.payload)
            for item in payload["result"]["recommendations"]:
                item.pop("requirement_matches")
                item["evidence"].pop("fields")
            # Explicitly flag the JSON change, as this is a simulated old record.
            from sqlalchemy.orm.attributes import flag_modified
            snapshot.payload = payload
            flag_modified(snapshot, "payload")
            db.commit()
        loaded = client.get(f"/api/search/{session_id}").json()["recommendations"][0]
        assert loaded["requirement_matches"] == []
        assert loaded["evidence"]["fields"] == []
        with SessionLocal() as db:
            saved = db.get(RecommendationSnapshot, session_id).payload["result"]["recommendations"][0]
            assert "requirement_matches" not in saved
            assert "fields" not in saved["evidence"]
