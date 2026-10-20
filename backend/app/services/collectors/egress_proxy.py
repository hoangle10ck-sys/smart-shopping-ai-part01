"""Small fail-closed CONNECT proxy used by the browser collector.

Chromium is configured to use this proxy for every HTTP(S) request. Only HTTPS
CONNECT to an explicitly allowed hostname is accepted; the proxy resolves and
pins the upstream socket itself using the same address policy as HTTPX.
"""

from __future__ import annotations

import asyncio
import socket
from contextlib import suppress
from urllib.parse import urlsplit

from app.services.collectors.network_policy import resolve_public_addresses


class BrowserEgressProxy:
    def __init__(self, host: str, *, resolver=socket.getaddrinfo) -> None:
        self.host = host.rstrip(".").lower()
        self.resolver = resolver
        self.server: asyncio.Server | None = None
        self.port: int | None = None
        self.connections = 0
        self.denials = 0
        self.last_denial: str | None = None

    async def __aenter__(self) -> "BrowserEgressProxy":
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *args) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()

    async def _deny(self, writer: asyncio.StreamWriter, status="403 Forbidden") -> None:
        self.denials += 1
        if self.last_denial is None:
            self.last_denial = status
        writer.write(f"HTTP/1.1 {status}\r\nConnection: close\r\n\r\n".encode())
        with suppress(Exception):
            await writer.drain()
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 3.0)
        except (Exception, asyncio.CancelledError):
            await self._deny(writer, "400 Bad Request")
            return
        if len(header) > 16_384:
            await self._deny(writer, "431 Request Header Fields Too Large")
            return
        try:
            method, authority, _ = header.split(b"\r\n", 1)[0].decode("ascii").split()
            parsed = urlsplit("//" + authority)
            host = (parsed.hostname or "").rstrip(".").lower()
            port = parsed.port
        except (UnicodeError, ValueError):
            await self._deny(writer, "400 Bad Request")
            return
        if method != "CONNECT" or host != self.host or port != 443:
            self.last_denial = f"{method} {host}:{port}"
            await self._deny(writer)
            return
        try:
            addresses = resolve_public_addresses(host, port, resolver=self.resolver)
            upstream_reader, upstream_writer = await asyncio.open_connection(
                addresses[0], port
            )
        except (OSError, ValueError) as exc:
            self.last_denial = f"upstream {type(exc).__name__}: {exc}"
            await self._deny(writer, "502 Bad Gateway")
            return

        self.connections += 1
        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await writer.drain()

        async def pipe(source, target):
            try:
                while data := await source.read(64 * 1024):
                    target.write(data)
                    await target.drain()
            except (OSError, asyncio.CancelledError):
                pass
            finally:
                target.close()

        tasks = [
            asyncio.create_task(pipe(reader, upstream_writer)),
            asyncio.create_task(pipe(upstream_reader, writer)),
        ]
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in tasks:
            task.cancel()
        upstream_writer.close()
        writer.close()

