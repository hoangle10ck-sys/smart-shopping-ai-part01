"""SQLAlchemy engine, session factory, and database health helpers."""

from collections.abc import Generator

from sqlalchemy import (
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
)

from app.core.config import (
    get_settings,
)


settings = get_settings()


_connect_args: dict[str, object] = {}


if settings.database_url.startswith(
    "sqlite"
):
    _connect_args.update(
        {
            "check_same_thread": False,

            # Wait instead of immediately raising
            # "database is locked".
            "timeout": 30,
        }
    )


engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
)


if settings.database_url.startswith(
    "sqlite"
):

    @event.listens_for(
        engine,
        "connect",
    )
    def _configure_sqlite(
        dbapi_connection: object,
        _: object,
    ) -> None:
        """Configure SQLite for concurrent web requests."""

        cursor = (
            dbapi_connection.cursor()
        )

        # Keep relational integrity enabled.
        cursor.execute(
            "PRAGMA foreign_keys=ON"
        )

        # Wait up to 30 seconds for a temporary lock
        # instead of failing immediately.
        cursor.execute(
            "PRAGMA busy_timeout=30000"
        )

        # WAL allows readers and a writer to coexist
        # much better than the default journal mode.
        cursor.execute(
            "PRAGMA journal_mode=WAL"
        )

        # Good balance for local application usage.
        cursor.execute(
            "PRAGMA synchronous=NORMAL"
        )

        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(
    DeclarativeBase
):
    """Base class for SQLAlchemy ORM models."""


def get_db() -> Generator[
    Session,
    None,
    None,
]:
    """Yield one database session per API request."""

    db = SessionLocal()

    try:
        yield db

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def init_db() -> None:
    """Import models and create missing database tables."""

    import app.models

    Base.metadata.create_all(
        bind=engine
    )


def check_database() -> bool:
    """Check whether the database accepts a query."""

    with engine.connect() as connection:
        connection.execute(
            text(
                "SELECT 1"
            )
        )

    return True