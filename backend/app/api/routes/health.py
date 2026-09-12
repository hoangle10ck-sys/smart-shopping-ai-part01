"""Health and system status endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.core.database import check_database
from app.schemas.common import HealthResponse, SystemStatusResponse

router = APIRouter(tags=["System"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Lightweight liveness check that does not depend on external APIs."""

    return HealthResponse(status="ok", service="smart-shopping-ai")


@router.get("/system/status", response_model=SystemStatusResponse)
def system_status() -> SystemStatusResponse:
    """Check local application and database readiness."""

    try:
        check_database()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable.",
        ) from exc

    return SystemStatusResponse(
        status="ok",
        environment=settings.app_env,
        database="ok",
        demo_mode=settings.demo_mode,
    )
