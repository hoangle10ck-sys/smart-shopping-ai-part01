"""Bounded, cancellable explanation I/O over already-ranked facts."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import copy
import time

import httpx
from pydantic import ValidationError

from app.schemas.evidence import RecommendationExplanation
from app.services.llm.client import provider_overloaded
from app.services.llm.explanation_service import OPENAI_RESPONSES_URL
from app.services.performance import current_trace, measure


class ExplanationBatch:
    def __init__(self, service):
        # No shared settings writes, overload set, DB session, SDK client or
        # request trace is passed to the I/O workers.
        self.service = copy(service)
        self.service.settings = service.settings.model_copy(deep=True)
        self.settings = self.service.settings
        self.limit = min(3, max(1, self.settings.explanation_concurrency))
        self.timeout = max(.001, min(8., self.settings.explanation_timeout_seconds,
                                    self.settings.llm_timeout_seconds))
        self.metrics = {}

    def run(self, jobs):
        """Sync pipeline bridge; all SQLAlchemy work stays on its caller.

        In a running loop use one joined helper thread for a private async loop.
        Only SDK calls run there, never ORM reads/writes.
        """
        with measure('explanation_ms'):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                results = asyncio.run(self.run_async(jobs))
            else:
                with ThreadPoolExecutor(max_workers=1, thread_name_prefix='explanation-loop') as pool:
                    results = pool.submit(lambda: asyncio.run(self.run_async(jobs))).result()
        trace = current_trace.get()
        if trace is not None:
            trace.diagnostics['explanations'] = self.metrics
        return results

    async def run_async(self, jobs):
        jobs = [{k:v.model_copy(deep=True) for k,v in job.items()} for job in jobs]
        results, records = [None] * len(jobs), [None] * len(jobs)
        work = iter(enumerate(jobs))
        unavailable = set()  # Request-local; accessed on this event loop only.
        active = peak = 0
        batch_started = time.perf_counter()

        async def worker():
            nonlocal active, peak
            for index, job in work:
                started = time.perf_counter()
                active += 1
                peak = max(peak, active)
                attempts = []
                try:
                    results[index] = await self._explain(job, unavailable, attempts)
                except Exception:
                    results[index] = self._fallback(job)
                finally:
                    active -= 1
                    records[index] = dict(product_id=job['candidate'].product_id,
                        duration_ms=round((time.perf_counter()-started)*1000,3),
                        providers_attempted=attempts,
                        generation_mode=results[index].generation_mode if results[index] else 'cancelled')

        # Fixed worker count rather than a task per recommendation.
        tasks = [asyncio.create_task(worker()) for _ in range(min(self.limit,len(jobs)))]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done(): task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.metrics = dict(concurrency_limit=self.limit, peak_active=peak,
                item_timeout_seconds=self.timeout, items=records,
                wall_ms=round((time.perf_counter()-batch_started)*1000,3))
        return results

    def _fallback(self, job):
        result = self.service.build_deterministic(**job)
        result.generation_mode = 'demo' if self.settings.demo_mode else 'fallback'
        return result

    async def _explain(self, job, unavailable, attempts):
        if not self.service.use_llm or self.settings.demo_mode:
            return self._fallback(job)
        prompt = self.service._build_prompt(payload=self.service._build_payload(**job))
        deadline = asyncio.get_running_loop().time() + self.timeout
        try:
            # Primary + secondary share a single deadline, starting after queue
            # admission. Cancellation unwinds native async client contexts.
            async with asyncio.timeout(self.timeout):
                for provider in self.service._provider_order():
                    if provider in unavailable or not getattr(self.settings,f'{provider}_api_key').strip():
                        continue
                    attempts.append(provider)
                    try:
                        remaining = max(.001, deadline - asyncio.get_running_loop().time())
                        raw = await self._request(provider, prompt, min(self.timeout, remaining))
                    except (TimeoutError, httpx.TimeoutException):
                        return self._fallback(job)
                    except (ValidationError, ValueError, TypeError):
                        return self._fallback(job)
                    except Exception as exc:
                        if provider_overloaded(exc): unavailable.add(provider)
                        continue  # One attempt per configured provider; no backoff.
                    try:
                        result = (RecommendationExplanation.model_validate_json(raw) if isinstance(raw,str)
                                  else RecommendationExplanation.model_validate(raw))
                    except (ValidationError, ValueError, TypeError):
                        return self._fallback(job)  # No LLM repair call.
                    result.generation_mode = provider
                    return self.service._constrain(result,**job)
        except TimeoutError:
            pass
        return self._fallback(job)

    async def _request(self, provider, prompt, timeout):
        """Each product owns its clients; no SDK thread-safety assumption."""
        if provider == 'openai':
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(OPENAI_RESPONSES_URL,
                    headers={'Authorization':f'Bearer {self.settings.openai_api_key}',
                             'Content-Type':'application/json'},
                    json={'model':self.settings.openai_model,'store':False,'temperature':.1,
                        'input':[{'role':'user','content':[{'type':'input_text','text':prompt}]}],
                        'text':{'format':{'type':'json_schema','name':'recommendation_explanation',
                            'schema':RecommendationExplanation.model_json_schema(),'strict':False}}})
                response.raise_for_status()
                try:
                    return self.service._extract_openai_text(response.json())
                except RuntimeError as exc:
                    raise ValueError('Invalid explanation response envelope') from exc
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=self.settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=max(1,int(timeout*1000)),
                                          retry_options=types.HttpRetryOptions(attempts=1)))
        try:
            async with client.aio as aio:
                response = await aio.models.generate_content(model=self.settings.gemini_model,
                    contents=prompt,config=types.GenerateContentConfig(response_mime_type='application/json',
                        response_schema=RecommendationExplanation,temperature=.1))
                return response.parsed if response.parsed is not None else response.text
        finally:
            # SDK aio context closes async transport; close the sync side too.
            client.close()
