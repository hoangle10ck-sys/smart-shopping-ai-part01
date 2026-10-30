"""Deterministic recommendation orchestration."""

from dataclasses import dataclass
from app.services.performance import measure, current_trace
from app.services.budget import stored_budget
from app.services.llm.explanation_batch import ExplanationBatch
from datetime import datetime, timezone

from pydantic import TypeAdapter

from sqlalchemy import (
    delete,
    select,
)
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.scoring.scoring_engine import ScoringEngine
from app.services.validation.structured_evidence import build_field_evidence
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
from app.services.product_images.eligibility import (
    apply_image_eligibility,
    apply_image_eligibility_to_items,
    has_verified_image,
)
from app.services.product_images.page_evidence import page_image_evidence


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

    @property
    def total_recommended(self) -> int:
        """Return the count of recommendations currently present in the result."""
        return len(self.recommendations)


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
        **stored_budget(model),
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


def _editorial_recommendation(item: RecommendationItem) -> bool:
    """Identify clearly editorial evidence without rejecting unknown merchants."""
    from urllib.parse import urlsplit

    blocked = {
        "youtube.com", "youtu.be", "tiktok.com", "instagram.com",
        "facebook.com", "wikipedia.org", "vnexpress.net",
        "vietnamnet.vn", "dantri.com.vn",
    }
    for value in (item.product_url, item.evidence_url):
        if not value:
            continue
        try:
            host = (urlsplit(value).hostname or "").lower().removeprefix("www.")
        except ValueError:
            continue
        if any(host == domain or host.endswith("." + domain) for domain in blocked):
            return True
    return False


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

    @staticmethod
    def persist_snapshot_rows(
        *, db: Session, session_id: str, result: RecommendationRunResult
    ) -> None:
        """Keep the legacy recommendation detail endpoint aligned with a saved snapshot."""
        db.execute(delete(Recommendation).where(Recommendation.session_id == session_id))
        seen_products: set[int] = set()
        for item in result.recommendations:
            if item.product_id in seen_products:
                continue
            seen_products.add(item.product_id)
            score = item.score
            db.add(Recommendation(
                session_id=session_id,
                product_id=item.product_id,
                final_score=score.final_score,
                budget_score=score.budget_score,
                requirement_score=score.requirement_score,
                purpose_score=score.purpose_score,
                rating_score=score.rating_score,
                review_score=score.review_score,
                source_score=score.source_score,
                confidence=item.confidence,
                rank=item.rank,
                explanation={
                    "evidence": item.evidence.model_dump(mode="json") if item.evidence else None,
                    "explanation": item.explanation.model_dump(mode="json") if item.explanation else None,
                },
            ))
        db.flush()

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

        with measure("filtering_ms"):
            accepted, decisions = (
                self.hard_filter.filter(
                    candidates,
                    requirement,
                )
            )

        with measure("scoring_ms"):
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

        # Prepare ORM-backed evidence before independent I/O. Workers receive
        # only Pydantic facts; persistence and ranking remain on this thread.
        evidence_by_product = {}
        jobs = []
        for ranked_item in ranked:
            candidate = ranked_item.candidate
            context = context_by_product[candidate.product_id]
            evidence = self.evidence_validator.validate(context)
            evidence.fields = build_field_evidence(db, session_id, context)
            evidence_by_product[candidate.product_id] = evidence
            jobs.append(dict(candidate=candidate,requirement=requirement,
                             score=ranked_item.score,evidence=evidence))
        if persist:
            explanations = ExplanationBatch(self.explanation_service).run(jobs)
        else:
            explanations = [self.explanation_service.build_deterministic(**job) for job in jobs]

        items: list[
            RecommendationItem
        ] = []

        for ranked_item, explanation in zip(ranked, explanations):
            candidate = (
                ranked_item.candidate
            )

            score = ranked_item.score

            context = (
                context_by_product[
                    candidate.product_id
                ]
            )

            evidence = evidence_by_product[candidate.product_id]

            if not persist:
                explanation.generation_mode = "fallback"

            items.append(
                self._build_item(
                    context=context,
                    requirement=requirement,
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

            items[-1].requirement_matches = ScoringEngine().requirement_matches(candidate, requirement)

        image_hashes: dict[str, set[int]] = {}
        image_rejections: dict[int, str] = {}
        for candidate in accepted:
            context = context_by_product[candidate.product_id]
            offer = context.offer
            proof = context.page_validation
            verified_image = page_image_evidence(
                proof=proof,
                image_url=proof.get("image_url") if proof else None,
                product_url=offer.product_url if offer else None,
                identifier_value=offer.external_product_id if offer else None,
                model=candidate.model,
            )
            if not verified_image or not has_verified_image(verified_image.image_url, verified_image):
                image_rejections[candidate.product_id] = "IMAGE_EVIDENCE_INCOMPLETE"
                continue
            image_hashes.setdefault(verified_image.content_sha256, set()).add(candidate.product_id)
        for product_ids in image_hashes.values():
            if len(product_ids) > 1:
                image_rejections.update({
                    product_id: "IMAGE_DUPLICATE_IDENTITY_CONFLICT" for product_id in product_ids
                })
        if image_rejections:
            decisions_by_id = {decision.product_id: decision for decision in decisions}
            for product_id, reason in image_rejections.items():
                decision = decisions_by_id.get(product_id)
                if decision is not None:
                    decision.accepted = False
                    decision.rejection_stage = "image_evidence"
                    if reason not in decision.reasons:
                        decision.reasons = [*decision.reasons, reason]
            accepted = [item for item in accepted if item.product_id not in image_rejections]
        items, ranked_rejections = apply_image_eligibility_to_items(
            items, decisions, image_rejections
        )
        image_rejections.update(ranked_rejections)

        trace = current_trace.get()
        if trace is not None:
            trace.diagnostics.update(final_recommendations=len(items), scoring_candidates=len(candidates), hard_filtered=len(candidates)-len(accepted))
            from collections import Counter
            trace.diagnostics.update(valid_candidates=len(candidates), eligible_offers=len(accepted),
                filter_reason_counts=dict(Counter(d.rejection_stage for d in decisions if not d.accepted)),
                filter_rejections=[dict(**d.model_dump(), name=c.name, price=c.price,
                    category=c.category, availability=c.availability)
                    for c, d in zip(candidates, decisions) if not d.accepted])

        result = RecommendationRunResult(
            requirement=requirement,
            candidates=candidates,
            filter_decisions=decisions,
            recommendations=items,
            total_found=len(
                candidates
            ),
            total_filtered=len(accepted),
            data_semantics="snapshot" if persist else "legacy_recomputed",
            data_mode=("demo" if self.settings.demo_mode else "live") if persist else None,
        )
        if persist:
            self.persist_snapshot_rows(db=db, session_id=session_id, result=result)
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
            result = TypeAdapter(RecommendationRunResult).validate_python(snapshot.payload["result"])
            unsafe_indexes = [
                index for index, item in enumerate(result.recommendations)
                if _editorial_recommendation(item)
            ]
            if unsafe_indexes:
                # Old snapshots can predate source filtering. Recompute only when
                # a saved item explicitly points at a known editorial host.
                try:
                    recomputed = self._evaluate(db=db, session_id=session_id, persist=False)
                except Exception as exc:
                    raise ValueError(
                        "Saved results contain a non-commercial source and could not be safely recomputed."
                    ) from exc
                recomputed.data_semantics = "legacy_recomputed"
                recomputed.data_mode = snapshot.payload.get("data_mode")
                recomputed.recommendations = [
                    item for item in recomputed.recommendations
                    if not _editorial_recommendation(item)
                ]
                return recomputed
            apply_image_eligibility(result)
            # Legacy version-1 snapshots predate unified source provenance.
            # Their mode is unknown; do not substitute today's runtime config.
            if result.data_mode is None:
                result.data_mode = snapshot.payload.get("data_mode")
            return result

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
        requirement: RequirementData,
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

        from app.services.scoring.two_level import SCORE_VERSION, offer_quality, offer_sort_key, product_suitability
        product_level = product_suitability(candidate, requirement)
        scored_offers = [(item, offer_quality(item, budget_max=requirement.budget_max,
                          preference=requirement.sort_preference)) for item in context.offers]
        scored_offers.sort(key=lambda pair: offer_sort_key(pair[1], pair[0]))
        selected_offer_level = next((value for item, value in scored_offers if offer and item.id == offer.id), None)
        alternate_offers = [{
            "purchase_rank": purchase_rank,
            "offer_id": item.id, "variant_id": item.variant_id, "platform": item.platform,
            "merchant": item.merchant, "price": item.price, "currency": item.currency,
            "availability": item.availability, "product_url": item.product_url,
            "shipping_fee": item.shipping_fee, "voucher": item.voucher, "warranty": item.warranty,
            "last_verified_at": item.last_verified_at, "freshness_status": item.freshness_status,
            "offer_quality": level.model_dump(mode="json"),
        } for purchase_rank, (item, level) in enumerate(scored_offers, start=1)]
        if offer is not None and offer.freshness_status == "STALE":
            evidence.warnings.append("STALE_DATA: offer observation is outside the configured freshness TTL; verify before buying.")

        proof = context.page_validation
        image_evidence = page_image_evidence(
            proof=proof,
            image_url=proof.get("image_url") if proof else None,
            product_url=offer.product_url if offer else None,
            identifier_value=offer.external_product_id if offer else None,
            model=candidate.model,
        )

        return RecommendationItem(
            product_id=(
                candidate.product_id
            ),
            variant_id=offer.variant_id if offer is not None else None,
            offer_id=offer.id if offer is not None else None,
            platform=offer.platform if offer is not None else None,
            freshness_status=offer.freshness_status if offer is not None else None,
            score_version=SCORE_VERSION,
            product_suitability=product_level.model_dump(mode="json"),
            offer_quality=selected_offer_level.model_dump(mode="json") if selected_offer_level else None,
            alternate_offers=alternate_offers,
            rank=rank,
            name=candidate.name,
            category=(
                candidate.category
            ),
            brand=candidate.brand,
            model=candidate.model,
            image_url=str(image_evidence.image_url) if image_evidence else None,
            image_evidence=image_evidence,
            product_page_valid=context.page_validation.get("product_page_valid") if context.page_validation is not None else None,
            source_observation_valid=context.page_validation.get("source_observation_valid") if context.page_validation is not None else None,
            price_type=context.page_validation.get('price_type') if context.page_validation is not None else None,
            variant=context.page_validation.get('variant') if context.page_validation is not None else None,
            verification_level=context.page_validation.get("verification_level") if context.page_validation is not None else None,
            product_page_confidence=context.page_validation.get("product_page_confidence") if context.page_validation is not None else None,
            evidence_url=context.page_validation.get("evidence_url") if context.page_validation is not None else None,
            image_source=context.page_validation.get("image_source") if context.page_validation is not None else None,
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
