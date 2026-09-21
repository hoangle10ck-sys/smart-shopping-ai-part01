"""Requirement-analysis API endpoints."""

import logging
from app.models.requirement import RequirementBudget
from app.services.budget import BUDGET_FIELDS

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.requirement import (
    Requirement as RequirementModel,
)
from app.models.search_query import (
    SearchQuery,
)
from app.models.search_session import (
    SearchSession,
    SearchSessionStatus,
)
from app.schemas.requirement import (
    AnalyzeRequirementRequest,
    ClarifyRequirementRequest,
    RequirementAnalysisResponse,
    RequirementData,
)
from app.services.llm.query_generator import (
    QueryGenerator,
)
from app.services.llm.requirement_analyzer import (
    RequirementAnalyzer,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/requirements",
    tags=["Requirements"],
)


def requirement_to_model_values(
    requirement: RequirementData,
) -> dict[str, object]:
    """Convert Pydantic requirement to SQLAlchemy-compatible values."""

    return {
        "category": requirement.category,
        "budget_metadata": RequirementBudget(values={key: getattr(requirement, key) for key in BUDGET_FIELDS}),
        "budget_min": requirement.budget_min,
        "budget_max": requirement.budget_max,
        "currency": requirement.currency,
        "purpose": requirement.purpose,
        "brands": requirement.brands,
        "requirements": [
            item.model_dump()
            for item in requirement.requirements
        ],
        "excluded_requirements": (
            requirement.excluded_requirements
        ),
        "sort_preference": (
            requirement.sort_preference
        ),
        "confidence": requirement.confidence,
    }


def save_search_queries(
    db: Session,
    session_id: str,
    queries: list[str],
) -> None:
    """Replace generated search queries for one session."""

    db.execute(
        delete(
            SearchQuery
        ).where(
            SearchQuery.session_id
            == session_id
        )
    )

    for index, query in enumerate(
        queries,
        start=1,
    ):
        db.add(
            SearchQuery(
                session_id=session_id,
                query=query,
                position=index,
            )
        )


@router.post(
    "/analyze",
    response_model=RequirementAnalysisResponse,
)
async def analyze_requirement(
    payload: AnalyzeRequirementRequest,
    db: Session = Depends(get_db),
) -> RequirementAnalysisResponse:
    """Analyze a new shopping request."""

    try:
        # -------------------------------------------------
        # 1. Call AI BEFORE opening a SQLite write
        # transaction.
        # -------------------------------------------------

        analyzer = (
            RequirementAnalyzer()
        )

        assessment = (
            await analyzer.analyze(
                payload.raw_query
            )
        )

        requirement_data = (
            assessment.requirement
        )

        # -------------------------------------------------
        # 2. Only touch the database after Gemini finishes.
        # -------------------------------------------------

        search_session = (
            SearchSession(
                raw_query=(
                    payload.raw_query
                    .strip()
                ),
                status=(
                    SearchSessionStatus
                    .PENDING
                ),
            )
        )

        db.add(
            search_session
        )

        # We need the generated session ID
        # for Requirement/SearchQuery.
        db.flush()

        requirement_model = (
            RequirementModel(
                session_id=(
                    search_session.id
                ),
                **requirement_to_model_values(
                    requirement_data
                ),
            )
        )

        db.add(
            requirement_model
        )

        queries: list[
            str
        ] = []

        if (
            not assessment
            .needs_clarification
        ):
            queries = (
                QueryGenerator()
                .generate(
                    requirement_data
                )
            )

            save_search_queries(
                db,
                search_session.id,
                queries,
            )

        # -------------------------------------------------
        # 3. Finish the write transaction immediately.
        # -------------------------------------------------

        db.commit()

        return (
            RequirementAnalysisResponse(
                session_id=(
                    search_session.id
                ),
                requirement=(
                    requirement_data
                ),
                needs_clarification=(
                    assessment
                    .needs_clarification
                ),
                missing_fields=(
                    assessment
                    .missing_fields
                ),
                clarification_question=(
                    assessment
                    .clarification_question
                ),
                search_queries=(
                    queries
                ),
            )
        )

    except Exception as exc:
        db.rollback()

        logger.exception(
            "Requirement analysis failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=(
                status
                .HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Không thể phân tích yêu cầu "
                "mua hàng lúc này."
            ),
        ) from exc


@router.post(
    "/clarify",
    response_model=RequirementAnalysisResponse,
)
async def clarify_requirement(
    payload: ClarifyRequirementRequest,
    db: Session = Depends(get_db),
) -> RequirementAnalysisResponse:
    """Analyze additional information for an existing session."""

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

    requirement_model = (
        search_session.requirement
    )

    if requirement_model is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Không tìm thấy requirement "
                "của session."
            ),
        )

    combined_query = (
        f"{search_session.raw_query}\n"
        f"Thông tin bổ sung: "
        f"{payload.answer.strip()}"
    )

    try:
        analyzer = RequirementAnalyzer()

        assessment = await analyzer.analyze(
            combined_query
        )

        requirement_data = (
            assessment.requirement
        )

        values = (
            requirement_to_model_values(
                requirement_data
            )
        )

        for (
            field_name,
            value,
        ) in values.items():
            setattr(
                requirement_model,
                field_name,
                value,
            )

        # Preserve clarification context
        # for possible next clarification turn.
        search_session.raw_query = (
            combined_query
        )

        queries: list[str] = []

        if not assessment.needs_clarification:
            queries = (
                QueryGenerator()
                .generate(
                    requirement_data
                )
            )

            save_search_queries(
                db,
                search_session.id,
                queries,
            )

        db.commit()

        return RequirementAnalysisResponse(
            session_id=search_session.id,
            requirement=requirement_data,
            needs_clarification=(
                assessment.needs_clarification
            ),
            missing_fields=(
                assessment.missing_fields
            ),
            clarification_question=(
                assessment.clarification_question
            ),
            search_queries=queries,
        )

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        logger.exception(
            "Requirement clarification failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Không thể xử lý thông tin "
                "bổ sung lúc này."
            ),
        ) from exc
