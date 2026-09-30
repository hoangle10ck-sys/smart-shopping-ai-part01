"""Request-local diagnostics. Never record settings, credentials or exception bodies."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import inspect
import json
import logging
import time

TIMINGS = ('requirement_analysis_ms', 'clarification_ms', 'query_generation_ms',
           'search_provider_ms', 'product_discovery_ms', 'product_verification_ms', 'page_fetch_ms', 'verification_ms',
           'extraction_ms', 'filtering_ms', 'scoring_ms', 'explanation_ms', 'total_search_ms')
current_trace = ContextVar('search_performance', default=None)
logger = logging.getLogger(__name__)


class PerformanceTrace:
    def __init__(self):
        self.timings = dict.fromkeys(TIMINGS, 0.0)
        self.diagnostics = dict.fromkeys(('candidates_found', 'pages_verified',
            'rejected_wrong_category', 'rejected_non_product_page', 'rejected_missing_price',
            'rejected_out_of_stock', 'rejected_duplicate', 'rejected_other', 'valid_offers',
            'final_recommendations', 'valid_candidates', 'eligible_offers'), 0)
        self.diagnostics.update(generated_queries=[], unique_candidate_urls=[], rounds=[], cache_hit=False)

    def snapshot(self):
        return {'timings': {k: round(v, 3) for k, v in self.timings.items()},
                'diagnostics': dict(self.diagnostics)}


@contextmanager
def measure(name):
    started = time.perf_counter()
    try:
        yield
    finally:
        trace = current_trace.get()
        if trace is not None:
            trace.timings[name] = trace.timings.get(name, 0) + (time.perf_counter() - started) * 1000


def timed(name):
    def decorate(function):
        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def asynchronous(*args, **kwargs):
                with measure(name):
                    return await function(*args, **kwargs)
            return asynchronous
        @wraps(function)
        def synchronous(*args, **kwargs):
            with measure(name):
                return function(*args, **kwargs)
        return synchronous
    return decorate


def profile_request(name):
    """Separate analyze/clarify/search requests; durations are not invented on GET."""
    def decorate(function):
        @wraps(function)
        async def wrapped(*args, **kwargs):
            trace = PerformanceTrace()
            token = current_trace.set(trace)
            try:
                with measure(name):
                    result = await function(*args, **kwargs)
                if hasattr(result, 'session_id'):
                    trace.diagnostics['session_id'] = result.session_id
                if hasattr(result, 'search_queries'):
                    trace.diagnostics['generated_queries'] = result.search_queries
                if hasattr(result, 'retrieval_diagnostics'):
                    result.retrieval_diagnostics.append({'performance': trace.snapshot()})
                return result
            finally:
                logger.info('shopping_performance %s', json.dumps(trace.snapshot(), ensure_ascii=False))
                current_trace.reset(token)
        return wrapped
    return decorate
