"""Explicit manual Live check, isolated SQLite; not part of automated pytest.

Run from backend/: .venv/Scripts/python.exe -B -X utf8 scripts/check_live_sales.py
Reads backend/.env through Settings, never prints keys or writes the application DB.
"""
import asyncio
import argparse
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--search-timeout', type=int, default=None,
                        help='Manual-only Tavily timeout; does not edit backend/.env')
    parser.add_argument('--scenario', choices=['A','B','C','D'], default=None,
                        help='Recheck one scenario and retain the other recorded scenarios')
    args = parser.parse_args()
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'scenarios': []}
    target = Path(__file__).resolve().parents[2] / 'docs/LIVE_TV_CHECK.json'
    if target.exists():
        old = json.loads(target.read_text(encoding='utf-8'))
        report['previous_check'] = {k: v for k, v in old.items() if k != 'previous_check'}
        if args.scenario:
            report['scenarios'] = old.get('scenarios', [])
    with TemporaryDirectory(prefix='shopping-manual-live-') as directory:
        os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(directory) / 'manual.sqlite3').as_posix()
        os.environ['DEMO_MODE'] = 'false'
        from app.core.config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        report['retrieval_config'] = {'configured_query_timeout': settings.search_timeout_seconds,
            'manual_query_timeout': args.search_timeout or settings.search_timeout_seconds, 'total_budget_seconds': settings.live_search_budget_seconds,
            'max_queries': settings.live_search_max_queries, 'target_products': settings.live_search_target_products}
        if args.search_timeout is not None:
            settings.search_timeout_seconds = args.search_timeout
        report['providers'] = {'search': 'tavily', 'llm': settings.llm_provider,
                               'fallback': settings.llm_fallback_provider,
                               'model': settings.gemini_model if settings.llm_provider == 'gemini' else settings.openai_model}
        if not settings.tavily_api_key:
            report['status'] = 'NOT VERIFIED: Tavily key missing'
        else:
            from fastapi.testclient import TestClient
            from app.main import app
            from app.core.database import engine
            from app.services.extraction.product_image_resolver import ProductImageResolver
            from app.services.search.progressive_retrieval import ProgressiveRetriever
            captured = []
            original_run = ProgressiveRetriever.run
            async def traced_run(retriever, *args, **kwargs):
                try:
                    return await original_run(retriever, *args, **kwargs)
                finally:
                    captured.extend(retriever.diagnostics)
            ProgressiveRetriever.run = traced_run
            assert Path(engine.url.database).resolve().parent == Path(directory).resolve()
            secrets = [settings.tavily_api_key, settings.gemini_api_key, settings.openai_api_key]
            def redact(value):
                text = json.dumps(value, ensure_ascii=False, default=str)
                for secret in secrets:
                    if secret: text = text.replace(secret, '[REDACTED]')
                return json.loads(text)
            try:
                with TestClient(app) as client:
                    for index, query in enumerate(['Tôi cần xe máy khoảng 33 triệu để đi học, ưu tiên tiết kiệm xăng.',
                                  'Tôi cần xe máy tối đa 33 triệu để đi học.',
                                  'Tôi cần TV khoảng 10 triệu để xem phim.',
                                  'Tôi cần điện thoại khoảng 10 triệu, camera tốt, pin lâu.']):
                        if args.scenario and 'ABCD'[index] != args.scenario: continue
                        print('Checking:', query, flush=True)
                        row = {'query': query, 'checked_at': datetime.now(timezone.utc).isoformat(), 'recommendations': []}
                        captured.clear()
                        analysis = client.post('/api/requirements/analyze', json={'raw_query': query})
                        row['analysis_status'] = analysis.status_code
                        if analysis.status_code != 200:
                            row['analysis_error'] = redact(analysis.json())
                            report['scenarios'].append(row)
                            continue
                        body = analysis.json()
                        row['analysis'] = redact(body)
                        if body.get('needs_clarification') and body.get('missing_fields') == ['purpose'] and 'camera' in query:
                            answer = 'chụp ảnh'
                            clarification = client.post('/api/requirements/clarify', json={'session_id': body['session_id'], 'answer': answer})
                            row['clarification_answer'] = answer
                            row['clarification_status'] = clarification.status_code
                            row['clarification_result'] = redact(clarification.json())
                        search = client.post('/api/search', json={'session_id': body['session_id']})
                        row['search_status'] = search.status_code
                        row['retrieval_diagnostics'] = redact(captured)
                        row['source_audit'] = [entry for diagnostic in captured for entry in diagnostic.get('source_audit',[])]
                        payload = search.json()
                        row['requirement'] = payload.get('requirement') or (row.get('clarification_result') or body).get('requirement')
                        row['warnings'] = redact(payload.get('warnings', []))
                        row['counts'] = {k: payload.get(k) for k in ('total_found', 'total_filtered', 'total_recommended')}
                        row['candidates'] = redact(payload.get('candidates', []))
                        row['filter_decisions'] = redact(payload.get('filter_decisions', []))
                        if search.status_code != 200: row['search_error'] = redact(payload)
                        stored = client.get('/api/search/' + body['session_id']).json()
                        row['persisted_warnings'] = redact(stored.get('warnings', []))
                        row['sources'] = [{k: source.get(k) for k in ('url', 'title', 'result_type', 'page_validation')} for source in payload.get('sources', [])]
                        async def verify(item):
                            resolver = ProductImageResolver()
                            proof = await resolver.inspect(item['product_url'], item['name']) if item.get('product_url') else {}
                            loads = await resolver._image_loads(item['image_url']) if item.get('image_url') else False
                            return {'name': item['name'], 'brand': item.get('brand'), 'model': item.get('model'),
                                    'variant': item.get('variant'), 'price_type': item.get('price_type'),
                                    'budget_mode': (row.get('requirement') or {}).get('budget_mode'),
                                    'target_budget': (row.get('requirement') or {}).get('budget_target'),
                                    'preferred_window': [(row.get('requirement') or {}).get('preferred_min'),
                                                         (row.get('requirement') or {}).get('preferred_max')],
                                    'requirement_matches': item.get('requirement_matches'), 'score': item.get('score'),
                                    'price': item['price'], 'merchant': item['merchant'],
                                    'domain': __import__('urllib.parse', fromlist=['urlsplit']).urlsplit(item.get('product_url') or '').hostname,
                                    'product_url': item.get('product_url'), 'product_page_valid': item.get('product_page_valid'),
                                    'verification_level': item.get('verification_level'), 'product_page_confidence': item.get('product_page_confidence'),
                                    'manual_content_confirmed': bool(proof.get('product_page_valid')),
                                    'manual_price': proof.get('price'),
                                    'category_evidence_source': (proof.get('category_evidence') or {}).get('source'),
                                    'category_evidence': proof.get('category_evidence'),
                                    'category': proof.get('category'),
                                    'availability': item.get('availability',proof.get('availability')),
                                    'manual_price_matches': proof.get('price') == item['price'],
                                    'manual_final_url': proof.get('product_url'),
                                    'manual_check_reason': proof.get('reason'),
                                    'image_url': item.get('image_url'), 'image_source': item.get('image_source'),
                                    'image_loads': loads, 'evidence_url': item.get('evidence_url'),
                                    'explanation_mode': (item.get('explanation') or {}).get('generation_mode')}
                        for item in payload.get('recommendations', []):
                            row['recommendations'].append(asyncio.run(verify(item)))
                        if args.scenario and index < len(report['scenarios']):
                            report['scenarios'][index] = redact(row)
                        else:
                            report['scenarios'].append(redact(row))
                        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                        print('Result:', row['search_status'], row['counts'], flush=True)
            finally:
                ProgressiveRetriever.run = original_run
                engine.dispose()
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Report:', target, flush=True)


if __name__ == '__main__':
    main()
