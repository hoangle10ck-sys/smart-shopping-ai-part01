import asyncio
from types import SimpleNamespace

import pytest
from google import genai

from app.core.config import get_settings
from app.services.llm.explanation_service import ExplanationService
from app.services.llm.explanation_batch import ExplanationBatch
from tests.fixtures.explanation_jobs import explanation_jobs, prompt_payload


def live_batch(monkeypatch, **settings):
    config=get_settings()
    for key,value in dict(demo_mode=False,llm_provider='gemini',llm_fallback_provider='',
        gemini_api_key='mock-only',explanation_concurrency=3,explanation_timeout_seconds=.15,
        **settings).items():
        monkeypatch.setattr(config,key,value)
    return ExplanationBatch(ExplanationService())


@pytest.mark.asyncio
@pytest.mark.parametrize('limit',[1,2,3,999])
async def test_fixed_worker_bound_for_many_items(monkeypatch,limit):
    batch=live_batch(monkeypatch)
    batch.limit=min(3,limit)
    active=peak=0
    async def request(provider,prompt,timeout):
        nonlocal active,peak
        active+=1;peak=max(peak,active)
        try:
            await asyncio.sleep(.001)
            return prompt_payload(prompt)['approved_explanation']
        finally: active-=1
    monkeypatch.setattr(batch,'_request',request)
    jobs=explanation_jobs(17);before=[{k:v.model_dump() for k,v in j.items()} for j in jobs]
    out=await batch.run_async(jobs)
    assert peak==min(3,limit) and active==0 and len(out)==17
    assert [r.summary for r in out]==[batch.service.build_deterministic(**j).summary for j in jobs]
    assert before==[{k:v.model_dump() for k,v in j.items()} for j in jobs]


@pytest.mark.asyncio
async def test_reverse_completion_preserves_rank_without_timing_assumptions(monkeypatch):
    batch=live_batch(monkeypatch);batch.timeout=2
    entered={i:asyncio.Event() for i in (1,2,3)}
    release={i:asyncio.Event() for i in (1,2,3)}
    finished={i:asyncio.Event() for i in (1,2,3)};order=[]
    async def request(provider,prompt,timeout):
        data=prompt_payload(prompt);i=data['candidate']['product_id'];entered[i].set()
        await release[i].wait();order.append(i);finished[i].set()
        return data['approved_explanation']
    monkeypatch.setattr(batch,'_request',request)
    task=asyncio.create_task(batch.run_async(explanation_jobs()))
    await asyncio.wait_for(asyncio.gather(*(e.wait() for e in entered.values())),1)
    for i in (3,2,1):
        release[i].set();await finished[i].wait()
    results=await task
    assert order==[3,2,1]
    assert [r.summary.split(' đạt ')[0] for r in results]==['Fixture Phone 1','Fixture Phone 2','Fixture Phone 3']


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['timeout','exception','malformed','unsupported','unavailable'])
async def test_native_gemini_async_failure_isolation_and_client_closure(monkeypatch,fault):
    batch=live_batch(monkeypatch);clients=[];calls=[]
    class Client:
        def __init__(self,*,api_key,http_options):
            assert http_options.retry_options.attempts==1 and 0<http_options.timeout<=150
            self.models=self;self.aio=self;self.sync_closed=self.async_closed=False;clients.append(self)
        async def __aenter__(self):return self
        async def __aexit__(self,*a):self.async_closed=True
        def close(self):self.sync_closed=True
        async def generate_content(self,*,contents,**kwargs):
            data=prompt_payload(contents);i=data['candidate']['product_id'];calls.append(i)
            await asyncio.sleep(0)  # All three are in flight before one fails.
            if i==2:
                if fault=='timeout':await asyncio.Event().wait()
                if fault=='exception':raise RuntimeError('isolated failure')
                if fault=='unavailable':raise RuntimeError('503 UNAVAILABLE')
                if fault=='malformed':return SimpleNamespace(parsed=None,text='{"summary":[]}')
                if fault=='unsupported':
                    data['approved_explanation']['summary']='Camera và pin đáp ứng tốt; trong ngân sách, còn hàng.'
            return SimpleNamespace(parsed=data['approved_explanation'],text=None)
    monkeypatch.setattr(genai,'Client',Client)
    jobs=explanation_jobs();out=await asyncio.wait_for(batch.run_async(jobs),1)
    assert [r.generation_mode for r in out]==['gemini','fallback','gemini']
    assert sorted(calls)==[1,2,3] and all(c.sync_closed and c.async_closed for c in clients)
    safe=batch.service.build_deterministic(**jobs[1])
    assert out[1].model_dump(exclude={'generation_mode'})==safe.model_dump(exclude={'generation_mode'})
    assert any('camera: chưa đủ' in s for s in out[1].tradeoffs)
    assert any('battery: không đáp ứng' in s for s in out[1].tradeoffs)
    assert any('ngân sách ưu tiên' in s for s in out[1].tradeoffs)
    assert any('Chưa xác minh' in s for s in out[1].tradeoffs)


@pytest.mark.asyncio
async def test_parent_cancellation_drains_all_workers_and_sdk_clients(monkeypatch):
    batch=live_batch(monkeypatch);batch.timeout=5;clients=[];entered=asyncio.Event()
    class Client:
        def __init__(self,**kwargs):
            self.aio=self;self.models=self;self.sync_closed=self.async_closed=False;clients.append(self)
        async def __aenter__(self):return self
        async def __aexit__(self,*a):self.async_closed=True
        def close(self):self.sync_closed=True
        async def generate_content(self,**kwargs):
            if len(clients)==3:entered.set()
            await asyncio.Event().wait()
    monkeypatch.setattr(genai,'Client',Client)
    task=asyncio.create_task(batch.run_async(explanation_jobs(9)))
    await asyncio.wait_for(entered.wait(),1);task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert len(clients)==3 and all(c.sync_closed and c.async_closed for c in clients)


@pytest.mark.asyncio
async def test_unavailability_is_per_batch_and_no_unbounded_retry(monkeypatch):
    batch=live_batch(monkeypatch);calls=[]
    async def fail(provider,prompt,timeout):calls.append(provider);raise RuntimeError('503 UNAVAILABLE')
    monkeypatch.setattr(batch,'_request',fail)
    out=await batch.run_async(explanation_jobs(9))
    assert all(r.generation_mode=='fallback' for r in out) and 1<=len(calls)<=3
    async def success(provider,prompt,timeout):return prompt_payload(prompt)['approved_explanation']
    monkeypatch.setattr(batch,'_request',success)
    assert all(r.generation_mode=='gemini' for r in await batch.run_async(explanation_jobs()))


@pytest.mark.asyncio
@pytest.mark.parametrize('demo,keys,enabled',[(True,True,True),(False,False,True),(False,True,False)])
async def test_disabled_demo_and_missing_keys_never_call_provider(monkeypatch,demo,keys,enabled):
    live_batch(monkeypatch)
    config=get_settings();monkeypatch.setattr(config,'demo_mode',demo)
    if not keys:monkeypatch.setattr(config,'gemini_api_key','')
    batch=ExplanationBatch(ExplanationService(use_llm=enabled))
    async def forbidden(*a):raise AssertionError('Provider must not be reached')
    # Assert calls separately because worker failure isolation catches errors.
    calls=[]
    async def request(*a):calls.append(1);return await forbidden(*a)
    monkeypatch.setattr(batch,'_request',request)
    result=await batch.run_async(explanation_jobs())
    assert not calls and all(r.generation_mode==('demo' if demo else 'fallback') for r in result)


@pytest.mark.asyncio
async def test_primary_secondary_share_deadline_without_prose_retries(monkeypatch):
    batch=live_batch(monkeypatch);batch.settings.llm_fallback_provider='openai';batch.settings.openai_api_key='mock-only';batch.timeout=.05
    calls=[];closed=[]
    async def request(provider,prompt,timeout):
        calls.append((provider,timeout))
        try:
            if provider=='gemini':await asyncio.sleep(.015);raise RuntimeError('provider failed')
            await asyncio.Event().wait()
        finally:closed.append(provider)
    monkeypatch.setattr(batch,'_request',request)
    out=await asyncio.wait_for(batch.run_async(explanation_jobs(1)),1)
    assert out[0].generation_mode=='fallback' and [p for p,_ in calls]==closed==['gemini','openai']
    assert calls[1][1]<calls[0][1] and calls[0][1]<=.05


def test_configuration_is_copied_and_limits_cannot_expand(monkeypatch):
    live_batch(monkeypatch)
    config=get_settings();monkeypatch.setattr(config,'explanation_concurrency',999)
    monkeypatch.setattr(config,'explanation_timeout_seconds',999)
    monkeypatch.setattr(config,'llm_timeout_seconds',2)
    batch=ExplanationBatch(ExplanationService())
    assert batch.limit==3 and batch.timeout==2
    batch.settings.llm_provider='openai'
    assert config.llm_provider=='gemini'
