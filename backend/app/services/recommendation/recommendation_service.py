"""Deterministic recommendation orchestration."""

from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import TypeAdapter

from sqlalchemy import (
    delete,
    select,
)
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.recommendation import (
    Recommendation,
)
from app.models.recommendation_snapshot import RecommendationSnapshot
from app.models.search_session import SearchSession, SearchSessionStatus
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
    RecommendationDataSemantics,
    RecommendationDataMode,
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

    data_semantics: RecommendationDataSemantics = "snapshot"
    data_mode: RecommendationDataMode | None = None


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

        self.explanation_service = ExplanationService()

    def run(self, *, db: Session, session_id: str) -> RecommendationRunResult:
        """Persist a complete snapshot in the same transaction as recommendations."""
        return self._evaluate(db=db, session_id=session_id, persist=True)

    def _evaluate(
        self,
        *,
        db: Session,
        session_id: str,
        persist: bool,
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

        if persist:
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
                (self.explanation_service.explain if persist
                 else self.explanation_service.build_deterministic)(
                    candidate=candidate,
                    requirement=requirement,
                    score=score,
                    evidence=evidence,
                )
            )

            if not persist:
                explanation.generation_mode = "fallback"

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

            if persist:
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

        result = RecommendationRunResult(
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
            data_semantics="snapshot" if persist else "legacy_recomputed",
            data_mode=("demo" if self.settings.demo_mode else "live") if persist else None,
        )
        if persist:
            snapshot = db.get(RecommendationSnapshot, session_id)
            if snapshot is None:
                snapshot = RecommendationSnapshot(session_id=session_id)
                db.add(snapshot)
            snapshot.payload = {
                "version": 1,
                "result": TypeAdapter(RecommendationRunResult).dump_python(result, mode="json"),
            }
            snapshot.created_at = datetime.now(timezone.utc)
            db.flush()
        return result

    def load(self, *, db: Session, session_id: str) -> RecommendationRunResult:
        """Read the last successful snapshot without joining mutable Product/Offer data.

        Pre-snapshot sessions cannot recover every historical value. Recompute their
        complete view from current evidence, explicitly labelled, without writing
        rows or calling an external LLM. Never mix old scores with current prices.
        """
        snapshot = db.get(RecommendationSnapshot, session_id)
        if snapshot is not None:
            if snapshot.payload.get("version") != 1:
                raise ValueError("Unsupported recommendation snapshot version.")
            return TypeAdapter(RecommendationRunResult).validate_python(snapshot.payload["result"])

        has_recommendations = db.scalar(select(Recommendation.id).where(
            Recommendation.session_id == session_id,
        ).limit(1)) is not None
        session = db.get(SearchSession, session_id)
        previously_completed = session is not None and (
            session.status == SearchSessionStatus.COMPLETED or session.completed_at is not None
        )
        if has_recommendations or previously_completed:
            return self._evaluate(db=db, session_id=session_id, persist=False)

        model = db.scalar(select(Requirement).where(Requirement.session_id == session_id))
        if model is None:
            raise ValueError("Search session has no requirement.")
        return RecommendationRunResult(
            requirement=requirement_to_schema(model), candidates=[], filter_decisions=[],
            recommendations=[], total_found=0, total_filtered=0, data_semantics="not_generated",
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
            image_url=context.product.image_url,
            price=candidate.price,
            last_checked_at=(
                offer.last_checked_at.replace(tzinfo=timezone.utc)
                if offer is not None and offer.last_checked_at is not None and offer.last_checked_at.tzinfo is None
                else offer.last_checked_at if offer is not None else None
            ),
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
