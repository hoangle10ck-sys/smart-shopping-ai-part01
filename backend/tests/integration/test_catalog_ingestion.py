from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import Product, ProductOffer
from app.schemas.collector import (
    CollectorSearchResult,
    FetchStatus,
    FieldEvidence,
    OfferObservation,
    ProductObservation,
    SourceFetchResult,
    VariantIdentity,
)
from app.services.collectors.catalog_ingestion import CatalogIngestionService


class FakeCollector:
    async def search_registered_sources(self, query):
        category = "điện thoại" if "điện thoại" in query else "tai nghe"
        product = SourceFetchResult(
            status=FetchStatus.SUCCESS,
            source_url=f"https://shop.example/product/{category}",
            source_domain="shop.example",
            platform="approved-shop",
            observation=ProductObservation(
                name=f"Sản phẩm {category} Demo",
                category=category,
                evidence=[FieldEvidence(field="name", value=category, evidence_type="PUBLIC_API")],
                offers=[
                    OfferObservation(
                        identity=VariantIdentity(
                            platform="approved-shop",
                            external_product_id=category,
                            external_shop_id="shop-1",
                            external_sku_id=f"sku-{category}",
                        ),
                        sale_price=2_000_000,
                        sale_price_minor_units=2_000_000,
                        currency_minor_unit=0,
                        currency="VND",
                        product_url=f"https://shop.example/product/{category}",
                    )
                ],
            ),
        )
        return [CollectorSearchResult(source_id="approved-shop", query=query, status=FetchStatus.SUCCESS, products=[product])]

    async def fetch(self, url):
        raise AssertionError("No direct URL expected")


async def test_catalog_ingestion_is_idempotent_and_uses_main_catalog():
    with SessionLocal() as db:
        service = CatalogIngestionService(collector=FakeCollector())
        first = await service.ingest(db, queries=["điện thoại", "tai nghe"])
        second = await service.ingest(db, queries=["điện thoại", "tai nghe"])

        assert first.persisted == 2
        assert first.products_created == 2
        assert second.products_created == 0
        assert first.offers_created == 2
        assert second.offers_created == 0
        assert db.scalar(select(func.count(Product.id))) == 2
        assert db.scalar(select(func.count(ProductOffer.id))) == 2
