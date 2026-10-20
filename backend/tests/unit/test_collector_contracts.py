from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.collector import (
    CollectorFailure, FetchStatus, FieldEvidence, OfferObservation, PriceRange,
    ProductObservation, SourceFetchResult, VariantIdentity,
)


def test_contract_round_trip_preserves_unknown_and_external_ids():
    observed = datetime(2026, 1, 2, tzinfo=timezone.utc)
    result = SourceFetchResult(status=FetchStatus.SUCCESS, source_url="https://shopee.vn/p-i.1.2",
        platform="shopee", observation=ProductObservation(name="Phone", offers=[OfferObservation(
            identity=VariantIdentity(platform="shopee", external_product_id="2", external_shop_id="1",
                external_sku_id="3", attributes={"storage": "256GB"}),
            listed_price=None, sale_price=0, shipping_fee=None, product_url="https://shopee.vn/p-i.1.2",
            observed_at=observed, evidence=[FieldEvidence(field="sale_price", value=0,
                source_url="https://shopee.vn/p-i.1.2", evidence_type="JSON_LD",
                observed_at=observed, verification_status="VERIFIED")])]))
    restored = SourceFetchResult.model_validate_json(result.model_dump_json())
    assert restored.observation.offers[0].listed_price is None
    assert restored.observation.offers[0].sale_price == 0
    assert restored.observation.offers[0].identity.external_sku_id == "3"


@pytest.mark.parametrize("factory", [
    lambda: OfferObservation(identity=VariantIdentity(), product_url="x", sale_price=-1),
    lambda: ProductObservation(name="x", product_rating=5.1),
    lambda: PriceRange(minimum=20, maximum=10),
    lambda: SourceFetchResult(status=FetchStatus.SUCCESS, source_url="x"),
    lambda: SourceFetchResult(status=FetchStatus.INVALID_URL, source_url="x"),
])
def test_contract_rejects_malformed_values(factory):
    with pytest.raises(ValidationError):
        factory()


def test_failed_result_has_structured_failure():
    item = SourceFetchResult(status=FetchStatus.ACCESS_RESTRICTED, source_url="https://lazada.vn/x",
        platform="lazada", failure=CollectorFailure(code=FetchStatus.ACCESS_RESTRICTED,
        message="blocked", http_status=403))
    assert item.failure.http_status == 403
