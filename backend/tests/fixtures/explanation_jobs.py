"""Synthetic explanation inputs; no provider/network dependency."""
import json

from app.schemas.evidence import EvidenceReport, EvidenceBreakdown
from app.schemas.ranking import ScoringCandidate
from app.services.scoring.scoring_engine import ScoringEngine
from tests.fixtures.discovery_scenarios import phone_requirement


def explanation_jobs(count=3):
    requirement = phone_requirement()
    result = []
    for number in range(1,count+1):
        c=ScoringCandidate(product_id=number,name=f'Fixture Phone {number}',category='điện thoại',
            price=15000000 if number==2 else 10000000,
            availability='unknown' if number==2 else 'in_stock',
            specifications={'camera':'50 MP' if number==2 else '50 MP OIS',
                            'pin':'2000 mAh' if number==2 else '8.500 mAh'})
        evidence=EvidenceReport(confidence=60,source_count=1,offer_count=1,
            breakdown=EvidenceBreakdown(source_reliability=50,product_completeness=70,
                offer_completeness=70,consistency=60,corroboration=40))
        result.append(dict(candidate=c,requirement=requirement,score=ScoringEngine().score(c,requirement),evidence=evidence))
    return result


def prompt_payload(prompt):
    return json.loads(prompt.split('DỮ LIỆU HỆ THỐNG:\n',1)[1])
