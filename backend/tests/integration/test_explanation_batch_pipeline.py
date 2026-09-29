"""Persist rank-ordered concurrent output without passing ORM state to workers."""
import asyncio
import threading

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.recommendation.recommendation_service import RecommendationService
from app.services.llm.explanation_batch import ExplanationBatch
from app.services.performance import PerformanceTrace, current_trace
from tests.fixtures.explanation_jobs import prompt_payload


@pytest.mark.parametrize('timeout_middle',[False,True])
def test_persisted_rank_facts_and_get_survive_reverse_order_and_one_timeout(monkeypatch,timeout_middle):
    settings=get_settings();monkeypatch.setattr(settings,'top_k',3)
    with TestClient(app) as client:
        analyzed=client.post('/api/requirements/analyze',json={'raw_query':'Tai nghe 500 nghìn để học online, microphone tốt, pin lâu'})
        sid=analyzed.json()['session_id']
        baseline=client.post('/api/search',json={'session_id':sid}).json()['recommendations']
        assert len(baseline)==3
        ids=[r['product_id'] for r in baseline];finished=[];calls=[]
        all_entered=asyncio.Event();third_done=asyncio.Event();second_done=asyncio.Event()
        for key,value in dict(demo_mode=False,llm_provider='gemini',llm_fallback_provider='',
                              gemini_api_key='mock-only',explanation_timeout_seconds=.2).items():
            monkeypatch.setattr(settings,key,value)
        async def request(self,provider,prompt,timeout):
            data=prompt_payload(prompt);pid=data['candidate']['product_id'];index=ids.index(pid);calls.append(pid)
            if len(calls)==3:all_entered.set()
            await all_entered.wait()
            if index!=2:await third_done.wait()
            if index==1 and timeout_middle:await asyncio.Event().wait()
            if index==0 and not timeout_middle:await second_done.wait()
            finished.append(pid)
            if index==2:third_done.set()
            if index==1:second_done.set()
            return data['approved_explanation']
        monkeypatch.setattr(ExplanationBatch,'_request',request)
        service=RecommendationService();owner=threading.get_ident();validate=service.evidence_validator.validate
        def validate_on_caller(context):
            assert threading.get_ident()==owner
            return validate(context)
        monkeypatch.setattr(service.evidence_validator,'validate',validate_on_caller)
        trace=PerformanceTrace();token=current_trace.set(trace)
        try:
            with SessionLocal() as db:
                result=service.run(db=db,session_id=sid);db.commit()
        finally:current_trace.reset(token)
        output=[r.model_dump(mode='json') for r in result.recommendations]
        assert finished[0]==ids[2] and [r['product_id'] for r in output]==ids
        assert [r['rank'] for r in output]==[1,2,3]
        for previous,actual in zip(baseline,output):
            for key in ('score','price','rating','specifications','availability','confidence','evidence','requirement_matches'):
                assert actual[key]==previous[key]
        assert [r['explanation']['generation_mode'] for r in output]==['gemini','fallback' if timeout_middle else 'gemini','gemini']
        assert client.get(f'/api/search/{sid}').json()['recommendations']==output
        assert sorted(calls)==sorted(ids)
        assert trace.timings['explanation_ms']>0
        assert trace.diagnostics['explanations']['peak_active']==3
        assert [r['product_id'] for r in trace.diagnostics['explanations']['items']]==ids
