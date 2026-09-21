"""Application configuration."""

from functools import lru_cache

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # =========================================================
    # APPLICATION
    # =========================================================

    app_env: str = "development"

    database_url: str = (
        "sqlite:///./smart_shopping.db"
    )

    secret_key: str = (
        "change-this-before-production"
    )


    # =========================================================
    # LLM PROVIDER
    # =========================================================

    # openai | gemini
    llm_provider: str = "openai"

    # openai | gemini | ""
    llm_fallback_provider: str = (
        "gemini"
    )


    # =========================================================
    # OPENAI
    # =========================================================

    openai_api_key: str = ""

    openai_model: str = (
        "gpt-4o-mini"
    )


    # =========================================================
    # GEMINI
    # =========================================================

    gemini_api_key: str = ""

    gemini_model: str = (
       "gemini-3.6-flash"
    )


    # =========================================================
    # INTERNET SEARCH
    # =========================================================

    tavily_api_key: str = ""


    # =========================================================
    # TIMEOUT / RETRY
    # =========================================================

    llm_timeout_seconds: int = 30

    search_timeout_seconds: int = 15

    llm_retry_count: int = 2

    search_retry_count: int = 1


    # =========================================================
    # SEARCH / RECOMMENDATION
    # =========================================================

    max_search_queries: int = 4

    max_results_per_query: int = 5
    live_search_budget_seconds: float = 120.0
    live_search_max_queries: int = 12
    live_search_target_products: int = 1

    top_k: int = 5


    # =========================================================
    # DEMO MODE
    # =========================================================

    demo_mode: bool = True


    # =========================================================
    # CACHE
    # =========================================================

    cache_ttl_seconds: int = 1800


    # =========================================================
    # PYDANTIC SETTINGS
    # =========================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
