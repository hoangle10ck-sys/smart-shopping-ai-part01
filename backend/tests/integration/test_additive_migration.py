from sqlalchemy import create_engine, inspect, text

from app.core.database import apply_additive_migrations


def test_legacy_offer_upgrade_preserves_row_and_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'legacy.sqlite').as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE product_offers (id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL, price INTEGER)"))
        connection.execute(text("INSERT INTO product_offers(id, product_id, price) VALUES (1, 9, 123000)"))
        connection.execute(text(
            "CREATE TABLE crawl_runs (id INTEGER PRIMARY KEY, platform VARCHAR(24), "
            "source_url TEXT, status VARCHAR(40), failure JSON, started_at DATETIME, "
            "completed_at DATETIME)"
        ))
    apply_additive_migrations(engine); apply_additive_migrations(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("product_offers")}
    assert {"variant_id", "platform", "sale_price", "last_verified_at", "freshness_status"} <= columns
    crawl_columns = {column["name"] for column in inspect(engine).get_columns("crawl_runs")}
    assert "robots_checked_at" in crawl_columns
    with engine.connect() as connection:
        assert connection.execute(text("SELECT product_id, price, freshness_status FROM product_offers WHERE id=1")).one() == (9, 123000, "UNKNOWN")
