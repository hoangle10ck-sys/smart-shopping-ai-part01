"""Read history from existing sessions and Phase 3 snapshots; never call providers."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.search import get_search_result
from app.core.database import get_db
from app.models.recommendation import Recommendation
from app.models.recommendation_snapshot import RecommendationSnapshot
from app.models.requirement import Requirement
from app.models.search_session import SearchSession
from app.schemas.history import HistoryDetailResponse, HistoryItem, HistoryListResponse


router = APIRouter(prefix="/api/history", tags=["History"])


def history_item(session: SearchSession, count: int) -> HistoryItem:
    return HistoryItem(
        session_id=session.id, raw_query=session.raw_query, status=session.status,
        created_at=session.created_at, completed_at=session.completed_at, recommendation_count=count,
    )


@router.get("", response_model=HistoryListResponse)
def list_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> HistoryListResponse:
    counts = select(
        Recommendation.session_id, func.count(Recommendation.id).label("count"),
    ).group_by(Recommendation.session_id).subquery()
    rows = db.execute(
        select(SearchSession, RecommendationSnapshot, counts.c.count)
        .outerjoin(RecommendationSnapshot, RecommendationSnapshot.session_id == SearchSession.id)
        .outerjoin(counts, counts.c.session_id == SearchSession.id)
        .order_by(SearchSession.created_at.desc(), SearchSession.id.desc())
        .limit(limit).offset(offset)
    ).all()
    items = []
    for session, snapshot, count in rows:
        if snapshot is not None:
            count = len(snapshot.payload["result"]["recommendations"])
        items.append(history_item(session, count or 0))
    return HistoryListResponse(
        items=items, total=db.scalar(select(func.count(SearchSession.id))) or 0,
        limit=limit, offset=offset,
    )


@router.get("/{session_id}", response_model=HistoryDetailResponse)
def get_history(session_id: str, db: Session = Depends(get_db)) -> HistoryDetailResponse:
    session = db.get(SearchSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy search session.")
    has_requirement = db.scalar(select(Requirement.id).where(Requirement.session_id == session_id)) is not None
    result = get_search_result(session_id=session_id, db=db) if has_requirement else None
    item = history_item(session, result.total_recommended if result is not None else 0)
    return HistoryDetailResponse(**item.model_dump(), result=result)
