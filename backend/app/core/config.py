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
    explanation_concurrency: int = 3
    explanation_timeout_seconds: float = 8.0

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
    live_search_target_products: int = 5
    live_search_min_products: int = 3
    live_search_query_concurrency: int = 2
    live_search_page_concurrency: int = 4
    live_search_per_domain_concurrency: int = 2
    live_search_initial_candidates: int = 10
    live_search_max_candidates: int = 20
    live_search_discovery_pages: int = 4
    live_search_page_budget_seconds: float = 4.0
    live_search_domain_budget_seconds: float = 6.0

    top_k: int = 5

    # =========================================================
    # UNIFIED SEARCH
    # =========================================================

    unified_top_k: int = 10
    unified_min_fresh_products: int = 3
    unified_source_timeout_seconds: float = 15.0
    unified_enhancement_enabled: bool = True


    # =========================================================
    # DEMO MODE
    # =========================================================

    demo_mode: bool = True


    # =========================================================
    # CACHE
    # =========================================================

    cache_ttl_seconds: int = 1800
    product_offer_freshness_ttl_seconds: int = 3600
    collector_max_urls: int = 5
    collector_live_enabled: bool = False
    collector_policy_confirmed: bool = False
    collector_source_registry_json: str = "[]"
    collector_max_pages: int = 2
    collector_max_bytes: int = 2_000_000
    collector_http_timeout_seconds: float = 8.0
    collector_min_interval_seconds: float = 1.0
    collector_browser_enabled: bool = False
    collector_browser_timeout_seconds: float = 12.0
    collector_browser_max_dom_bytes: int = 2_000_000
    enable_llm_extraction_fallback: bool = False
    llm_extraction_max_input_chars: int = 12000
    llm_extraction_cache_ttl_seconds: int = 3600


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
