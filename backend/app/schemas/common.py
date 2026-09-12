"""Common API response schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class SystemStatusResponse(BaseModel):
    status: str
    environment: str
    database: str
    demo_mode: bool
