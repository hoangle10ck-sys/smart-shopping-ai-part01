"""Grounded multi-provider recommendation explanation service."""

from __future__ import annotations

import json
import time

import httpx

from app.core.config import (
    get_settings,
)

from app.schemas.evidence import (
    EvidenceReport,
    RecommendationExplanation,
)

from app.schemas.ranking import (
    ScoreBreakdown,
    ScoringCandidate,
)

from app.schemas.requirement import (
    RequirementData,
)


OPENAI_RESPONSES_URL = (
    "https://api.openai.com/v1/responses"
)


class ExplanationService:
    """Generate grounded recommendation explanations.

    LLM providers are only allowed to explain existing
    deterministic scores and evidence.

    They must never modify:
    - final score
    - confidence
    - price
    - rating
    - review count
    - product URL
    - specifications
    """

    def __init__(
        self,
        *,
        use_llm: bool | None = None,
    ) -> None:
        self.settings = (
            get_settings()
        )

        # Demo is an unconditional network boundary, even with an explicit hint.
        self.use_llm = not self.settings.demo_mode and use_llm is not False


    # =========================================================
    # PUBLIC API
    # =========================================================

    def explain(
        self,
        *,
        candidate: ScoringCandidate,
        requirement: RequirementData,
        score: ScoreBreakdown,
        evidence: EvidenceReport,
    ) -> RecommendationExplanation:
        """Generate explanation using configured provider."""

        if not self.use_llm:
            result = (
                self.build_deterministic(
                    candidate=candidate,
                    requirement=requirement,
                    score=score,
                    evidence=evidence,
                )
            )

            result.generation_mode = "demo" if self.settings.demo_mode else "fallback"

            return result


        provider_names = (
            self._provider_order()
        )


        for provider_name in (
            provider_names
        ):
            try:
                result = (
                    self._generate_with_provider(
                        provider=provider_name,
                        candidate=candidate,
                        requirement=requirement,
                        score=score,
                        evidence=evidence,
                    )
                )

                result.generation_mode = (
                    provider_name
                )

                return result

            except Exception:
                # Try next provider.
                continue


        # All external providers failed.
        result = (
            self.build_deterministic(
                candidate=candidate,
                requirement=requirement,
                score=score,
                evidence=evidence,
            )
        )

        result.generation_mode = (
            "fallback"
        )

        return result


    # =========================================================
    # PROVIDER ORDER
    # =========================================================

    def _provider_order(
        self,
    ) -> list[str]:
        """Return unique primary/fallback provider order."""

        primary = (
            self.settings
            .llm_provider
            .strip()
            .lower()
        )

        fallback = (
            self.settings
            .llm_fallback_provider
            .strip()
            .lower()
        )

        providers: list[str] = []


        if primary in {
            "openai",
            "gemini",
        }:
            providers.append(
                primary
            )


        if (
            fallback
            in {
                "openai",
                "gemini",
            }
            and fallback
            not in providers
        ):
            providers.append(
                fallback
            )


        return providers


    # =========================================================
    # PROVIDER ROUTER
    # =========================================================

    def _generate_with_provider(
        self,
        *,
        provider: str,
        candidate: ScoringCandidate,
        requirement: RequirementData,
        score: ScoreBreakdown,
        evidence: EvidenceReport,
    ) -> RecommendationExplanation:
        """Call one configured explanation provider."""

        if provider == "openai":
            return (
                self._generate_with_openai(
                    candidate=candidate,
                    requirement=requirement,
                    score=score,
                    evidence=evidence,
                )
            )


        if provider == "gemini":
            return (
                self._generate_with_gemini(
                    candidate=candidate,
                    requirement=requirement,
                    score=score,
                    evidence=evidence,
                )
            )


        raise RuntimeError(
            (
                "Unsupported explanation "
                f"provider: {provider}"
            )
        )


    # =========================================================
    # SHARED PAYLOAD
    # =========================================================

    @staticmethod
    def _build_payload(
        *,
        candidate: ScoringCandidate,
        requirement: RequirementData,
        score: ScoreBreakdown,
        evidence: EvidenceReport,
    ) -> dict:
        """Build grounded input for explanation providers."""

        return {
            "requirement": (
                requirement.model_dump(
                    mode="json",
                )
            ),

            "candidate": (
                candidate.model_dump(
                    mode="json",
                )
            ),

            "ai_match_score": (
                score.model_dump(
                    mode="json",
                )
            ),

            "data_confidence": (
                evidence.model_dump(
                    mode="json",
                )
            ),
        }


    @staticmethod
    def _build_prompt(
        *,
        payload: dict,
    ) -> str:
        """Create provider-neutral grounded prompt."""

        return (
            "Bạn là mô-đun giải thích đề xuất của "
            "hệ thống Smart Shopping AI.\n\n"

            "NHIỆM VỤ:\n"
            "Giải thích ngắn gọn vì sao sản phẩm phù hợp "
            "hoặc chưa phù hợp với nhu cầu người dùng.\n\n"

            "QUY TẮC BẮT BUỘC:\n"
            "1. Chỉ sử dụng dữ liệu trong JSON được cung cấp.\n"
            "2. Không tự tạo giá sản phẩm.\n"
            "3. Không tự tạo rating hoặc số lượt đánh giá.\n"
            "4. Không tự tạo thông số kỹ thuật.\n"
            "5. Không tự tạo URL hoặc nguồn bán.\n"
            "6. Không thay đổi final_score.\n"
            "7. Không thay đổi Data Confidence.\n"
            "8. Phải phân biệt AI Match và Data Confidence.\n"
            "9. Nếu dữ liệu thiếu, phải nói rõ dữ liệu đang thiếu.\n"
            "10. Trả lời hoàn toàn bằng tiếng Việt.\n"
            "11. Không khẳng định điều không có trong evidence.\n"
            "12. summary phải ngắn gọn, dễ hiểu.\n"
            "13. why_fit là các lý do sản phẩm phù hợp.\n"
            "14. tradeoffs là hạn chế hoặc điều cần cân nhắc.\n"
            "15. evidence_notes phải dựa trên evidence được cung cấp.\n\n"

            "DỮ LIỆU HỆ THỐNG:\n"
            + json.dumps(
                payload,
                ensure_ascii=False,
            )
        )


    # =========================================================
    # DETERMINISTIC EXPLANATION
    # =========================================================

    def build_deterministic(
        self,
        *,
        candidate: ScoringCandidate,
        requirement: RequirementData,
        score: ScoreBreakdown,
        evidence: EvidenceReport,
    ) -> RecommendationExplanation:
        """Create evidence-grounded deterministic explanation."""

        summary = (
            f"{candidate.name} đạt "
            f"{score.final_score:.2f}/100 điểm phù hợp "
            f"và {evidence.confidence:.2f}/100 "
            "điểm tin cậy dữ liệu."
        )


        why_fit: list[str] = []

        tradeoffs: list[str] = []


        # -----------------------------------------------------
        # BUDGET
        # -----------------------------------------------------

        if (
            requirement.budget_max
            is not None
            and candidate.price
            is not None
        ):
            if (
                candidate.price
                <= requirement.budget_max
            ):
                why_fit.append(
                    (
                        f"Giá {candidate.price} "
                        f"{candidate.currency} nằm trong "
                        f"ngân sách tối đa "
                        f"{requirement.budget_max} "
                        f"{requirement.currency}."
                    )
                )

            else:
                tradeoffs.append(
                    (
                        f"Giá {candidate.price} "
                        f"{candidate.currency} vượt ngân sách "
                        f"tối đa {requirement.budget_max} "
                        f"{requirement.currency}."
                    )
                )


        elif candidate.price is None:
            tradeoffs.append(
                (
                    "Chưa có dữ liệu giá đáng tin cậy "
                    "để đối chiếu với ngân sách."
                )
            )


        # -----------------------------------------------------
        # REQUIREMENT MATCH
        # -----------------------------------------------------

        if requirement.requirements:
            why_fit.append(
                (
                    "Mức đáp ứng các tiêu chí yêu cầu đạt "
                    f"{score.requirement_score:.2f}/100."
                )
            )


        # -----------------------------------------------------
        # PURPOSE MATCH
        # -----------------------------------------------------

        if requirement.purpose:
            purpose_text = ", ".join(
                requirement.purpose
            )

            why_fit.append(
                (
                    f"Mức phù hợp cho mục đích "
                    f"{purpose_text}: "
                    f"{score.purpose_score:.2f}/100."
                )
            )


        # -----------------------------------------------------
        # RATING
        # -----------------------------------------------------

        if candidate.rating is not None:
            why_fit.append(
                (
                    f"Rating hiện có là "
                    f"{candidate.rating}/5."
                )
            )

        else:
            tradeoffs.append(
                (
                    "Chưa có dữ liệu rating "
                    "đáng tin cậy."
                )
            )


        # -----------------------------------------------------
        # REVIEW COUNT
        # -----------------------------------------------------

        if (
            candidate.review_count
            is not None
        ):
            why_fit.append(
                (
                    f"Có {candidate.review_count} "
                    "lượt đánh giá."
                )
            )

        else:
            tradeoffs.append(
                (
                    "Chưa có dữ liệu số lượt "
                    "đánh giá."
                )
            )


        # -----------------------------------------------------
        # SPECIFICATIONS
        # -----------------------------------------------------

        if not candidate.specifications:
            tradeoffs.append(
                (
                    "Thông số kỹ thuật hiện "
                    "chưa đầy đủ."
                )
            )


        # -----------------------------------------------------
        # BUDGET EDGE
        # -----------------------------------------------------

        if (
            requirement.budget_max
            is not None
            and candidate.price
            is not None
            and candidate.price
            <= requirement.budget_max
            and candidate.price
            >= requirement.budget_max
            * 0.9
        ):
            tradeoffs.append(
                (
                    "Giá sản phẩm khá sát mức "
                    "ngân sách tối đa."
                )
            )


        # -----------------------------------------------------
        # EVIDENCE CONFIDENCE
        # -----------------------------------------------------

        if (
            evidence.confidence
            <=  60
        ):
            tradeoffs.append(
                (
                    "Độ tin cậy dữ liệu còn thấp; "
                    "nên kiểm tra lại nguồn trước khi mua."
                )
            )


        if not why_fit:
            why_fit.append(
                (
                    "Sản phẩm được xếp hạng dựa trên "
                    "điểm phù hợp tổng hợp của hệ thống."
                )
            )


        if not tradeoffs:
            tradeoffs.append(
                (
                    "Chưa phát hiện hạn chế lớn "
                    "từ dữ liệu hiện có."
                )
            )


        evidence_notes = list(
            evidence.supporting_evidence
        )

        evidence_notes.extend(
            evidence.warnings
        )


        return (
            RecommendationExplanation(
                summary=summary,

                why_fit=why_fit,

                tradeoffs=tradeoffs,

                evidence_notes=(
                    evidence_notes
                ),

                generation_mode=(
                    "demo"
                ),
            )
        )


    # =========================================================
    # OPENAI
    # =========================================================

    def _generate_with_openai(
        self,
        *,
        candidate: ScoringCandidate,
        requirement: RequirementData,
        score: ScoreBreakdown,
        evidence: EvidenceReport,
    ) -> RecommendationExplanation:
        """Generate structured explanation with OpenAI."""

        api_key = (
            self.settings
            .openai_api_key
            .strip()
        )

        model = (
            self.settings
            .openai_model
            .strip()
        )


        if not api_key:
            raise RuntimeError(
                (
                    "OPENAI_API_KEY "
                    "is not configured."
                )
            )


        if not model:
            raise RuntimeError(
                (
                    "OPENAI_MODEL "
                    "is not configured."
                )
            )


        payload_data = (
            self._build_payload(
                candidate=candidate,
                requirement=requirement,
                score=score,
                evidence=evidence,
            )
        )


        prompt = (
            self._build_prompt(
                payload=payload_data,
            )
        )


        schema = (
            RecommendationExplanation
            .model_json_schema()
        )


        request_body = {
            "model":
                model,

            "input": [
                {
                    "role":
                        "user",

                    "content": [
                        {
                            "type":
                                "input_text",

                            "text":
                                prompt,
                        }
                    ],
                }
            ],

            "temperature":
                0.1,

            "store":
                False,

            "text": {
                "format": {
                    "type":
                        "json_schema",

                    "name":
                        "recommendation_explanation",

                    "schema":
                        schema,

                    "strict":
                        False,
                }
            },
        }


        headers = {
            "Authorization":
                f"Bearer {api_key}",

            "Content-Type":
                "application/json",
        }


        attempts = max(
            1,
            int(
                self.settings
                .llm_retry_count
            )
            + 1,
        )


        last_error: (
            Exception
            | None
        ) = None


        for attempt in range(
            attempts
        ):
            try:
                with httpx.Client(
                    timeout=float(
                        self.settings
                        .llm_timeout_seconds
                    ),
                ) as client:
                    response = (
                        client.post(
                            OPENAI_RESPONSES_URL,
                            headers=headers,
                            json=request_body,
                        )
                    )


                if (
                    response.status_code
                    >= 400
                ):
                    detail = ""

                    try:
                        body = (
                            response.json()
                        )

                        error = (
                            body.get(
                                "error",
                                {},
                            )
                        )

                        if isinstance(
                            error,
                            dict,
                        ):
                            detail = str(
                                error.get(
                                    "message",
                                    "",
                                )
                                or ""
                            )

                    except ValueError:
                        detail = (
                            response.text[
                                :500
                            ]
                        )


                    raise RuntimeError(
                        (
                            "OpenAI API returned "
                            f"HTTP "
                            f"{response.status_code}"
                        )
                        + (
                            f": {detail}"
                            if detail
                            else ""
                        )
                    )


                data = (
                    response.json()
                )


                text = (
                    self
                    ._extract_openai_text(
                        data
                    )
                )


                result = (
                    RecommendationExplanation
                    .model_validate_json(
                        text
                    )
                )


                result.generation_mode = (
                    "openai"
                )

                return result


            except Exception as exc:
                last_error = exc


                if (
                    attempt
                    >= attempts - 1
                ):
                    break


                time.sleep(
                    0.5
                    * (
                        2
                        ** attempt
                    )
                )


        raise RuntimeError(
            (
                "OpenAI recommendation "
                "explanation failed."
            )
        ) from last_error


    @staticmethod
    def _extract_openai_text(
        data: dict,
    ) -> str:
        """Extract text from OpenAI Responses API."""

        output = (
            data.get(
                "output",
                [],
            )
        )


        if not isinstance(
            output,
            list,
        ):
            raise RuntimeError(
                (
                    "Invalid OpenAI "
                    "response output."
                )
            )


        for item in output:
            if not isinstance(
                item,
                dict,
            ):
                continue


            if (
                item.get("type")
                != "message"
            ):
                continue


            content = (
                item.get(
                    "content",
                    [],
                )
            )


            if not isinstance(
                content,
                list,
            ):
                continue


            for part in content:
                if not isinstance(
                    part,
                    dict,
                ):
                    continue


                if (
                    part.get("type")
                    == "output_text"
                ):
                    text = str(
                        part.get(
                            "text",
                            "",
                        )
                        or ""
                    ).strip()


                    if text:
                        return text


                if (
                    part.get("type")
                    == "refusal"
                ):
                    refusal = str(
                        part.get(
                            "refusal",
                            "",
                        )
                        or ""
                    ).strip()


                    raise RuntimeError(
                        (
                            "OpenAI refused "
                            "the request"
                        )
                        + (
                            f": {refusal}"
                            if refusal
                            else "."
                        )
                    )


        raise RuntimeError(
            (
                "OpenAI returned "
                "an empty explanation."
            )
        )


    # =========================================================
    # GEMINI
    # =========================================================

    def _generate_with_gemini(
        self,
        *,
        candidate: ScoringCandidate,
        requirement: RequirementData,
        score: ScoreBreakdown,
        evidence: EvidenceReport,
    ) -> RecommendationExplanation:
        """Generate structured explanation with Gemini."""

        api_key = (
            self.settings
            .gemini_api_key
            .strip()
        )

        model = (
            self.settings
            .gemini_model
            .strip()
        )


        if not api_key:
            raise RuntimeError(
                (
                    "GEMINI_API_KEY "
                    "is not configured."
                )
            )


        if not model:
            raise RuntimeError(
                (
                    "GEMINI_MODEL "
                    "is not configured."
                )
            )


        try:
            from google import (
                genai,
            )

            from google.genai import (
                types,
            )

        except ImportError as exc:
            raise RuntimeError(
                (
                    "google-genai "
                    "is not installed."
                )
            ) from exc


        payload_data = (
            self._build_payload(
                candidate=candidate,
                requirement=requirement,
                score=score,
                evidence=evidence,
            )
        )


        prompt = (
            self._build_prompt(
                payload=payload_data,
            )
        )


        client = (
            genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    timeout=max(1, self.settings.llm_timeout_seconds * 1000),
                    # The surrounding loop owns retry count for both providers.
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
        )


        attempts = max(
            1,
            int(
                self.settings
                .llm_retry_count
            )
            + 1,
        )


        last_error: (
            Exception
            | None
        ) = None


        try:
            for attempt in range(
                attempts
            ):
                try:
                    response = (
                        client
                        .models
                        .generate_content(
                            model=model,

                            contents=prompt,

                            config=(
                                types
                                .GenerateContentConfig(
                                    response_mime_type=(
                                        "application/json"
                                    ),

                                    response_schema=(
                                        RecommendationExplanation
                                    ),

                                    temperature=(
                                        0.1
                                    ),
                                )
                            ),
                        )
                    )


                    if (
                        response.parsed
                        is not None
                    ):
                        if isinstance(
                            response.parsed,
                            RecommendationExplanation,
                        ):
                            result = (
                                response.parsed
                            )

                        else:
                            result = (
                                RecommendationExplanation
                                .model_validate(
                                    response.parsed
                                )
                            )


                    else:
                        if not response.text:
                            raise RuntimeError(
                                (
                                    "Gemini returned "
                                    "an empty response."
                                )
                            )


                        result = (
                            RecommendationExplanation
                            .model_validate_json(
                                response.text
                            )
                        )


                    result.generation_mode = (
                        "gemini"
                    )

                    return result


                except Exception as exc:
                    last_error = exc


                    if (
                        attempt
                        >= attempts - 1
                    ):
                        break


                    time.sleep(
                        0.5
                        * (
                            2
                            ** attempt
                        )
                    )


            raise RuntimeError(
                (
                    "Gemini recommendation "
                    "explanation failed."
                )
            ) from last_error
        finally:
            client.close()
