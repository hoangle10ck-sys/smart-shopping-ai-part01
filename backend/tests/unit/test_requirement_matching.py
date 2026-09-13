"""Three-state matching must agree with deterministic requirement scoring."""

import pytest

from app.schemas.ranking import ScoringCandidate
from app.schemas.requirement import RequirementData, RequirementItem
from app.services.scoring.scoring_engine import ScoringEngine


@pytest.mark.parametrize("key,requested,actual,status", [
    ("ram", "16GB", "8GB", "unmet"),
    ("ram", "16GB", "16GB", "matched"),
    ("ram", "16GB", "32GB", "matched"),
    ("ram", "16GB", None, "unknown"),
    ("ram", "16GB", "unknown", "unknown"),
    ("ram", "16GB", "Chưa có thông tin", "unknown"),
    ("ram", "16GB", "16", "unknown"),
    ("ram", "16GB DDR5", "16GB", "unknown"),
    ("ram", "16GB DDR5", "8GB", "unmet"),
    ("ram", "16GB DDR5", "16GB DDR4", "unmet"),
    ("ram", "16GB", "8GB upgrade to 32GB", "unmet"),
    ("storage", "1TB", "1024GB", "matched"),
    ("ram", "tối đa 16GB", "32GB", "unmet"),
    ("microphone", "tốt", "ENC", "matched"),
    ("microphone", "tốt", "Không có", "unmet"),
    ("microphone", "tốt", "yes", "unknown"),
    ("microphone", "tốt", "bad", "unmet"),
    ("battery", "pin lâu", "4h", "unmet"),
    ("battery", "pin lâu", "12h", "matched"),
    ("battery", "pin lâu", "5000mAh", "unknown"),
    ("camera", "tốt", "present", "unknown"),
])
def test_three_state_matching(key, requested, actual, status):
    candidate = ScoringCandidate(product_id=1, name="Laptop", category="laptop",
                                 specifications={} if actual is None else {key: actual})
    requirement = RequirementData(requirements=[RequirementItem(name=key, value=requested, priority=5)])
    engine = ScoringEngine()
    match, = engine.requirement_matches(candidate, requirement)
    assert (match.name, match.requested_value, match.product_value) == (key, requested, actual)
    assert match.status == status
    assert match.reason
    assert engine.requirement_score(candidate, requirement) == (100 if status == "matched" else 0)


def test_priority_aliases_and_missing_properties_share_the_scoring_decision():
    candidate = ScoringCandidate(product_id=1, name="Laptop", specifications={"memory": "16GB", "storage": "256GB"})
    requirement = RequirementData(requirements=[
        RequirementItem(name="ram", value="16GB", priority=5),
        RequirementItem(name="storage", value="512GB", priority=3),
        RequirementItem(name="microphone", value="tốt", priority=2),
    ])
    engine = ScoringEngine()
    assert [item.status for item in engine.requirement_matches(candidate, requirement)] == ["matched", "unmet", "unknown"]
    assert engine.requirement_score(candidate, requirement) == 50


def test_no_requirements_produces_no_invented_matches():
    candidate = ScoringCandidate(product_id=1, name="Laptop")
    assert ScoringEngine().requirement_matches(candidate, RequirementData()) == []
    assert ScoringEngine().requirement_score(candidate, RequirementData()) == 100
