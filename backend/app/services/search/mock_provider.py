"""Deterministic search provider used by Demo Mode."""

import unicodedata

from app.services.search.base import (
    SearchProvider,
    SearchResult,
)


def normalize_text(text: str) -> str:
    """Normalize Vietnamese text for simple keyword matching."""

    value = unicodedata.normalize(
        "NFD",
        text.lower(),
    )

    value = "".join(
        char
        for char in value
        if unicodedata.category(char) != "Mn"
    )

    return value.replace("đ", "d")


PHONE_RESULTS = [
    SearchResult(
        title="DemoPhone X5 5G",
        url=(
            "https://demo-store.example/"
            "dien-thoai/demophone-x5"
        ),
        content=(
            "PRODUCT: DemoPhone X5 5G | "
            "BRAND: DemoPhone | "
            "MODEL: X5 | "
            "PRICE: 4.790.000đ | "
            "RATING: 4.6/5 | "
            "REVIEWS: 128 | "
            "AVAILABILITY: in_stock | "
            "SPECS: camera=50MP; "
            "battery=5000mAh; "
            "weight=188g"
        ),
        score=0.94,
    ),
    SearchResult(
        title="Nova Mobile A20",
        url=(
            "https://mobile-demo.example/"
            "products/nova-a20"
        ),
        content=(
            "PRODUCT: Nova Mobile A20 | "
            "BRAND: Nova | "
            "MODEL: A20 | "
            "PRICE: 4.490.000 VND | "
            "RATING: 4,5/5 | "
            "REVIEWS: 86 | "
            "AVAILABILITY: in_stock | "
            "SPECS: camera=64MP; "
            "battery=5100mAh; "
            "weight=195g"
        ),
        score=0.90,
    ),
    SearchResult(
        title="PixelDemo G8",
        url=(
            "https://tech-demo.example/"
            "phone/pixeldemo-g8"
        ),
        content=(
            "PRODUCT: PixelDemo G8 | "
            "BRAND: PixelDemo | "
            "MODEL: G8 | "
            "PRICE: 4.950.000đ | "
            "RATING: 4.7/5 | "
            "REVIEWS: 231 | "
            "AVAILABILITY: in_stock | "
            "SPECS: camera=50MP OIS; "
            "battery=4800mAh; "
            "weight=181g"
        ),
        score=0.89,
    ),
]


HEADPHONE_RESULTS = [
    SearchResult(
        title="SoundDemo H20 Wireless",
        url=(
            "https://audio-demo.example/"
            "headphones/sounddemo-h20"
        ),
        content=(
            "PRODUCT: SoundDemo H20 Wireless | "
            "BRAND: SoundDemo | "
            "MODEL: H20 | "
            "PRICE: 449.000đ | "
            "RATING: 4.6/5 | "
            "REVIEWS: 310 | "
            "AVAILABILITY: in_stock | "
            "SPECS: microphone=ENC; "
            "battery=40 hours"
        ),
        score=0.95,
    ),
    SearchResult(
        title="StudyBeat M5",
        url=(
            "https://audio-shop.example/"
            "tai-nghe/studybeat-m5"
        ),
        content=(
            "PRODUCT: StudyBeat M5 | "
            "BRAND: StudyBeat | "
            "MODEL: M5 | "
            "PRICE: 399K | "
            "RATING: 4,4/5 | "
            "REVIEWS: 155 | "
            "AVAILABILITY: in_stock | "
            "SPECS: microphone=dual mic; "
            "battery=35 hours"
        ),
        score=0.91,
    ),
    SearchResult(
        title="LearnSound Pro",
        url=(
            "https://demo-market.example/"
            "learnsound-pro"
        ),
        content=(
            "PRODUCT: LearnSound Pro | "
            "BRAND: LearnSound | "
            "MODEL: Pro | "
            "PRICE: 499.000 VND | "
            "RATING: 4.5/5 | "
            "REVIEWS: 72 | "
            "AVAILABILITY: in_stock | "
            "SPECS: microphone=noise reduction; "
            "battery=45 hours"
        ),
        score=0.87,
    ),
]


LAPTOP_RESULTS = [
    SearchResult(
        title="CodeBook 15",
        url=(
            "https://laptop-demo.example/"
            "codebook-15"
        ),
        content=(
            "PRODUCT: CodeBook 15 | "
            "BRAND: CodeBook | "
            "MODEL: CB15 | "
            "PRICE: 14.490.000đ | "
            "RATING: 4.6/5 | "
            "REVIEWS: 104 | "
            "AVAILABILITY: in_stock | "
            "SPECS: ram=16GB; "
            "storage=512GB SSD; "
            "cpu=Demo Core 5"
        ),
        score=0.94,
    ),
    SearchResult(
        title="DevNote 14",
        url=(
            "https://computer-demo.example/"
            "devnote-14"
        ),
        content=(
            "PRODUCT: DevNote 14 | "
            "BRAND: DevNote | "
            "MODEL: DN14 | "
            "PRICE: 13.990.000 VND | "
            "RATING: 4.5/5 | "
            "REVIEWS: 89 | "
            "AVAILABILITY: in_stock | "
            "SPECS: ram=16GB; "
            "storage=512GB SSD; "
            "weight=1.45kg"
        ),
        score=0.90,
    ),
    SearchResult(
        title="StudyPro L15",
        url=(
            "https://demo-computer.example/"
            "studypro-l15"
        ),
        content=(
            "PRODUCT: StudyPro L15 | "
            "BRAND: StudyPro | "
            "MODEL: L15 | "
            "PRICE: 14.900.000đ | "
            "RATING: 4.4/5 | "
            "REVIEWS: 61 | "
            "AVAILABILITY: in_stock | "
            "SPECS: ram=16GB; "
            "storage=1TB SSD"
        ),
        score=0.86,
    ),
]


class MockSearchProvider(SearchProvider):
    """Return deterministic mock results without network access."""

    async def search(
        self,
        query: str,
        max_results: int,
    ) -> list[SearchResult]:
        """Return products based on category keywords."""

        normalized = normalize_text(
            query
        )

        if "tai nghe" in normalized:
            results = HEADPHONE_RESULTS

        elif (
            "dien thoai" in normalized
            or "smartphone" in normalized
        ):
            results = PHONE_RESULTS

        elif "laptop" in normalized:
            results = LAPTOP_RESULTS

        else:
            results = []

        return list(
            results[:max_results]
        )