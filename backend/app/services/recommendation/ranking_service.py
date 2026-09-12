"""Deterministic product ranking."""

from app.schemas.ranking import (
    RankedCandidate,
    ScoringCandidate,
)
from app.schemas.requirement import (
    RequirementData,
)
from app.services.scoring.scoring_engine import (
    ScoringEngine,
)


class RankingService:
    """Rank already-filtered candidates."""

    def __init__(self) -> None:
        self.scoring_engine = (
            ScoringEngine()
        )

    def rank(
        self,
        candidates: list[
            ScoringCandidate
        ],
        requirement: RequirementData,
        top_k: int = 5,
    ) -> list[RankedCandidate]:
        """Score, sort and return at most TOP_K candidates."""

        scored = [
            (
                candidate,
                self.scoring_engine.score(
                    candidate,
                    requirement,
                ),
            )
            for candidate
            in candidates
        ]

        scored.sort(
            key=lambda item: (
                -item[1].final_score,
                -(
                    item[0].rating
                    or 0.0
                ),
                -(
                    item[0].review_count
                    or 0
                ),
                (
                    item[0].price
                    if item[0].price
                    is not None
                    else 10**18
                ),
                item[0].product_id,
            )
        )

        result: list[
            RankedCandidate
        ] = []

        for (
            index,
            (
                candidate,
                score,
            ),
        ) in enumerate(
            scored[:top_k],
            start=1,
        ):
            result.append(
                RankedCandidate(
                    rank=index,
                    candidate=candidate,
                    score=score,
                )
            )

        return result