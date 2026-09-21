"""Validation and reliability scoring for web search sources."""

import unicodedata
from app.services.extraction.product_page_validator import classify_source

from urllib.parse import (
    urlparse,
)

from app.core.constants import (
    MARKETPLACE_DOMAINS,
    OFFICIAL_BRAND_DOMAINS,
    REVIEW_DOMAINS,
    SOURCE_SCORE_MARKETPLACE,
    SOURCE_SCORE_OFFICIAL,
    SOURCE_SCORE_REVIEW,
    SOURCE_SCORE_TRUSTED_RETAILER,
    SOURCE_SCORE_UNKNOWN,
    TRUSTED_RETAILER_DOMAINS,
)

from app.schemas.search import (
    SearchSourceItem,
)

from app.services.search.base import (
    SearchResult,
)


# =============================================================
# RENTAL / SERVICE MARKERS
# =============================================================


RENTAL_MARKERS = {
    "for rent",
    "rental",
    "rent a",
    "daily rate",
    "/day",
    "per day",
    "motorcycle rental",
    "bike rental",
    "car rental",
    "cho thue",
    "gia thue",
    "thue xe",
    "thue may",
}


# =============================================================
# TEXT NORMALIZATION
# =============================================================


def normalize_text(
    value: str,
) -> str:
    """Normalize text for deterministic filtering."""

    value = (
        value
        .strip()
        .lower()
    )

    value = unicodedata.normalize(
        "NFD",
        value,
    )

    value = "".join(
        char
        for char in value
        if unicodedata.category(
            char
        )
        != "Mn"
    )

    value = value.replace(
        "đ",
        "d",
    )

    return value


# =============================================================
# RENTAL SOURCE DETECTOR
# =============================================================


def looks_like_rental_source(
    text: str | None = None,
    *,
    title: str | None = None,
    url: str | None = None,
    content: str | None = None,
) -> bool:
    """
    Return True when source content looks like a rental/service page.

    Supports both calling styles:

        looks_like_rental_source("some text")

    and:

        looks_like_rental_source(
            title="...",
            url="...",
            content="...",
        )

    This keeps compatibility with ProductExtractionService.
    """

    parts = [
        text or "",
        title or "",
        url or "",
        content or "",
    ]

    combined = " ".join(
        part
        for part in parts
        if part
    )

    normalized = normalize_text(
        combined
    )

    return any(
        marker in normalized
        for marker
        in RENTAL_MARKERS
    )


# =============================================================
# DOMAIN NORMALIZATION
# =============================================================


def normalize_domain(
    url: str,
) -> str | None:
    """Extract normalized hostname."""

    try:
        parsed = urlparse(
            url
        )

    except ValueError:
        return None

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return None

    domain = (
        parsed.hostname
        or ""
    ).lower()

    if domain.startswith(
        "www."
    ):
        domain = (
            domain[4:]
        )

    return (
        domain
        or None
    )


# =============================================================
# DOMAIN MATCHING
# =============================================================


def domain_matches(
    domain: str,
    candidates: set[str],
) -> bool:
    """Match exact domain or subdomain."""

    return any(
        domain == candidate
        or domain.endswith(
            f".{candidate}"
        )
        for candidate
        in candidates
    )


# =============================================================
# SOURCE RELIABILITY
# =============================================================


def calculate_source_reliability(
    domain: str,
) -> float:
    """Return reliability score."""

    if domain_matches(
        domain,
        OFFICIAL_BRAND_DOMAINS,
    ):
        return (
            SOURCE_SCORE_OFFICIAL
        )

    if domain_matches(
        domain,
        TRUSTED_RETAILER_DOMAINS,
    ):
        return (
            SOURCE_SCORE_TRUSTED_RETAILER
        )

    if domain_matches(
        domain,
        MARKETPLACE_DOMAINS,
    ):
        return (
            SOURCE_SCORE_MARKETPLACE
        )

    if domain_matches(
        domain,
        REVIEW_DOMAINS,
    ):
        return (
            SOURCE_SCORE_REVIEW
        )

    return (
        SOURCE_SCORE_UNKNOWN
    )


# =============================================================
# SEARCH RESULT RENTAL CHECK
# =============================================================


def is_rental_result(
    result: SearchResult,
) -> bool:
    """Reject rental/service results from product purchase search."""

    return looks_like_rental_source(
        title=(
            result.title
            or ""
        ),
        url=(
            result.url
            or ""
        ),
        content=(
            result.content
            or ""
        ),
    )


# =============================================================
# SOURCE FILTER
# =============================================================


class SourceFilter:
    """Validate, score and deduplicate web sources."""

    def filter(
        self,
        results: list[
            SearchResult
        ],
    ) -> list[
        SearchSourceItem
    ]:
        """Return valid product-related sources."""

        output: list[
            SearchSourceItem
        ] = []

        seen_urls: set[
            str
        ] = set()

        for result in results:

            # -------------------------------------------------
            # URL
            # -------------------------------------------------

            url = (
                result.url
                .strip()
            )

            if not url:
                continue

            if url in seen_urls:
                continue


            # -------------------------------------------------
            # DOMAIN
            # -------------------------------------------------

            domain = (
                normalize_domain(
                    url
                )
            )

            if domain is None:
                continue


            # -------------------------------------------------
            # RENTAL / SERVICE FILTER
            # -------------------------------------------------

            if is_rental_result(
                result
            ):
                continue


            # -------------------------------------------------
            # DEDUPLICATION
            # -------------------------------------------------

            seen_urls.add(
                url
            )


            # -------------------------------------------------
            # SOURCE ITEM
            # -------------------------------------------------

            output.append(
                SearchSourceItem(
                    result_type=classify_source(url),
                    title=(
                        result.title
                        .strip()
                        or None
                    ),

                    url=url,

                    domain=domain,

                    content=(
                        result.content
                        .strip()
                    ),

                    image_url=(
                        result.image_url
                    ),

                    provider_score=(
                        result.score
                    ),

                    reliability_score=(
                        calculate_source_reliability(
                            domain
                        )
                    ),
                )
            )

        return output
