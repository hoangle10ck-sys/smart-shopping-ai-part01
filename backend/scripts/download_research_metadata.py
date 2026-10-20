"""Bounded, pinned official metadata prefix for local noncommercial thesis research.

Not a general crawler. No live flags, no dataset code, no full-corpus download.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from app.services.collectors.network_policy import build_pinned_http_client
from app.services.research.importer import CATEGORIES, source_url, MAX_LINE_BYTES

REVISION = "2b6d039ed471f2ba5fd2acb718bf33b0a7e5598e"
ALLOWED = {"huggingface.co", "cas-bridge.xethub.hf.co", "cdn-lfs.huggingface.co", "cdn-lfs.hf.co", "us.aws.cdn.hf.co"}
MAX_DOWNLOAD = 4 * 1024 * 1024  # per category, wire-body cap; Range must be honored


async def open_response(client, method, url, headers):
    for _ in range(6):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED or parsed.port not in (None, 443) or parsed.username:
            raise ValueError("Redirect outside approved official download hosts")
        response = await client.send(client.build_request(method, url, headers=headers), stream=True)
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("location")
            await response.aclose()
            if not location:
                raise ValueError("Redirect without location")
            from urllib.parse import urljoin
            url = urljoin(url, location)
            continue
        return response
    raise ValueError("Too many redirects")


async def download(category: str, output_dir: Path, records: int = 150) -> dict:
    if not 1 <= records <= 1000:
        raise ValueError("records must be 1..1000")
    url = source_url(REVISION, category)
    path = output_dir / f"meta_{category}.prefix.jsonl"
    if path.exists() or path.with_suffix(".manifest.json").exists():
        raise ValueError("Output exists: reuse and verify it, or choose a new directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    async with build_pinned_http_client(allowed_domains=ALLOWED, timeout=45) as client:
        head = await open_response(client, "HEAD", url, {})
        try:
            head.raise_for_status()
            full_size = int(head.headers.get("content-length", "0"))
        finally:
            await head.aclose()
        if full_size <= 0:
            raise ValueError("Full source size unknown; refusing download")
        response = await open_response(client, "GET", url, {"Range": f"bytes=0-{MAX_DOWNLOAD-1}", "Accept-Encoding": "identity"})
        data = bytearray()
        try:
            if response.status_code != 206 or not re.fullmatch(rf"bytes 0-\d+/{full_size}", response.headers.get("content-range", "")):
                raise ValueError("Server did not honor bounded Range")
            async for chunk in response.aiter_raw(65536):
                if len(data) + len(chunk) > MAX_DOWNLOAD:
                    raise ValueError("Download byte cap exceeded")
                data.extend(chunk)
                if data.count(b"\n") >= records:
                    break
        finally:
            await response.aclose()
    lines = bytes(data).split(b"\n")[:-1][:records]
    if len(lines) != records:
        raise ValueError("Not enough complete records within download cap")
    if any(len(line) > MAX_LINE_BYTES for line in lines):
        raise ValueError("Oversized native record")
    for line in lines:
        if not isinstance(json.loads(line), dict):
            raise ValueError("Invalid native metadata")
    retained = b"\n".join(lines) + b"\n"
    path.write_bytes(retained)
    manifest = dict(dataset="McAuley-Lab/Amazon-Reviews-2023", revision=REVISION, category=category,
        source_url=url, downloaded_at=datetime.now(timezone.utc).isoformat(), head_status=200,
        full_source_bytes=full_size, range_status=206, requested_range=f"bytes=0-{MAX_DOWNLOAD-1}",
        received_bytes=len(data), retained_bytes=len(retained), complete_records=records,
        sha256=hashlib.sha256(retained).hexdigest(), checksum_scope="retained native JSONL prefix, NOT full corpus",
        permission_basis="local noncommercial thesis research; source assessment; no redistribution",
        selection="first complete native records, prefix-biased; importer selection recorded separately")
    path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/research"))
    parser.add_argument("--records-per-category", type=int, default=150)
    parser.add_argument("--acknowledge-research-only", action="store_true", required=True)
    args = parser.parse_args()
    for category in CATEGORIES:
        print(json.dumps(await download(category, args.output_dir, args.records_per_category)))


if __name__ == "__main__":
    asyncio.run(main())
