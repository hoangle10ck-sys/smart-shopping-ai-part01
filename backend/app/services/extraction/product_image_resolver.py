"""Resolve a real product image from the source product page."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from contextlib import asynccontextmanager

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import (
    urljoin,
    urlparse,
)

import httpx

from app.core.config import get_settings
from app.schemas.search import (
    SearchSourceItem,
)


# =============================================================
# CONSTANTS
# =============================================================


BAD_IMAGE_MARKERS = {
    "logo",
    "favicon",
    "icon",
    "sprite",
    "spinner",
    "loading",
    "placeholder",
    "no-image",
    "no_image",
    "noimage",
    "default-image",
    "default_image",
    "avatar",
    "magnifier",
    "magnify",
    "search-icon",
    "search_icon",
    "tracking",
    "pixel.gif",
    "1x1",
    "blank.gif",
}


IMAGE_ATTRIBUTES = (
    "src",
    "data-src",
    "data-lazy-src",
    "data-original",
    "data-image",
    "data-zoom-image",
)


META_IMAGE_KEYS = (
    "og:image:secure_url",
    "og:image",
    "twitter:image",
    "twitter:image:src",
)


# =============================================================
# PARSED IMAGE
# =============================================================


@dataclass(slots=True)
class HtmlImage:
    """One img tag parsed from a HTML page."""

    url: str

    alt: str = ""

    class_name: str = ""

    element_id: str = ""

    width: int | None = None

    height: int | None = None


# =============================================================
# HTML PARSER
# =============================================================


class ProductPageHTMLParser(
    HTMLParser
):
    """Extract metadata and image candidates from HTML."""

    def __init__(
        self,
        *,
        concurrency: int = 8,
    ) -> None:
        super().__init__(
            convert_charrefs=True
        )

        self.meta: dict[
            str,
            str,
        ] = {}

        self.images: list[
            HtmlImage
        ] = []

        self.json_ld_blocks: list[
            str
        ] = []

        self._inside_json_ld = False

        self._json_ld_parts: list[
            str
        ] = []


    def handle_starttag(
        self,
        tag: str,
        attrs: list[
            tuple[
                str,
                str | None,
            ]
        ],
    ) -> None:
        attributes = {
            key.lower(): (
                value
                or ""
            )
            for key, value
            in attrs
        }

        tag = tag.lower()


        # -----------------------------------------------------
        # META
        # -----------------------------------------------------

        if tag == "meta":
            key = (
                attributes.get(
                    "property"
                )
                or attributes.get(
                    "name"
                )
                or attributes.get(
                    "itemprop"
                )
                or ""
            ).strip().lower()

            content = (
                attributes.get(
                    "content"
                )
                or ""
            ).strip()

            if (
                key
                and content
            ):
                self.meta[
                    key
                ] = content

            return


        # -----------------------------------------------------
        # JSON-LD
        # -----------------------------------------------------

        if tag == "script":
            script_type = (
                attributes.get(
                    "type"
                )
                or ""
            ).strip().lower()

            if (
                script_type
                == "application/ld+json"
            ):
                self._inside_json_ld = (
                    True
                )

                self._json_ld_parts = []

            return


        # -----------------------------------------------------
        # IMG
        # -----------------------------------------------------

        if tag != "img":
            return

        image_url = ""

        for attribute_name in (
            IMAGE_ATTRIBUTES
        ):
            value = (
                attributes.get(
                    attribute_name
                )
                or ""
            ).strip()

            if value:
                image_url = value
                break

        if not image_url:
            return

        width = _parse_dimension(
            attributes.get(
                "width"
            )
        )

        height = _parse_dimension(
            attributes.get(
                "height"
            )
        )

        self.images.append(
            HtmlImage(
                url=image_url,

                alt=(
                    attributes.get(
                        "alt"
                    )
                    or ""
                ).strip(),

                class_name=(
                    attributes.get(
                        "class"
                    )
                    or ""
                ).strip(),

                element_id=(
                    attributes.get(
                        "id"
                    )
                    or ""
                ).strip(),

                width=width,

                height=height,
            )
        )


    def handle_data(
        self,
        data: str,
    ) -> None:
        if (
            self
            ._inside_json_ld
        ):
            self._json_ld_parts.append(
                data
            )


    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        if (
            tag.lower()
            != "script"
        ):
            return

        if not (
            self
            ._inside_json_ld
        ):
            return

        value = "".join(
            self._json_ld_parts
        ).strip()

        if value:
            self.json_ld_blocks.append(
                value
            )

        self._inside_json_ld = False

        self._json_ld_parts = []


# =============================================================
# GENERIC HELPERS
# =============================================================


def _parse_dimension(
    value: str | None,
) -> int | None:
    """Parse width/height attributes such as 600 or 600px."""

    if not value:
        return None

    digits = "".join(
        character
        for character
        in value
        if character.isdigit()
    )

    if not digits:
        return None

    try:
        return int(
            digits
        )

    except ValueError:
        return None


def _valid_http_url(
    value: object,
    *,
    base_url: str | None = None,
) -> str | None:
    """Return absolute HTTP(S) URL."""

    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    if not value:
        return None

    if base_url:
        value = urljoin(
            base_url,
            value,
        )

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


def _looks_like_bad_image(
    value: str,
) -> bool:
    """Reject obvious logos, icons and placeholders."""

    normalized = (
        value
        .strip()
        .lower()
    )

    if not normalized:
        return True

    if normalized.startswith(
        "data:"
    ):
        return True

    parsed = urlparse(
        normalized
    )

    path = (
        parsed.path
        or ""
    ).lower()

    if path.endswith(
        ".svg"
    ):
        return True

    return any(
        marker in normalized
        for marker
        in BAD_IMAGE_MARKERS
    )


def _text_tokens(
    value: str,
) -> set[str]:
    """Build simple matching tokens."""

    value = (
        value
        .lower()
        .replace("-", " ")
        .replace("_", " ")
        .replace("/", " ")
        .replace("|", " ")
        .replace(":", " ")
    )

    return {
        token
        for token
        in value.split()
        if len(token) >= 3
    }


# =============================================================
# JSON-LD
# =============================================================


def _is_product_type(
    value: object,
) -> bool:
    """Return True for schema.org Product type."""

    if isinstance(
        value,
        str,
    ):
        return (
            value.lower()
            == "product"
        )

    if isinstance(
        value,
        list,
    ):
        return any(
            _is_product_type(
                item
            )
            for item
            in value
        )

    return False


def _extract_image_value(
    value: object,
    *,
    base_url: str,
) -> str | None:
    """Extract image URL from JSON-LD image shapes."""

    if isinstance(
        value,
        str,
    ):
        url = _valid_http_url(
            value,
            base_url=base_url,
        )

        if (
            url
            and not
            _looks_like_bad_image(
                url
            )
        ):
            return url

        return None


    if isinstance(
        value,
        list,
    ):
        for item in value:
            url = (
                _extract_image_value(
                    item,
                    base_url=base_url,
                )
            )

            if url:
                return url

        return None


    if isinstance(
        value,
        dict,
    ):
        for key in (
            "url",
            "contentUrl",
            "thumbnailUrl",
        ):
            url = (
                _extract_image_value(
                    value.get(
                        key
                    ),
                    base_url=base_url,
                )
            )

            if url:
                return url

    return None


def _find_product_image_in_json(
    value: object,
    *,
    base_url: str,
) -> str | None:
    """Recursively search JSON-LD for Product.image."""

    if isinstance(
        value,
        list,
    ):
        for item in value:
            image = (
                _find_product_image_in_json(
                    item,
                    base_url=base_url,
                )
            )

            if image:
                return image

        return None


    if not isinstance(
        value,
        dict,
    ):
        return None


    if _is_product_type(
        value.get(
            "@type"
        )
    ):
        image = (
            _extract_image_value(
                value.get(
                    "image"
                ),
                base_url=base_url,
            )
        )

        if image:
            return image


    graph = value.get(
        "@graph"
    )

    if graph is not None:
        image = (
            _find_product_image_in_json(
                graph,
                base_url=base_url,
            )
        )

        if image:
            return image


    for child_value in (
        value.values()
    ):
        if not isinstance(
            child_value,
            (
                dict,
                list,
            ),
        ):
            continue

        image = (
            _find_product_image_in_json(
                child_value,
                base_url=base_url,
            )
        )

        if image:
            return image

    return None


def _extract_json_ld_product_image(
    parser: ProductPageHTMLParser,
    *,
    page_url: str,
) -> str | None:
    """Extract Product.image from all JSON-LD blocks."""

    for block in (
        parser.json_ld_blocks
    ):
        try:
            data = json.loads(
                block
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            continue

        image = (
            _find_product_image_in_json(
                data,
                base_url=page_url,
            )
        )

        if image:
            return image

    return None


# =============================================================
# META IMAGE
# =============================================================


def _extract_meta_image(
    parser: ProductPageHTMLParser,
    *,
    page_url: str,
) -> str | None:
    """Extract OpenGraph/Twitter image."""

    for key in (
        META_IMAGE_KEYS
    ):
        raw = (
            parser.meta.get(
                key
            )
        )

        url = (
            _valid_http_url(
                raw,
                base_url=page_url,
            )
        )

        if (
            url
            and not
            _looks_like_bad_image(
                url
            )
        ):
            return url


    # itemprop=image
    raw = (
        parser.meta.get(
            "image"
        )
    )

    url = (
        _valid_http_url(
            raw,
            base_url=page_url,
        )
    )

    if (
        url
        and not
        _looks_like_bad_image(
            url
        )
    ):
        return url

    return None


# =============================================================
# HTML IMAGE SCORING
# =============================================================


def _score_html_image(
    image: HtmlImage,
    *,
    title: str,
) -> int:
    """Score a normal img tag for likelihood of being product image."""

    combined = " ".join(
        [
            image.url,
            image.alt,
            image.class_name,
            image.element_id,
        ]
    )

    if _looks_like_bad_image(
        combined
    ):
        return -1000


    score = 0

    title_tokens = (
        _text_tokens(
            title
        )
    )

    image_tokens = (
        _text_tokens(
            " ".join(
                [
                    image.url,
                    image.alt,
                ]
            )
        )
    )

    overlap = len(
        title_tokens
        & image_tokens
    )

    score += (
        overlap
        * 10
    )


    # Alt text is useful evidence.
    if image.alt:
        score += 3


    # Prefer reasonably large images.
    if (
        image.width
        is not None
        and image.width
        >= 300
    ):
        score += 4

    if (
        image.height
        is not None
        and image.height
        >= 250
    ):
        score += 4

    if (
        image.width
        is not None
        and image.height
        is not None
        and image.width
        <= 100
        and image.height
        <= 100
    ):
        score -= 20


    normalized_context = (
        " ".join(
            [
                image.alt,
                image.class_name,
                image.element_id,
            ]
        )
        .lower()
    )

    for marker in (
        "product",
        "gallery",
        "main-image",
        "main_image",
        "product-image",
        "product_image",
        "featured",
    ):
        if (
            marker
            in normalized_context
        ):
            score += 8

    return score


def _extract_best_html_image(
    parser: ProductPageHTMLParser,
    *,
    page_url: str,
    title: str,
) -> str | None:
    """Choose best normal <img> candidate."""

    candidates: list[
        tuple[
            int,
            str,
        ]
    ] = []

    seen: set[
        str
    ] = set()

    for image in (
        parser.images
    ):
        url = (
            _valid_http_url(
                image.url,
                base_url=page_url,
            )
        )

        if not url:
            continue

        if url in seen:
            continue

        seen.add(
            url
        )

        if _looks_like_bad_image(
            url
        ):
            continue

        score = (
            _score_html_image(
                image,
                title=title,
            )
        )

        if score < 0:
            continue

        candidates.append(
            (
                score,
                url,
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0]
        ),
        reverse=True,
    )

    best_score, best_url = (
        candidates[0]
    )

    # A completely random img with no evidence
    # is not trustworthy enough.
    if best_score < 3:
        return None

    return best_url


# =============================================================
# NETWORK SAFETY
# =============================================================


def _hostname_is_public(
    hostname: str,
) -> bool:
    """Reject localhost/private/link-local/reserved addresses."""

    normalized = (
        hostname
        .strip()
        .lower()
        .rstrip(".")
    )

    if normalized in {
        "localhost",
        "localhost.localdomain",
    }:
        return False


    try:
        direct_ip = (
            ipaddress
            .ip_address(
                normalized
            )
        )

        return (
            direct_ip.is_global
        )

    except ValueError:
        pass


    try:
        records = (
            socket.getaddrinfo(
                normalized,
                None,
            )
        )

    except OSError:
        return False


    found_ip = False

    for record in records:
        address = (
            record[4][0]
        )

        try:
            ip = (
                ipaddress
                .ip_address(
                    address
                )
            )

        except ValueError:
            continue

        found_ip = True

        if not ip.is_global:
            return False

    return found_ip


async def _safe_public_url(
    url: str,
) -> bool:
    """Validate URL before server-side fetching."""

    from app.services.extraction.product_page_validator import http_url
    if not http_url(url):
        return False
    parsed = urlparse(url)

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return False

    if not parsed.hostname:
        return False

    return await asyncio.to_thread(
        _hostname_is_public,
        parsed.hostname,
    )


# =============================================================
# RESOLVER
# =============================================================


class ProductImageResolver:
    """
    Resolve the best image for a source page.

    Priority:
    1. JSON-LD Product.image
    2. og:image / twitter:image
    3. Good <img> product candidate
    4. Existing Tavily image, only if not obviously bad
    """

    def __init__(
        self,
        *,
        concurrency: int = 5,
    ) -> None:
        settings = (
            get_settings()
        )
        self._client = None
        self._configure_limits(settings, concurrency)

    @asynccontextmanager
    async def session(self):
        """Connection pooling scoped to one retrieval, including image probes."""
        if self._client is not None:
            yield
            return
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=min(2.5, self.timeout)),
            follow_redirects=False,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=8),
        ) as client:
            self._client = client
            try:
                yield
            finally:
                self._client = None

    @asynccontextmanager
    async def _http_client(self):
        if self._client is not None:
            yield self._client
        else:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                yield client

    def _configure_limits(self, settings, concurrency):

        configured_timeout = float(
            settings
            .search_timeout_seconds
        )

        self.timeout = min(
        max(
            configured_timeout,
            2.5,
        ),
        4.0,
    )


        self.semaphore = (
            asyncio.Semaphore(
                max(
                    1,
                    concurrency,
                )
            )
        )


    async def _fetch_html(
        self,
        url: str,
    ) -> tuple[
        str,
        str,
    ] | None:
        """
        Fetch HTML with validated redirects.

        Returns:
            (final_url, html)
        """

        current_url = url

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/152.0 Safari/537.36"
            ),

            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "*/*;q=0.8"
            ),

            "Accept-Language": (
                "vi-VN,vi;q=0.9,en;q=0.7"
            ),
        }


        async with self._http_client() as client:

            for _ in range(
                4
            ):
                if not await (
                    _safe_public_url(
                        current_url
                    )
                ):
                    return None

                try:
                    # Stream with a byte cap; slicing response.text after a
                    # full download does not bound network/memory consumption.
                    async with client.stream('GET', current_url, headers=headers) as response:
                        if response.status_code == 200:
                            body = bytearray()
                            async for chunk in response.aiter_bytes():
                                body.extend(chunk)
                                if len(body) > 2_000_000:
                                    return None
                            # aiter_bytes already decodes Content-Encoding (gzip,
                            # br). Do not feed decoded bytes through that decoder again.
                            html = bytes(body).decode(response.encoding or 'utf-8', errors='replace')

                except httpx.HTTPError:
                    return None


                # ---------------------------------------------
                # REDIRECT
                # ---------------------------------------------

                if response.status_code in {
                    301,
                    302,
                    303,
                    307,
                    308,
                }:
                    location = (
                        response.headers.get(
                            "location"
                        )
                    )

                    if not location:
                        return None

                    current_url = (
                        urljoin(
                            current_url,
                            location,
                        )
                    )

                    continue


                if (
                    response.status_code
                    != 200
                ):
                    return None


                content_type = (
                    response.headers.get(
                        "content-type",
                        ""
                    )
                    .lower()
                )

                if (
                    "text/html"
                    not in content_type
                    and
                    "application/xhtml+xml"
                    not in content_type
                ):
                    return None


                if not html:
                    return None

                return (
                    current_url,
                    html,
                )

        return None

    async def inspect(self, page_url: str, expected_name: str = "", *, resolve_images: bool = True) -> dict:
        """Validate the page and verify a bounded number of image responses."""
        from app.services.extraction.product_page_validator import inspect_page
        from app.services.performance import measure
        async with self.semaphore:
            result = None
            try:
                async with asyncio.timeout(18):
                    with measure('page_fetch_ms'):
                        fetched = await self._fetch_html(page_url)
                    if not fetched:
                        return {"product_page_valid": False, "evidence_url": page_url,
                                "page_fetched": False, "fetch_failure": "http_or_network",
                                "fetch_blocked": True, "verification_level": "UNVERIFIED", "product_page_confidence": 0,
                                "reason": "Không tải được trang để xác minh.", "image_url": None}
                    final_url, html = fetched
                    with measure('verification_ms'):
                        result = inspect_page(final_url, html, expected_name)
                    result['page_fetched'] = True
                    if not resolve_images:
                        return result
                    for image_url, origin in result.pop("image_candidates", []):
                        if await self._image_loads(image_url):
                            result.update(image_url=image_url, image_source=origin)
                            break
                    return result
            except (TimeoutError, ValueError, httpx.HTTPError):
                if result is not None:
                    # A failed image probe must not invalidate a verified sales page.
                    return result
                return {"product_page_valid": False, "evidence_url": page_url,
                        "page_fetched": bool(result), "fetch_failure": "timeout_or_invalid_data",
                        "fetch_blocked": True, "verification_level": "UNVERIFIED", "product_page_confidence": 0,
                        "reason": "Hết thời gian hoặc dữ liệu trang không hợp lệ.", "image_url": None}

    async def _image_loads(self, url: str) -> bool:
        """Bounded GET prefix probe; HEAD support is never required."""
        from app.services.extraction.product_page_validator import http_url, same_identity
        from app.services.extraction.product_image_candidates import (
            bad_image, image_label, normalized_image_url, raster_prefix,
        )
        from app.services.performance import current_trace
        original_label = image_label(url)
        record = dict(url=url, attempts=[], reason='cancelled_or_interrupted', accepted=False, bytes_read=0)
        trace = current_trace.get()
        if trace is not None:
            records = trace.diagnostics.setdefault('image_probes', [])
            if len(records) < 100: records.append(record)
        def finish(accepted, reason):
            record.update(accepted=accepted, reason=reason)
            return accepted
        async with self._http_client() as client:
            for _ in range(4):
                if not http_url(url) or bad_image(url) or not await _safe_public_url(url):
                    return finish(False, 'unsafe_url')
                try:
                    async with client.stream('GET', url, headers={
                        'Range': 'bytes=0-4095',
                        'Accept': 'image/avif,image/webp,image/png,image/jpeg,image/gif',
                    }) as response:
                        mime = response.headers.get('content-type', '').split(';')[0].strip().lower()
                        record['attempts'].append(dict(url=url, status=response.status_code, mime=mime))
                        if response.is_redirect:
                            target = normalized_image_url(response.headers.get('location'), url)
                            if not target:
                                return finish(False, 'unsafe_redirect')
                            label = image_label(target)
                            # Opaque original URLs remain valid; changing the asset
                            # needs matching identity. A different opaque hash is unknown.
                            if label != original_label and not same_identity(original_label, label):
                                return finish(False, 'unrelated_or_unproven_redirect')
                            url = target
                            continue
                        if response.status_code not in {200, 206}:
                            return finish(False, 'http_status')
                        if response.status_code == 206:
                            import re
                            if not re.fullmatch(r'bytes 0-\d+/(?:\d+|\*)', response.headers.get('content-range', '')):
                                return finish(False, 'invalid_content_range')
                        if mime not in {'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/avif'}:
                            return finish(False, 'non_raster_mime')
                        data = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=4096):
                            data.extend(chunk[:4096 - len(data)])
                            if len(data) >= 4096: break
                        record['bytes_read'] = len(data)
                        accepted = raster_prefix(bytes(data))
                        return finish(accepted, 'verified_raster_prefix' if accepted else 'invalid_or_tiny_raster')
                except httpx.HTTPError:
                    return finish(False, 'http_transport_error')
        return finish(False, 'redirect_limit')

    async def resolve(self, *, page_url: str, title: str = "", tavily_image_url: str | None = None) -> str | None:
        # Query-wide/provider images do not prove product identity.
        return (await self.inspect(page_url, title)).get("image_url")

    async def enrich_sources(self, sources: list[SearchSourceItem]) -> None:
        from app.services.extraction.product_page_validator import classify_source
        async def enrich(source):
            source.image_url = None
            try:
                source.page_validation = await self.inspect(source.url)
                source.image_url = source.page_validation.get("image_url")
                source.result_type = source.page_validation.get('result_type') or classify_source(source.url)
            except Exception:
                source.page_validation = {"product_page_valid": False, "evidence_url": source.url,
                                          "reason": "Không xác minh được trang.", "image_url": None}
                source.result_type = classify_source(source.url)
        await asyncio.gather(*(enrich(source) for source in sources))
