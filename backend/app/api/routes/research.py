"""Local SQLite research endpoints: no external search/model calls."""
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.models import ResearchProduct, SearchSession, SearchSessionStatus, Requirement, SearchExecutionState
from app.models.search_session import utc_now
from app.schemas.requirement import RequirementData
from app.schemas.recommendation import SearchPipelineResponse
from app.api.routes.requirements import requirement_to_model_values
from app.services.research.recommendation import evaluate, parse_query, save_result, WARNING

router = APIRouter(prefix="/api/research", tags=["Historical research"])


class ResearchSearchRequest(BaseModel):
    raw_query: str = Field(min_length=3, max_length=2000)
    requirement: RequirementData | None = None
    revision: str | None = Field(default=None, max_length=100)


@router.get("/status")
def status(db: Session = Depends(get_db)):
    return dict(products=db.scalar(select(func.count(ResearchProduct.id))), source_mode="HISTORICAL_RESEARCH",
                default_mode="demo" if get_settings().demo_mode else "live", warning=WARNING)


@router.post("/search", response_model=SearchPipelineResponse)
def search(payload: ResearchSearchRequest, db: Session = Depends(get_db)):
    start = time.perf_counter()
    try:
        requirement = payload.requirement or parse_query(payload.raw_query)
        result, warnings = evaluate(db, requirement, revision=payload.revision)
        session = SearchSession(raw_query=payload.raw_query, status=SearchSessionStatus.COMPLETED, completed_at=utc_now())
        db.add(session)
        db.flush()
        db.add(Requirement(session_id=session.id, **requirement_to_model_values(requirement)))
        db.add(SearchExecutionState(session_id=session.id, warnings=warnings))
        save_result(db, session.id, result)
        session.processing_time_ms = round((time.perf_counter() - start) * 1000, 2)
        db.commit()
        return SearchPipelineResponse(session_id=session.id, status="COMPLETED", requirement=requirement,
            candidates=result.candidates, filter_decisions=result.filter_decisions, recommendations=result.recommendations,
            total_found=result.total_found, total_filtered=result.total_filtered, total_recommended=len(result.recommendations),
            data_mode="research", data_semantics="snapshot", demo_mode=False, warnings=warnings,
            processing_time_ms=session.processing_time_ms)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
