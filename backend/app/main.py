"""FastAPI application entry point for Smart Shopping AI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.api.routes.comparison import (
    router as comparison_router,
)
from app.api.routes.feedback import (
    router as feedback_router,
)
from app.api.routes.health import (
    router as health_router,
)
from app.api.routes.requirements import (
    router as requirements_router,
)
from app.api.routes.products import (
    router as products_router,
)
from app.api.routes.recommendations import (
    router as recommendations_router,
)
from app.api.routes.search import (
    router as search_router,
)
from app.core.database import init_db



@asynccontextmanager
async def lifespan(
    _: FastAPI,
):
    """Initialize application resources."""

    init_db()

    yield



app = FastAPI(
    title="Smart Shopping AI API",
    description=(
        "Backend API for the Smart Shopping AI "
        "graduation project."
    ),
    version="0.5.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    health_router,
    prefix="/api",
)

app.include_router(
    products_router,
)

app.include_router(
    recommendations_router,
)

app.include_router(
    requirements_router,
)

app.include_router(
    search_router,
)

app.include_router(
    comparison_router,
)

app.include_router(
    feedback_router,
)


@app.get("/")
def root() -> dict[str, str]:
    """Return basic API information."""

    return {
        "message": (
            "Smart Shopping AI API is running"
        ),
        "docs": "/docs",
        "health": "/api/health",
    }