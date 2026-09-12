"""Deterministic product-candidate normalization."""

import re

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


# Explicit product-type words only: a feature (mic, RAM, camera specs) does not
# establish the product's category. Ambiguous titles stay unknown.
PRODUCT_CATEGORY_ALIASES = {
    "laptop": ("laptop", "notebook", "may tinh xach tay", "macbook"),
    "tai nghe": ("tai nghe", "headphone", "headphones", "headset", "earphone", "earphones", "earbuds"),
    "điện thoại": ("dien thoai", "smartphone", "phone", "iphone"),
    "chuột": ("chuot", "mouse"),
    "bàn phím": ("ban phim", "keyboard"),
    "màn hình": ("man hinh", "monitor"),
    "máy tính bảng": ("may tinh bang", "tablet", "ipad"),
    "đồng hồ thông minh": ("dong ho thong minh", "smartwatch", "apple watch"),
    "loa": ("loa", "speaker"),
    "tivi": ("tivi", "tv"),
    "máy ảnh": ("may anh", "camera", "dslr", "mirrorless"),
    "máy giặt": ("may giat", "washing machine"),
    "tủ lạnh": ("tu lanh", "refrigerator"),
    "điều hòa": ("dieu hoa", "may lanh", "air conditioner"),
    "máy lọc không khí": ("may loc khong khi", "air purifier"),
    "nồi chiên không dầu": ("noi chien khong dau", "air fryer"),
    "nồi cơm điện": ("noi com dien", "rice cooker"),
    "máy hút bụi": ("may hut bui", "robot hut bui", "vacuum cleaner"),
    "máy khoan": ("may khoan", "drill"),
    "giày": ("giay", "sneaker", "shoes"),
    "quần áo": ("quan ao", "ao thun", "ao khoac", "quan jean", "dam", "vay"),
    "mỹ phẩm": ("my pham", "son", "kem chong nang", "serum", "sua rua mat"),
    "xe máy": ("xe may", "motorcycle", "motorbike", "scooter"),
    "ô tô": ("o to", "oto", "xe hoi", "car", "suv", "sedan"),
    "xe đạp": ("xe dap", "bicycle"),
}


def infer_product_category(name: str | None, explicit_category: str | None = None) -> str | None:
    """Use a source category or an unambiguous product name; otherwise unknown."""
    explicit = normalize_display_text(explicit_category)
    if explicit:
        key = normalize_product_text(explicit)
        for category, aliases in PRODUCT_CATEGORY_ALIASES.items():
            if key == normalize_product_text(category) or key in aliases:
                return category
        # A source may explicitly describe a category outside our vocabulary.
        return explicit
    text = normalize_product_text(name) or ""
    matches = [category for category, aliases in PRODUCT_CATEGORY_ALIASES.items()
               if any(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text) for alias in aliases)]
    return matches[0] if len(matches) == 1 else None


class ProductNormalizer:
    """Convert extracted raw product data into normalized data."""

    def normalize(
        self,
        candidate: RawProductCandidateData,
        *,
        category: str | None = None,
    ) -> NormalizedProductCandidate | None:
        """Normalize product evidence. Legacy category hint is intentionally ignored."""

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
            category=infer_product_category(candidate.name, candidate.category),
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
