"""Unit tests for canonical-product deduplication."""

import app.models  # noqa: F401

from sqlalchemy import (
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from app.core.database import Base
from app.models.product import Product
from app.schemas.normalization import (
    NormalizedProductCandidate,
)
from app.services.dedup.product_deduplicator import (
    ProductDeduplicator,
)


def make_db() -> Session:
    """Create an isolated in-memory test database."""

    engine = create_engine(
        "sqlite:///:memory:",
    )

    Base.metadata.create_all(
        bind=engine
    )

    factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    return factory()


def make_candidate(
    *,
    name: str,
    brand: str | None,
    model: str | None,
    normalized_name: str,
    normalized_brand: str | None,
    normalized_model: str | None,
) -> NormalizedProductCandidate:
    """Build a normalized test candidate."""

    return NormalizedProductCandidate(
        name=name,
        normalized_name=(
            normalized_name
        ),
        brand=brand,
        normalized_brand=(
            normalized_brand
        ),
        model=model,
        normalized_model=(
            normalized_model
        ),
        price=500000,
        rating=4.5,
        review_count=100,
    )


def test_same_brand_and_model_are_deduplicated() -> None:
    db = make_db()

    try:
        service = (
            ProductDeduplicator()
        )

        first = make_candidate(
            name="SoundDemo H20 Wireless",
            brand="SoundDemo",
            model="H20",
            normalized_name=(
                "sounddemo h20 wireless"
            ),
            normalized_brand="sounddemo",
            normalized_model="h20",
        )

        second = make_candidate(
            name="SoundDemo H20 Black",
            brand="SoundDemo",
            model="H20",
            normalized_name=(
                "sounddemo h20 black"
            ),
            normalized_brand="sounddemo",
            normalized_model="h20",
        )

        product_1, created_1 = (
            service.get_or_create(
                db,
                first,
            )
        )

        product_2, created_2 = (
            service.get_or_create(
                db,
                second,
            )
        )

        assert created_1 is True
        assert created_2 is False

        assert (
            product_1.id
            == product_2.id
        )

        count = db.scalar(
            select(
                func.count(Product.id)
            )
        )

        assert count == 1

    finally:
        db.close()


def test_different_models_are_not_merged() -> None:
    db = make_db()

    try:
        service = (
            ProductDeduplicator()
        )

        first = make_candidate(
            name="SoundDemo H20",
            brand="SoundDemo",
            model="H20",
            normalized_name=(
                "sounddemo h20"
            ),
            normalized_brand="sounddemo",
            normalized_model="h20",
        )

        second = make_candidate(
            name="SoundDemo H30",
            brand="SoundDemo",
            model="H30",
            normalized_name=(
                "sounddemo h30"
            ),
            normalized_brand="sounddemo",
            normalized_model="h30",
        )

        service.get_or_create(
            db,
            first,
        )

        service.get_or_create(
            db,
            second,
        )

        count = db.scalar(
            select(
                func.count(Product.id)
            )
        )

        assert count == 2

    finally:
        db.close()


def test_missing_model_falls_back_to_name() -> None:
    db = make_db()

    try:
        service = (
            ProductDeduplicator()
        )

        first = make_candidate(
            name="Demo Headphone Pro",
            brand=None,
            model=None,
            normalized_name=(
                "demo headphone pro"
            ),
            normalized_brand=None,
            normalized_model=None,
        )

        second = make_candidate(
            name="Demo Headphone Pro",
            brand=None,
            model=None,
            normalized_name=(
                "demo headphone pro"
            ),
            normalized_brand=None,
            normalized_model=None,
        )

        product_1, _ = (
            service.get_or_create(
                db,
                first,
            )
        )

        product_2, created = (
            service.get_or_create(
                db,
                second,
            )
        )

        assert created is False

        assert (
            product_1.id
            == product_2.id
        )

    finally:
        db.close()


def test_same_model_different_brand_not_merged() -> None:
    db = make_db()

    try:
        service = (
            ProductDeduplicator()
        )

        first = make_candidate(
            name="Brand A M5",
            brand="Brand A",
            model="M5",
            normalized_name="brand a m5",
            normalized_brand="brand a",
            normalized_model="m5",
        )

        second = make_candidate(
            name="Brand B M5",
            brand="Brand B",
            model="M5",
            normalized_name="brand b m5",
            normalized_brand="brand b",
            normalized_model="m5",
        )

        service.get_or_create(
            db,
            first,
        )

        service.get_or_create(
            db,
            second,
        )

        count = db.scalar(
            select(
                func.count(Product.id)
            )
        )

        assert count == 2

    finally:
        db.close()