"""Transactional, idempotent persistence for collector observations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crawl_run import CrawlRun
from app.models.price_observation import PriceObservation
from app.models.product_offer import ProductOffer
from app.models.product_variant import ProductVariant
from app.schemas.collector import OfferObservation


def variant_key(attributes: dict[str, str], condition: str | None) -> str:
    payload = {"attributes": {str(k).strip().lower(): str(v).strip().lower() for k, v in attributes.items()},
               "condition": (condition or "unknown").strip().lower()}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(slots=True)
class CollectorPersistenceResult:
    variant: ProductVariant
    offer: ProductOffer
    price_observation_created: bool
    offer_created: bool


def persist_offer_observation(
    db: Session, *, product_id: int, source_id: int | None, observation: OfferObservation,
    crawl_run: CrawlRun | None = None,
) -> CollectorPersistenceResult:
    """Upsert one exact variant/offer and append history only when values change."""

    key = variant_key(observation.identity.attributes, observation.identity.condition)
    variant = db.scalar(select(ProductVariant).where(
        ProductVariant.product_id == product_id, ProductVariant.identity_key == key,
    ))
    if variant is None:
        variant = ProductVariant(product_id=product_id, identity_key=key,
                                 attributes=dict(observation.identity.attributes),
                                 condition=observation.identity.condition)
        db.add(variant)
        db.flush()

    identity = observation.identity
    offer = None
    if identity.external_product_id and identity.external_shop_id and identity.external_sku_id:
        offer = db.scalar(select(ProductOffer).where(
            ProductOffer.platform == identity.platform,
            ProductOffer.external_product_id == identity.external_product_id,
            ProductOffer.external_shop_id == identity.external_shop_id,
            ProductOffer.external_sku_id == identity.external_sku_id,
        ))
    offer_created = offer is None
    if offer_created:
        offer = db.scalar(select(ProductOffer).where(
            ProductOffer.product_id == product_id,
            ProductOffer.variant_id == variant.id,
            ProductOffer.product_url == observation.product_url,
        ))

    current_price = observation.sale_price if observation.sale_price is not None else observation.listed_price
    now = observation.observed_at
    if offer is None:
        offer = ProductOffer(product_id=product_id, variant_id=variant.id, platform=identity.platform,
            external_product_id=identity.external_product_id, external_shop_id=identity.external_shop_id,
            external_sku_id=identity.external_sku_id, merchant=observation.merchant, price=current_price,
            listed_price=observation.listed_price, sale_price=observation.sale_price,
            listed_price_minor_units=observation.listed_price_minor_units,
            sale_price_minor_units=observation.sale_price_minor_units,
            currency_minor_unit=observation.currency_minor_unit,
            price_min=observation.price_range.minimum if observation.price_range else None,
            price_max=observation.price_range.maximum if observation.price_range else None,
            currency=observation.currency, shipping_fee=observation.shipping_fee, voucher=observation.voucher,
            warranty=observation.warranty,
            availability=observation.availability, source_id=source_id, product_url=observation.product_url,
            last_checked_at=now, last_seen_at=now, last_verified_at=now,
            freshness_status="FRESH", evidence_method="COLLECTOR")
        db.add(offer)
        db.flush()
    else:
        offer.variant_id = variant.id
        offer.merchant = observation.merchant or offer.merchant
        offer.price = current_price
        offer.listed_price, offer.sale_price = observation.listed_price, observation.sale_price
        offer.listed_price_minor_units = observation.listed_price_minor_units
        offer.sale_price_minor_units = observation.sale_price_minor_units
        offer.currency_minor_unit = observation.currency_minor_unit
        offer.price_min = observation.price_range.minimum if observation.price_range else None
        offer.price_max = observation.price_range.maximum if observation.price_range else None
        offer.shipping_fee, offer.voucher = observation.shipping_fee, observation.voucher
        offer.warranty = observation.warranty
        offer.availability, offer.source_id = observation.availability, source_id or offer.source_id
        offer.last_checked_at = offer.last_seen_at = offer.last_verified_at = now
        offer.freshness_status, offer.evidence_method = "FRESH", "COLLECTOR"

    state = {"listed_price": observation.listed_price, "sale_price": observation.sale_price,
             "listed_price_minor_units": observation.listed_price_minor_units,
             "sale_price_minor_units": observation.sale_price_minor_units,
             "currency_minor_unit": observation.currency_minor_unit,
             "price_range": observation.price_range.model_dump() if observation.price_range else None,
             "currency": observation.currency, "shipping_fee": observation.shipping_fee,
             "voucher": observation.voucher, "availability": observation.availability}
    fingerprint = hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    history = db.scalar(select(PriceObservation).where(
        PriceObservation.offer_id == offer.id, PriceObservation.fingerprint == fingerprint,
    ))
    created = history is None
    if created:
        db.add(PriceObservation(offer_id=offer.id, crawl_run_id=crawl_run.id if crawl_run else None,
            listed_price=observation.listed_price, sale_price=observation.sale_price,
            listed_price_minor_units=observation.listed_price_minor_units,
            sale_price_minor_units=observation.sale_price_minor_units,
            currency_minor_unit=observation.currency_minor_unit,
            price_min=observation.price_range.minimum if observation.price_range else None,
            price_max=observation.price_range.maximum if observation.price_range else None,
            currency=observation.currency, shipping_fee=observation.shipping_fee, voucher=observation.voucher,
            availability=observation.availability, source_id=source_id,
            observed_at=observation.observed_at, fingerprint=fingerprint))
    db.flush()
    return CollectorPersistenceResult(variant, offer, created, offer_created)
