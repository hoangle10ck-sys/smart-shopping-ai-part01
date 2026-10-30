"""Verified local catalog rows for unified-search integration tests."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_offer import ProductOffer
from app.models.source import Source


def seed_headphones(db: Session, *, count: int = 3) -> list[int]:
    """Add current, evidence-backed test offers without invoking Demo or Live sources."""
    source = Source(
        url="https://qa-catalog.example/products",
        domain="qa-catalog.example",
        title="Isolated QA catalog",
    )
    db.add(source)
    db.flush()
    product_ids = []
    for index in range(1, count + 1):
        product = Product(
            name=f"QA Headphones H{index}",
            category="tai nghe",
            brand="QA Audio",
            model=f"H{index}",
            normalized_name=f"qa headphones h{index}",
            image_url=f"https://qa-catalog.example/images/headphones-h{index}.jpg",
            rating=4.5,
            review_count=100 + index,
            specifications={"microphone": "good", "battery": "long-lasting"},
        )
        db.add(product)
        db.flush()
        db.add(ProductOffer(
            product_id=product.id,
            source_id=source.id,
            merchant="QA Audio Shop",
            price=320_000 + index * 50_000,
            currency="VND",
            availability="in_stock",
            product_url=f"https://qa-catalog.example/products/headphones-h{index}",
            last_checked_at=datetime.now(timezone.utc),
        ))
        product_ids.append(product.id)
    db.commit()
    return product_ids
