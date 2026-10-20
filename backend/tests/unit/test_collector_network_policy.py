import asyncio
import socket
from datetime import datetime, timezone

import httpcore
import httpx
import pytest

from app.schemas.collector import SourceRegistration
from app.services.collectors.network_policy import (
    EgressPolicyError,
    PinnedAsyncHTTPTransport,
    PinnedAsyncNetworkBackend,
    public_ip,
)
from app.services.collectors.egress_proxy import BrowserEgressProxy
from app.services.collectors.preflight import validate_registered_url


def dns(address):
    return lambda *args, **kwargs: [
        (socket.AF_INET6 if ":" in address else socket.AF_INET,
         socket.SOCK_STREAM, 6, "", (address, 443))
    ]


class RecordingStream(httpcore.AsyncNetworkStream):
    def __init__(self):
        self.writes = []
        self.server_hostname = None
        self.sent_response = False

    async def read(self, max_bytes, timeout=None):
        if self.sent_response:
            return b""
        self.sent_response = True
        return b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"

    async def write(self, buffer, timeout=None):
        self.writes.append(buffer)

    async def aclose(self):
        return None

    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        self.server_hostname = server_hostname
        return self

    def get_extra_info(self, info):
        return None


class RecordingBackend(httpcore.AsyncNetworkBackend):
    def __init__(self):
        self.connections = []
        self.streams = []

    async def connect_tcp(self, host, port, **kwargs):
        self.connections.append((host, port))
        stream = RecordingStream()
        self.streams.append(stream)
        return stream

    async def connect_unix_socket(self, *args, **kwargs):
        raise AssertionError("unix connection attempted")

    async def sleep(self, seconds):
        return None


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1", "10.0.0.1", "169.254.169.254", "224.0.0.1",
        "0.0.0.0", "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1",
        "::ffff:169.254.169.254",
    ],
)
def test_public_ip_rejects_ssrf_address_classes(address):
    with pytest.raises(ValueError, match="non-public"):
        public_ip(address)


@pytest.mark.parametrize("address", ["8.8.8.8", "2606:4700:4700::1111"])
def test_public_ip_accepts_global_ipv4_and_ipv6(address):
    assert str(public_ip(address)) == address


@pytest.mark.asyncio
async def test_connection_is_pinned_but_host_and_tls_sni_remain_original(monkeypatch):
    raw = RecordingBackend()
    backend = PinnedAsyncNetworkBackend(
        ["shop.example"], resolver=dns("93.184.216.34"), backend=raw
    )
    transport = PinnedAsyncHTTPTransport(backend)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8888")
    async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
        response = await client.get("https://shop.example/product/1")

    assert response.text == "ok"
    assert raw.connections == [("93.184.216.34", 443)]
    assert raw.streams[0].server_hostname == "shop.example"
    request_bytes = b"".join(raw.streams[0].writes)
    assert b"Host: shop.example" in request_bytes
    assert b"127.0.0.1:8888" not in request_bytes


@pytest.mark.asyncio
async def test_dns_rebinding_is_denied_at_connection_after_public_preflight():
    answers = iter(["93.184.216.34", "127.0.0.1"])

    def rebinding_resolver(*args, **kwargs):
        return dns(next(answers))(*args, **kwargs)

    source = SourceRegistration(
        source_id="shop",
        domain="shop.example",
        kind="product_page",
        permission_status="approved",
        permission_basis="Test approval",
        terms_url="https://shop.example/terms",
        terms_checked_at=datetime(2026, 10, 16, tzinfo=timezone.utc),
        enabled=True,
        allowed_paths=["/"],
    )
    validate_registered_url(
        "https://shop.example/product/1", source, resolver=rebinding_resolver
    )
    raw = RecordingBackend()
    backend = PinnedAsyncNetworkBackend(
        ["shop.example"], resolver=rebinding_resolver, backend=raw
    )

    with pytest.raises(EgressPolicyError, match="non-public"):
        await backend.connect_tcp("shop.example", 443)
    assert raw.connections == []


@pytest.mark.asyncio
async def test_every_reconnect_and_retry_rechecks_dns_and_host_allowlist():
    answers = iter(["93.184.216.34", "10.0.0.2"])
    resolver = lambda *args, **kwargs: dns(next(answers))(*args, **kwargs)
    raw = RecordingBackend()
    backend = PinnedAsyncNetworkBackend(
        ["shop.example"], resolver=resolver, backend=raw
    )

    await backend.connect_tcp("shop.example", 443)
    with pytest.raises(EgressPolicyError):
        await backend.connect_tcp("shop.example", 443)
    with pytest.raises(EgressPolicyError, match="outside"):
        await backend.connect_tcp("redirect.attacker.example", 443)
    assert raw.connections == [("93.184.216.34", 443)]


@pytest.mark.asyncio
async def test_browser_proxy_rejects_wrong_host_before_upstream_connection():
    async with BrowserEgressProxy(
        "shop.example", resolver=dns("93.184.216.34")
    ) as proxy:
        reader, writer = await asyncio.open_connection("127.0.0.1", proxy.port)
        writer.write(
            b"CONNECT metadata.google.internal:443 HTTP/1.1\r\n"
            b"Host: metadata.google.internal:443\r\n\r\n"
        )
        await writer.drain()
        response = await reader.read(1024)
        writer.close()
        await writer.wait_closed()

    assert response.startswith(b"HTTP/1.1 403")
    assert proxy.connections == 0
    assert proxy.denials == 1
