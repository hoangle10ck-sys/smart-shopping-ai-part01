import pytest
from sqlalchemy import func, select

from app.core.database import SessionLocal, check_database, engine
from app.models.search_session import SearchSession


def test_database_connection() -> None:
    assert check_database() is True


@pytest.mark.parametrize("run", [1, 2])
def test_database_is_clean_between_tests(run: int) -> None:
    """Committed rows must not leak into the next test or the real database."""
    assert engine.url.database is not None
    assert "smart-shopping-tests-" in engine.url.database
    with SessionLocal() as db:
        assert db.scalar(select(func.count(SearchSession.id))) == 0
        db.add(SearchSession(raw_query=f"Isolation check {run}"))
        db.commit()
        assert db.scalar(select(func.count(SearchSession.id))) == 1
