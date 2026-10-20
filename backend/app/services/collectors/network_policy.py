"""Connection-time egress enforcement for collector HTTP clients.

URL validation is useful for clear errors, but it is not a security boundary:
DNS may change between validation and the TCP connection. This backend resolves
the original hostname at ``connect_tcp`` time, rejects the entire answer set if
any address is unsafe, and gives the socket backend a validated IP literal. The
HTTP origin remains unchanged, so HTTPX/httpcore still use the original hostname
for the Host header, TLS SNI, and certificate verification.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable
from typing import Any

import httpcore
import httpx


Resolver = Callable[..., list[tuple[Any, Any, Any, Any, tuple[Any, ...]]]]


class EgressPolicyError(httpcore.ConnectError):
    """A connection was denied before any socket was opened."""


def public_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Return a safe public address, including safe IPv4-mapped IPv6 handling."""
    if "%" in value:
        raise ValueError("scoped IPv6 addresses are not permitted")
    address = ipaddress.ip_address(value)
    mapped = address.ipv4_mapped if isinstance(address, ipaddress.IPv6Address) else None
    checked = mapped or address
    if (
        not checked.is_global
        or checked.is_private
        or checked.is_loopback
        or checked.is_link_local
        or checked.is_multicast
        or checked.is_reserved
        or checked.is_unspecified
    ):
        raise ValueError("non-public network address is not permitted")
    return address


def resolve_public_addresses(
    host: str,
    port: int,
    *,
    resolver: Resolver = socket.getaddrinfo,
) -> tuple[str, ...]:
    """Resolve a host and fail closed if any returned address is unsafe."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return (str(public_ip(host)),)

    try:
        infos = resolver(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("DNS resolution failed") from exc
    addresses = {str(info[4][0]) for info in infos if info[4]}
    if not addresses:
        raise ValueError("DNS returned no address")
    return tuple(str(public_ip(value)) for value in sorted(addresses))


class PinnedAsyncNetworkBackend(httpcore.AsyncNetworkBackend):
    """Resolve, validate, and pin each TCP connection to a safe IP literal."""

    def __init__(
        self,
        allowed_domains: Iterable[str],
        *,
        resolver: Resolver = socket.getaddrinfo,
        allow_subdomains: bool = False,
        backend: httpcore.AsyncNetworkBackend | None = None,
    ) -> None:
        self.allowed_domains = frozenset(
            domain.rstrip(".").lower() for domain in allowed_domains
        )
        if not self.allowed_domains:
            raise ValueError("At least one egress domain is required")
        self.resolver = resolver
        self.allow_subdomains = allow_subdomains
        self.backend = backend or httpcore.AnyIOBackend()

    def _host_allowed(self, host: str) -> bool:
        return host in self.allowed_domains or (
            self.allow_subdomains
            and any(host.endswith("." + domain) for domain in self.allowed_domains)
        )

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ) -> httpcore.AsyncNetworkStream:
        canonical_host = host.rstrip(".").lower()
        if not self._host_allowed(canonical_host):
            raise EgressPolicyError("Connection host is outside the egress allowlist")
        try:
            addresses = resolve_public_addresses(
                canonical_host, port, resolver=self.resolver
            )
        except ValueError as exc:
            raise EgressPolicyError(str(exc)) from exc
        return await self.backend.connect_tcp(
            addresses[0],
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(self, *args, **kwargs):
        raise EgressPolicyError("Unix sockets are not permitted for collectors")

    async def sleep(self, seconds: float) -> None:
        await self.backend.sleep(seconds)


class PinnedAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """HTTPX transport whose pool uses the enforcing network backend."""

    def __init__(self, network_backend: PinnedAsyncNetworkBackend) -> None:
        # Proxies and transport retries are intentionally unavailable.
        super().__init__(verify=True, trust_env=False, retries=0, proxy=None)
        pool = getattr(self, "_pool", None)
        if pool is None or not hasattr(pool, "_network_backend"):
            raise RuntimeError("Installed HTTPX/httpcore does not support safe egress")
        pool._network_backend = network_backend


def build_pinned_http_client(
    *,
    allowed_domains: Iterable[str],
    resolver: Resolver = socket.getaddrinfo,
    allow_subdomains: bool = False,
    timeout: float = 8.0,
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    backend = PinnedAsyncNetworkBackend(
        allowed_domains,
        resolver=resolver,
        allow_subdomains=allow_subdomains,
    )
    return httpx.AsyncClient(
        transport=PinnedAsyncHTTPTransport(backend),
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
        headers=headers,
    )
