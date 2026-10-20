"""Conservative JSON-LD/meta extraction; it never turns a range into a SKU price."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

from app.schemas.collector import FieldEvidence, OfferObservation, PriceRange, ProductObservation, VariantIdentity


class _DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.json_ld: list[str] = []
        self.visible_data: list[str] = []
        self._ignored_tags: list[str] = []
        self._json_depth = 0
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = dict(attrs)
        if tag == "meta" and values.get("content"):
            key = values.get("property") or values.get("name")
            if key:
                self.meta[key.lower()] = values["content"] or ""
        if tag in {"script", "style", "noscript"}:
            self._ignored_tags.append(tag)
        if tag == "script" and (values.get("type") or "").lower() == "application/ld+json":
            self._json_depth += 1
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._json_depth:
            self._buffer.append(data)
        elif not self._ignored_tags:
            self.visible_data.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "script" and self._json_depth:
            self.json_ld.append("".join(self._buffer))
            self._json_depth = 0
        if tag in {"script", "style", "noscript"} and self._ignored_tags:
            self._ignored_tags.pop()

    def visible_text(self, max_chars: int = 12000) -> str:
        return " ".join(" ".join(self.visible_data).split())[:max_chars]


def extract_visible_text(html: str, *, max_chars: int = 12000) -> str:
    parser = _DocumentParser()
    parser.feed(html)
    return parser.visible_text(max_chars)


def _walk(value: Any, *, inside_item_list: bool = False):
    if isinstance(value, list):
        for item in value:
            yield from _walk(item, inside_item_list=inside_item_list)
    elif isinstance(value, dict):
        kind = value.get("@type")
        kinds = (
            {kind}
            if isinstance(kind, str)
            else {item for item in kind if isinstance(item, str)}
            if isinstance(kind, list)
            else set()
        )
        in_item_list = inside_item_list or "ItemList" in kinds
        if "Product" in kinds and not inside_item_list:
            yield value
        for item in value.values():
            if isinstance(item, (dict, list)):
                yield from _walk(item, inside_item_list=in_item_list)


def _money(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() and number >= 0 else None


def _minor_units(value: Decimal | None, exponent: int | None) -> int | None:
    if value is None or exponent is None:
        return None
    scaled = value * (10**exponent)
    return int(scaled) if scaled == scaled.to_integral_value() else None


def _rating(value: Any) -> float | None:
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None
    return rating if 0 <= rating <= 5 else None


def extract_product(
    html: str,
    *,
    url: str,
    platform: str,
    default_currency: str | None = None,
    currency_minor_unit: int | None = None,
) -> ProductObservation | None:
    parser = _DocumentParser()
    parser.feed(html)
    products: list[dict[str, Any]] = []
    for raw in parser.json_ld:
        try:
            products.extend(_walk(json.loads(raw)))
        except (json.JSONDecodeError, TypeError):
            continue
    product = products[0] if products else {}
    name = product.get("name") or parser.meta.get("og:title")
    if not name:
        return None
    now = datetime.now(timezone.utc)
    brand = product.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")
    offers_data = product.get("offers")
    offer_items = offers_data if isinstance(offers_data, list) else ([offers_data] if isinstance(offers_data, dict) else [])
    offers: list[OfferObservation] = []
    shopee_ids = re.search(r"(?:-i\.|/product/)(\d+)[./](\d+)", url)
    lazada_id = re.search(r"-i(\d+)(?:-s(\d+))?\.html", url)
    for item in offer_items:
        currency_value = item.get("priceCurrency") or default_currency
        if currency_value is None and platform in {"shopee", "lazada"}:
            currency_value = "VND"
        currency = str(currency_value).upper() if isinstance(currency_value, str) and currency_value else "UNK"
        exponent = currency_minor_unit
        if exponent is None and currency == "VND":
            exponent = 0
        low, high = _money(item.get("lowPrice")), _money(item.get("highPrice"))
        exact = _money(item.get("price"))
        low_units, high_units, exact_units = (
            _minor_units(low, exponent),
            _minor_units(high, exponent),
            _minor_units(exact, exponent),
        )
        price_range = (
            PriceRange(minimum=low_units, maximum=high_units)
            if low_units is not None and high_units is not None and exponent == 0
            else None
        )
        sku = item.get("sku") or product.get("sku")
        attributes = {str(k): str(v) for k, v in (item.get("additionalProperty") or {}).items()} if isinstance(item.get("additionalProperty"), dict) else {}
        identity = VariantIdentity(platform=platform,
            external_product_id=(shopee_ids.group(2) if shopee_ids else lazada_id.group(1) if lazada_id else None),
            external_shop_id=shopee_ids.group(1) if shopee_ids else None,
            external_sku_id=str(sku) if sku else (lazada_id.group(2) if lazada_id and lazada_id.group(2) else None),
            attributes=attributes)
        offer_url = item.get("url") or url
        evidence = []
        if exact_units is not None and currency != "UNK":
            evidence.append(FieldEvidence(
                field="sale_price",
                value={"amount": str(exact), "minor_units": exact_units,
                       "currency": currency, "currency_minor_unit": exponent},
                source_url=url, json_path="offers.price",
                evidence_type="JSON_LD", observed_at=now,
                verification_status="VERIFIED"))
        if sku:
            evidence.append(FieldEvidence(
                field="sku", value=str(sku), source_url=url, evidence_type="JSON_LD",
                json_path="offers.sku" if item.get("sku") else "sku",
                observed_at=now, verification_status="VERIFIED"))
        offers.append(OfferObservation(identity=identity,
            merchant=(item.get("seller") or {}).get("name") if isinstance(item.get("seller"), dict) else None,
            sale_price=int(exact) if exact is not None and exponent == 0 and exact == exact.to_integral_value() else None,
            sale_price_minor_units=exact_units,
            currency_minor_unit=exponent,
            price_range=price_range,
            currency=currency, availability=item.get("availability"),
            product_url=offer_url, observed_at=now, evidence=evidence))
    rating = product.get("aggregateRating") or {}
    return ProductObservation(name=str(name), brand=str(brand) if brand else None,
        model=str(product.get("model")) if product.get("model") else None,
        product_rating=_rating(rating.get("ratingValue")),
        review_count=int(rating["reviewCount"]) if str(rating.get("reviewCount", "")).isdigit() else None,
        image_url=(str(product.get("image")) if isinstance(product.get("image"), str) else None),
        offers=offers, evidence=[FieldEvidence(field="name", value=name, source_url=url,
            json_path="name" if products else None,
            evidence_type="JSON_LD" if products else "META", observed_at=now, verification_status="VERIFIED")])
