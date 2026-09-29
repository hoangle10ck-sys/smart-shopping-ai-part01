"""Offline fake-delay benchmark. Provider override never opens HTTP or SDK clients."""
import asyncio
import json
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.core.config import Settings
from app.services.llm.explanation_service import ExplanationService
from app.services.llm.explanation_batch import ExplanationBatch
from tests.fixtures.explanation_jobs import explanation_jobs, prompt_payload


class FakeBatch(ExplanationBatch):
    def __init__(self,service,delay=1.,fail=None):
        super().__init__(service);self.delay=delay;self.fail=fail;self.calls=[];self.finished=[]
    async def _request(self,provider,prompt,timeout):
        data=prompt_payload(prompt);pid=data['candidate']['product_id'];self.calls.append(pid)
        if pid==self.fail:await asyncio.Event().wait()
        await asyncio.sleep(self.delay)
        self.finished.append(pid)
        return data['approved_explanation']


async def main():
    service=ExplanationService(use_llm=False)
    service.settings=Settings(_env_file=None,demo_mode=False,llm_provider='gemini',llm_fallback_provider='',
                              gemini_api_key='fake-benchmark-only',explanation_timeout_seconds=8)
    service.use_llm=True
    jobs=explanation_jobs();trials=[]
    for _ in range(2):
        row={}
        for name,limit in [('sequential',1),('concurrent',3)]:
            runner=FakeBatch(service);runner.limit=limit
            started=time.perf_counter();out=await runner.run_async(jobs)
            row[name]=dict(wall_seconds=round(time.perf_counter()-started,4),concurrency_limit=limit,
                peak_active=runner.metrics['peak_active'],calls=runner.calls,
                output_order=[i['product_id'] for i in runner.metrics['items']],
                modes=[r.generation_mode for r in out])
            assert row[name]['output_order']==[1,2,3] and row[name]['modes']==['gemini']*3
        trials.append(row)
    failed=FakeBatch(service,delay=.001,fail=2);failed.timeout=.05
    out=await failed.run_async(jobs)
    before=statistics.median(t['sequential']['wall_seconds'] for t in trials)
    after=statistics.median(t['concurrent']['wall_seconds'] for t in trials)
    result=dict(method='Same three synthetic inputs and 1-second async mock responses; single worker models previous sequential execution. No network.',
        trials=trials,before_median_seconds=round(before,4),after_median_seconds=round(after,4),
        reduction_percent=round((1-after/before)*100,2),concurrency=3,
        isolated_timeout=dict(product_id=2,modes=[r.generation_mode for r in out],
            output_order=[i['product_id'] for i in failed.metrics['items']],calls=failed.calls),
        limitations='Not a Live benchmark or prediction of provider latency. Remaining search/verification time is unchanged.')
    assert after<before*.75 and result['isolated_timeout']['modes']==['gemini','fallback','gemini']
    (ROOT.parent/'docs/EXPLANATION_LATENCY_BENCHMARK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':asyncio.run(main())
