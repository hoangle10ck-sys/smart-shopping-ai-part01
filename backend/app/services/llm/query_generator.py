"""Universal deterministic search-query generator."""

from app.core.config import (
    get_settings,
)

from app.schemas.requirement import (
    RequirementData,
)

from app.services.search.source_strategy import (
    SourceStrategy,
    commerce_search_terms,
    is_motorcycle_category,
)


class QueryGenerator:
    """Generate purchase-oriented product search queries."""

    def __init__(
        self,
        max_queries: int | None = None,
    ) -> None:

        settings = get_settings()

        self.max_queries = (
            max_queries
            if max_queries is not None
            else settings.max_search_queries
        )

        self.source_strategy = (
            SourceStrategy()
        )


    @staticmethod
    def _budget_text(
        requirement: RequirementData,
    ) -> str:

        budget_min = (
            requirement.budget_min
        )

        budget_max = (
            requirement.budget_max
        )

        if (
            budget_min is not None
            and budget_max is not None
        ):
            return (
                f"giá từ {budget_min} "
                f"đến {budget_max} VND"
            )

        if budget_max is not None:
            return (
                f"giá dưới {budget_max} VND"
            )

        if budget_min is not None:
            return (
                f"giá từ {budget_min} VND"
            )

        return ""


    @staticmethod
    def _requirement_text(
        requirement: RequirementData,
    ) -> str:

        parts: list[str] = []

        for item in (
            requirement.requirements
        ):
            name = str(
                item.name
            ).strip()

            value = str(
                item.value
            ).strip()

            if name and value:
                parts.append(
                    f"{name} {value}"
                )

        return " ".join(
            parts
        )


    @staticmethod
    def _join(
        *parts: str,
    ) -> str:

        return " ".join(
            part.strip()
            for part in parts
            if part
            and part.strip()
        )


    def generate(
        self,
        requirement: RequirementData,
    ) -> list[str]:

        category = (
            requirement.category
            or ""
        ).strip()

        if not category:
            return []


        budget = (
            self._budget_text(
                requirement
            )
        )

        purpose = " ".join(
            item.strip()
            for item
            in requirement.purpose
            if item.strip()
        )

        brands = [
            item.strip()
            for item
            in requirement.brands
            if item.strip()
        ]

        criteria = (
            self._requirement_text(
                requirement
            )
        )


        candidates: list[str] = []


        # =====================================================
        # MOTORCYCLE
        # =====================================================

        if is_motorcycle_category(
            category
        ):
            normalized_brands = {
                brand.lower()
                for brand in brands
            }


            if (
                not brands
                or "honda"
                in normalized_brands
            ):
                candidates.append(
                    self._join(
                        "site:honda.com.vn",
                        "Honda xe máy",
                        "Vision Air Blade Lead Wave",
                        "giá bán sản phẩm",
                        budget,
                    )
                )


            if (
                not brands
                or "yamaha"
                in normalized_brands
            ):
                candidates.append(
                    self._join(
                        "site:yamaha-motor.com.vn",
                        "Yamaha xe máy",
                        "Janus Sirius Grande FreeGo Exciter",
                        "giá bán sản phẩm",
                        budget,
                    )
                )


            candidates.append(
                self._join(
                    brands[0]
                    if len(brands) == 1
                    else "",
                    "xe máy",
                    budget,
                    purpose,
                    criteria,
                    "giá bán chính hãng",
                    "Việt Nam",
                )
            )


            candidates.append(
                self._join(
                    "Honda Yamaha xe máy",
                    budget,
                    "Vision Air Blade Lead Wave",
                    "Janus Sirius Grande",
                    "giá bán",
                    "Việt Nam",
                )
            )

        else:
            # =================================================
            # GENERIC PRODUCTS
            # =================================================

            brand_text = " ".join(
                brands
            )

            product_phrase = (
                self._join(
                    brand_text,
                    category,
                )
            )

            candidates.append(
                self._join(
                    product_phrase,
                    budget,
                    purpose,
                    criteria,
                    "mua",
                    "giá bán",
                    "Việt Nam",
                )
            )

            for query in (
                commerce_search_terms(
                    product_phrase
                )
            ):
                candidates.append(
                    self._join(
                        query,
                        budget,
                        criteria,
                    )
                )

            preferred_domains = (
                self.source_strategy
                .preferred_domains(
                    category
                )
            )

            for domain in (
                preferred_domains
            ):
                candidates.append(
                    self._join(
                        f"site:{domain}",
                        product_phrase,
                        budget,
                        criteria,
                        "giá bán",
                    )
                )

            candidates.append(
                self._join(
                    product_phrase,
                    budget,
                    criteria,
                    "nơi bán",
                    "mua online",
                    "Việt Nam",
                )
            )


        # =====================================================
        # DEDUP
        # =====================================================

        output: list[str] = []

        seen: set[str] = set()

        for query in candidates:

            normalized = " ".join(
                query.split()
            ).strip()

            if not normalized:
                continue

            key = normalized.lower()

            if key in seen:
                continue

            seen.add(
                key
            )

            output.append(
                normalized
            )

            if (
                len(output)
                >= self.max_queries
            ):
                break

        return output