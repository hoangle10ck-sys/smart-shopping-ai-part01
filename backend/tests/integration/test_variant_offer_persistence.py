from datetime import datetime, timezone
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import PriceObservation, Product, ProductOffer, ProductVariant, Source
from app.schemas.collector import OfferObservation, VariantIdentity
from app.services.collectors.persistence import persist_offer_observation


def test_same_variant_two_shops_two_offers_and_idempotent_history():
    with SessionLocal.begin() as db:
        product = Product(name="Phone X", brand="Demo", model="X", specifications={})
        source_a = Source(url="https://shopee.vn/x-i.1.2", domain="shopee.vn")
        source_b = Source(url="https://www.lazada.vn/products/x-i2.html", domain="lazada.vn")
        db.add_all([product, source_a, source_b]); db.flush()
        common = {"storage": "256GB", "color": "black"}
        a = OfferObservation(identity=VariantIdentity(platform="shopee", external_product_id="2",
            external_shop_id="1", external_sku_id="9", attributes=common), merchant="A",
            sale_price=2_000_000, product_url=source_a.url, observed_at=datetime.now(timezone.utc))
        b = OfferObservation(identity=VariantIdentity(platform="lazada", external_product_id="2",
            external_shop_id="8", external_sku_id="9", attributes=common), merchant="B",
            sale_price=2_100_000, product_url=source_b.url, observed_at=datetime.now(timezone.utc))
        first = persist_offer_observation(db, product_id=product.id, source_id=source_a.id, observation=a)
        persist_offer_observation(db, product_id=product.id, source_id=source_a.id, observation=a)
        second = persist_offer_observation(db, product_id=product.id, source_id=source_b.id, observation=b)
        assert first.variant.id == second.variant.id
        assert db.scalar(select(func.count(ProductVariant.id))) == 1
        assert db.scalar(select(func.count(ProductOffer.id))) == 2
        assert db.scalar(select(func.count(PriceObservation.id))) == 2


def test_different_sku_attributes_never_share_variant():
    with SessionLocal.begin() as db:
        product = Product(name="Phone X", specifications={}); db.add(product); db.flush()
        for storage in ("128GB", "256GB"):
            observation = OfferObservation(identity=VariantIdentity(platform="shopee",
                attributes={"storage": storage}), sale_price=1_000_000,
                product_url=f"https://shopee.vn/{storage}")
            persist_offer_observation(db, product_id=product.id, source_id=None, observation=observation)
        assert db.scalar(select(func.count(ProductVariant.id))) == 2


def test_collector_transaction_rollback_leaves_no_partial_rows():
    db = SessionLocal()
    try:
        product = Product(name="Rollback Phone", specifications={}); db.add(product); db.flush()
        observation = OfferObservation(identity=VariantIdentity(platform="shopee", attributes={"storage": "64GB"}),
            sale_price=500_000, product_url="https://shopee.vn/rollback")
        persist_offer_observation(db, product_id=product.id, source_id=None, observation=observation)
        db.rollback()
        assert db.scalar(select(func.count(Product.id)).where(Product.name == "Rollback Phone")) == 0
        assert db.scalar(select(func.count(ProductVariant.id))) == 0
        assert db.scalar(select(func.count(ProductOffer.id))) == 0
    finally:
        db.close()
