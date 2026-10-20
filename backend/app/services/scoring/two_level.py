"""Versioned product-suitability and offer-quality scoring."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.product_offer import ProductOffer
from app.schemas.ranking import ScoringCandidate
from app.schemas.requirement import RequirementData
from app.services.filter.hard_filter import is_unavailable
from app.services.scoring.scoring_engine import ScoringEngine


SCORE_VERSION = "two-level-v1"


class ScoreWeights(BaseModel):
    values: dict[str, float]

    @model_validator(mode="after")
    def valid_total(self) -> "ScoreWeights":
        if any(value < 0 for value in self.values.values()):
            raise ValueError("weights must be non-negative")
        if abs(sum(self.values.values()) - 1.0) > 1e-9:
            raise ValueError("weights must sum to 1")
        return self


class LevelScore(BaseModel):
    version: str = SCORE_VERSION
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    insufficient_evidence: bool
    weights: dict[str, float]
    breakdown: dict[str, float | None]


PRODUCT_WEIGHTS = ScoreWeights(values={"requirements": .50, "purpose": .30, "budget": .20})
OFFER_WEIGHTS = ScoreWeights(values={"price": .30, "availability": .15, "freshness": .15,
                                    "source_reliability": .15, "seller_trust": .10,
                                    "shipping": .075, "warranty": .075})


def product_suitability(candidate: ScoringCandidate, requirement: RequirementData) -> LevelScore:
    engine = ScoringEngine()
    parts = {"requirements": engine.requirement_score(candidate, requirement),
             "purpose": engine.purpose_score(candidate, requirement),
             "budget": engine.budget_score(candidate, requirement)}
    score = sum(parts[key] * weight for key, weight in PRODUCT_WEIGHTS.values.items())
    known = sum(value is not None for value in candidate.specifications.values())
    confidence = min(100.0, 40.0 + known * 10.0)
    return LevelScore(score=round(score, 2), confidence=confidence,
        insufficient_evidence=known == 0 and bool(requirement.requirements),
        weights=PRODUCT_WEIGHTS.values, breakdown=parts)


def offer_quality(offer: ProductOffer, *, budget_max: int | None, source_reliability: float = 50.0,
                  seller_rating: float | None = None, now: datetime | None = None,
                  preference: str = "balanced") -> LevelScore:
    now = now or datetime.now(timezone.utc)
    price = offer.sale_price if offer.sale_price is not None else offer.price
    price_score = None if price is None else (100.0 if not budget_max else max(0.0, min(100.0, 100 * budget_max / max(price, budget_max))))
    availability = None if not offer.availability else (0.0 if is_unavailable(offer.availability) else 100.0)
    checked = offer.last_verified_at or offer.last_checked_at
    if checked and checked.tzinfo is None:
        checked = checked.replace(tzinfo=timezone.utc)
    freshness = None if checked is None else max(0.0, 100.0 - (now - checked).total_seconds() / 86400 * 5)
    trust = None if seller_rating is None else seller_rating / 5 * 100
    shipping = None
    if offer.shipping_fee is not None:
        shipping = 100.0 if offer.shipping_fee == 0 else (
            max(0.0, 100.0 - offer.shipping_fee / budget_max * 100) if budget_max else 50.0
        )
    warranty = 100.0 if offer.warranty and offer.warranty.strip() else None
    parts = {"price": price_score, "availability": availability, "freshness": freshness,
             "source_reliability": max(0.0, min(100.0, source_reliability)), "seller_trust": trust,
             "shipping": shipping, "warranty": warranty}
    weights = dict(OFFER_WEIGHTS.values)
    if preference in {"price_first", "price_asc"}:
        weights = {"price": .50, "availability": .10, "freshness": .10, "source_reliability": .10,
                   "seller_trust": .05, "shipping": .10, "warranty": .05}
    elif preference in {"trusted_seller", "rating"}:
        weights = {"price": .15, "availability": .15, "freshness": .15, "source_reliability": .15,
                   "seller_trust": .25, "shipping": .075, "warranty": .075}
    available_weight = sum(weights[k] for k, value in parts.items() if value is not None)
    # Missing fields do not receive a neutral/good score; confidence captures missingness.
    score = sum((value or 0) * weights[k] for k, value in parts.items())
    confidence = available_weight * 100
    return LevelScore(score=round(score, 2), confidence=round(confidence, 2),
        insufficient_evidence=available_weight < .6, weights=weights, breakdown=parts)


def offer_sort_key(score: LevelScore, offer: ProductOffer) -> tuple:
    return (-score.score, -score.confidence, offer.price if offer.price is not None else 10**18, offer.id or 0)
