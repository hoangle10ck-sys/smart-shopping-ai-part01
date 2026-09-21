"""Tavily implementation of SearchProvider."""

from __future__ import annotations

import asyncio
import re
import unicodedata

from urllib.parse import (
    urlparse,
)

import httpx

from app.core.config import (
    get_settings,
)

from app.services.search.base import (
    SearchProvider,
    SearchProviderError,
    SearchResult,
)


TAVILY_SEARCH_URL = (
    "https://api.tavily.com/search"
)


# =============================================================
# URL HELPERS
# =============================================================


def _valid_http_url(
    value: object,
) -> str | None:
    """Return valid HTTP/HTTPS URL or None."""

    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    if not value:
        return None

    try:
        parsed = urlparse(
            value
        )

    except ValueError:
        return None

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return None

    if not parsed.netloc:
        return None

    return value


# =============================================================
# TEXT NORMALIZATION
# =============================================================


def _normalize_text(
    value: str,
) -> str:
    """Normalize Vietnamese/English text for image matching."""

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
        character
        for character in value
        if unicodedata.category(
            character
        )
        != "Mn"
    )

    value = value.replace(
        "đ",
        "d",
    )

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


STOP_WORDS = {
    "va",
    "voi",
    "cho",
    "cua",
    "tai",
    "gia",
    "moi",
    "nam",
    "san",
    "pham",
    "cap",
    "nhat",
    "chinh",
    "hang",
    "the",
    "and",
    "the",
    "for",
    "from",
    "with",
    "price",
    "product",
    "official",
}


def _tokens(
    value: str,
) -> set[str]:
    """Create useful matching tokens."""

    normalized = (
        _normalize_text(
            value
        )
    )

    return {
        token
        for token
        in normalized.split()
        if (
            len(token) >= 2
            and token
            not in STOP_WORDS
        )
    }


# =============================================================
# IMAGE HELPERS
# =============================================================


def _extract_result_image(
    item: dict,
) -> str | None:
    """
    Extract image attached directly to one Tavily result.

    Supports:
    - list[str]
    - list[dict]
    """

    images = item.get(
        "images"
    )

    if not isinstance(
        images,
        list,
    ):
        return None

    for image in images:

        if isinstance(
            image,
            str,
        ):
            url = (
                _valid_http_url(
                    image
                )
            )

            if url:
                return url

        elif isinstance(
            image,
            dict,
        ):
            url = (
                _valid_http_url(
                    image.get(
                        "url"
                    )
                )
            )

            if url:
                return url

    return None


def _extract_top_level_images(
    data: dict,
) -> list[
    tuple[str, str]
]:
    """
    Extract query-related images returned at response level.

    Returns:
        [
            (image_url, description),
            ...
        ]
    """

    raw_images = (
        data.get(
            "images",
            [],
        )
    )

    if not isinstance(
        raw_images,
        list,
    ):
        return []

    output: list[
        tuple[str, str]
    ] = []

    seen: set[
        str
    ] = set()

    for image in raw_images:

        image_url: (
            str
            | None
        ) = None

        description = ""

        if isinstance(
            image,
            str,
        ):
            image_url = (
                _valid_http_url(
                    image
                )
            )

        elif isinstance(
            image,
            dict,
        ):
            image_url = (
                _valid_http_url(
                    image.get(
                        "url"
                    )
                )
            )

            description = str(
                image.get(
                    "description",
                    "",
                )
                or ""
            ).strip()

        if not image_url:
            continue

        if image_url in seen:
            continue

        seen.add(
            image_url
        )

        output.append(
            (
                image_url,
                description,
            )
        )

    return output
def _choose_top_level_image(
    *,
    item: dict,
    images: list[
        tuple[str, str]
    ],
    used_urls: set[str],
) -> str | None:
    """
    Choose a query-level image only when its
    description actually matches the search result.

    Never assign an arbitrary unused image because
    that causes logos/icons/unrelated pictures to
    become product images.
    """

    if not images:
        return None

    title = str(
        item.get(
            "title",
            "",
        )
        or ""
    )

    content = str(
        item.get(
            "content",
            "",
        )
        or ""
    )

    title_tokens = (
        _tokens(
            title
        )
    )

    content_tokens = (
        _tokens(
            content
        )
    )

    best_url: (
        str
        | None
    ) = None

    best_score = 0

    for (
        image_url,
        description,
    ) in images:

        if (
            image_url
            in used_urls
        ):
            continue

        if not description:
            continue

        image_tokens = (
            _tokens(
                description
            )
        )

        if not image_tokens:
            continue

        title_matches = len(
            title_tokens
            & image_tokens
        )

        content_matches = len(
            content_tokens
            & image_tokens
        )

        score = (
            title_matches * 5
            + content_matches
        )

        if score > best_score:
            best_score = score
            best_url = image_url


    # Require at least meaningful textual overlap.
    if (
        best_url
        and best_score >= 5
    ):
        return best_url

    return None


# =============================================================
# PROVIDER
# =============================================================


class TavilyProvider(
    SearchProvider
):
    """Search public web through Tavily."""

    def __init__(
        self,
    ) -> None:

        settings = (
            get_settings()
        )

        api_key = (
            settings
            .tavily_api_key
            .strip()
        )

        if not api_key:
            raise SearchProviderError(
                "TAVILY_API_KEY is not configured.", kind="configuration"
            )

        self.api_key = (
            api_key
        )

        self.timeout = float(
            settings
            .search_timeout_seconds
        )

        self.retry_count = max(
            0,
            int(
                settings
                .search_retry_count
            ),
        )


    async def search(
        self,
        query: str,
        max_results: int,
    ) -> list[
        SearchResult
    ]:
        """Execute one Tavily search."""

        payload = {
            "api_key":
                self.api_key,

            "query":
                query,

            # Keep search fast.
            "search_depth":
                "basic",

            "max_results":
                max_results,

            "include_answer":
                False,

            "include_raw_content":
                False,

            # Images are verified from each direct product page. Query-wide
            # image search adds provider work without establishing identity.
            "include_images":
                False,

            "include_image_descriptions":
                False,
        }


        last_error: (
            Exception
            | None
        ) = None

        attempts = (
            self.retry_count
            + 1
        )


        for attempt in range(
            attempts
        ):
            try:

                async with (
                    httpx.AsyncClient(
                        timeout=(
                            self.timeout
                        )
                    )
                    as client
                ):
                    response = (
                        await client.post(
                            TAVILY_SEARCH_URL,
                            json=payload,
                        )
                    )


                response.raise_for_status()

                data = (
                    response.json()
                )

                if not isinstance(
                    data,
                    dict,
                ):
                    raise SearchProviderError(
                        "Tavily returned invalid JSON object.", kind="malformed_response"
                    )


                raw_items = (
                    data.get(
                        "results",
                    )
                )

                if not isinstance(
                    raw_items,
                    list,
                ):
                    raise SearchProviderError("Tavily results must be a list.", kind="malformed_response")

                if any(not isinstance(item, dict) or not isinstance(item.get('url'), str) for item in raw_items):
                    raise SearchProviderError("Tavily result item is malformed.", kind="malformed_response")


                # -------------------------------------------------
                # QUERY-LEVEL IMAGES
                # -------------------------------------------------

                top_level_images = (
                    _extract_top_level_images(
                        data
                    )
                )

                used_image_urls: set[
                    str
                ] = set()


                results: list[
                    SearchResult
                ] = []


                # -------------------------------------------------
                # RESULTS
                # -------------------------------------------------

                for item in raw_items:

                    if not isinstance(
                        item,
                        dict,
                    ):
                        continue


                    url = (
                        _valid_http_url(
                            item.get(
                                "url"
                            )
                        )
                    )

                    if not url:
                        continue


                    title = str(
                        item.get(
                            "title",
                            "",
                        )
                        or ""
                    ).strip()


                    content = str(
                        item.get(
                            "content",
                            "",
                        )
                        or ""
                    ).strip()


                    # ---------------------------------------------
                    # SCORE
                    # ---------------------------------------------

                    provider_score: (
                        float
                        | None
                    ) = None

                    raw_score = (
                        item.get(
                            "score"
                        )
                    )

                    if isinstance(
                        raw_score,
                        (
                            int,
                            float,
                        ),
                    ):
                        provider_score = (
                            float(
                                raw_score
                            )
                        )


                    # ---------------------------------------------
                    # IMAGE
                    #
                    # 1. Prefer image from the exact result.
                    # 2. Fallback to query-level Tavily images.
                    # ---------------------------------------------

                    image_url = (
                        _extract_result_image(
                            item
                        )
                    )

                    if (
                        image_url
                        is None
                    ):
                        image_url = (
                            _choose_top_level_image(
                                item=item,
                                images=(
                                    top_level_images
                                ),
                                used_urls=(
                                    used_image_urls
                                ),
                            )
                        )


                    if image_url:
                        used_image_urls.add(
                            image_url
                        )


                    # ---------------------------------------------
                    # OUTPUT
                    # ---------------------------------------------

                    results.append(
                        SearchResult(
                            title=title,

                            url=url,

                            content=content,

                            score=(
                                provider_score
                            ),

                            image_url=(
                                image_url
                            ),
                        )
                    )


                return results


            except (
                httpx.HTTPError,
                ValueError,
                SearchProviderError,
            ) as exc:

                last_error = (
                    exc
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


        # Keep actionable diagnostics without exposing payload/API key or response body.
        if isinstance(last_error, SearchProviderError):
            raise last_error
        if isinstance(last_error, httpx.TimeoutException):
            raise SearchProviderError(f"Tavily timeout after {self.timeout:g}s per attempt.", kind="timeout") from last_error
        if isinstance(last_error, httpx.HTTPStatusError):
            code = last_error.response.status_code
            kind = "rate_limit" if code == 429 else "http_error"
            raise SearchProviderError(f"Tavily {kind}: HTTP {code}.", kind=kind, status_code=code) from last_error
        if isinstance(last_error, ValueError):
            raise SearchProviderError("Tavily returned malformed JSON.", kind="malformed_response") from last_error
        raise SearchProviderError("Tavily network/transport failure.", kind="network_error") from last_error
