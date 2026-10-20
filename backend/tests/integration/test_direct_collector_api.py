from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.main import app
from app.models import Product, ProductOffer, ProductVariant
from app.schemas.collector import (
    FetchStatus,
    FieldEvidence,
    OfferObservation,
    ProductObservation,
    SourceFetchResult,
    VariantIdentity,
)
from app.services.collectors.service import CollectorService


client = TestClient(app)


async def fake_fetch(self, url):
    return SourceFetchResult(status=FetchStatus.SUCCESS, source_url=url, platform="shopee",
        observation=ProductObservation(name="Demo Laptop 16GB", brand="Demo", model="L16", category="laptop",
            specifications={"ram":"16GB"}, offers=[OfferObservation(
                identity=VariantIdentity(platform="shopee", external_product_id="2", external_shop_id="1",
                    external_sku_id="16", attributes={"ram":"16GB", "storage":"512GB"}),
                merchant="Official", sale_price=12_000_000, availability="in_stock", product_url=url)]))


def test_direct_url_path_does_not_require_tavily_and_is_idempotent(monkeypatch):
    monkeypatch.setattr(CollectorService, "fetch", fake_fetch)
    analyzed = client.post("/api/requirements/analyze", json={
        "raw_query":"Laptop lập trình RAM 16 GB, ngân sách dưới 20 triệu"
    })
    session_id = analyzed.json()["session_id"]
    payload = {"session_id":session_id, "direct_urls":["https://shopee.vn/demo-i.1.2"],
               "source_platforms":["shopee"], "refresh":True}
    first = client.post("/api/search", json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["recommendations"][0]["variant_id"] is not None
    second = client.post("/api/search", json=payload)
    assert second.status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(func.count(ProductVariant.id))) == 1
        assert db.scalar(select(func.count(ProductOffer.id))) == 1


def test_direct_url_platform_choice_is_enforced(monkeypatch):
    monkeypatch.setattr(CollectorService, "fetch", fake_fetch)
    analyzed = client.post("/api/requirements/analyze", json={
        "raw_query":"Laptop lập trình RAM 16 GB, ngân sách dưới 20 triệu"
    })
    response = client.post("/api/search", json={"session_id": analyzed.json()["session_id"],
        "direct_urls":["https://shopee.vn/demo-i.1.2"], "source_platforms":["lazada"]})
    # Demo search remains available, while the direct source is explicitly warned and excluded.
    assert response.status_code == 200
    assert any("không nằm trong lựa chọn" in warning for warning in response.json()["warnings"])


def test_registered_public_api_observation_reaches_recommendation_pipeline(monkeypatch):
    async def fake_api_fetch(self, url):
        return SourceFetchResult(
            status=FetchStatus.SUCCESS,
            source_url=url,
            source_domain="shop.example",
            platform="sample-store",
            content_type="application/json",
            observation=ProductObservation(
                name="Laptop Pipeline Test 16GB",
                brand="Example",
                category="laptop",
                evidence=[
                    FieldEvidence(
                        field="name",
                        value="Laptop Pipeline Test 16GB",
                        source_url="https://shop.example/wp-json/wc/store/v1/products",
                        evidence_type="PUBLIC_API",
                        verification_status="VERIFIED",
                    )
                ],
                offers=[
                    OfferObservation(
                        identity=VariantIdentity(
                            platform="sample-store",
                            external_product_id="pipeline-test-1",
                            external_sku_id="PIPELINE-TEST-1",
                        ),
                        merchant="shop.example",
                        sale_price=18_900_000,
                        sale_price_minor_units=18_900_000,
                        currency_minor_unit=0,
                        currency="VND",
                        availability="in_stock",
                        product_url=url,
                        evidence=[
                            FieldEvidence(
                                field="price",
                                value={
                                    "minor_units": 18_900_000,
                                    "currency": "VND",
                                    "currency_minor_unit": 0,
                                },
                                source_url="https://shop.example/wp-json/wc/store/v1/products",
                                evidence_type="PUBLIC_API",
                                verification_status="VERIFIED",
                            ),
                            FieldEvidence(
                                field="sku",
                                value="PIPELINE-TEST-1",
                                source_url="https://shop.example/wp-json/wc/store/v1/products",
                                evidence_type="PUBLIC_API",
                                verification_status="VERIFIED",
                            ),
                        ],
                    )
                ],
            ),
        )

    monkeypatch.setattr(CollectorService, "fetch", fake_api_fetch)
    analyzed = client.post("/api/requirements/analyze", json={
        "raw_query": "Laptop lập trình RAM 16 GB, ngân sách dưới 20 triệu"
    })
    session_id = analyzed.json()["session_id"]
    response = client.post(
        "/api/search",
        json={
            "session_id": session_id,
            "direct_urls": ["https://shop.example/product/pipeline-test"],
            "refresh": True,
        },
    )

    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        product = db.scalar(
            select(Product).where(Product.name == "Laptop Pipeline Test 16GB")
        )
        assert product is not None
        offer = db.scalar(
            select(ProductOffer).where(
                ProductOffer.product_id == product.id,
                ProductOffer.platform == "sample-store",
            )
        )
        assert offer is not None
        assert offer.price == 18_900_000
        assert offer.sale_price_minor_units == 18_900_000
