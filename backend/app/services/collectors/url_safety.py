"""Strict marketplace URL validation and SSRF protections."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from app.services.collectors.network_policy import resolve_public_addresses


ALLOWED_HOSTS = {
    "shopee": ("shopee.vn",),
    "lazada": ("lazada.vn",),
}


class UnsafeURL(ValueError):
    pass


def platform_for_host(host: str) -> str | None:
    host = host.rstrip(".").lower()
    for platform, suffixes in ALLOWED_HOSTS.items():
        if any(host == suffix or host.endswith("." + suffix) for suffix in suffixes):
            return platform
    return None


def _public_addresses(host: str, resolver=socket.getaddrinfo) -> None:
    try:
        resolve_public_addresses(host, 443, resolver=resolver)
    except ValueError as exc:
        raise UnsafeURL(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class ValidatedURL:
    url: str
    platform: str
    host: str


def validate_marketplace_url(url: str, *, resolve_dns: bool = True, resolver=socket.getaddrinfo) -> ValidatedURL:
    try:
        parsed = urlsplit(url.strip())
    except ValueError as exc:
        raise UnsafeURL("Malformed URL") from exc
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeURL("Only HTTP(S) URLs are allowed")
    if not parsed.hostname or parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
        raise UnsafeURL("URL authority is not allowed")
    host = parsed.hostname.rstrip(".").lower()
    platform = platform_for_host(host)
    if platform is None:
        raise UnsafeURL("Host is not an allowed marketplace domain")
    if resolve_dns:
        _public_addresses(host, resolver)
    normalized = urlunsplit((parsed.scheme.lower(), host, parsed.path or "/", parsed.query, ""))
    return ValidatedURL(normalized, platform, host)
