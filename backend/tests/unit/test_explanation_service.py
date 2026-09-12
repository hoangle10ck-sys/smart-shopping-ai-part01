"""Unit tests for grounded explanation generation."""

import pytest

from app.core.config import get_settings
from app.schemas.evidence import (
    EvidenceBreakdown,
    EvidenceReport,
    RecommendationExplanation,
)
from app.schemas.ranking import (
    ScoreBreakdown,
    ScoringCandidate,
)
from app.schemas.requirement import (
    RequirementData,
)
from app.services.llm.explanation_service import (
    ExplanationService,
)


def make_evidence(
    confidence: float = 75,
) -> EvidenceReport:
    return EvidenceReport(
        confidence=confidence,
        breakdown=EvidenceBreakdown(
            source_reliability=50,
            product_completeness=100,
            offer_completeness=100,
            consistency=60,
            corroboration=40,
        ),
        source_count=1,
        offer_count=1,
        supporting_evidence=[
            "Giá đã xác minh: 449000 VND."
        ],
        warnings=[
            (
                "Sản phẩm mới được xác minh "
                "từ một nguồn."
            )
        ],
    )


def make_score() -> ScoreBreakdown:
    return ScoreBreakdown(
        budget_score=96,
        requirement_score=100,
        purpose_score=100,
        rating_score=92,
        review_score=80,
        source_score=50,
        final_score=92.2,
    )


def make_candidate() -> ScoringCandidate:
    return ScoringCandidate(
        product_id=1,
        name="SoundDemo H20 Wireless",
        category="tai nghe",
        brand="SoundDemo",
        model="H20",
        price=449000,
        currency="VND",
        rating=4.6,
        review_count=310,
        availability="in_stock",
        source_reliability=50,
        specifications={
            "microphone": "ENC",
            "battery": "40 hours",
        },
    )


def make_requirement() -> RequirementData:
    return RequirementData(
        category="tai nghe",
        budget_max=500000,
        currency="VND",
        purpose=[
            "học online"
        ],
        brands=[],
        requirements=[],
        excluded_requirements=[],
        sort_preference="best_match",
        confidence=0.95,
    )


def test_demo_explanation_contains_product_name() -> None:
    explanation = (
        ExplanationService(
            use_llm=False
        )
        .explain(
            candidate=make_candidate(),
            requirement=make_requirement(),
            score=make_score(),
            evidence=make_evidence(),
        )
    )

    assert (
        "SoundDemo H20 Wireless"
        in explanation.summary
    )

    assert (
        explanation.generation_mode
        == "demo"
    )


def test_low_confidence_creates_tradeoff() -> None:
    explanation = (
        ExplanationService(
            use_llm=False
        )
        .explain(
            candidate=make_candidate(),
            requirement=make_requirement(),
            score=make_score(),
            evidence=make_evidence(
                confidence=60
            ),
        )
    )

    assert any(
        "tin cậy" in item
        for item
        in explanation.tradeoffs
    )


@pytest.mark.parametrize("mode", ["demo", "openai", "gemini", "fallback"])
def test_generation_modes_roundtrip(mode):
    explanation = RecommendationExplanation(summary="Grounded explanation", generation_mode=mode)
    assert RecommendationExplanation.model_validate_json(explanation.model_dump_json()).generation_mode == mode


@pytest.mark.parametrize("use_llm", [None, True])
def test_demo_never_calls_provider_even_with_explicit_hint(monkeypatch, use_llm):
    calls = []
    monkeypatch.setattr(ExplanationService, "_generate_with_provider", lambda *a, **kw: calls.append(kw))
    result = ExplanationService(use_llm=use_llm).explain(
        candidate=make_candidate(), requirement=make_requirement(), score=make_score(), evidence=make_evidence(),
    )
    assert result.generation_mode == "demo"
    assert calls == []


def test_live_uses_configured_secondary_provider(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_fallback_provider", "gemini")
    calls = []

    def generate(self, *, provider, **kwargs):
        calls.append(provider)
        if provider == "openai":
            raise RuntimeError("Mock provider failure")
        return RecommendationExplanation(summary="Secondary provider explanation")

    monkeypatch.setattr(ExplanationService, "_generate_with_provider", generate)
    result = ExplanationService().explain(
        candidate=make_candidate(), requirement=make_requirement(), score=make_score(), evidence=make_evidence(),
    )
    assert calls == ["openai", "gemini"]
    assert result.generation_mode == "gemini"


def test_missing_live_keys_falls_back_without_network(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    result = ExplanationService().explain(
        candidate=make_candidate(), requirement=make_requirement(), score=make_score(), evidence=make_evidence(),
    )
    assert result.generation_mode == "fallback"
    assert "449000" in str(result.why_fit)
