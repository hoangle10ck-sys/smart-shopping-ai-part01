"""Unit tests for Product/ProductOffer persistence."""

from datetime import datetime, timezone

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
from app.models.product_offer import (
    ProductOffer,
)
from app.models.price_observation import PriceObservation
from app.schemas.search import (
    RawProductCandidateData,
)
from app.services.normalization.normalization_service import (
    NormalizationService,
)


def make_db() -> Session:
    """Create an isolated in-memory database."""

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


def make_raw_candidate(
    *,
    url: str,
    price: str = "449.000đ",
    observed_at: datetime | None = datetime(2026, 1, 1, tzinfo=timezone.utc),
) -> RawProductCandidateData:
    """Build one raw candidate."""

    return RawProductCandidateData(
        name="SoundDemo H20 Wireless",
        brand="SoundDemo",
        model="H20",
        price_text=price,
        rating_text="4.6/5",
        review_count_text="310",
        availability="in_stock",
        product_url=url,
        source_domain=(
            "audio-demo.example"
        ),
        observed_at=observed_at,
        specifications={
            "microphone": "ENC",
            "battery": "40 hours",
        },
    )


def test_persist_creates_product_and_offer() -> None:
    db = make_db()

    try:
        service = (
            NormalizationService()
        )

        result = (
            service.persist_candidate(
                db=db,
                candidate=make_raw_candidate(
                    url=(
                        "https://shop-a.example/"
                        "sounddemo-h20"
                    )
                ),
                source_id=None,
            )
        )

        assert result is not None
        assert (
            result.created_product
            is True
        )
        assert (
            result.created_offer
            is True
        )

        product = db.get(
            Product,
            result.product_id,
        )

        offer = db.get(
            ProductOffer,
            result.offer_id,
        )

        assert product is not None
        assert offer is not None

        assert (
            product.normalized_name
            == "sounddemo h20 wireless"
        )

        assert product.rating == 4.6

        assert (
            product.review_count
            == 310
        )

        assert offer.price == 449000
        assert offer.currency == "VND"

    finally:
        db.close()


def test_same_product_multiple_sources_create_multiple_offers() -> None:
    db = make_db()

    try:
        service = (
            NormalizationService()
        )

        first = make_raw_candidate(
            url=(
                "https://shop-a.example/"
                "sounddemo-h20"
            ),
            price="449.000đ",
        )

        second = make_raw_candidate(
            url=(
                "https://shop-b.example/"
                "sounddemo-h20"
            ),
            price="439.000đ",
        )

        service.persist_candidate(
            db=db,
            candidate=first,
        )

        service.persist_candidate(
            db=db,
            candidate=second,
        )

        product_count = db.scalar(
            select(
                func.count(Product.id)
            )
        )

        offer_count = db.scalar(
            select(
                func.count(ProductOffer.id)
            )
        )

        assert product_count == 1
        assert offer_count == 2

    finally:
        db.close()


def test_same_offer_is_updated_not_duplicated() -> None:
    db = make_db()

    try:
        service = (
            NormalizationService()
        )

        url = (
            "https://shop-a.example/"
            "sounddemo-h20"
        )

        first = make_raw_candidate(
            url=url,
            price="449.000đ",
        )

        second = make_raw_candidate(
            url=url,
            price="429.000đ",
        )

        first_result = (
            service.persist_candidate(
                db=db,
                candidate=first,
            )
        )

        second_result = (
            service.persist_candidate(
                db=db,
                candidate=second,
            )
        )

        assert first_result is not None
        assert second_result is not None

        assert (
            first_result.product_id
            == second_result.product_id
        )

        assert (
            second_result.created_product
            is False
        )

        assert (
            second_result.created_offer
            is False
        )

        product_count = db.scalar(
            select(
                func.count(Product.id)
            )
        )

        offer_count = db.scalar(
            select(
                func.count(ProductOffer.id)
            )
        )

        assert product_count == 1
        assert offer_count == 1

        offer = db.scalar(
            select(ProductOffer)
        )

        assert offer is not None

        assert offer.price == 429000

    finally:
        db.close()


def test_candidate_without_trusted_timestamp_keeps_product_but_skips_offer_history() -> None:
    db = make_db()

    try:
        service = NormalizationService()
        for observed_at in (None, datetime(2026, 1, 2, 12, 0)):
            candidate_url = f"https://shop.example/phone-{observed_at}"
            result = service.persist_candidate(
                db=db,
                candidate=make_raw_candidate(
                    url=candidate_url,
                    observed_at=observed_at,
                ),
            )

            assert result is not None
            assert result.created_product is (observed_at is None)
            assert result.offer_id is None
            assert result.created_offer is False

        assert db.scalar(select(func.count(Product.id))) == 1
        assert db.scalar(select(func.count(ProductOffer.id))) == 0
        assert db.scalar(select(func.count(PriceObservation.id))) == 0
    finally:
        db.close()


def test_aware_non_utc_timestamp_is_normalized_to_utc_without_changing_instant() -> None:
    db = make_db()

    try:
        service = NormalizationService()
        observed_at = datetime.fromisoformat("2026-01-02T12:00:00+05:30")

        result = service.persist_candidate(
            db=db,
            candidate=make_raw_candidate(
                url="https://shop.example/phone-offset-time",
                observed_at=observed_at,
            ),
        )

        assert result is not None and result.offer_id is not None
        offer = db.get(ProductOffer, result.offer_id)
        assert offer is not None
        expected_checked_at = datetime(2026, 1, 2, 6, 30, tzinfo=timezone.utc)
        assert offer.last_checked_at is not None
        actual_checked_at = offer.last_checked_at.replace(tzinfo=timezone.utc)
        assert actual_checked_at == expected_checked_at
    finally:
        db.close()


def test_untrusted_candidate_does_not_change_existing_offer_timestamps_or_price() -> None:
    db = make_db()

    try:
        service = NormalizationService()
        url = "https://shop.example/phone-existing"
        initial = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        created = service.persist_candidate(
            db=db,
            candidate=make_raw_candidate(url=url, observed_at=initial),
        )
        assert created is not None and created.offer_id is not None
        offer = db.get(ProductOffer, created.offer_id)
        assert offer is not None
        original_timestamps = (
            offer.last_checked_at,
            offer.last_seen_at,
            offer.last_verified_at,
        )
        original_price = offer.price

        skipped = service.persist_candidate(
            db=db,
            candidate=make_raw_candidate(
                url=url,
                price="1.000đ",
                observed_at=datetime(2026, 1, 2, 10, 0),
            ),
        )

        assert skipped is not None
        assert skipped.product_id == created.product_id
        assert skipped.offer_id is None
        assert (
            offer.last_checked_at,
            offer.last_seen_at,
            offer.last_verified_at,
        ) == original_timestamps
        assert offer.price == original_price
        assert db.scalar(select(func.count(PriceObservation.id))) == 0
    finally:
        db.close()