"""Alembic environment wired to application Settings and model metadata.

Chạy từ ``backend/``: ``alembic revision --autogenerate -m "..."``.
URL lấy từ ``DATABASE_URL`` (app Settings), không hardcode trong alembic.ini.
"""

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.core.database import Base

import app.models  # noqa: F401  # registers every table on Base.metadata

config = context.config
config.set_main_option(
    "sqlalchemy.url",
    get_settings().database_url,
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL without a live database connection."""

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},

        # SQLite cannot ALTER most table attributes in place;
        # batch mode rewrites tables the way the additive
        # migrations in app.core.database already do.
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live engine."""

    connectable = engine_from_config(
        config.get_section(
            config.config_ini_section,
            {},
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=(
                connection.dialect.name == "sqlite"
            ),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
