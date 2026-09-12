from sqlalchemy import inspect, select

from app.core.database import SessionLocal, engine, init_db
from app.models import (
    Product,
    ProductOffer,
    Recommendation,
    Requirement,
    SearchSession,
    SearchSessionStatus,
    Source,
    User,
)


EXPECTED_TABLES = {
    "users",
    "search_sessions",
    "requirements",
    "search_queries",
    "sources",
    "products",
    "product_offers",
    "recommendations",
    "comparison_sessions",
    "feedback",
}


def test_all_required_tables_exist() -> None:
    init_db()

    table_names = set(
        inspect(engine).get_table_names()
    )

    assert EXPECTED_TABLES.issubset(table_names)


def test_core_model_relationships_can_be_persisted() -> None:
    init_db()

    with SessionLocal() as db:
        user = User()

        session = SearchSession(
            user=user,
            raw_query=(
                "Tôi có 5 triệu, cần điện thoại "
                "chụp ảnh và chơi game."
            ),
            status=SearchSessionStatus.PROCESSING,
        )

        session.requirement = Requirement(
            category="điện thoại",
            budget_max=5_000_000,
            purpose=[
                "chụp ảnh",
                "chơi game",
            ],
            requirements=[
                {
                    "name": "camera",
                    "value": "tốt",
                    "priority": 5,
                },
                {
                    "name": "battery",
                    "value": "pin lâu",
                    "priority": 4,
                },
            ],
            excluded_requirements=[
                "máy quá nặng"
            ],
            confidence=0.95,
        )

        source = Source(
            url="https://example.com/products/demo-phone",
            domain="example.com",
            title="Demo Phone",
            reliability_score=80,
        )

        product = Product(
            name="Demo Phone X",
            brand="Demo",
            model="X",
            normalized_name="demo phone x",
            rating=4.6,
            review_count=120,
            specifications={
                "battery": "5000mAh"
            },
        )

        product.offers.append(
            ProductOffer(
                merchant="Demo Store",
                price=4_790_000,
                availability="in_stock",
                source=source,
                product_url=(
                    "https://example.com/products/"
                    "demo-phone"
                ),
            )
        )

        db.add_all([
            session,
            product,
        ])

        db.flush()

        recommendation = Recommendation(
            session=session,
            product=product,
            final_score=91.5,
            budget_score=25.0,
            requirement_score=27.0,
            purpose_score=18.0,
            rating_score=9.0,
            review_score=4.0,
            source_score=8.5,
            confidence=0.90,
            rank=1,
            explanation={
                "summary": (
                    "Dữ liệu demo dùng để "
                    "kiểm tra model."
                )
            },
        )

        db.add(recommendation)

        db.commit()

        persisted = db.scalar(
            select(SearchSession).where(
                SearchSession.id == session.id
            )
        )

        assert persisted is not None

        assert persisted.requirement is not None

        assert (
            persisted.requirement.budget_max
            == 5_000_000
        )

        assert len(product.offers) == 1

        assert recommendation.final_score == 91.5

        # Xóa dữ liệu test sau khi kiểm tra.
        db.delete(session)
        db.delete(product)
        db.delete(source)

        db.commit()