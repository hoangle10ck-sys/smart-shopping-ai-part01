"""Read-only history API contracts."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator

from app.models.search_session import SearchSessionStatus
from app.schemas.recommendation import SearchPipelineResponse


class HistoryItem(BaseModel):
    session_id: str
    raw_query: str
    status: SearchSessionStatus
    created_at: datetime
    completed_at: datetime | None = None
    recommendation_count: int = Field(default=0, ge=0)

    @field_validator("created_at", "completed_at")
    @classmethod
    def timestamps_are_utc(cls, value):
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


class HistoryListResponse(BaseModel):
    items: list[HistoryItem]
    total: int = Field(ge=0)
    limit: int
    offset: int


class HistoryDetailResponse(HistoryItem):
    result: SearchPipelineResponse | None = None
