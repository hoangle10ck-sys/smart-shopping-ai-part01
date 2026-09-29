"""Deterministic 0-100 product scoring engine."""

import re

from app.schemas.evidence import RequirementMatch

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


REQUIREMENT_ALIASES: dict[str, set[str]] = {
    "microphone": {"mic", "micro"},
    "battery": {"pin"},
    "camera": {"may anh", "camera sau", "camera truoc", "rear camera", "front camera"},
    "weight": {"trong luong"},
    "ram": {"memory", "bo nho ram"},
    "storage": {"ssd", "bo nho", "dung luong"},
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


def _property_key(name: str) -> str:
    key = normalized(name)
    for canonical, aliases in REQUIREMENT_ALIASES.items():
        if key == canonical or key in aliases:
            return canonical
    return key


def _capacity_gb(value: str) -> float | None:
    # First capacity is installed capacity; a later upgrade limit is not RAM.
    match = re.search(r"(?<![\d.\-])(\d+(?:[.,]\d+)?)\s*(mb|gb|tb)\b", value.lower())
    if match is None:
        return None
    number, unit = match.groups()
    return float(number.replace(",", ".")) * {"mb": 1 / 1024, "gb": 1, "tb": 1024}[unit]


def _battery_mah(value: str) -> float | None:
    """mAh-specific grouping; do not change decimal parsing for kg/hours/GB."""
    match = re.search(r"(?<![\w.,+-])(\d+(?:[.,]\d+)*)\s*mah\b", value, re.I)
    if not match:
        return None
    number = match.group(1)
    if re.fullmatch(r"[1-9]\d{0,2}([.,])\d{3}(?:\1\d{3})*", number):
        return float(number.replace('.', '').replace(',', ''))
    if re.fullmatch(r"\d+(?:[.,]\d+)?", number):
        return float(number.replace(',', '.'))
    return None


def _value_satisfies(key: str, actual: str, required: str, category: str | None) -> bool:
    """Compare a property's own value; unknown/absent evidence earns no credit."""
    actual_text, required_text = normalized(actual), normalized(required)
    if actual_text in {
        "", "unknown", "none", "null", "n a", "not available", "not specified",
        "chua ro", "khong ro", "khong co thong tin", "chua co thong tin",
        "khong", "khong co", "false", "no",
    }:
        return False
    if re.search(r"\b(?:khong co|khong tot|not good|without|no)\b", actual_text):
        return False

    if key in {"ram", "storage"}:
        wanted, available = _capacity_gb(required), _capacity_gb(actual)
        if wanted is not None:
            if available is None:
                return False
            # Do not ignore an explicitly requested RAM generation.
            generation = re.search(r"\bddr[345]\b", required_text)
            if generation and generation.group() not in actual_text:
                return False
            if any(marker in required_text for marker in ("toi da", "khong qua", "at most")) or "<=" in required:
                return available <= wanted
            if any(marker in required_text for marker in ("chinh xac", "exactly")):
                return available == wanted
            return available >= wanted

    # Explicit, conservative rubrics for the existing qualitative preferences.
    # These are deterministic suitability heuristics, not claims of measured quality.
    if key == "microphone" and required_text in {"tot", "mic tot", "microphone tot", "good"}:
        return bool(re.search(r"\b(?:tot|good|enc|dual mic|noise reduction)\b", actual_text))
    if key == "camera" and required_text in {"tot", "camera tot", "good"}:
        return bool(re.search(r"\b(?:tot|good|ois)\b", actual_text))
    if key == "battery" and required_text in {"pin lau", "lau", "long battery life"}:
        if actual_text in {"pin lau", "lau", "long battery life"}:
            return True
        hours = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:hours?|hrs?|h|gio)\b", actual.lower())
        minimum_hours = {"tai nghe": 24, "laptop": 8}.get(normalized(category))
        if hours and minimum_hours is not None:
            return float(hours.group(1).replace(",", ".")) >= minimum_hours
        mah = _battery_mah(actual)
        return mah is not None and normalized(category) == "dien thoai" and mah >= 4000

    # Preserve the complete requested value; matching one token is insufficient.
    return bool(required_text and re.search(
        rf"(?<!\w){re.escape(required_text)}(?!\w)", actual_text
    ))


def _is_known_mismatch(key: str, actual: str, required: str, category: str | None) -> bool:
    """Separate insufficient evidence from an observed failure of the rubric."""
    text, wanted = normalized(actual), normalized(required)
    if text in {"", "unknown", "none", "null", "n a", "not available", "not specified",
                "chua ro", "khong ro", "khong co thong tin", "chua co thong tin"}:
        return False
    if text in {"khong", "khong co", "false", "no"} or re.search(
        r"\b(?:khong co|khong tot|not good|without|no|bad|kem)\b", text
    ):
        return True
    if key in {"ram", "storage"} and _capacity_gb(required) is not None:
        if _capacity_gb(actual) is None:
            return False
        # Enough capacity but unspecified requested DDR generation is unknown.
        generation = re.search(r"\bddr[345]\b", wanted)
        if generation and not re.search(r"\bddr[345]\b", text):
            return not _value_satisfies(key, actual, re.sub(r"\bDDR[345]\b", "", required, flags=re.I), category)
        return True
    if key in {"microphone", "camera"} and wanted in {
        "tot", "mic tot", "microphone tot", "camera tot", "good",
    }:
        return False  # Presence or an unspecified quality is not measured quality.
    if key == "battery" and wanted in {"pin lau", "lau", "long battery life"}:
        if normalized(category) == 'dien thoai':
            return _battery_mah(actual) is not None
        unit = r"(?:hours?|hrs?|h|gio)" if normalized(category) in {"tai nghe", "laptop"} else (
            "mah" if normalized(category) == "dien thoai" else None
        )
        return bool(unit and re.search(rf"\d+(?:[.,]\d+)?\s*{unit}\b", actual.lower()))
    return True


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

        if requirement.budget_mode == 'FLEXIBLE_TARGET':
            if candidate.price is None:
                return 0.0
            target = requirement.budget_target
            radius = max(target - requirement.preferred_min, requirement.preferred_max - target, 1)
            return clamp(100 - 25 * abs(candidate.price - target) / radius)

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

    def requirement_score(self, candidate: ScoringCandidate, requirement: RequirementData) -> float:
        """Score verified property values using the user's unchanged priorities."""
        if not requirement.requirements:
            return 100.0
        total_weight = sum(item.priority for item in requirement.requirements)
        matched_weight = sum(item.priority for item, match in zip(
            requirement.requirements, self.requirement_matches(candidate, requirement)
        ) if match.status == "matched")
        return matched_weight / total_weight * 100.0 if total_weight else 100.0

    def requirement_matches(self, candidate: ScoringCandidate, requirement: RequirementData) -> list[RequirementMatch]:
        """Use exactly the scoring comparator; missing evidence remains unknown."""
        values: dict[str, list[str]] = {}
        for name, value in candidate.specifications.items():
            values.setdefault(_property_key(name), []).append(value)
        matches = []
        for item in requirement.requirements:
            key = _property_key(item.name)
            actuals = values.get(key, [])
            # A specifically requested front/rear camera must not borrow the
            # other camera's OIS. Generic camera requests may inspect both.
            requested_key = normalized(item.name)
            sides = ({'camera sau', 'rear camera'}, {'camera truoc', 'front camera'})
            side = next((group for group in sides if requested_key in group), None)
            if side:
                actuals = [v for k,v in candidate.specifications.items() if normalized(k) in side]
            matched = next((value for value in actuals if _value_satisfies(
                key, value, item.value, candidate.category
            )), None)
            if matched is not None:
                status, reason, actual = "matched", "Giá trị đáp ứng quy tắc so sánh deterministic.", matched
            elif actuals and all(_is_known_mismatch(key, value, item.value, candidate.category) for value in actuals):
                status, reason, actual = "unmet", "Giá trị đã biết không đáp ứng yêu cầu.", "; ".join(actuals)
            else:
                status, reason, actual = "unknown", "Chưa đủ dữ liệu để đối chiếu giá trị yêu cầu.", "; ".join(actuals) or None
            matches.append(RequirementMatch(name=item.name, requested_value=item.value,
                                            product_value=actual, status=status, reason=reason))
        return matches

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
