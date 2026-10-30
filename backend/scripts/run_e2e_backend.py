"""Start an isolated Demo backend for Playwright; never open the developer DB."""

import os
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory


def main():
    with TemporaryDirectory(prefix="smart-shopping-e2e-") as directory:
        database = Path(directory) / "e2e.sqlite3"
        os.environ.update(
            DATABASE_URL=f"sqlite:///{database.as_posix()}", DEMO_MODE="true",
            OPENAI_API_KEY="", GEMINI_API_KEY="", TAVILY_API_KEY="",
            SEARXNG_BASE_URL="", COLLECTOR_LIVE_ENABLED="false",
            COLLECTOR_POLICY_CONFIRMED="false", COLLECTOR_SOURCE_REGISTRY_JSON="[]",
            APP_ENV="test",
        )
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

        # Fail closed if any application code accidentally attempts external I/O.
        original_connect = socket.socket.connect

        def local_connect(sock, address):
            if not isinstance(address, tuple) or address[0] not in {"127.0.0.1", "::1", "localhost"}:
                raise RuntimeError("External network is disabled in browser E2E")
            return original_connect(sock, address)

        socket.socket.connect = local_connect
        from app.core.config import get_settings
        get_settings.cache_clear()
        from app.core.database import engine
        from app.main import app
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn

        assert Path(engine.url.database).resolve() == database.resolve()
        assert get_settings().demo_mode
        assert not get_settings().searxng_base_url
        assert not get_settings().collector_live_enabled
        assert not get_settings().collector_policy_confirmed
        from app.core.database import init_db, SessionLocal
        from app.services.search.unified.catalog_source import DatabaseCatalogSource
        from app.services.research.importer import CATEGORIES, import_catalog

        # Test-only byte/source proof for the reserved QA image host. This
        # process has an isolated disposable database and blocks external I/O.
        from datetime import datetime, timezone
        from hashlib import sha256
        from urllib.parse import urlsplit

        catalog_payload = DatabaseCatalogSource._catalog_payload

        def payload_with_qa_image_proof(product, offer):
            payload = catalog_payload(product, offer)
            image_url = product.image_url
            if image_url and urlsplit(image_url).hostname == "qa-catalog.example":
                payload["page_validation"].update(
                    source_observation_valid=True,
                    image_url=image_url,
                    image_probe={
                        "accepted": True,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "content_type": "image/png",
                        "content_sha256": sha256(image_url.encode("utf-8")).hexdigest(),
                    },
                    evidence_url=offer.product_url,
                )
            return payload

        DatabaseCatalogSource._catalog_payload = staticmethod(payload_with_qa_image_proof)
        init_db()
        real_dir = os.environ.get("RESEARCH_E2E_DATA")
        fixture_dir = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "research"
        with SessionLocal() as db:
            for category in CATEGORIES:
                path = Path(real_dir) / f"meta_{category}.prefix.jsonl" if real_dir else fixture_dir / f"{category}.jsonl"
                if real_dir:
                    from scripts.download_research_metadata import REVISION
                    revision = REVISION
                else:
                    revision = "SYNTHETIC-TEST-ONLY"
                import_catalog(db, path=path, category=category, revision=revision, limit=75)
            db.commit()
            # Current verified offers exist only in this disposable E2E DB.
            # The UI journey must exercise unified catalog search, not Demo offers.
            from tests.fixtures.unified_catalog import seed_headphones
            seed_headphones(db, count=3)
        # Test-only origin, without changing application CORS or routes.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://127.0.0.1:13000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        try:
            uvicorn.run(app, host="127.0.0.1", port=18000, log_level="warning")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
