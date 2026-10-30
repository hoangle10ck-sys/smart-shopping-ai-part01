"""Run every test against a clean, disposable database with Demo disabled."""

from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


# Configure before collection imports app.main / app.core.database. Existing
# tests import SessionLocal and engine directly, so a dependency override alone
# would still let those tests write to the developer's database.
_test_directory = TemporaryDirectory(prefix="smart-shopping-tests-")
_database_path = Path(_test_directory.name) / "test.sqlite3"
_environment = pytest.MonkeyPatch()
_environment.setenv("DATABASE_URL", f"sqlite:///{_database_path.as_posix()}")
_environment.setenv("DEMO_MODE", "false")
# Tests must remain deterministic and free of external API charges regardless
# of credentials or collector settings in the developer's ignored .env file.
_environment.setenv("LLM_PROVIDER", "mock")
_environment.setenv("LLM_FALLBACK_PROVIDER", "")
_environment.setenv("OPENAI_API_KEY", "")
_environment.setenv("GEMINI_API_KEY", "")
_environment.setenv("TAVILY_API_KEY", "")
_environment.setenv("SEARXNG_BASE_URL", "")
_environment.setenv("COLLECTOR_LIVE_ENABLED", "false")
_environment.setenv("COLLECTOR_POLICY_CONFIRMED", "false")
_environment.setenv("COLLECTOR_SOURCE_REGISTRY_JSON", "[]")

from app.core.config import get_settings

get_settings.cache_clear()

from app.core.database import Base, engine, init_db

if engine.url.database is None or Path(engine.url.database).resolve() != _database_path.resolve():
    raise pytest.UsageError("Refusing to run tests against a non-test database.")


@pytest.fixture(scope="session", autouse=True)
def temporary_database() -> Generator[None, None, None]:
    """Dispose connections before removing the temporary SQLite files."""
    try:
        yield
    finally:
        engine.dispose()
        _environment.undo()
        get_settings.cache_clear()
        _test_directory.cleanup()


@pytest.fixture(autouse=True)
def clean_database(temporary_database: None) -> Generator[None, None, None]:
    """Create the schema for each test, including tests without app lifespan."""
    init_db()
    try:
        yield
    finally:
        Base.metadata.drop_all(bind=engine)
