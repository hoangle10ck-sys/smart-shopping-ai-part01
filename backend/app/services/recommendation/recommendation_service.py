"""Deterministic recommendation orchestration."""

from dataclasses import dataclass

from sqlalchemy import (
    delete,
    select,
)
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.recommendation import (
    Recommendation,
)
from app.models.requirement import (
    Requirement,
)
from app.schemas.evidence import (
    EvidenceReport,
    RecommendationExplanation,
)
from app.schemas.ranking import (
    FilterDecision,
    ScoringCandidate,
    ScoreBreakdown,
)
from app.schemas.recommendation import (
    RecommendationItem,
)
from app.schemas.requirement import (
    RequirementData,
    RequirementItem,
)
from app.services.filter.hard_filter import (
    HardFilterService,
)
from app.services.llm.explanation_service import (
    ExplanationService,
)
from app.services.recommendation.candidate_builder import (
    CandidateBuilder,
    CandidateContext,
)
from app.services.recommendation.ranking_service import (
    RankingService,
)
from app.services.validation.evidence_validator import (
    EvidenceValidator,
)


@dataclass(slots=True)
class RecommendationRunResult:
    """Result of filtering, scoring and explanation."""

    requirement: RequirementData

    candidates: list[
        ScoringCandidate
    ]

    filter_decisions: list[
        FilterDecision
    ]

    recommendations: list[
        RecommendationItem
    ]

    total_found: int

    total_filtered: int


def requirement_to_schema(
    model: Requirement,
) -> RequirementData:
    """Convert SQLAlchemy Requirement to Pydantic."""

    items = [
        RequirementItem.model_validate(
            item
        )
        for item
        in (
            model.requirements
            or []
        )
    ]

    return RequirementData(
        category=model.category,
        budget_min=model.budget_min,
        budget_max=model.budget_max,
        currency=model.currency,
        purpose=list(
            model.purpose
            or []
        ),
        brands=list(
            model.brands
            or []
        ),
        requirements=items,
        excluded_requirements=list(
            model.excluded_requirements
            or []
        ),
        sort_preference=(
            model.sort_preference
        ),
        confidence=(
            model.confidence
            if model.confidence
            is not None
            else 0.0
        ),
    )


class RecommendationService:
    """Filter, score, validate evidence, explain and persist."""

    def __init__(self) -> None:
        self.settings = get_settings()

        self.candidate_builder = (
            CandidateBuilder()
        )

        self.hard_filter = (
            HardFilterService()
        )

        self.ranking_service = (
            RankingService()
        )

        self.evidence_validator = (
            EvidenceValidator()
        )

        self.explanation_service = (
    ExplanationService(
        use_llm=False
    )
)

    def run(
        self,
        *,
        db: Session,
        session_id: str,
    ) -> RecommendationRunResult:
        """Generate recommendations for a search session."""

        requirement_model = db.scalar(
            select(Requirement).where(
                Requirement.session_id
                == session_id
            )
        )

        if requirement_model is None:
            raise ValueError(
                "Search session has no requirement."
            )

        requirement = (
            requirement_to_schema(
                requirement_model
            )
        )

        contexts = (
            self.candidate_builder.build(
                db=db,
                session_id=session_id,
                requirement=requirement,
            )
        )

        candidates = [
            context.candidate
            for context in contexts
        ]

        accepted, decisions = (
            self.hard_filter.filter(
                candidates,
                requirement,
            )
        )

        ranked = (
            self.ranking_service.rank(
                accepted,
                requirement,
                top_k=(
                    self.settings.top_k
                ),
            )
        )

        context_by_product = {
            context.candidate.product_id:
            context
            for context
            in contexts
        }

        db.execute(
            delete(
                Recommendation
            ).where(
                Recommendation.session_id
                == session_id
            )
        )

        items: list[
            RecommendationItem
        ] = []

        for ranked_item in ranked:
            candidate = (
                ranked_item.candidate
            )

            score = ranked_item.score

            context = (
                context_by_product[
                    candidate.product_id
                ]
            )

            evidence = (
                self.evidence_validator.validate(
                    context
                )
            )

            explanation = (
                self.explanation_service.explain(
                    candidate=candidate,
                    requirement=requirement,
                    score=score,
                    evidence=evidence,
                )
            )

            stored_explanation = {
                "evidence": (
                    evidence.model_dump(
                        mode="json"
                    )
                ),
                "explanation": (
                    explanation.model_dump(
                        mode="json"
                    )
                ),
            }

            db.add(
                Recommendation(
                    session_id=session_id,
                    product_id=(
                        candidate.product_id
                    ),
                    final_score=(
                        score.final_score
                    ),
                    budget_score=(
                        score.budget_score
                    ),
                    requirement_score=(
                        score.requirement_score
                    ),
                    purpose_score=(
                        score.purpose_score
                    ),
                    rating_score=(
                        score.rating_score
                    ),
                    review_score=(
                        score.review_score
                    ),
                    source_score=(
                        score.source_score
                    ),
                    confidence=(
                        evidence.confidence
                    ),
                    rank=ranked_item.rank,
                    explanation=(
                        stored_explanation
                    ),
                )
            )

            items.append(
                self._build_item(
                    context=context,
                    rank=(
                        ranked_item.rank
                    ),
                    score=score,
                    evidence=evidence,
                    explanation=(
                        explanation
                    ),
                )
            )

        db.flush()

        return RecommendationRunResult(
            requirement=requirement,
            candidates=candidates,
            filter_decisions=decisions,
            recommendations=items,
            total_found=len(
                candidates
            ),
            total_filtered=len(
                accepted
            ),
        )

    def load(
        self,
        *,
        db: Session,
        session_id: str,
    ) -> RecommendationRunResult:
        """Load persisted recommendations."""

        requirement_model = db.scalar(
            select(Requirement).where(
                Requirement.session_id
                == session_id
            )
        )

        if requirement_model is None:
            raise ValueError(
                "Search session has no requirement."
            )

        requirement = (
            requirement_to_schema(
                requirement_model
            )
        )

        contexts = (
            self.candidate_builder.build(
                db=db,
                session_id=session_id,
                requirement=requirement,
            )
        )

        candidates = [
            context.candidate
            for context in contexts
        ]

        accepted, decisions = (
            self.hard_filter.filter(
                candidates,
                requirement,
            )
        )

        context_by_product = {
            context.candidate.product_id:
            context
            for context
            in contexts
        }

        rows = list(
            db.scalars(
                select(Recommendation)
                .where(
                    Recommendation.session_id
                    == session_id
                )
                .order_by(
                    Recommendation.rank
                )
            )
        )

        items: list[
            RecommendationItem
        ] = []

        for row in rows:
            context = (
                context_by_product.get(
                    row.product_id
                )
            )

            if context is None:
                continue

            score = ScoreBreakdown(
                budget_score=(
                    row.budget_score
                ),
                requirement_score=(
                    row.requirement_score
                ),
                purpose_score=(
                    row.purpose_score
                ),
                rating_score=(
                    row.rating_score
                ),
                review_score=(
                    row.review_score
                ),
                source_score=(
                    row.source_score
                ),
                final_score=(
                    row.final_score
                ),
            )

            evidence: (
                EvidenceReport
                | None
            ) = None

            explanation: (
                RecommendationExplanation
                | None
            ) = None

            stored = (
                row.explanation
                if isinstance(
                    row.explanation,
                    dict,
                )
                else {}
            )

            raw_evidence = (
                stored.get("evidence")
            )

            raw_explanation = (
                stored.get("explanation")
            )

            if raw_evidence:
                evidence = (
                    EvidenceReport
                    .model_validate(
                        raw_evidence
                    )
                )

            if raw_explanation:
                explanation = (
                    RecommendationExplanation
                    .model_validate(
                        raw_explanation
                    )
                )

            if evidence is None:
                evidence = (
                    self.evidence_validator
                    .validate(
                        context
                    )
                )

            if explanation is None:
                explanation = (
                    self.explanation_service
                    .build_deterministic(
                        candidate=(
                            context.candidate
                        ),
                        requirement=(
                            requirement
                        ),
                        score=score,
                        evidence=evidence,
                    )
                )

                explanation.generation_mode = (
                    "fallback"
                )

            items.append(
                self._build_item(
                    context=context,
                    rank=row.rank,
                    score=score,
                    evidence=evidence,
                    explanation=(
                        explanation
                    ),
                )
            )

        return RecommendationRunResult(
            requirement=requirement,
            candidates=candidates,
            filter_decisions=decisions,
            recommendations=items,
            total_found=len(
                candidates
            ),
            total_filtered=len(
                accepted
            ),
        )

    def _build_item(
        self,
        *,
        context: CandidateContext,
        rank: int,
        score: ScoreBreakdown,
        evidence: EvidenceReport,
        explanation: (
            RecommendationExplanation
        ),
    ) -> RecommendationItem:
        """Build API recommendation item."""

        candidate = (
            context.candidate
        )

        offer = context.offer

        return RecommendationItem(
            product_id=(
                candidate.product_id
            ),
            rank=rank,
            name=candidate.name,
            category=(
                candidate.category
            ),
            brand=candidate.brand,
model=candidate.model,
image_url=(
    context.product.image_url
),
price=candidate.price,
            currency=(
                candidate.currency
            ),
            merchant=(
                offer.merchant
                if offer is not None
                else None
            ),
            product_url=(
                offer.product_url
                if offer is not None
                else None
            ),
            availability=(
                candidate.availability
            ),
            rating=candidate.rating,
            review_count=(
                candidate.review_count
            ),
            specifications=(
                candidate.specifications
            ),
            score=score,
            confidence=(
                evidence.confidence
            ),
            evidence=evidence,
            explanation=explanation,
        )