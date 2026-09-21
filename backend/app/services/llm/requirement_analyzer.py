"""Requirement analysis and backend validation service."""

from dataclasses import dataclass
from app.services.budget import apply_budget_semantics

from app.schemas.requirement import (
    RequirementData,
)
from app.services.llm.client import (
    BaseLLMClient,
    get_llm_client,
)


@dataclass(slots=True)
class RequirementAssessment:
    """Backend validation result for one requirement."""

    requirement: RequirementData

    needs_clarification: bool

    missing_fields: list[str]

    clarification_question: str | None


class RequirementAnalyzer:
    """Analyze natural language and decide whether clarification is required."""

    def __init__(
        self,
        client: BaseLLMClient | None = None,
    ) -> None:
        self.client = (
            client
            if client is not None
            else get_llm_client()
        )

    async def analyze(
        self,
        raw_query: str,
    ) -> RequirementAssessment:
        """Analyze and validate one user shopping request."""

        requirement = (
            await self.client.analyze_requirement(
                raw_query
            )
        )

        requirement = (
            self._backend_normalize(
                requirement
            )
        )

        requirement = apply_budget_semantics(requirement, raw_query)
        return self.assess(
            requirement
        )

    @staticmethod
    def _backend_normalize(
        requirement: RequirementData,
    ) -> RequirementData:
        """Normalize data before backend business validation."""

        if requirement.category:
            requirement.category = (
                requirement.category.strip().lower()
            )

        requirement.currency = (
            requirement.currency.strip().upper()
            or "VND"
        )

        requirement.purpose = list(
            dict.fromkeys(
                item.strip()
                for item in requirement.purpose
                if item.strip()
            )
        )

        requirement.brands = list(
            dict.fromkeys(
                item.strip()
                for item in requirement.brands
                if item.strip()
            )
        )

        requirement.excluded_requirements = list(
            dict.fromkeys(
                item.strip()
                for item
                in requirement.excluded_requirements
                if item.strip()
            )
        )

        return requirement

    @staticmethod
    def assess(
        requirement: RequirementData,
    ) -> RequirementAssessment:
        """Apply deterministic backend clarification rules."""

        missing_fields: list[str] = []

        if not requirement.category:
            missing_fields.append(
                "category"
            )

        if (
            requirement.budget_min is None
            and requirement.budget_max is None
        ):
            missing_fields.append(
                "budget"
            )

        if not requirement.purpose:
            missing_fields.append(
                "purpose"
            )

        question: str | None = None

        # Only ask one important question per turn.
        if "category" in missing_fields:
            question = (
                "Bạn muốn mua loại sản phẩm nào?"
            )

        elif "budget" in missing_fields:
            question = (
                "Bạn dự kiến ngân sách khoảng bao nhiêu?"
            )

        elif "purpose" in missing_fields:
            question = (
                "Bạn chủ yếu dùng sản phẩm cho mục đích gì?"
            )

        needs_clarification = (
            question is not None
        )

        return RequirementAssessment(
            requirement=requirement,
            needs_clarification=needs_clarification,
            missing_fields=missing_fields,
            clarification_question=question,
        )
