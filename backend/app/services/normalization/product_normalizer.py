"""Deterministic product-candidate normalization."""

from app.schemas.normalization import (
    NormalizedProductCandidate,
)
from app.schemas.search import (
    RawProductCandidateData,
)
from app.services.normalization.price_parser import (
    parse_price,
)
from app.services.normalization.rating_parser import (
    parse_rating,
)
from app.services.normalization.review_count_parser import (
    parse_review_count,
)
from app.services.normalization.text_normalizer import (
    normalize_display_text,
    normalize_product_text,
)


class ProductNormalizer:
    """Convert extracted raw product data into normalized data."""

    def normalize(
        self,
        candidate: RawProductCandidateData,
        *,
        category: str | None = None,
    ) -> NormalizedProductCandidate | None:
        """Normalize one raw product candidate."""

        name = normalize_display_text(
            candidate.name
        )

        if name is None:
            return None

        normalized_name = normalize_product_text(
            name
        )

        if normalized_name is None:
            return None

        brand = normalize_display_text(
            candidate.brand
        )

        model = normalize_display_text(
            candidate.model
        )

        normalized_specs = {
            str(key).strip().lower(): (
                str(value).strip()
            )
            for key, value
            in candidate.specifications.items()
            if str(key).strip()
            and str(value).strip()
        }

        return NormalizedProductCandidate(
            name=name,
            normalized_name=normalized_name,
            category=normalize_display_text(
                category
            ),
            brand=brand,
            normalized_brand=(
                normalize_product_text(
                    brand
                )
            ),
            model=model,
            normalized_model=(
                normalize_product_text(
                    model
                )
            ),
            price=parse_price(
                candidate.price_text
            ),
            currency="VND",
            rating=parse_rating(
                candidate.rating_text
            ),
            review_count=parse_review_count(
                candidate.review_count_text
            ),
            availability=(
                normalize_display_text(
                    candidate.availability
                )
            ),
            product_url=candidate.product_url,
            source_domain=(
                candidate.source_domain
            ),
            specifications=normalized_specs,
            raw_price_text=(
                candidate.price_text
            ),
            raw_rating_text=(
                candidate.rating_text
            ),
            raw_review_count_text=(
                candidate.review_count_text
            ),
        )