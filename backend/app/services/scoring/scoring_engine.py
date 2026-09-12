"""Deterministic 0-100 product scoring engine."""

from app.schemas.ranking import (
    ScoreBreakdown,
    ScoringCandidate,
)
from app.schemas.requirement import (
    RequirementData,
)
from app.services.normalization.text_normalizer import (
    normalize_product_text,
)


BUDGET_WEIGHT = 0.25
REQUIREMENT_WEIGHT = 0.30
PURPOSE_WEIGHT = 0.20
RATING_WEIGHT = 0.10
REVIEW_WEIGHT = 0.05
SOURCE_WEIGHT = 0.10


REQUIREMENT_ALIASES: dict[
    str,
    set[str],
] = {
    "microphone": {
        "microphone",
        "mic",
        "dual mic",
        "enc",
        "noise reduction",
    },
    "battery": {
        "battery",
        "pin",
        "mah",
        "hours",
        "hour",
        "gio",
    },
    "camera": {
        "camera",
        "mp",
        "ois",
    },
    "weight": {
        "weight",
        "trong luong",
        "nhe",
        "g",
        "kg",
    },
    "ram": {
        "ram",
        "memory",
    },
    "storage": {
        "storage",
        "ssd",
        "bo nho",
    },
}


PURPOSE_ALIASES: dict[
    str,
    set[str],
] = {
    "hoc online": {
        "microphone",
        "mic",
        "enc",
        "noise reduction",
        "battery",
    },
    "hoc lap trinh": {
        "ram",
        "ssd",
        "storage",
        "cpu",
        "processor",
        "core",
    },
    "choi game": {
        "gpu",
        "graphics",
        "ram",
        "refresh",
        "hz",
        "chip",
        "battery",
    },
    "chup anh": {
        "camera",
        "mp",
        "ois",
        "sensor",
    },
    "nghe nhac": {
        "audio",
        "sound",
        "bass",
        "driver",
        "codec",
    },
    "hop online": {
        "microphone",
        "mic",
        "camera",
        "webcam",
        "enc",
    },
    "van phong": {
        "battery",
        "keyboard",
        "office",
        "weight",
    },
    "thiet ke": {
        "display",
        "screen",
        "gpu",
        "ram",
        "color",
    },
    "chinh sua video": {
        "gpu",
        "ram",
        "ssd",
        "cpu",
        "display",
    },
}


def normalized(
    value: str | None,
) -> str:
    """Normalize text."""

    return (
        normalize_product_text(value)
        or ""
    )


def clamp(
    value: float,
) -> float:
    """Clamp score to 0-100."""

    return max(
        0.0,
        min(
            100.0,
            value,
        ),
    )


def candidate_text(
    candidate: ScoringCandidate,
) -> str:
    """Create deterministic evidence text."""

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


class ScoringEngine:
    """Calculate deterministic weighted product scores."""

    def score(
        self,
        candidate: ScoringCandidate,
        requirement: RequirementData,
    ) -> ScoreBreakdown:
        """Score one product from 0 to 100."""

        budget = self.budget_score(
            candidate,
            requirement,
        )

        requirements = (
            self.requirement_score(
                candidate,
                requirement,
            )
        )

        purpose = self.purpose_score(
            candidate,
            requirement,
        )

        rating = self.rating_score(
            candidate
        )

        reviews = self.review_score(
            candidate
        )

        source = self.source_score(
            candidate
        )

        final = (
            budget
            * BUDGET_WEIGHT
            + requirements
            * REQUIREMENT_WEIGHT
            + purpose
            * PURPOSE_WEIGHT
            + rating
            * RATING_WEIGHT
            + reviews
            * REVIEW_WEIGHT
            + source
            * SOURCE_WEIGHT
        )

        return ScoreBreakdown(
            budget_score=round(
                budget,
                2,
            ),
            requirement_score=round(
                requirements,
                2,
            ),
            purpose_score=round(
                purpose,
                2,
            ),
            rating_score=round(
                rating,
                2,
            ),
            review_score=round(
                reviews,
                2,
            ),
            source_score=round(
                source,
                2,
            ),
            final_score=round(
                clamp(final),
                2,
            ),
        )

    def budget_score(
        self,
        candidate: ScoringCandidate,
        requirement: RequirementData,
    ) -> float:
        """Score budget fit after hard filtering."""

        if (
            requirement.budget_min
            is None
            and requirement.budget_max
            is None
        ):
            return 100.0

        if candidate.price is None:
            return 0.0

        if (
            requirement.budget_min
            is not None
            and requirement.budget_max
            is not None
        ):
            minimum = (
                requirement.budget_min
            )

            maximum = (
                requirement.budget_max
            )

            if maximum <= minimum:
                return 100.0

            center = (
                minimum + maximum
            ) / 2

            half_range = (
                maximum - minimum
            ) / 2

            distance = abs(
                candidate.price - center
            )

            closeness = max(
                0.0,
                1.0
                - (
                    distance
                    / half_range
                ),
            )

            return (
                75.0
                + 25.0 * closeness
            )

        if (
            requirement.budget_max
            is not None
        ):
            maximum = (
                requirement.budget_max
            )

            if maximum <= 0:
                return 0.0

            ratio = (
                candidate.price
                / maximum
            )

            return clamp(
                70.0
                + 30.0 * ratio
            )

        return 100.0

    def requirement_score(
        self,
        candidate: ScoringCandidate,
        requirement: RequirementData,
    ) -> float:
        """Score prioritized requirement satisfaction."""

        if not requirement.requirements:
            return 100.0

        text = candidate_text(
            candidate
        )

        total_weight = 0

        matched_weight = 0

        for item in (
            requirement.requirements
        ):
            weight = item.priority

            total_weight += weight

            key = normalized(
                item.name
            )

            value = normalized(
                item.value
            )

            aliases = set(
                REQUIREMENT_ALIASES.get(
                    key,
                    set(),
                )
            )

            if key:
                aliases.add(key)

            if value:
                aliases.add(value)

                aliases.update(
                    token
                    for token
                    in value.split()
                    if len(token) >= 3
                )

            if any(
                alias
                and alias in text
                for alias in aliases
            ):
                matched_weight += (
                    weight
                )

        if total_weight <= 0:
            return 100.0

        return (
            matched_weight
            / total_weight
        ) * 100.0

    def purpose_score(
        self,
        candidate: ScoringCandidate,
        requirement: RequirementData,
    ) -> float:
        """Score product suitability for requested purposes."""

        if not requirement.purpose:
            return 100.0

        text = candidate_text(
            candidate
        )

        matched = 0

        for raw_purpose in (
            requirement.purpose
        ):
            purpose = normalized(
                raw_purpose
            )

            aliases = set(
                PURPOSE_ALIASES.get(
                    purpose,
                    set(),
                )
            )

            if purpose:
                aliases.add(
                    purpose
                )

            if any(
                alias in text
                for alias in aliases
                if alias
            ):
                matched += 1

        return (
            matched
            / len(requirement.purpose)
        ) * 100.0

    def rating_score(
        self,
        candidate: ScoringCandidate,
    ) -> float:
        """Convert 0-5 rating to 0-100."""

        if candidate.rating is None:
            return 0.0

        return clamp(
            (
                candidate.rating
                / 5.0
            )
            * 100.0
        )

    def review_score(
        self,
        candidate: ScoringCandidate,
    ) -> float:
        """Score review-volume evidence."""

        count = (
            candidate.review_count
        )

        if count is None or count <= 0:
            return 0.0

        if count >= 1000:
            return 100.0

        if count >= 500:
            return 90.0

        if count >= 200:
            return 80.0

        if count >= 100:
            return 70.0

        if count >= 50:
            return 60.0

        if count >= 10:
            return 40.0

        return 20.0

    def source_score(
        self,
        candidate: ScoringCandidate,
    ) -> float:
        """Use deterministic source reliability score."""

        return clamp(
            candidate.source_reliability
        )