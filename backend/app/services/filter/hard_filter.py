"""Deterministic hard filtering for product candidates."""

import re

from app.schemas.ranking import (
    FilterDecision,
    ScoringCandidate,
)
from app.schemas.requirement import (
    RequirementData,
)
from app.services.normalization.text_normalizer import (
    normalize_product_text,
)


CATEGORY_ALIASES: dict[str, set[str]] = {
    "dien thoai": {
        "dien thoai",
        "smartphone",
        "phone",
    },
    "tai nghe": {
        "tai nghe",
        "headphone",
        "headphones",
        "earphone",
        "earphones",
        "earbuds",
    },
    "laptop": {
        "laptop",
        "notebook",
    },
    "chuot": {
        "chuot",
        "mouse",
    },
    "ban phim": {
        "ban phim",
        "keyboard",
    },
    "man hinh": {
        "man hinh",
        "monitor",
        "display",
    },
}


UNAVAILABLE_VALUES = {
    "out of stock",
    "out_of_stock",
    "sold out",
    "unavailable",
    "het hang",
    "khong con hang",
}


WEIGHT_LIMITS_GRAMS = {
    "dien thoai": 220.0,
    "laptop": 2200.0,
    "tai nghe": 350.0,
}


def normalized(
    value: str | None,
) -> str:
    """Return normalized text or an empty string."""

    return (
        normalize_product_text(value)
        or ""
    )


def category_matches(
    required_category: str,
    candidate_category: str | None,
) -> bool:
    """Compare product categories using deterministic aliases."""

    required = normalized(
        required_category
    )

    candidate = normalized(
        candidate_category
    )

    if not required or not candidate:
        return False

    if required == candidate:
        return True

    required_aliases = (
        CATEGORY_ALIASES.get(
            required,
            {required},
        )
    )

    candidate_aliases = (
        CATEGORY_ALIASES.get(
            candidate,
            {candidate},
        )
    )

    return bool(
        required_aliases
        & candidate_aliases
    )


def build_candidate_text(
    candidate: ScoringCandidate,
) -> str:
    """Build searchable deterministic product evidence text."""

    parts = [
        candidate.name,
        candidate.brand or "",
        candidate.model or "",
    ]

    for (
        key,
        value,
    ) in candidate.specifications.items():
        parts.append(
            f"{key} {value}"
        )

    return normalized(
        " ".join(parts)
    )


def parse_weight_grams(
    candidate: ScoringCandidate,
) -> float | None:
    """Extract weight from product specifications."""

    for (
        key,
        value,
    ) in candidate.specifications.items():
        key_normalized = normalized(key)

        if (
            "weight" not in key_normalized
            and "trong luong"
            not in key_normalized
        ):
            continue

        # Text matching strips punctuation; quantities must retain decimals.
        value_normalized = str(value).strip().lower().replace(",", ".")

        kg_match = re.search(
            r"(?<![\d.\-])(\d+(?:\.\d+)?)\s*kg\b",
            value_normalized,
        )

        if kg_match:
            number = float(
                kg_match.group(1)
                .replace(",", ".")
            )

            return number * 1000

        gram_match = re.search(
            r"(?<![\d.\-])(\d+(?:\.\d+)?)\s*g\b",
            value_normalized,
        )

        if gram_match:
            return float(
                gram_match.group(1)
                .replace(",", ".")
            )

    return None


def violates_exclusion(
    candidate: ScoringCandidate,
    excluded_requirement: str,
) -> bool:
    """Return True if candidate violates one exclusion."""

    exclusion = normalized(
        excluded_requirement
    )

    if not exclusion:
        return False

    candidate_text = (
        build_candidate_text(
            candidate
        )
    )

    if (
        exclusion
        and exclusion in candidate_text
    ):
        return True

    if (
        "nang" in exclusion
        or "heavy" in exclusion
    ):
        weight = parse_weight_grams(
            candidate
        )

        category = normalized(
            candidate.category
        )

        limit = (
            WEIGHT_LIMITS_GRAMS.get(
                category
            )
        )

        if (
            weight is not None
            and limit is not None
            and weight > limit
        ):
            return True

    return False


class HardFilterService:
    """Apply mandatory filters in the required order."""

    def evaluate(
        self,
        candidate: ScoringCandidate,
        requirement: RequirementData,
    ) -> FilterDecision:
        """Evaluate one candidate."""

        if requirement.category:
            if not category_matches(
                requirement.category,
                candidate.category,
            ):
                return FilterDecision(
                    product_id=(
                        candidate.product_id
                    ),
                    accepted=False,
                    rejection_stage="category",
                    reasons=[
                        (
                            "Sản phẩm không đúng "
                            "danh mục yêu cầu."
                        )
                    ],
                )

        if (
            requirement.budget_min
            is not None
            or requirement.budget_max
            is not None
        ):
            if candidate.price is None:
                return FilterDecision(
                    product_id=(
                        candidate.product_id
                    ),
                    accepted=False,
                    rejection_stage="budget",
                    reasons=[
                        (
                            "Không có giá để xác minh "
                            "ràng buộc ngân sách."
                        )
                    ],
                )

            if (
                requirement.budget_min
                is not None
                and candidate.price
                < requirement.budget_min
            ):
                return FilterDecision(
                    product_id=(
                        candidate.product_id
                    ),
                    accepted=False,
                    rejection_stage="budget",
                    reasons=[
                        (
                            "Giá thấp hơn ngân sách "
                            "tối thiểu yêu cầu."
                        )
                    ],
                )

            if (
                requirement.budget_max
                is not None
                and candidate.price
                > requirement.budget_max
            ):
                return FilterDecision(
                    product_id=(
                        candidate.product_id
                    ),
                    accepted=False,
                    rejection_stage="budget",
                    reasons=[
                        (
                            "Giá vượt ngân sách "
                            "tối đa."
                        )
                    ],
                )

        if requirement.brands:
            allowed_brands = {
                normalized(brand)
                for brand
                in requirement.brands
                if normalized(brand)
            }

            product_brand = normalized(
                candidate.brand
            )

            if (
                not product_brand
                or product_brand
                not in allowed_brands
            ):
                return FilterDecision(
                    product_id=(
                        candidate.product_id
                    ),
                    accepted=False,
                    rejection_stage="brand",
                    reasons=[
                        (
                            "Thương hiệu không thuộc "
                            "danh sách yêu cầu."
                        )
                    ],
                )

        for exclusion in (
            requirement.excluded_requirements
        ):
            if violates_exclusion(
                candidate,
                exclusion,
            ):
                return FilterDecision(
                    product_id=(
                        candidate.product_id
                    ),
                    accepted=False,
                    rejection_stage="exclusion",
                    reasons=[
                        (
                            "Sản phẩm vi phạm tiêu chí "
                            f"loại trừ: {exclusion}"
                        )
                    ],
                )

        availability = normalized(
            candidate.availability
        )

        if (
            availability
            and availability
            in UNAVAILABLE_VALUES
        ):
            return FilterDecision(
                product_id=(
                    candidate.product_id
                ),
                accepted=False,
                rejection_stage="availability",
                reasons=[
                    "Sản phẩm hiện không còn hàng."
                ],
            )

        return FilterDecision(
            product_id=(
                candidate.product_id
            ),
            accepted=True,
            rejection_stage=None,
            reasons=[],
        )

    def filter(
        self,
        candidates: list[
            ScoringCandidate
        ],
        requirement: RequirementData,
    ) -> tuple[
        list[ScoringCandidate],
        list[FilterDecision],
    ]:
        """Filter a candidate collection."""

        accepted: list[
            ScoringCandidate
        ] = []

        decisions: list[
            FilterDecision
        ] = []

        for candidate in candidates:
            decision = self.evaluate(
                candidate,
                requirement,
            )

            decisions.append(
                decision
            )

            if decision.accepted:
                accepted.append(
                    candidate
                )

        return accepted, decisions
