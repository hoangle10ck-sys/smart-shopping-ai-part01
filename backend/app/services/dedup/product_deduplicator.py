"""Deterministic canonical-product deduplication."""

from app.services.extraction.product_page_validator import identity_tokens, VARIANTS

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.normalization import (
    NormalizedProductCandidate,
)
from app.services.normalization.text_normalizer import (
    normalize_product_text,
)


class ProductDeduplicator:
    """Find or create canonical products without using an LLM."""

    def find_match(
        self,
        db: Session,
        candidate: NormalizedProductCandidate,
    ) -> Product | None:
        """Find an existing canonical product."""

        products = list(
            db.scalars(
                select(Product)
                .order_by(Product.id)
            )
        )

        def variant_signature(item):
            tokens = identity_tokens(item.name)
            capacities = {t for t in tokens if t.endswith(("gb", "tb")) and any(c.isdigit() for c in t)}
            specs = item.specifications or {}
            return (tokens & VARIANTS, capacities, str(specs.get("storage", "")).lower().replace(" ", ""),
                    str(specs.get('variant', '')).lower())
        signature = variant_signature(candidate)
        products = [p for p in products if variant_signature(p)[:2] == signature[:2]
                    and variant_signature(p)[3] == signature[3]
                    and (not signature[2] or not variant_signature(p)[2] or signature[2] == variant_signature(p)[2])]

        candidate_category = (
            normalize_product_text(
                candidate.category
            )
        )

        if (
            candidate.normalized_brand
            and candidate.normalized_model
        ):
            for product in products:
                existing_category = (
                    normalize_product_text(
                        product.category
                    )
                )

                if (
                    candidate_category
                    and existing_category
                    and candidate_category
                    != existing_category
                ):
                    continue

                existing_brand = (
                    normalize_product_text(
                        product.brand
                    )
                )

                existing_model = (
                    normalize_product_text(
                        product.model
                    )
                )

                if (
                    existing_brand
                    == candidate.normalized_brand
                    and existing_model
                    == candidate.normalized_model
                ):
                    return product

            return None

        for product in products:
            existing_category = (
                normalize_product_text(
                    product.category
                )
            )

            if (
                candidate_category
                and existing_category
                and candidate_category
                != existing_category
            ):
                continue

            existing_name = (
                product.normalized_name
                or normalize_product_text(
                    product.name
                )
            )

            if (
                existing_name
                == candidate.normalized_name
            ):
                return product

        return None

    def get_or_create(
        self,
        db: Session,
        candidate: NormalizedProductCandidate,
    ) -> tuple[Product, bool]:
        """Return canonical product and creation state."""

        product = self.find_match(
            db,
            candidate,
        )

        if product is not None:
            self._merge_evidence(
                product,
                candidate,
            )

            db.flush()

            return product, False

        product = Product(
            name=candidate.name,
            category=candidate.category,
            brand=candidate.brand,
            model=candidate.model,
            normalized_name=(
                candidate.normalized_name
            ),
            image_url=None,
            rating=candidate.rating,
            review_count=(
                candidate.review_count
            ),
            specifications=dict(
                candidate.specifications
            ),
            pros=[],
            cons=[],
        )

        db.add(product)

        db.flush()

        return product, True

    def _merge_evidence(
        self,
        product: Product,
        candidate: NormalizedProductCandidate,
    ) -> None:
        """Merge available deterministic evidence."""

        if (
            not product.name
            and candidate.name
        ):
            product.name = candidate.name

        if (
            not product.category
            and candidate.category
        ):
            product.category = (
                candidate.category
            )

        if (
            not product.normalized_name
            and candidate.normalized_name
        ):
            product.normalized_name = (
                candidate.normalized_name
            )

        if (
            not product.brand
            and candidate.brand
        ):
            product.brand = candidate.brand

        if (
            not product.model
            and candidate.model
        ):
            product.model = candidate.model

        if (
            product.rating is None
            and candidate.rating is not None
        ):
            product.rating = (
                candidate.rating
            )

        if (
            candidate.review_count
            is not None
        ):
            current_count = (
                product.review_count
            )

            if (
                current_count is None
                or candidate.review_count
                > current_count
            ):
                product.review_count = (
                    candidate.review_count
                )

                if (
                    candidate.rating
                    is not None
                ):
                    product.rating = (
                        candidate.rating
                    )

        merged_specs = dict(
            product.specifications
            or {}
        )

        for (
            key,
            value,
        ) in candidate.specifications.items():
            if (
                key not in merged_specs
                or not merged_specs[key]
            ):
                merged_specs[key] = value

        product.specifications = (
            merged_specs
        )
