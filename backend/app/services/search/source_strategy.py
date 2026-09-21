"""Dynamic source strategy for open product search."""

import re
import unicodedata


def normalize_text(
    value: str | None,
) -> str:
    """Normalize Vietnamese text for deterministic matching."""

    if not value:
        return ""

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
        if unicodedata.category(char)
        != "Mn"
    )

    value = value.replace(
        "đ",
        "d",
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


SOURCE_GROUPS: tuple[
    tuple[
        tuple[str, ...],
        tuple[str, ...],
    ],
    ...,
] = (
    (
        (
            "dien thoai",
            "smartphone",
            "laptop",
            "tablet",
            "macbook",
            "iphone",
            "tai nghe",
            "dong ho thong minh",
            "smartwatch",
        ),
        (
            "thegioididong.com",
            "cellphones.com.vn",
            "fptshop.com.vn",
        ),
    ),

    (
        (
            "may tinh",
            "card do hoa",
            "gpu",
            "cpu",
            "ram",
            "ssd",
            "man hinh",
            "ban phim",
            "chuot",
            "gaming",
            "linh kien",
        ),
        (
            "phongvu.vn",
            "gearvn.com",
            "cellphones.com.vn",
        ),
    ),

    (
        (
            "tu lanh",
            "may giat",
            "tivi",
            "television",
            "smart tv",
            "tv",
            "dieu hoa",
            "may lanh",
            "noi chien",
            "may hut bui",
            "robot hut bui",
            "may loc khong khi",
            "may loc nuoc",
            "may pha ca phe",
            "gia dung",
        ),
        (
            "dienmayxanh.com",
            "nguyenkim.com",
            "mediamart.vn",
        ),
    ),

    (
        (
            "ao ",
            "quan ",
            "giay",
            "dep",
            "tui xach",
            "thoi trang",
            "vali",
        ),
        (
            "shopee.vn",
            "lazada.vn",
            "tiki.vn",
        ),
    ),

    (
        (
            "my pham",
            "kem duong",
            "son ",
            "sua rua mat",
            "serum",
            "cham soc da",
            "nuoc hoa",
        ),
        (
            "hasaki.vn",
            "watsons.vn",
            "guardian.com.vn",
        ),
    ),

    # MOTORCYCLE
    (
        (
            "xe may",
            "xe tay ga",
            "xe con tay",
            "air blade",
            "vision",
            "vario",
            "lead",
            "wave",
            "winner",
            "sirius",
            "janus",
            "grande",
            "exciter",
            "freego",
            "jupiter",
        ),
        (
            "honda.com.vn",
            "yamaha-motor.com.vn",
        ),
    ),

    (
        (
            "oto",
            "o to",
            "xe hoi",
            "sedan",
            "suv",
            "pickup",
        ),
        (
            "toyota.com.vn",
            "ford.com.vn",
            "hyundai.thanhcong.vn",
            "mazdamotors.vn",
        ),
    ),

    (
        (
            "vot cau long",
            "giay chay bo",
            "bong da",
            "the thao",
            "xe dap",
            "leu",
            "camping",
        ),
        (
            "decathlon.vn",
            "shopee.vn",
            "lazada.vn",
        ),
    ),

    (
        (
            "may khoan",
            "may cat",
            "may han",
            "may mai",
            "dung cu",
            "do nghe",
        ),
        (
            "bosch-professional.com",
            "makita.com.vn",
            "shopee.vn",
        ),
    ),
)


class SourceStrategy:
    """Resolve preferred commerce domains without restricting categories."""

    def preferred_domains(
        self,
        category: str | None,
    ) -> list[str]:
        """Return preferred domains for category."""

        normalized = normalize_text(
            category
        )

        if not normalized:
            return []

        output: list[str] = []

        for (
            keywords,
            domains,
        ) in SOURCE_GROUPS:

            if not any(
                keyword in normalized
                for keyword in keywords
            ):
                continue

            for domain in domains:
                if domain not in output:
                    output.append(
                        domain
                    )

            break

        return output


def is_motorcycle_category(
    category: str | None,
) -> bool:
    """Detect motorcycle category."""

    value = normalize_text(
        category
    )

    return any(
        keyword in value
        for keyword in (
            "xe may",
            "xe tay ga",
            "xe con tay",
            "air blade",
            "vision",
            "lead",
            "wave",
            "vario",
            "winner",
            "sirius",
            "janus",
            "grande",
            "exciter",
            "freego",
            "jupiter",
        )
    )


def commerce_search_terms(
    category: str,
) -> list[str]:
    """Purchase-intent queries."""

    clean = re.sub(
        r"\s+",
        " ",
        category,
    ).strip()

    return [
        (
            f"{clean} giá bán "
            "mua chính hãng Việt Nam"
        ),
        (
            f"{clean} sản phẩm "
            "giá VND Việt Nam"
        ),
    ]
