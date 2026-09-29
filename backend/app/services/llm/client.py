"""LLM clients for Demo, OpenAI and Gemini modes."""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
import json
from copy import deepcopy
from pydantic import create_model
from app.services.budget import BUDGET_FIELDS

from abc import ABC, abstractmethod

import httpx

from app.core.config import get_settings
from app.schemas.requirement import (
    RequirementData,
    RequirementItem,
)
from app.services.llm.prompts import (
    build_requirement_prompt,
)


logger = logging.getLogger(__name__)


def provider_overloaded(error: Exception) -> bool:
    """Recognize SDK status codes and wrapped overloads without logging payloads."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        code = getattr(error, 'code', None) or getattr(error, 'status_code', None)
        status = str(getattr(error, 'status', '')).upper()
        text = str(error).upper()
        if str(code) in {'429', '503'} or status in {'UNAVAILABLE', 'RESOURCE_EXHAUSTED'}:
            return True
        if re.search(r'\b(?:503|429|UNAVAILABLE|RESOURCE_EXHAUSTED)\b', text):
            return True
        error = error.__cause__
    return False

# LLMs extract facts only. Budget mode/window are computed by Python afterward.
RequirementExtraction = create_model('RequirementExtraction', **{
    name: (field.annotation, deepcopy(field)) for name, field in RequirementData.model_fields.items()
    if name not in BUDGET_FIELDS
})


def parsed_requirement(value) -> RequirementData:
    if isinstance(value, str): value = json.loads(value)
    if hasattr(value, 'model_dump'): value = value.model_dump()
    extraction = RequirementExtraction.model_validate(value)
    return RequirementData.model_validate(extraction.model_dump())


# =============================================================
# TEXT NORMALIZATION
# =============================================================


def normalize_text(
    text: str,
) -> str:
    """Normalize Vietnamese text for deterministic local matching."""

    normalized = unicodedata.normalize(
        "NFD",
        text.lower(),
    )

    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character)
        != "Mn"
    )

    normalized = normalized.replace(
        "đ",
        "d",
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    return normalized.strip()


# =============================================================
# LOCAL BUDGET PARSER
# =============================================================


BUDGET_NUMBER = r"(?:\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)"
BUDGET_UNIT = r"(?:trieu|nghin|ngan|ty|tr|k|vnd|dong|d)"
BUDGET_MULTIPLIERS = {
    "ty": 1_000_000_000, "trieu": 1_000_000, "tr": 1_000_000,
    "nghin": 1_000, "ngan": 1_000, "k": 1_000,
    "vnd": 1, "dong": 1, "d": 1,
}


def _budget_amount(number: str, unit: str) -> int:
    """Distinguish grouped integer VND from decimal compact amounts."""
    from decimal import Decimal
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", number):
        number = re.sub(r"[.,]", "", number)
    return int(Decimal(number.replace(",", ".")) * BUDGET_MULTIPLIERS[unit])


def parse_budget_range(text: str) -> tuple[int | None, int | None]:
    """Read an explicit range (including shared units) or a single upper budget."""
    value = normalize_text(text).replace("₫", " vnd")
    range_match = re.search(
        rf"(?<![\w.,])(?:tu\s+)?({BUDGET_NUMBER})\s*({BUDGET_UNIT})?\s*"
        rf"(?:den|toi|-)\s*({BUDGET_NUMBER})\s*({BUDGET_UNIT})\b",
        value,
    )
    if range_match:
        low, low_unit, high, high_unit = range_match.groups()
        minimum = _budget_amount(low, low_unit or high_unit)
        maximum = _budget_amount(high, high_unit)
        return (minimum, maximum) if minimum <= maximum else (None, None)
    match = re.search(rf"(?<![\w.,])({BUDGET_NUMBER})\s*({BUDGET_UNIT})\b", value)
    if match:
        return None, _budget_amount(*match.groups())
    prefix_match = re.search(rf"\bvnd\s*({BUDGET_NUMBER})(?![\d.,])", value)
    if prefix_match:
        return None, _budget_amount(prefix_match.group(1), "vnd")
    return None, None


def parse_budget(text: str) -> int | None:
    """Keep the existing single-budget helper compatible."""
    return parse_budget_range(text)[1]


# =============================================================
# LOCAL CATEGORY DETECTOR
# =============================================================


def detect_category(
    normalized: str,
) -> str | None:
    """Detect common shopping product categories."""

    category_keywords = {
        "laptop": [
            "laptop",
            "may tinh xach tay",
            "notebook",
        ],

        "điện thoại": [
            "dien thoai",
            "smartphone",
            "phone",
            "iphone",
        ],

        "tai nghe": [
            "tai nghe",
            "headphone",
            "headphones",
            "headset",
            "earphone",
            "earphones",
            "earbuds",
        ],

        "chuột": [
            "chuot",
            "mouse",
        ],

        "bàn phím": [
            "ban phim",
            "keyboard",
        ],

        "màn hình": [
            "man hinh",
            "monitor",
        ],

        "máy tính bảng": [
            "may tinh bang",
            "tablet",
            "ipad",
        ],

        "đồng hồ thông minh": [
            "dong ho thong minh",
            "smartwatch",
            "apple watch",
        ],

        "loa": [
            "loa bluetooth",
            "loa di dong",
            "speaker",
        ],

        "tivi": [
            "tivi",
            "tv",
            "smart tv",
        ],

        "máy ảnh": [
            "may anh",
            "camera",
            "dslr",
            "mirrorless",
        ],

        "máy giặt": [
            "may giat",
        ],

        "tủ lạnh": [
            "tu lanh",
        ],

        "điều hòa": [
            "dieu hoa",
            "may lanh",
        ],

        "máy lọc không khí": [
            "may loc khong khi",
            "air purifier",
        ],

        "nồi chiên không dầu": [
            "noi chien khong dau",
            "air fryer",
        ],

        "nồi cơm điện": [
            "noi com dien",
        ],

        "máy hút bụi": [
            "may hut bui",
            "robot hut bui",
        ],

        "máy khoan": [
            "may khoan",
            "khoan pin",
            "drill",
        ],

        "giày": [
            "giay",
            "sneaker",
            "giay chay bo",
            "giay the thao",
        ],

        "quần áo": [
            "quan ao",
            "ao thun",
            "ao khoac",
            "quan jean",
            "quan jeans",
            "dam",
            "vay",
        ],

        "mỹ phẩm": [
            "my pham",
            "son",
            "kem chong nang",
            "serum",
            "sua rua mat",
        ],

        "xe máy": [
            "xe may",
            "air blade",
            "ab125",
            "vario",
            "vision",
            "lead",
            "wave",
            "exciter",
            "winner",
        ],

        "ô tô": [
            "o to",
            "oto",
            "xe hoi",
            "car",
            "suv",
            "sedan",
        ],

        "xe đạp": [
            "xe dap",
            "xe dap the thao",
            "xe dap dia hinh",
        ],
    }

    for category, keywords in (
        category_keywords.items()
    ):
        if any(
            re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", normalized)
            for keyword in keywords
        ):
            return category

    return None


# =============================================================
# LOCAL PURPOSE DETECTOR
# =============================================================


def detect_purposes(
    normalized: str,
) -> list[str]:
    """Detect common shopping purposes."""

    purpose_keywords = {
        "xem phim": ["xem phim", "watch movies", "watching movies"],
        "học online": [
            "hoc online",
            "hoc truc tuyen",
        ],

        "học lập trình": [
            "hoc lap trinh",
            "lap trinh",
            "coding",
            "code",
        ],

        "chơi game": [
            "choi game",
            "gaming",
            "game",
        ],

        "chụp ảnh": [
            "chup anh",
            "chup hinh",
        ],

        "nghe nhạc": [
            "nghe nhac",
        ],

        "họp online": [
            "hop online",
            "meeting online",
        ],

        "văn phòng": [
            "van phong",
            "office",
        ],

        "thiết kế": [
            "thiet ke",
            "do hoa",
            "graphic",
        ],

        "chỉnh sửa video": [
            "chinh sua video",
            "edit video",
            "dung phim",
        ],

        "đi học": [
            "di hoc",
            "den truong",
            "sinh vien",
            "hoc sinh",
        ],

        "đi làm": [
            "di lam",
            "cong viec",
        ],

        "chạy bộ": [
            "chay bo",
            "running",
        ],

        "thể thao": [
            "the thao",
            "tap gym",
            "gym",
        ],

        "du lịch": [
            "du lich",
            "travel",
        ],
    }

    purposes: list[str] = []

    for purpose, keywords in (
        purpose_keywords.items()
    ):
        if any(
            keyword in normalized
            for keyword in keywords
        ):
            purposes.append(
                purpose
            )

    return purposes


# =============================================================
# LOCAL BRAND DETECTOR
# =============================================================


def detect_brands(
    normalized: str,
) -> list[str]:
    """Detect explicitly mentioned brands."""

    known_brands = {
        "apple": "Apple",
        "iphone": "Apple",
        "macbook": "Apple",
        "ipad": "Apple",

        "samsung": "Samsung",
        "xiaomi": "Xiaomi",
        "oppo": "OPPO",
        "vivo": "Vivo",
        "realme": "Realme",
        "sony": "Sony",

        "asus": "ASUS",
        "acer": "Acer",
        "dell": "Dell",
        "lenovo": "Lenovo",
        "hp": "HP",
        "msi": "MSI",

        "logitech": "Logitech",
        "razer": "Razer",
        "jbl": "JBL",

        "honda": "Honda",
        "air blade": "Honda",
        "ab125": "Honda",
        "vision": "Honda",
        "lead": "Honda",
        "wave": "Honda",

        "yamaha": "Yamaha",
        "exciter": "Yamaha",

        "toyota": "Toyota",
        "ford": "Ford",
        "hyundai": "Hyundai",
        "mazda": "Mazda",
        "kia": "Kia",
        "vinfast": "VinFast",

        "nike": "Nike",
        "adidas": "Adidas",
        "puma": "Puma",

        "bosch": "Bosch",
        "makita": "Makita",

        "lg": "LG",
        "panasonic": "Panasonic",
        "sharp": "Sharp",
        "electrolux": "Electrolux",
    }

    brands: list[str] = []

    for (
        keyword,
        canonical_name,
    ) in known_brands.items():
        if keyword not in normalized:
            continue

        if canonical_name not in brands:
            brands.append(
                canonical_name
            )

    return brands


# =============================================================
# LOCAL REQUIREMENT DETECTOR
# =============================================================


def detect_requirements(
    normalized: str,
) -> tuple[
    list[RequirementItem],
    list[str],
]:
    """Detect common requirements and exclusions."""

    requirements: list[
        RequirementItem
    ] = []

    excluded: list[str] = []


    # ---------------------------------------------------------
    # MICROPHONE
    # ---------------------------------------------------------

    if (
        "mic tot" in normalized
        or "microphone tot" in normalized
        or "mic ro" in normalized
    ):
        requirements.append(
            RequirementItem(
                name="microphone",
                value="tốt",
                priority=5,
            )
        )


    # ---------------------------------------------------------
    # BATTERY
    # ---------------------------------------------------------

    if (
        "pin lau" in normalized
        or "battery lau" in normalized
        or "thoi luong pin" in normalized
    ):
        priority = (
            5
            if (
                "uu tien" in normalized
                and "pin" in normalized
            )
            else 4
        )

        requirements.append(
            RequirementItem(
                name="battery",
                value="pin lâu",
                priority=priority,
            )
        )


    # ---------------------------------------------------------
    # CAMERA
    # ---------------------------------------------------------

    if (
        "camera tot" in normalized
        or "camera dep" in normalized
        or "chup anh dep" in normalized
    ):
        priority = (
            5
            if "uu tien" in normalized
            else 4
        )

        requirements.append(
            RequirementItem(
                name="camera",
                value="tốt",
                priority=priority,
            )
        )


    # ---------------------------------------------------------
    # RAM
    # ---------------------------------------------------------

    ram_match = re.search(
        r"\b(8|12|16|24|32|64)\s*gb\s*ram\b",
        normalized,
    )

    if not ram_match:
        ram_match = re.search(
            r"\bram\s*(8|12|16|24|32|64)\s*gb\b",
            normalized,
        )

    if ram_match:
        requirements.append(
            RequirementItem(
                name="RAM",
                value=(
                    f"{ram_match.group(1)}GB"
                ),
                priority=4,
            )
        )


    # ---------------------------------------------------------
    # STORAGE / SSD
    # ---------------------------------------------------------

    storage_match = re.search(
        r"\b(128|256|512|1024|2048)\s*gb\b",
        normalized,
    )

    if storage_match:
        storage = (
            storage_match.group(1)
        )

        requirements.append(
            RequirementItem(
                name="storage",
                value=f"{storage}GB",
                priority=3,
            )
        )

    tb_match = re.search(
        r"\b([12])\s*tb\b",
        normalized,
    )

    if tb_match:
        requirements.append(
            RequirementItem(
                name="storage",
                value=(
                    f"{tb_match.group(1)}TB"
                ),
                priority=3,
            )
        )


    # ---------------------------------------------------------
    # LIGHT WEIGHT
    # ---------------------------------------------------------

    if (
        "nhe" in normalized
        and "khong muon" not in normalized
    ):
        requirements.append(
            RequirementItem(
                name="weight",
                value="nhẹ",
                priority=3,
            )
        )


    # ---------------------------------------------------------
    # FUEL
    # ---------------------------------------------------------

    if (
        "tiet kiem xang" in normalized
        or "it hao xang" in normalized
    ):
        requirements.append(
            RequirementItem(
                name="fuel_efficiency",
                value="tiết kiệm xăng",
                priority=4,
            )
        )


    # ---------------------------------------------------------
    # PERFORMANCE
    # ---------------------------------------------------------

    if (
        "cau hinh manh" in normalized
        or "hieu nang cao" in normalized
        or "hieu nang manh" in normalized
    ):
        requirements.append(
            RequirementItem(
                name="performance",
                value="hiệu năng tốt",
                priority=4,
            )
        )


    # ---------------------------------------------------------
    # SCREEN
    # ---------------------------------------------------------

    if (
        "man hinh dep" in normalized
        or "man hinh tot" in normalized
    ):
        requirements.append(
            RequirementItem(
                name="display",
                value="màn hình tốt",
                priority=4,
            )
        )


    # ---------------------------------------------------------
    # NOISE CANCELLATION
    # ---------------------------------------------------------

    if (
        "chong on" in normalized
        or "noise cancelling" in normalized
        or "noise cancellation" in normalized
        or "anc" in normalized
    ):
        requirements.append(
            RequirementItem(
                name="noise_cancellation",
                value="có chống ồn",
                priority=4,
            )
        )


    # ---------------------------------------------------------
    # EXCLUSIONS
    # ---------------------------------------------------------

    heavy_exclusion_patterns = [
        "khong muon may qua nang",
        "khong muon qua nang",
        "khong qua nang",
        "khong muon may nang",
    ]

    if any(
        pattern in normalized
        for pattern in heavy_exclusion_patterns
    ):
        excluded.append(
            "máy quá nặng"
        )

    if (
        "khong hang cu" in normalized
        or "khong mua hang cu" in normalized
        or "khong mua do cu" in normalized
    ):
        excluded.append(
            "hàng cũ"
        )

    return (
        requirements,
        excluded,
    )


# =============================================================
# BASE LLM CLIENT
# =============================================================


class BaseLLMClient(
    ABC
):
    """Common interface for requirement-analysis LLM providers."""

    @abstractmethod
    async def analyze_requirement(
        self,
        raw_query: str,
    ) -> RequirementData:
        """Convert natural language into RequirementData."""


# =============================================================
# LOCAL / MOCK LLM
# =============================================================


class MockLLMClient(
    BaseLLMClient
):
    """
    Deterministic local analyzer.

    Used in:
    - Demo Mode.
    - Automated tests.
    - Final fallback when Gemini/OpenAI is unavailable.
    """

    async def analyze_requirement(
        self,
        raw_query: str,
    ) -> RequirementData:
        """Analyze input without calling an external API."""

        normalized = normalize_text(
            raw_query
        )

        category = detect_category(
            normalized
        )

        budget_min, budget_max = parse_budget_range(
            raw_query
        )

        purposes = detect_purposes(
            normalized
        )

        brands = detect_brands(
            normalized
        )

        (
            requirements,
            excluded,
        ) = detect_requirements(
            normalized
        )

        completeness = 0.0

        if category is not None:
            completeness += 0.35

        if budget_min is not None or budget_max is not None:
            completeness += 0.30

        if purposes:
            completeness += 0.20

        if (
            requirements
            or brands
        ):
            completeness += 0.10

        if excluded:
            completeness += 0.05

        confidence = min(
            round(
                completeness,
                2,
            ),
            0.95,
        )

        return RequirementData(
            category=category,
            budget_min=budget_min,
            budget_max=budget_max,
            currency="VND",
            purpose=purposes,
            brands=brands,
            requirements=requirements,
            excluded_requirements=excluded,
            sort_preference="best_match",
            confidence=confidence,
        )


# =============================================================
# GEMINI LLM
# =============================================================


class GeminiLLMClient(
    BaseLLMClient
):
    """Gemini implementation using Pydantic Structured Output."""

    def __init__(
        self,
    ) -> None:
        settings = get_settings()

        if not (
            settings
            .gemini_api_key
            .strip()
        ):
            raise RuntimeError(
                "GEMINI_API_KEY is not configured."
            )

        if not (
            settings
            .gemini_model
            .strip()
        ):
            raise RuntimeError(
                "GEMINI_MODEL is not configured."
            )

        try:
            from google import genai
            from google.genai import types

        except ImportError as exc:
            raise RuntimeError(
                (
                    "google-genai is not installed. "
                    "Run: pip install -r requirements.txt"
                )
            ) from exc

        self._client = genai.Client(
            http_options=types.HttpOptions(
                timeout=max(1, settings.llm_timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
            api_key=(
                settings
                .gemini_api_key
                .strip()
            )
        )

        self._model = (
            settings
            .gemini_model
            .strip()
        )

        self._timeout_seconds = float(
            settings.llm_timeout_seconds
        )

        self._retry_count = max(
            0,
            int(
                settings
                .llm_retry_count
            ),
        )


    def _generate_sync(
        self,
        raw_query: str,
    ) -> RequirementData:
        """Make one synchronous Gemini request."""

        from google.genai import types

        prompt = build_requirement_prompt(
            raw_query
        )

        response = (
            self
            ._client
            .models
            .generate_content(
                model=self._model,
                contents=prompt,
                config=(
                    types.GenerateContentConfig(
                        response_mime_type=(
                            "application/json"
                        ),
                        response_schema=(
                            RequirementExtraction
                        ),
                        temperature=0.1,
                    )
                ),
            )
        )

        if (
            response.parsed
            is not None
        ):
            if isinstance(
                response.parsed,
                RequirementData,
            ):
                return parsed_requirement(response.parsed)

            return (
                parsed_requirement(
                    response.parsed
                )
            )

        if not response.text:
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        return (
            parsed_requirement(
                response.text
            )
        )


    async def analyze_requirement(
        self,
        raw_query: str,
    ) -> RequirementData:
        """Analyze requirement with timeout and retry."""

        last_error: Exception | None = None

        attempts = (
            self._retry_count
            + 1
        )

        for attempt in range(
            attempts
        ):
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(
                        self._generate_sync,
                        raw_query,
                    ),
                    timeout=(
                        self
                        ._timeout_seconds
                    ),
                )

            except Exception as exc:
                last_error = exc

                logger.warning(
                    (
                        "Gemini requirement "
                        "analysis attempt %s/%s "
                        "failed: %s"
                    ),
                    attempt + 1,
                    attempts,
                    type(exc).__name__,
                )

                if provider_overloaded(exc) or isinstance(exc, TimeoutError):
                    break

                if (
                    attempt
                    >= attempts - 1
                ):
                    break

                await asyncio.sleep(
                    0.5
                    * (
                        2 ** attempt
                    )
                )

        raise RuntimeError(
            "Gemini requirement analysis failed."
        ) from last_error


# =============================================================
# OPENAI LLM
# =============================================================


class OpenAILLMClient(
    BaseLLMClient
):
    """OpenAI implementation using Responses API."""

    API_URL = (
        "https://api.openai.com/v1/responses"
    )

    def __init__(
        self,
    ) -> None:
        settings = get_settings()

        api_key = (
            settings
            .openai_api_key
            .strip()
        )

        model = (
            settings
            .openai_model
            .strip()
        )

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured."
            )

        if not model:
            raise RuntimeError(
                "OPENAI_MODEL is not configured."
            )

        self._api_key = api_key
        self._model = model

        self._timeout_seconds = float(
            settings.llm_timeout_seconds
        )

        self._retry_count = max(
            0,
            int(
                settings
                .llm_retry_count
            ),
        )


    @staticmethod
    def _extract_output_text(
        data: dict,
    ) -> str:
        """Extract assistant text from Responses API."""

        output = data.get(
            "output",
            [],
        )

        if not isinstance(
            output,
            list,
        ):
            raise RuntimeError(
                "OpenAI returned invalid output."
            )

        for item in output:
            if not isinstance(
                item,
                dict,
            ):
                continue

            if (
                item.get("type")
                != "message"
            ):
                continue

            content = item.get(
                "content",
                [],
            )

            if not isinstance(
                content,
                list,
            ):
                continue

            for part in content:
                if not isinstance(
                    part,
                    dict,
                ):
                    continue

                part_type = part.get(
                    "type"
                )

                if (
                    part_type
                    == "output_text"
                ):
                    text = str(
                        part.get(
                            "text",
                            "",
                        )
                        or ""
                    ).strip()

                    if text:
                        return text

                if (
                    part_type
                    == "refusal"
                ):
                    refusal = str(
                        part.get(
                            "refusal",
                            "",
                        )
                        or ""
                    ).strip()

                    raise RuntimeError(
                        (
                            "OpenAI refused "
                            "the request"
                        )
                        + (
                            f": {refusal}"
                            if refusal
                            else "."
                        )
                    )

        raise RuntimeError(
            "OpenAI returned an empty response."
        )


    async def _request_once(
        self,
        raw_query: str,
    ) -> RequirementData:
        """Perform one OpenAI Responses API call."""

        prompt = build_requirement_prompt(
            raw_query
        )

        schema = (
            RequirementExtraction
            .model_json_schema()
        )

        payload = {
            "model": self._model,

            "input": [
                {
                    "role": "user",

                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt,
                        }
                    ],
                }
            ],

            "temperature": 0.1,

            "store": False,

            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "requirement_data",
                    "schema": schema,
                    "strict": False,
                }
            },
        }

        headers = {
            "Authorization": (
                "Bearer "
                + self._api_key
            ),
            "Content-Type": (
                "application/json"
            ),
        }

        async with httpx.AsyncClient(
            timeout=(
                self
                ._timeout_seconds
            )
        ) as client:
            response = await client.post(
                self.API_URL,
                headers=headers,
                json=payload,
            )

        if (
            response.status_code
            >= 400
        ):
            detail = ""

            try:
                error_data = (
                    response.json()
                )

                error_object = (
                    error_data.get(
                        "error",
                        {},
                    )
                )

                if isinstance(
                    error_object,
                    dict,
                ):
                    detail = str(
                        error_object.get(
                            "message",
                            "",
                        )
                        or ""
                    )

            except ValueError:
                detail = (
                    response.text[
                        :500
                    ]
                )

            raise RuntimeError(
                (
                    "OpenAI API returned HTTP "
                    f"{response.status_code}"
                )
                + (
                    f": {detail}"
                    if detail
                    else ""
                )
            )

        try:
            data = response.json()

        except ValueError as exc:
            raise RuntimeError(
                "OpenAI returned invalid JSON."
            ) from exc

        text = self._extract_output_text(
            data
        )

        try:
            return (
                parsed_requirement(
                    text
                )
            )

        except Exception as exc:
            raise RuntimeError(
                (
                    "OpenAI returned invalid "
                    "RequirementData."
                )
            ) from exc


    async def analyze_requirement(
        self,
        raw_query: str,
    ) -> RequirementData:
        """Analyze shopping requirement using OpenAI."""

        last_error: Exception | None = None

        attempts = (
            self._retry_count
            + 1
        )

        for attempt in range(
            attempts
        ):
            try:
                return await asyncio.wait_for(
                    self._request_once(
                        raw_query
                    ),
                    timeout=(
                        self
                        ._timeout_seconds
                        + 2
                    ),
                )

            except Exception as exc:
                last_error = exc

                logger.warning(
                    (
                        "OpenAI requirement "
                        "analysis attempt %s/%s "
                        "failed: %s"
                    ),
                    attempt + 1,
                    attempts,
                    exc,
                )

                if (
                    attempt
                    >= attempts - 1
                ):
                    break

                await asyncio.sleep(
                    0.5
                    * (
                        2 ** attempt
                    )
                )

        raise RuntimeError(
            "OpenAI requirement analysis failed."
        ) from last_error


# =============================================================
# FALLBACK LLM
# =============================================================


class FallbackLLMClient(
    BaseLLMClient
):
    """
    Try the primary provider first.

    If it fails because of:
    - quota / HTTP 429
    - timeout
    - network error
    - invalid response
    - provider error

    automatically use the fallback provider.
    """

    def __init__(
        self,
        primary: BaseLLMClient,
        fallback: BaseLLMClient | None = None,
    ) -> None:
        self.primary = primary
        self.fallback = fallback


    async def analyze_requirement(
        self,
        raw_query: str,
    ) -> RequirementData:
        """Use primary LLM and automatically fallback on failure."""

        try:
            return await (
                self
                .primary
                .analyze_requirement(
                    raw_query
                )
            )

        except Exception as exc:
            if (
                self.fallback
                is None
            ):
                raise

            logger.warning(
                (
                    "LLM provider %s failed: %s. "
                    "Falling back to %s."
                ),
                type(
                    self.primary
                ).__name__,
                exc,
                type(
                    self.fallback
                ).__name__,
            )

            return await (
                self
                .fallback
                .analyze_requirement(
                    raw_query
                )
            )


# =============================================================
# PROVIDER FACTORY
# =============================================================


def create_llm_provider(
    provider: str,
) -> BaseLLMClient:
    """Create one configured LLM provider."""

    normalized = (
        provider
        .strip()
        .lower()
    )

    if normalized in {
        "local",
        "mock",
    }:
        return MockLLMClient()

    if normalized == "openai":
        return OpenAILLMClient()

    if normalized == "gemini":
        return GeminiLLMClient()

    raise RuntimeError(
        (
            "Unsupported LLM provider: "
            f"{provider}"
        )
    )


# =============================================================
# PUBLIC LLM FACTORY
# =============================================================


def get_llm_client(
) -> BaseLLMClient:
    """
    Return configured LLM client.

    Behaviour:

    DEMO_MODE=true:
        MockLLMClient only.

    DEMO_MODE=false:
        primary configured provider
            ↓ if failed
        configured fallback provider
            ↓ if failed
        local MockLLMClient

    Local analyzer is always kept as the final safety fallback
    in live mode so the web application does not completely fail
    when an external AI provider is unavailable.
    """

    settings = get_settings()


    # ---------------------------------------------------------
    # DEMO MODE
    # ---------------------------------------------------------

    if settings.demo_mode:
        return MockLLMClient()


    # ---------------------------------------------------------
    # PROVIDER NAMES
    # ---------------------------------------------------------

    primary_name = (
        settings
        .llm_provider
        .strip()
        .lower()
    )

    fallback_name = (
        settings
        .llm_fallback_provider
        .strip()
        .lower()
    )

    provider_names: list[str] = []

    if primary_name:
        provider_names.append(
            primary_name
        )

    if (
        fallback_name
        and fallback_name
        not in provider_names
    ):
        provider_names.append(
            fallback_name
        )


    # ---------------------------------------------------------
    # CREATE EXTERNAL / CONFIGURED PROVIDERS
    # ---------------------------------------------------------

    clients: list[
        BaseLLMClient
    ] = []

    for provider_name in (
        provider_names
    ):
        try:
            client = (
                create_llm_provider(
                    provider_name
                )
            )

            clients.append(
                client
            )

        except Exception as exc:
            logger.warning(
                (
                    "Could not initialize "
                    "LLM provider '%s': %s"
                ),
                provider_name,
                exc,
            )


    # ---------------------------------------------------------
    # LOCAL SAFETY FALLBACK
    # ---------------------------------------------------------

    chain: BaseLLMClient = (
        MockLLMClient()
    )


    # ---------------------------------------------------------
    # BUILD FALLBACK CHAIN
    #
    # Example:
    #
    # Gemini
    #   ↓
    # OpenAI
    #   ↓
    # Local
    #
    # or:
    #
    # Gemini
    #   ↓
    # Local
    # ---------------------------------------------------------

    for client in reversed(
        clients
    ):
        if isinstance(
            client,
            MockLLMClient,
        ):
            chain = client
            continue

        chain = FallbackLLMClient(
            primary=client,
            fallback=chain,
        )


    # ---------------------------------------------------------
    # FINAL CLIENT
    # ---------------------------------------------------------

    return chain
