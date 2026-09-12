"""Search API endpoints."""

import time

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.raw_product_candidate import (
    RawProductCandidate,
)
from app.models.search_execution_state import SearchExecutionState
from app.models.search_query import (
    SearchQuery,
)
from app.models.search_session import (
    SearchSession,
    SearchSessionStatus,
    utc_now,
)
from app.models.source import Source
from app.schemas.recommendation import (
    SearchPipelineResponse,
)
from app.schemas.search import (
    RawProductCandidateData,
    SearchExecutionResponse,
    SearchRequest,
    SearchSourceItem,
)
from app.services.recommendation.recommendation_service import (
    RecommendationService,
)
from app.services.search.search_service import (
    AllSearchQueriesFailed,
    SearchService,
)
from app.services.search.base import SearchProviderError


router = APIRouter(
    prefix="/api/search",
    tags=["Search"],
)


def save_search_warnings(db: Session, session_id: str, warnings: list[str]) -> None:
    """Store the latest attempt's warnings in the caller's transaction."""
    execution_state = db.get(SearchExecutionState, session_id)
    if execution_state is None:
        execution_state = SearchExecutionState(session_id=session_id)
        db.add(execution_state)
    execution_state.warnings = list(warnings)


def load_raw_search_result(
    *,
    db: Session,
    session_id: str,
) -> SearchExecutionResponse:
    """Load persisted extraction results."""

    settings = get_settings()

    query_models = list(
        db.scalars(
            select(SearchQuery)
            .where(
                SearchQuery.session_id
                == session_id
            )
            .order_by(
                SearchQuery.position
            )
        )
    )

    candidate_models = list(
        db.scalars(
            select(RawProductCandidate)
            .where(
                RawProductCandidate.session_id
                == session_id
            )
            .order_by(
                RawProductCandidate.id
            )
        )
    )

    raw_products: list[
        RawProductCandidateData
    ] = []

    sources: list[
        SearchSourceItem
    ] = []

    seen_source_ids: set[int] = set()

    for candidate_model in candidate_models:
        raw_products.append(
            RawProductCandidateData.model_validate(
                candidate_model.payload
            )
        )

        if (
            candidate_model.source_id
            is None
            or candidate_model.source_id
            in seen_source_ids
        ):
            continue

        source_model = db.get(
            Source,
            candidate_model.source_id,
        )

        if source_model is None:
            continue

        seen_source_ids.add(
            source_model.id
        )

        sources.append(
            SearchSourceItem(
                title=source_model.title,
                url=source_model.url,
                domain=source_model.domain,
                content="",
                provider_score=None,
                reliability_score=(
                    source_model.reliability_score
                    if source_model.reliability_score
                    is not None
                    else 50.0
                ),
            )
        )

    execution_state = db.get(SearchExecutionState, session_id)
    search_session = db.get(SearchSession, session_id)

    return SearchExecutionResponse(
        session_id=session_id,
        status=search_session.status.value if search_session is not None else None,
        queries=[
            item.query
            for item in query_models
        ],
        sources=sources,
        raw_products=raw_products,
        total_results=len(
            candidate_models
        ),
        total_sources=len(
            sources
        ),
        total_products=len(
            raw_products
        ),
        warnings=list(execution_state.warnings) if execution_state is not None else [],
        demo_mode=settings.demo_mode,
        processing_time_ms=0.0,
    )


@router.post(
    "",
    response_model=SearchPipelineResponse,
)
async def execute_search(
    payload: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchPipelineResponse:
    """Execute the complete deterministic search/ranking pipeline."""

    started_at = (
        time.perf_counter()
    )

    search_session = db.get(
        SearchSession,
        payload.session_id,
    )

    if search_session is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Không tìm thấy search session."
            ),
        )

    query_models = list(
        db.scalars(
            select(SearchQuery)
            .where(
                SearchQuery.session_id
                == payload.session_id
            )
            .order_by(
                SearchQuery.position
            )
        )
    )

    if not query_models:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Session chưa có search query. "
                "Hãy hoàn tất clarification trước."
            ),
        )

    queries = [
        item.query
        for item in query_models
    ]

    search_session.status = (
        SearchSessionStatus.PROCESSING
    )

    db.commit()

    try:
        raw_result = (
            await SearchService().execute(
                db=db,
                session_id=(
                    payload.session_id
                ),
                queries=queries,
            )
        )

        recommendation_result = (
            RecommendationService().run(
                db=db,
                session_id=(
                    payload.session_id
                ),
            )
        )

        duration_ms = (
            time.perf_counter()
            - started_at
        ) * 1000

        search_session = db.get(
            SearchSession,
            payload.session_id,
        )

        if search_session is not None:
            search_session.status = (
                SearchSessionStatus.COMPLETED
            )

            search_session.completed_at = (
                utc_now()
            )

            search_session.processing_time_ms = (
                round(
                    duration_ms,
                    2,
                )
            )

        save_search_warnings(db, payload.session_id, raw_result.warnings)
        db.commit()
        raw_result.status = "COMPLETED"

        return SearchPipelineResponse(
            **raw_result.model_dump(
                exclude={
                    "processing_time_ms"
                }
            ),
            processing_time_ms=round(
                duration_ms,
                2,
            ),
            requirement=(
                recommendation_result.requirement
            ),
            candidates=(
                recommendation_result.candidates
            ),
            filter_decisions=(
                recommendation_result.filter_decisions
            ),
            recommendations=(
                recommendation_result.recommendations
            ),
            data_semantics=recommendation_result.data_semantics,
            total_found=(
                recommendation_result.total_found
            ),
            total_filtered=(
                recommendation_result.total_filtered
            ),
            total_recommended=len(
                recommendation_result.recommendations
            ),
        )

    except SearchProviderError as exc:
        # SearchService raises before any result writes when every query fails.
        # Record only the failed attempt; keep the last successful data/timing.
        db.rollback()
        search_session = db.get(SearchSession, payload.session_id)
        message = (
            "Không thể hoàn tất tìm kiếm vì dịch vụ tìm kiếm không khả dụng. "
            "Hãy thử lại sau. Kết quả thành công trước đó (nếu có) được giữ nguyên."
        )
        warnings = [message]
        if isinstance(exc, AllSearchQueriesFailed):
            warnings.extend(exc.warnings)
        if search_session is not None:
            search_session.status = SearchSessionStatus.FAILED
            save_search_warnings(db, payload.session_id, warnings)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=message,
        ) from exc

    except Exception as exc:
        db.rollback()

        search_session = db.get(
            SearchSession,
            payload.session_id,
        )

        if search_session is not None:
            search_session.status = (
                SearchSessionStatus.FAILED
            )

            db.commit()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Không thể thực hiện pipeline "
                "tìm kiếm và xếp hạng."
            ),
        ) from exc


@router.get(
    "/{session_id}",
    response_model=SearchPipelineResponse,
)
def get_search_result(
    session_id: str,
    db: Session = Depends(get_db),
) -> SearchPipelineResponse:
    """Return persisted search and recommendation results."""

    search_session = db.get(
        SearchSession,
        session_id,
    )

    if search_session is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Không tìm thấy search session."
            ),
        )

    raw_result = (
        load_raw_search_result(
            db=db,
            session_id=session_id,
        )
    )

    try:
        recommendation_result = (
            RecommendationService().load(
                db=db,
                session_id=session_id,
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=str(exc),
        ) from exc

    return SearchPipelineResponse(
        **raw_result.model_dump(
            exclude={
                "processing_time_ms"
            }
        ),
        processing_time_ms=(
            search_session.processing_time_ms
            or 0.0
        ),
        requirement=(
            recommendation_result.requirement
        ),
        candidates=(
            recommendation_result.candidates
        ),
        filter_decisions=(
            recommendation_result.filter_decisions
        ),
        recommendations=(
            recommendation_result.recommendations
        ),
        data_semantics=recommendation_result.data_semantics,
        total_found=(
            recommendation_result.total_found
        ),
        total_filtered=(
            recommendation_result.total_filtered
        ),
        total_recommended=len(
            recommendation_result.recommendations
        ),
    )
