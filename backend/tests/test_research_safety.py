"""Negative and additive-upgrade checks; always offline."""
import gzip
import json

import httpx
import pytest
from sqlalchemy import func, select

from app.core.database import SessionLocal, engine, init_db
from app.models import Product, ResearchProduct, HistoricalPriceReference, ResearchImportRun
from app.services.research.importer import import_catalog, source_url
from scripts.download_research_metadata import open_response


def test_additive_tables_preserve_legacy_catalog():
    with SessionLocal() as db:
        product = Product(name="Existing user product")
        db.add(product)
        db.commit()
        identity = product.id
    for model in (HistoricalPriceReference, ResearchImportRun, ResearchProduct):
        model.__table__.drop(engine)
    init_db()
    with SessionLocal() as db:
        assert db.get(Product, identity).name == "Existing user product"
        assert db.scalar(select(func.count(ResearchProduct.id))) == 0


def test_truncated_gzip_atomic_rollback(tmp_path):
    path = tmp_path / "broken.gz"
    raw = dict(title="Fixture title", parent_asin="B000000001", categories=["Electronics"], details={})
    path.write_bytes(gzip.compress((json.dumps(raw) + "\n").encode())[:-8])
    with SessionLocal() as db:
        with pytest.raises(EOFError):
            import_catalog(db, path=path, category="Electronics", revision="fixture")
        assert db.scalar(select(func.count(Product.id))) == 0


@pytest.mark.asyncio
async def test_downloader_denies_unapproved_redirect_before_connection():
    calls = []
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="Redirect outside"):
            await open_response(client, "GET", "https://huggingface.co/approved", {})
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_downloader_redirect_loop_capped():
    calls = []
    def handler(request):
        calls.append(request.url)
        return httpx.Response(302, headers={"Location": "/loop"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="Too many"):
            await open_response(client, "HEAD", "https://huggingface.co/loop", {})
    assert len(calls) == 6


@pytest.mark.parametrize("category,revision", [("Other", "main"), ("Electronics", "../private"), ("Electronics", "https://evil")])
def test_source_path_injection_rejected(category, revision):
    with pytest.raises(ValueError):
        source_url(revision, category)
