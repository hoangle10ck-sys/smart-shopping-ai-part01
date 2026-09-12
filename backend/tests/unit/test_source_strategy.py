"""Tests for open product source strategy."""

from app.services.search.source_strategy import (
    SourceStrategy,
)


def test_phone_has_specialist_sources() -> None:
    domains = (
        SourceStrategy()
        .preferred_domains(
            "điện thoại"
        )
    )

    assert (
        "thegioididong.com"
        in domains
    )


def test_fashion_has_marketplace_sources() -> None:
    domains = (
        SourceStrategy()
        .preferred_domains(
            "áo khoác nam"
        )
    )

    assert (
        "shopee.vn"
        in domains
    )


def test_unknown_product_uses_open_web() -> None:
    domains = (
        SourceStrategy()
        .preferred_domains(
            "máy đóng đai thùng carton"
        )
    )

    # Empty means unrestricted Internet search,
    # not unsupported.
    assert domains == []