"""Add Product.category to an existing SQLite MVP database."""

from sqlalchemy import inspect, text

from app.core.database import engine


def main() -> None:
    """Add the missing category column and index if necessary."""

    if engine.dialect.name != "sqlite":
        raise RuntimeError(
            "This development migration is intended for SQLite only."
        )

    inspector = inspect(engine)

    columns = {
        column["name"]
        for column in inspector.get_columns("products")
    }

    with engine.begin() as connection:
        if "category" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE products "
                    "ADD COLUMN category VARCHAR(120)"
                )
            )

            print(
                "Added products.category"
            )

        else:
            print(
                "products.category already exists"
            )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_products_category "
                "ON products (category)"
            )
        )

    print(
        "Product category migration completed."
    )


if __name__ == "__main__":
    main()