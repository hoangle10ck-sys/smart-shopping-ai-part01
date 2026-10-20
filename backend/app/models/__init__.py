"""SQLAlchemy model registry.

Importing this package registers every table with Base.metadata.
"""

from app.models.user import User
from app.models.search_session import (
    SearchSession,
    SearchSessionStatus,
)
from app.models.requirement import Requirement, RequirementBudget
from app.models.search_query import SearchQuery
from app.models.source import Source
from app.models.product import Product
from app.models.product_offer import ProductOffer
from app.models.recommendation import Recommendation
from app.models.recommendation_snapshot import RecommendationSnapshot
from app.models.comparison import ComparisonSession
from app.models.feedback import Feedback
from app.models.raw_product_candidate import RawProductCandidate
from app.models.search_execution_state import SearchExecutionState
from app.models.search_cache import SearchCacheEntry
from app.models.product_variant import ProductVariant
from app.models.price_observation import PriceObservation
from app.models.crawl_run import CrawlRun
from app.models.research import ResearchProduct, HistoricalPriceReference, ResearchImportRun


__all__ = [
    "ResearchProduct", "HistoricalPriceReference", "ResearchImportRun",
    "User",
    "SearchSession",
    "SearchSessionStatus",
    "Requirement",
    "RequirementBudget",
    "SearchQuery",
    "Source",
    "Product",
    "ProductOffer",
    "Recommendation",
    "RecommendationSnapshot",
    "ComparisonSession",
    "Feedback",
    "RawProductCandidate",
    "SearchExecutionState",
    "SearchCacheEntry",
    "ProductVariant",
    "PriceObservation",
    "CrawlRun",
]
