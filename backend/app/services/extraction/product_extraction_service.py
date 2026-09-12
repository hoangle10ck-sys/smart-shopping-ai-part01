"""Best-effort product extraction from search-result text."""

from __future__ import annotations

import re
import unicodedata

from app.schemas.search import (
    RawProductCandidateData,
    SearchSourceItem,
)
from app.services.search.source_filter import (
    looks_like_rental_source,
)
from app.services.normalization.product_normalizer import infer_product_category


# =============================================================
# LABELED DEMO FIELDS
# =============================================================


LABELED_FIELD_PATTERN = re.compile(
    r"""
    (?P<key>
        PRODUCT|
        CATEGORY|
        BRAND|
        MODEL|
        PRICE|
        RATING|
        REVIEWS|
        AVAILABILITY|
        SPECS
    )
    \s*:\s*
    (?P<value>.*?)
    (?=
        \s*\|\s*
        (?:
            PRODUCT|
            CATEGORY|
            BRAND|
            MODEL|
            PRICE|
            RATING|
            REVIEWS|
            AVAILABILITY|
            SPECS
        )
        \s*:
        |
        $
    )
    """,
    re.IGNORECASE
    | re.VERBOSE,
)


# =============================================================
# PRICE
# =============================================================


PRICE_PATTERNS = (
    # VND 43,681,000
    re.compile(
        r"""
        \b
        VND
        \s*
        \d{1,3}
        (?:[.,]\d{3})+
        \b
        """,
        re.IGNORECASE
        | re.VERBOSE,
    ),

    # 43.681.000đ
    # 43,681,000 VND
    re.compile(
        r"""
        \b
        \d{1,3}
        (?:[.,]\d{3})+
        \s*
        (?:
            VND|
            VNĐ|
            đ|
            ₫|
            d|
            Ä‘|
            â‚«
        )
        """,
        re.IGNORECASE
        | re.VERBOSE,
    ),

    # 43,5 triệu
    # 15 tr
    re.compile(
        r"""
        \b
        \d+
        (?:[.,]\d+)?
        \s*
        (?:
            triệu|
            trieu|
            triá»‡u|
            million|
            tr
        )
        (?:
            \s*
            (?:
                VND|
                VNĐ|
                đ|
                ₫|
                d|
                Ä‘|
                â‚«
            )
        )?
        """,
        re.IGNORECASE
        | re.VERBOSE,
    ),

    # 399K
    # 500 nghìn
    re.compile(
        r"""
        \b
        \d+
        (?:[.,]\d+)?
        \s*
        (?:
            k|
            nghìn|
            nghin|
            ngàn|
            ngan|
            nghĂ¬n|
            thousand
        )
        (?:
            \s*
            (?:
                VND|
                VNĐ|
                đ|
                ₫|
                d|
                Ä‘|
                â‚«
            )
        )?
        """,
        re.IGNORECASE
        | re.VERBOSE,
    ),
)


# =============================================================
# RATING / REVIEW
# =============================================================


RATING_PATTERN = re.compile(
    r"\b([0-5](?:[.,]\d+)?)\s*/\s*5\b",
    re.IGNORECASE,
)


REVIEW_PATTERN = re.compile(
    r"""
    (?:
        reviews?
        |
        đánh\s*giá
        |
        danh\s*gia
        |
        Ä‘Ă¡nh\s*giĂ¡
    )
    \s*[:\-]?\s*
    ([\d.,]+)
    """,
    re.IGNORECASE
    | re.VERBOSE,
)


# =============================================================
# BRANDS
# =============================================================


KNOWN_BRANDS = (
    "Honda",
    "Yamaha",
    "Apple",
    "Samsung",
    "Xiaomi",
    "Redmi",
    "OPPO",
    "Vivo",
    "Realme",
    "ASUS",
    "Acer",
    "Lenovo",
    "Dell",
    "HP",
    "MSI",
    "Sony",
    "JBL",
    "Logitech",
    "Anker",
    "Baseus",
)


MOTORCYCLE_BRANDS = {
    "honda",
    "yamaha",
}


# =============================================================
# MOTORCYCLE MODELS
#
# Specific names must appear before generic names.
# =============================================================


MOTORCYCLE_FAMILIES = (
    # HONDA
    "Super Cub C125",
    "CBR1000RR-R",
    "Africa Twin",
    "Gold Wing",

    "Wave RSX FI",
    "Wave Alpha",
    "Wave RSX",

    "Air Blade",

    "SH Mode",
    "SH 160i",
    "SH 150i",
    "SH 125i",

    "Winner X",

    "Future FI",
    "Future",

    "Vision",
    "Vario",
    "Lead",
    "Blade",

    "Monkey",
    "Rebel 500",
    "CBR150R",
    "CB150R",

    # YAMAHA
    "Sirius FI",
    "Sirius",

    "Janus",
    "Grande",
    "FreeGo",
    "Exciter",
    "Jupiter",
    "Latte",
    "NVX",

    "PG-1",

    "XSR 155",
    "MT-15",
    "MT-03",

    "YZF-R15",
    "Yamaha R15",
    "Yamaha R3",

    "XMAX 300",
    "NEO's",
)


KNOWN_PRODUCT_FAMILIES = (
    *MOTORCYCLE_FAMILIES,

    "iPhone",
    "MacBook",
    "Galaxy",

    "ThinkPad",
    "IdeaPad",
    "Vivobook",
    "Zenbook",
    "Aspire",

    "Redmi Note",
    "POCO",
)


# =============================================================
# STOP WORDS
# =============================================================


PHRASE_STOP_WORDS = {
    "price",
    "prices",
    "list",

    "review",
    "reviews",

    "spec",
    "specs",
    "specification",
    "specifications",

    "detail",
    "details",

    "for",
    "rent",
    "rental",

    "is",
    "are",
    "was",
    "were",

    "comes",
    "come",
    "with",

    "offers",
    "offer",

    "officially",

    "in",
    "at",
    "from",

    "has",
    "have",

    "motorcycle",
    "motorbike",
    "scooter",

    "smartphone",
    "phone",
    "laptop",

    "model",

    "gia",
    "bang",
    "danh",
    "mau",

    "san",
    "pham",

    "chi",
    "tiet",

    "example",

    "cong",
    "suat",

    "kich",
    "thuoc",

    "cap",
    "nhat",
}


# =============================================================
# GENERIC / ARTICLE MOTORCYCLE TITLES
# =============================================================


MOTORCYCLE_NOISE_MARKERS = {
    "xe may chi tiet",

    "chi tiet example",

    "chi tiet cong suat",

    "chi tiet 175 mm",

    "tiet kiem xang nhat hien nay",

    "phu hop di lam di hoc",

    "nhung xe may",

    "bang gia xe may",

    "danh sach xe may",

    "top xe may",

    "tu van mua xe",
}


# A Honda/Yamaha motorcycle for a few thousand VND is
# obviously a spec/dimension incorrectly interpreted as price.
MOTORCYCLE_PRICE_MIN = (
    5_000_000
)


# =============================================================
# TEXT NORMALIZATION
# =============================================================


def repair_common_mojibake(
    value: str,
) -> str:
    """Repair common UTF-8 display corruption for matching."""

    replacements = (
        (
            "Ä‘",
            "đ",
        ),
        (
            "â‚«",
            "₫",
        ),
        (
            "triá»‡u",
            "triệu",
        ),
        (
            "nghĂ¬n",
            "nghìn",
        ),
        (
            "Ä‘Ă¡nh giĂ¡",
            "đánh giá",
        ),
        (
            "háº¿t hĂ ng",
            "hết hàng",
        ),
        (
            "cĂ²n hĂ ng",
            "còn hàng",
        ),
        (
            "dung tĂch",
            "dung tích",
        ),
        (
            "cmÂ³",
            "cm³",
        ),
        (
            "báº£ng giĂ¡",
            "bảng giá",
        ),
    )

    for (
        source,
        target,
    ) in replacements:
        value = value.replace(
            source,
            target,
        )

    return value


def normalize_match_text(
    value: str | None,
) -> str:
    """Normalize Vietnamese text for deterministic matching."""

    if not value:
        return ""

    value = repair_common_mojibake(
        value
    )

    value = unicodedata.normalize(
        "NFD",
        value.lower(),
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

    value = re.sub(
        r"[^a-z0-9+./_-]+",
        " ",
        value,
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


# =============================================================
# DEMO SPECS
# =============================================================


def parse_specs(
    value: str | None,
) -> dict[str, str]:
    """Parse demo-style key=value specifications."""

    if not value:
        return {}

    output: dict[
        str,
        str,
    ] = {}

    for piece in value.split(
        ";"
    ):
        piece = (
            piece.strip()
        )

        if "=" not in piece:
            continue

        (
            key,
            raw_value,
        ) = piece.split(
            "=",
            maxsplit=1,
        )

        key = (
            key.strip()
        )

        raw_value = (
            raw_value.strip()
        )

        if (
            key
            and raw_value
        ):
            output[
                key
            ] = raw_value

    return output


# =============================================================
# PRICE EXTRACTION
# =============================================================


def find_price_text(
    text: str,
) -> str | None:
    """Extract a likely explicit VND purchase price."""

    if not text:
        return None

    for pattern in (
        PRICE_PATTERNS
    ):
        match = (
            pattern.search(
                text
            )
        )

        if match:
            return (
                match
                .group(0)
                .strip()
            )

    return None


def raw_price_to_vnd(
    value: str | None,
) -> int | None:
    """
    Best-effort price conversion.

    Only used for validation inside extraction.
    Final normalization still belongs to PriceParser.
    """

    if not value:
        return None

    normalized = (
        normalize_match_text(
            value
        )
    )


    # ---------------------------------------------------------
    # MILLION
    # ---------------------------------------------------------

    million_match = re.search(
        r"""
        (\d+(?:[.,]\d+)?)
        \s*
        (?:
            trieu|
            million|
            tr
        )
        \b
        """,
        normalized,
        re.IGNORECASE
        | re.VERBOSE,
    )

    if million_match:
        try:
            number = float(
                million_match
                .group(1)
                .replace(
                    ",",
                    ".",
                )
            )

        except ValueError:
            return None

        return round(
            number
            * 1_000_000
        )


    # ---------------------------------------------------------
    # THOUSAND
    # ---------------------------------------------------------

    thousand_match = re.search(
        r"""
        (\d+(?:[.,]\d+)?)
        \s*
        (?:
            k|
            nghin|
            ngan|
            thousand
        )
        \b
        """,
        normalized,
        re.IGNORECASE
        | re.VERBOSE,
    )

    if thousand_match:
        try:
            number = float(
                thousand_match
                .group(1)
                .replace(
                    ",",
                    ".",
                )
            )

        except ValueError:
            return None

        return round(
            number
            * 1_000
        )


    # ---------------------------------------------------------
    # INTEGER
    # ---------------------------------------------------------

    digits = re.sub(
        r"[^\d]",
        "",
        value,
    )

    if not digits:
        return None

    try:
        return int(
            digits
        )

    except ValueError:
        return None


# =============================================================
# BRAND
# =============================================================


def infer_brand(
    text: str,
) -> str | None:
    """Infer first known brand from free text."""

    best_match: (
        tuple[
            int,
            str,
        ]
        | None
    ) = None

    for brand in (
        KNOWN_BRANDS
    ):
        match = re.search(
            rf"""
            (?<!\w)
            {re.escape(brand)}
            (?!\w)
            """,
            text,
            re.IGNORECASE
            | re.VERBOSE,
        )

        if match is None:
            continue

        candidate = (
            match.start(),
            brand,
        )

        if (
            best_match
            is None
            or candidate[0]
            < best_match[0]
        ):
            best_match = (
                candidate
            )

    if (
        best_match
        is None
    ):
        return None

    return (
        best_match[1]
    )


# =============================================================
# PRODUCT NAME CLEANING
# =============================================================


def normalize_product_phrase(
    value: str,
) -> str:
    """Clean inferred product names."""

    value = (
        repair_common_mojibake(
            value
        )
    )

    # Air Blade 125cc -> Air Blade 125
    value = re.sub(
        r"""
        (?<=\d)
        \s*
        cc
        \b
        """,
        "",
        value,
        flags=(
            re.IGNORECASE
            | re.VERBOSE
        ),
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip(
        " ,.;:|-"
    )


def normalize_phrase_token(
    value: str,
) -> str:
    """Normalize token for stop-word matching."""

    return normalize_match_text(
        value
    )


# =============================================================
# GENERIC NAME EXTRACTION
# =============================================================


def extract_phrase_after_match(
    text: str,
    *,
    start: int,
    prefix: str,
    max_tokens: int = 6,
) -> str | None:
    """Read plausible model tokens after a brand/family."""

    remainder = (
        text[
            start:
        ]
    )

    tokens = re.findall(
        r"""
        [A-Za-zÀ-ỹ0-9]
        [A-Za-zÀ-ỹ0-9+./_-]*
        """,
        remainder,
        re.VERBOSE,
    )

    collected: list[
        str
    ] = []

    for token in tokens:
        normalized = (
            normalize_phrase_token(
                token
            )
        )

        if (
            normalized
            in PHRASE_STOP_WORDS
        ):
            break

        collected.append(
            token
        )

        if (
            len(
                collected
            )
            >= max_tokens
        ):
            break

    if not collected:
        return None

    return normalize_product_phrase(
        " ".join(
            [
                prefix,
                *collected,
            ]
        )
    )


def infer_brand_product_name(
    text: str,
) -> str | None:
    """Infer a generic product name beginning with a known brand."""

    matches: list[
        tuple[
            int,
            str,
            int,
        ]
    ] = []

    for brand in (
        KNOWN_BRANDS
    ):
        match = re.search(
            rf"""
            (?<!\w)
            {re.escape(brand)}
            (?!\w)
            """,
            text,
            re.IGNORECASE
            | re.VERBOSE,
        )

        if (
            match
            is not None
        ):
            matches.append(
                (
                    match.start(),
                    brand,
                    match.end(),
                )
            )

    if not matches:
        return None

    matches.sort(
        key=lambda item: (
            item[0]
        )
    )

    (
        _,
        brand,
        end,
    ) = matches[0]

    return extract_phrase_after_match(
        text,
        start=end,
        prefix=brand,
    )


# =============================================================
# MOTORCYCLE NAME
# =============================================================


def motorcycle_suffix(
    text: str,
    *,
    family_end: int,
) -> str:
    """Read only safe motorcycle model/year/trim tokens."""

    remainder = (
        text[
            family_end:
        ]
    )

    raw_tokens = re.findall(
        r"""
        [A-Za-zÀ-ỹ0-9]
        [A-Za-zÀ-ỹ0-9+./_-]*
        """,
        remainder,
        re.VERBOSE,
    )

    output: list[
        str
    ] = []

    allowed_words = {
        "fi",
        "abs",
        "cbs",
        "hybrid",
        "standard",
        "special",
        "premium",
        "deluxe",
        "sport",
        "sports",
        "sp",
        "v3",
    }

    for token in (
        raw_tokens[
            :4
        ]
    ):
        normalized = (
            normalize_match_text(
                token
            )
        )

        if not normalized:
            continue

        if (
            normalized
            in PHRASE_STOP_WORDS
        ):
            break


        # 125, 160, 2025, 125cc
        if re.fullmatch(
            r"\d{2,4}(?:cc)?",
            normalized,
        ):
            token = re.sub(
                r"cc$",
                "",
                token,
                flags=(
                    re.IGNORECASE
                ),
            )

            output.append(
                token
            )

            continue


        # FI / ABS / CBS...
        if (
            normalized
            in allowed_words
        ):
            output.append(
                token
            )

            continue


        # Natural article text begins.
        break

    return " ".join(
        output
    ).strip()


def infer_motorcycle_product_name(
    title: str,
    content: str,
    brand: str | None,
) -> str | None:
    """
    Infer actual motorcycle model.

    Examples:
    - Honda Xe Máy Chi tiết Wave RSX
      -> Honda Wave RSX

    - Yamaha Sirius 2025 quốc dân tiết kiệm
      -> Yamaha Sirius 2025

    - Honda Xe Máy Chi tiết Công suất
      -> None
    """

    for source_text in (
        title,
        content,
        f"{title}\n{content}",
    ):
        if not source_text:
            continue

        for family in (
            MOTORCYCLE_FAMILIES
        ):
            match = re.search(
                rf"""
                (?<!\w)
                {re.escape(family)}
                (?!\w)
                """,
                source_text,
                re.IGNORECASE
                | re.VERBOSE,
            )

            if (
                match
                is None
            ):
                continue

            inferred_brand = (
                brand
                or infer_brand(
                    source_text
                )
            )

            prefix = (
                f"{inferred_brand} {family}"
                if inferred_brand
                else family
            )

            suffix = (
                motorcycle_suffix(
                    source_text,
                    family_end=(
                        match.end()
                    ),
                )
            )

            name = (
                f"{prefix} {suffix}"
                if suffix
                else prefix
            )

            return (
                normalize_product_phrase(
                    name
                )
            )

    return None


# =============================================================
# GENERIC FAMILY
# =============================================================


def infer_family_product_name(
    text: str,
) -> str | None:
    """Infer product name from a known family."""

    matches: list[
        tuple[
            int,
            str,
            int,
        ]
    ] = []

    for family in (
        KNOWN_PRODUCT_FAMILIES
    ):
        match = re.search(
            rf"""
            (?<!\w)
            {re.escape(family)}
            (?!\w)
            """,
            text,
            re.IGNORECASE
            | re.VERBOSE,
        )

        if (
            match
            is not None
        ):
            matches.append(
                (
                    match.start(),
                    family,
                    match.end(),
                )
            )

    if not matches:
        return None

    matches.sort(
        key=lambda item: (
            item[0]
        )
    )

    (
        _,
        family,
        end,
    ) = matches[0]

    inferred = (
        extract_phrase_after_match(
            text,
            start=end,
            prefix=family,
            max_tokens=4,
        )
    )

    return (
        inferred
        or family
    )


# =============================================================
# TITLE CLEANING
# =============================================================


def clean_title(
    title: str | None,
) -> str | None:
    """Clean common article/search wording from title."""

    if not title:
        return None

    value = (
        repair_common_mojibake(
            title.strip()
        )
    )

    cut_patterns = (
        r"\bprice\s+list\b",
        r"\bprices?\b",

        r"\bbảng\s+giá\b",
        r"\bbang\s+gia\b",

        r"\breview\b",

        r"\bspecifications?\b",

        r"\bfor\s+rent\b",
        r"\brental\b",
    )

    for pattern in (
        cut_patterns
    ):
        match = re.search(
            pattern,
            value,
            re.IGNORECASE,
        )

        if match:
            value = (
                value[
                    :match.start()
                ]
            )

    value = (
        normalize_product_phrase(
            value
        )
    )

    return (
        value
        or None
    )


# =============================================================
# MODEL
# =============================================================


def infer_model(
    name: str | None,
    brand: str | None,
) -> str | None:
    """Infer model from product name."""

    if not name:
        return None

    value = (
        name.strip()
    )

    if brand:
        value = re.sub(
            rf"""
            ^\s*
            {re.escape(brand)}
            \s*
            """,
            "",
            value,
            count=1,
            flags=(
                re.IGNORECASE
                | re.VERBOSE
            ),
        )

    value = re.sub(
        r"""
        \b
        (?:
            motorcycle|
            motorbike|
            scooter|
            smartphone|
            laptop
        )
        \b
        .*$
        """,
        "",
        value,
        flags=(
            re.IGNORECASE
            | re.VERBOSE
        ),
    )

    value = (
        normalize_product_phrase(
            value
        )
    )

    return (
        value
        or None
    )


# =============================================================
# AVAILABILITY
# =============================================================


def infer_availability(
    text: str,
) -> str | None:
    """Infer simple availability state."""

    normalized = (
        normalize_match_text(
            text
        )
    )

    if any(
        marker
        in normalized
        for marker in (
            "out of stock",
            "het hang",
            "sold out",
            "unavailable",
        )
    ):
        return (
            "out_of_stock"
        )

    if any(
        marker
        in normalized
        for marker in (
            "in stock",
            "con hang",
            "available",
        )
    ):
        return (
            "in_stock"
        )

    return None


# =============================================================
# BASIC SPECS
# =============================================================


def extract_basic_specs(
    text: str,
) -> dict[str, str]:
    """Extract basic specs from natural web snippets."""

    repaired = (
        repair_common_mojibake(
            text
        )
    )

    specs: dict[
        str,
        str,
    ] = {}


    patterns = {
        "ram": re.compile(
            r"""
            \bRAM
            \s*[:\-]?\s*
            (\d+\s*GB)
            \b
            """,
            re.IGNORECASE
            | re.VERBOSE,
        ),

        "storage": re.compile(
            r"""
            \b
            (?:
                SSD|
                storage|
                bộ\ nhớ
            )
            \s*[:\-]?\s*
            (
                \d+
                \s*
                (?:
                    GB|
                    TB
                )
            )
            \b
            """,
            re.IGNORECASE
            | re.VERBOSE,
        ),

        "battery": re.compile(
            r"""
            \b
            (?:
                battery|
                pin
            )
            \s*[:\-]?\s*
            (
                \d+
                (?:[.,]\d+)?
                \s*
                (?:
                    mAh|
                    hours?|
                    hrs?|
                    h
                )
            )
            \b
            """,
            re.IGNORECASE
            | re.VERBOSE,
        ),

        "engine_displacement": re.compile(
            r"""
            \b
            (?:
                engine\ displacement|
                dung\ tích
            )
            \s*[:|\-]?\s*
            (
                \d+
                (?:[.,]\d+)?
                \s*
                (?:
                    cc|
                    cm3|
                    cm³
                )
            )
            \b
            """,
            re.IGNORECASE
            | re.VERBOSE,
        ),

        "fuel_consumption": re.compile(
            r"""
            \b
            (?:
                fuel\ consuming|
                fuel\ consumption|
                mức\ tiêu\ thụ\ nhiên\ liệu
            )
            \s*[:|\-]?\s*
            (
                \d+
                (?:[.,]\d+)?
                \s*
                (?:
                    km/liter|
                    km/l|
                    l/100km
                )
            )
            \b
            """,
            re.IGNORECASE
            | re.VERBOSE,
        ),
    }


    for (
        key,
        pattern,
    ) in patterns.items():
        match = (
            pattern.search(
                repaired
            )
        )

        if match:
            specs[
                key
            ] = (
                match
                .group(1)
                .strip()
            )

    return specs


# =============================================================
# MOTORCYCLE VALIDATION
# =============================================================


def is_motorcycle_context(
    *,
    brand: str | None,
    title: str,
    content: str,
) -> bool:
    """Detect Honda/Yamaha motorcycle result."""

    if (
        brand
        and brand.lower()
        in MOTORCYCLE_BRANDS
    ):
        return True

    normalized = (
        normalize_match_text(
            f"{title} {content}"
        )
    )

    return any(
        normalize_match_text(
            family
        )
        in normalized
        for family
        in MOTORCYCLE_FAMILIES
    )


def looks_like_generic_motorcycle_page(
    title: str,
) -> bool:
    """Detect generic/article/specification motorcycle pages."""

    normalized = (
        normalize_match_text(
            title
        )
    )

    return any(
        marker
        in normalized
        for marker
        in MOTORCYCLE_NOISE_MARKERS
    )


def validate_motorcycle_price(
    price_text: str | None,
) -> str | None:
    """
    Remove obviously impossible motorcycle prices.

    4.000đ / 100.000đ / 11.300đ
    are almost certainly specs, dimensions or other values.
    """

    if not price_text:
        return None

    value = (
        raw_price_to_vnd(
            price_text
        )
    )

    if (
        value
        is None
    ):
        return None

    if (
        value
        < MOTORCYCLE_PRICE_MIN
    ):
        return None

    return (
        price_text
    )


# =============================================================
# EXTRACTION SERVICE
# =============================================================


class ProductExtractionService:
    """Extract raw product fields without normalization or ranking."""

    def extract(
        self,
        source: SearchSourceItem,
    ) -> RawProductCandidateData | None:
        """Extract one possible product from a search source."""

        title = (
            source.title
            or ""
        ).strip()

        text = (
            source.content
            or ""
        ).strip()


        # -----------------------------------------------------
        # EMPTY
        # -----------------------------------------------------

        if (
            not text
            and not title
        ):
            return None


        # -----------------------------------------------------
        # RENTAL
        # -----------------------------------------------------

        if looks_like_rental_source(
            title=title,
            url=source.url,
            content=text,
        ):
            return None


        # -----------------------------------------------------
        # LABELED FIELDS
        # -----------------------------------------------------

        fields: dict[
            str,
            str,
        ] = {}

        for match in (
            LABELED_FIELD_PATTERN.finditer(
                text
            )
        ):
            key = (
                match.group(
                    "key"
                )
                .strip()
                .upper()
            )

            value = (
                match.group(
                    "value"
                )
                .strip()
            )

            fields[
                key
            ] = value


        combined_text = "\n".join(
            value
            for value
            in (
                title,
                text,
            )
            if value
        )


        # -----------------------------------------------------
        # BRAND
        # -----------------------------------------------------

        brand = (
            fields.get(
                "BRAND"
            )
            or infer_brand(
                combined_text
            )
        )


        # -----------------------------------------------------
        # PRODUCT TYPE
        # -----------------------------------------------------

        motorcycle_context = (
            is_motorcycle_context(
                brand=brand,
                title=title,
                content=text,
            )
        )


        # -----------------------------------------------------
        # NAME
        # -----------------------------------------------------

        if motorcycle_context:

            labeled_name = (
                fields.get(
                    "PRODUCT"
                )
            )

            motorcycle_name = (
                infer_motorcycle_product_name(
                    title=title,
                    content=text,
                    brand=brand,
                )
            )


            # IMPORTANT:
            #
            # For Honda/Yamaha we DO NOT use generic:
            #
            #   Honda Xe Máy Chi tiết Công suất
            #   Honda Xe Máy Chi tiết 175 mm
            #
            # as a product name.
            #
            name = (
                labeled_name
                or motorcycle_name
            )


            if (
                name
                is None
            ):
                return None


            if (
                looks_like_generic_motorcycle_page(
                    title
                )
                and motorcycle_name
                is None
                and labeled_name
                is None
            ):
                return None

        else:
            brand_product_name = (
                infer_brand_product_name(
                    combined_text
                )
            )

            family_product_name = (
                infer_family_product_name(
                    combined_text
                )
            )

            name = (
                fields.get(
                    "PRODUCT"
                )
                or brand_product_name
                or family_product_name
                or clean_title(
                    title
                )
            )


        # -----------------------------------------------------
        # PRICE
        # -----------------------------------------------------

        price_text = (
            fields.get(
                "PRICE"
            )
        )

        if (
            price_text
            is None
        ):
            price_text = (
                find_price_text(
                    text
                )
                or find_price_text(
                    title
                )
            )


        # Honda/Yamaha motorcycle:
        # reject fake prices like 4.000đ / 11.300đ / 100.000đ.
        if (
            motorcycle_context
        ):
            price_text = (
                validate_motorcycle_price(
                    price_text
                )
            )


        # -----------------------------------------------------
        # RATING
        # -----------------------------------------------------

        rating_text = (
            fields.get(
                "RATING"
            )
        )

        if (
            rating_text
            is None
        ):
            rating_match = (
                RATING_PATTERN.search(
                    combined_text
                )
            )

            if rating_match:
                rating_text = (
                    rating_match
                    .group(0)
                )


        # -----------------------------------------------------
        # REVIEWS
        # -----------------------------------------------------

        review_count_text = (
            fields.get(
                "REVIEWS"
            )
        )

        if (
            review_count_text
            is None
        ):
            review_match = (
                REVIEW_PATTERN.search(
                    combined_text
                )
            )

            if review_match:
                review_count_text = (
                    review_match
                    .group(1)
                )


        # -----------------------------------------------------
        # MODEL
        # -----------------------------------------------------

        model = (
            fields.get(
                "MODEL"
            )
            or infer_model(
                name,
                brand,
            )
        )


        # -----------------------------------------------------
        # SPECS
        # -----------------------------------------------------

        specifications = (
            parse_specs(
                fields.get(
                    "SPECS"
                )
            )
        )

        inferred_specs = (
            extract_basic_specs(
                combined_text
            )
        )

        for (
            key,
            value,
        ) in (
            inferred_specs.items()
        ):
            specifications.setdefault(
                key,
                value,
            )


        # -----------------------------------------------------
        # AVAILABILITY
        # -----------------------------------------------------

        availability = (
            fields.get(
                "AVAILABILITY"
            )
            or infer_availability(
                combined_text
            )
        )


        # -----------------------------------------------------
        # PRODUCT EVIDENCE
        # -----------------------------------------------------

        if (
            motorcycle_context
        ):
            # Motorcycle must have an actual identified model.
            has_product_evidence = (
                name
                is not None
                and model
                is not None
            )

        else:
            # Keep generic/open-category behavior for
            # laptops, headphones, phones, appliances, etc.
            has_product_evidence = any(
                [
                    price_text
                    is not None,

                    brand
                    is not None,

                    model
                    is not None,

                    bool(
                        specifications
                    ),
                ]
            )


        if (
            name
            is None
            or not
            has_product_evidence
        ):
            return None


        # -----------------------------------------------------
        # RESULT
        # -----------------------------------------------------

        return (
            RawProductCandidateData(
                name=name,
                category=infer_product_category(
                    fields.get("PRODUCT") or title,
                    fields.get("CATEGORY") or ("xe máy" if motorcycle_context else None),
                ),

                brand=brand,

                model=model,

                price_text=(
                    price_text
                ),

                rating_text=(
                    rating_text
                ),

                review_count_text=(
                    review_count_text
                ),

                availability=(
                    availability
                ),

                product_url=(
                    source.url
                ),

                source_domain=(
                    source.domain
                ),

                image_url=(
                    source.image_url
                ),

                specifications=(
                    specifications
                ),

                raw_text=(
                    text
                    or None
                ),
            )
        )
