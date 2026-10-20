from datetime import datetime, timedelta, timezone
import pytest

from app.models import ProductOffer
from app.schemas.ranking import ScoringCandidate
from app.schemas.requirement import RequirementData, RequirementItem
from app.services.scoring.two_level import ScoreWeights, offer_quality, product_suitability


def requirement():
    return RequirementData(category="laptop", budget_max=20_000_000, purpose=["học lập trình"],
        requirements=[RequirementItem(name="RAM", value="16GB", priority=5)])


def test_product_score_is_shop_independent_while_offer_score_differs():
    candidate = ScoringCandidate(product_id=1, name="Laptop coding", category="laptop", price=15_000_000,
        specifications={"ram":"16GB", "purpose":"học lập trình"})
    assert product_suitability(candidate, requirement()) == product_suitability(candidate, requirement())
    now = datetime.now(timezone.utc)
    fresh = ProductOffer(product_id=1, price=15_000_000, availability="in_stock", last_checked_at=now,
                         last_verified_at=now)
    stale = ProductOffer(product_id=1, price=15_000_000, availability="in_stock", last_checked_at=now - timedelta(days=30),
                         last_verified_at=now - timedelta(days=30))
    assert offer_quality(fresh, budget_max=20_000_000, now=now).score > offer_quality(stale, budget_max=20_000_000, now=now).score


def test_missing_seller_data_does_not_receive_points_and_weights_validate():
    offer = ProductOffer(product_id=1, price=None, availability=None)
    score = offer_quality(offer, budget_max=1_000_000)
    assert score.breakdown["seller_trust"] is None
    assert score.breakdown["shipping"] is None
    assert score.breakdown["warranty"] is None
    assert score.insufficient_evidence
    with pytest.raises(ValueError):
        ScoreWeights(values={"a": .8, "b": .3})


def test_shipping_and_warranty_only_score_when_evidenced():
    offer = ProductOffer(product_id=1, price=900_000, availability="in_stock",
                         shipping_fee=0, warranty="12 months")
    score = offer_quality(offer, budget_max=1_000_000)
    assert score.breakdown["shipping"] == 100
    assert score.breakdown["warranty"] == 100
