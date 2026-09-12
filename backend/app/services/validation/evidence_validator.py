"""Deterministic evidence validation and data-confidence scoring."""

from app.schemas.evidence import (
    EvidenceBreakdown,
    EvidenceReport,
)
from app.services.recommendation.candidate_builder import (
    CandidateContext,
)


SOURCE_WEIGHT = 0.30

PRODUCT_COMPLETENESS_WEIGHT = 0.25

OFFER_COMPLETENESS_WEIGHT = 0.20

CONSISTENCY_WEIGHT = 0.15

CORROBORATION_WEIGHT = 0.10


def clamp(
    value: float,
) -> float:
    """Clamp a score to 0-100."""

    return max(
        0.0,
        min(
            100.0,
            value,
        ),
    )


class EvidenceValidator:
    """Calculate Data Confidence separately from AI Match."""

    def validate(
        self,
        context: CandidateContext,
    ) -> EvidenceReport:
        """Validate product evidence deterministically."""

        source_score = (
            self._source_reliability(
                context
            )
        )

        product_score = (
            self._product_completeness(
                context
            )
        )

        offer_score = (
            self._offer_completeness(
                context
            )
        )

        consistency_score = (
            self._consistency(
                context
            )
        )

        corroboration_score = (
            self._corroboration(
                context
            )
        )

        final = (
            source_score
            * SOURCE_WEIGHT
            + product_score
            * PRODUCT_COMPLETENESS_WEIGHT
            + offer_score
            * OFFER_COMPLETENESS_WEIGHT
            + consistency_score
            * CONSISTENCY_WEIGHT
            + corroboration_score
            * CORROBORATION_WEIGHT
        )

        supporting_evidence = (
            self._supporting_evidence(
                context
            )
        )

        warnings = self._warnings(
            context
        )

        return EvidenceReport(
            confidence=round(
                clamp(final),
                2,
            ),
            breakdown=EvidenceBreakdown(
                source_reliability=round(
                    source_score,
                    2,
                ),
                product_completeness=round(
                    product_score,
                    2,
                ),
                offer_completeness=round(
                    offer_score,
                    2,
                ),
                consistency=round(
                    consistency_score,
                    2,
                ),
                corroboration=round(
                    corroboration_score,
                    2,
                ),
            ),
            source_count=len(
                context.source_reliabilities
            ),
            offer_count=len(
                context.offers
            ),
            supporting_evidence=(
                supporting_evidence
            ),
            warnings=warnings,
        )

    def _source_reliability(
        self,
        context: CandidateContext,
    ) -> float:
        """Average available source-reliability scores."""

        scores = (
            context.source_reliabilities
        )

        if not scores:
            return 50.0

        return clamp(
            sum(scores)
            / len(scores)
        )

    def _product_completeness(
        self,
        context: CandidateContext,
    ) -> float:
        """Score canonical product field completeness."""

        product = context.product

        score = 0.0

        if product.name:
            score += 20

        if product.brand:
            score += 15

        if product.model:
            score += 15

        if product.specifications:
            score += 20

        if product.rating is not None:
            score += 15

        if product.review_count is not None:
            score += 15

        return clamp(score)

    def _offer_completeness(
        self,
        context: CandidateContext,
    ) -> float:
        """Score selected offer completeness."""

        offer = context.offer

        if offer is None:
            return 0.0

        score = 0.0

        if offer.price is not None:
            score += 35

        if offer.product_url:
            score += 25

        if offer.availability:
            score += 20

        if offer.merchant:
            score += 10

        if offer.source_id is not None:
            score += 10

        return clamp(score)

    def _consistency(
        self,
        context: CandidateContext,
    ) -> float:
        """Measure price agreement between multiple offers."""

        prices = [
            offer.price
            for offer
            in context.offers
            if (
                offer.price is not None
                and offer.price > 0
            )
        ]

        if not prices:
            return 0.0

        if len(prices) == 1:
            return 60.0

        minimum = min(prices)

        maximum = max(prices)

        average = (
            sum(prices)
            / len(prices)
        )

        if average <= 0:
            return 0.0

        spread = (
            maximum - minimum
        ) / average

        if spread <= 0.05:
            return 100.0

        if spread <= 0.10:
            return 85.0

        if spread <= 0.20:
            return 65.0

        return 40.0

    def _corroboration(
        self,
        context: CandidateContext,
    ) -> float:
        """Score independent-source corroboration."""

        count = len(
            context.source_reliabilities
        )

        if count <= 0:
            return 0.0

        if count == 1:
            return 40.0

        if count == 2:
            return 70.0

        return 100.0

    def _supporting_evidence(
        self,
        context: CandidateContext,
    ) -> list[str]:
        """Generate evidence statements from stored data only."""

        candidate = (
            context.candidate
        )

        evidence: list[str] = []

        if candidate.price is not None:
            evidence.append(
                (
                    "Giá đã xác minh: "
                    f"{candidate.price} {candidate.currency}."
                )
            )

        if candidate.rating is not None:
            evidence.append(
                (
                    "Rating đã xác minh: "
                    f"{candidate.rating}/5."
                )
            )

        if (
            candidate.review_count
            is not None
        ):
            evidence.append(
                (
                    "Số lượt đánh giá: "
                    f"{candidate.review_count}."
                )
            )

        if candidate.specifications:
            keys = ", ".join(
                sorted(
                    candidate.specifications.keys()
                )
            )

            evidence.append(
                (
                    "Có thông số kỹ thuật: "
                    f"{keys}."
                )
            )

        if context.offer is not None:
            if context.offer.merchant:
                evidence.append(
                    (
                        "Nguồn bán: "
                        f"{context.offer.merchant}."
                    )
                )

            if context.offer.product_url:
                evidence.append(
                    (
                        "Có URL sản phẩm để "
                        "kiểm chứng."
                    )
                )

        return evidence

    def _warnings(
        self,
        context: CandidateContext,
    ) -> list[str]:
        """Return data-quality warnings."""

        candidate = (
            context.candidate
        )

        warnings: list[str] = []

        if candidate.price is None:
            warnings.append(
                "Thiếu dữ liệu giá."
            )

        if candidate.rating is None:
            warnings.append(
                "Thiếu dữ liệu rating."
            )

        if candidate.review_count is None:
            warnings.append(
                "Thiếu số lượt đánh giá."
            )

        if not candidate.specifications:
            warnings.append(
                "Thiếu thông số kỹ thuật."
            )

        if len(
            context.source_reliabilities
        ) <= 1:
            warnings.append(
                (
                    "Sản phẩm mới được xác minh "
                    "từ một nguồn."
                )
            )

        if (
            self._source_reliability(
                context
            )
            < 60
        ):
            warnings.append(
                (
                    "Độ tin cậy nguồn hiện "
                    "ở mức thấp hoặc trung bình."
                )
            )

        return warnings