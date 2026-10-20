"""SQLAlchemy engine, session factory, and database health helpers."""

from collections.abc import Generator

from sqlalchemy import (
    create_engine,
    event,
    inspect,
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


def apply_additive_migrations(target_engine=engine) -> None:
    """Upgrade legacy SQLite offer columns without deleting or rewriting rows."""
    if not str(target_engine.url).startswith("sqlite"):
        return
    existing = inspect(target_engine).get_table_names()
    if "product_offers" not in existing:
        return
    columns = {item["name"] for item in inspect(target_engine).get_columns("product_offers")}
    additions = {
        "variant_id": "INTEGER REFERENCES product_variants(id) ON DELETE SET NULL",
        "platform": "VARCHAR(24)", "external_product_id": "VARCHAR(160)",
        "external_shop_id": "VARCHAR(160)", "external_sku_id": "VARCHAR(160)",
        "listed_price": "INTEGER", "sale_price": "INTEGER", "price_min": "INTEGER",
        "price_max": "INTEGER", "shipping_fee": "INTEGER", "voucher": "JSON", "warranty": "TEXT",
        "listed_price_minor_units": "INTEGER", "sale_price_minor_units": "INTEGER",
        "currency_minor_unit": "INTEGER",
        "last_seen_at": "DATETIME", "last_verified_at": "DATETIME",
        "freshness_status": "VARCHAR(24) NOT NULL DEFAULT 'UNKNOWN'", "evidence_method": "VARCHAR(40)",
    }
    with target_engine.begin() as connection:
        for name, sql_type in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE product_offers ADD COLUMN {name} {sql_type}"))
    if "price_observations" in existing:
        observation_columns = {
            item["name"] for item in inspect(target_engine).get_columns("price_observations")
        }
        with target_engine.begin() as connection:
            for name in (
                "listed_price_minor_units",
                "sale_price_minor_units",
                "currency_minor_unit",
            ):
                if name not in observation_columns:
                    connection.execute(
                        text(f"ALTER TABLE price_observations ADD COLUMN {name} INTEGER")
                    )
    if "crawl_runs" in existing:
        crawl_run_columns = {
            item["name"] for item in inspect(target_engine).get_columns("crawl_runs")
        }
        if "robots_checked_at" not in crawl_run_columns:
            with target_engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE crawl_runs ADD COLUMN robots_checked_at DATETIME")
                )


def init_db() -> None:
    """Apply additive compatibility changes and create missing tables.

    SQLite has no server-side migration runner in this local MVP.  These
    idempotent ALTERs preserve every legacy row/snapshot and are deliberately
    additive; operators should still back up the database before upgrading.
    """

    import app.models

    apply_additive_migrations(engine)

    Base.metadata.create_all(
        bind=engine
    )

    if settings.database_url.startswith("sqlite"):
        with engine.begin() as connection:
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_product_offers_variant_id ON product_offers (variant_id)"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_product_offers_platform ON product_offers (platform)"
            ))
            connection.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_offer_external_identity "
                "ON product_offers(platform, external_product_id, external_shop_id, external_sku_id) "
                "WHERE external_product_id IS NOT NULL AND external_shop_id IS NOT NULL AND external_sku_id IS NOT NULL"
            ))


def check_database() -> bool:
    """Check whether the database accepts a query."""

    with engine.connect() as connection:
        connection.execute(
            text(
                "SELECT 1"
            )
        )

    return True
