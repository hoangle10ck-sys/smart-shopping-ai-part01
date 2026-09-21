from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session
from app.core import database
from app.models import Requirement, RequirementBudget, SearchSession
from app.services.recommendation.recommendation_service import requirement_to_schema
from app.services.budget import apply_budget_semantics
from app.schemas.requirement import RequirementData
from app.services.cache.search_cache import make_cache_key


def test_init_adds_budget_table_without_deleting_or_backfilling_legacy_rows(tmp_path,monkeypatch):
    engine=create_engine('sqlite:///'+(tmp_path/'legacy.sqlite3').as_posix())
    try:
        database.Base.metadata.create_all(engine,tables=[t for t in database.Base.metadata.sorted_tables if t.name!='requirement_budgets'])
        with Session(engine) as db:
            old=SearchSession(raw_query='xe máy khoảng 33 triệu')
            db.add(old);db.flush()
            sid=old.id
            db.add(Requirement(session_id=sid,category='xe máy',budget_max=33000000));db.commit()
        assert 'requirement_budgets' not in inspect(engine).get_table_names()
        monkeypatch.setattr(database,'engine',engine)
        database.init_db();database.init_db()
        assert 'requirement_budgets' in inspect(engine).get_table_names()
        with Session(engine) as db:
            assert db.get(SearchSession,sid).raw_query=='xe máy khoảng 33 triệu'
            model=db.scalar(select(Requirement).where(Requirement.session_id==sid))
            assert requirement_to_schema(model).budget_mode=='HARD_MAX'
            assert list(db.scalars(select(RequirementBudget)))==[]
    finally:
        engine.dispose()


def test_cache_keys_keep_all_three_budget_modes_separate():
    keys={make_cache_key(apply_budget_semantics(RequirementData(category='xe máy'),query)) for query in
          ['khoảng 33 triệu','tối đa 33 triệu','31 đến 35 triệu']}
    assert len(keys)==3
