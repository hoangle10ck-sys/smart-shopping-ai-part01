"""Exercise configured explanation providers without making external requests."""

import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from google import genai

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.services.llm import explanation_service as module
from app.services.recommendation.recommendation_service import RecommendationService


@pytest.mark.parametrize("provider", ["openai", "gemini"])
@pytest.mark.parametrize("outcome", ["success", "timeout", "invalid"])
def test_live_provider_roundtrip_and_safe_fallback(monkeypatch, provider, outcome):
    settings = get_settings()
    monkeypatch.setattr(settings, "top_k", 1)
    with TestClient(app) as client:
        analyzed = client.post("/api/requirements/analyze", json={
            "raw_query": "Tai nghe 500 nghìn để học online, microphone tốt, pin lâu",
        })
        session_id = analyzed.json()["session_id"]
        baseline = client.post("/api/search", json={"session_id": session_id})
        assert baseline.status_code == 200
        original = baseline.json()["recommendations"][0]

        monkeypatch.setattr(settings, "demo_mode", False)
        monkeypatch.setattr(settings, "llm_provider", provider)
        monkeypatch.setattr(settings, "llm_fallback_provider", "")
        monkeypatch.setattr(settings, "llm_retry_count", 1)
        monkeypatch.setattr(settings, "llm_timeout_seconds", 7)
        monkeypatch.setattr(settings, "openai_api_key", "test-only-placeholder")
        monkeypatch.setattr(settings, "gemini_api_key", "test-only-placeholder")
        monkeypatch.setattr(module.time, "sleep", lambda _: None)
        calls, timeouts, closed = [], [], []

        def response_text():
            calls.append(provider)
            if outcome == "timeout":
                raise httpx.ReadTimeout("Mock timeout")
            if outcome == "invalid":
                return json.dumps({"summary": []})
            # Provider attempts to add numeric data; the pipeline must never use it.
            return json.dumps({
                "summary": "Giải thích dựa trên evidence được cung cấp.",
                "why_fit": ["Phù hợp cho học online."], "tradeoffs": [], "evidence_notes": [],
                "generation_mode": provider,
                "price": 1, "rating": 0, "specifications": {"ram": "999GB"}, "final_score": 0,
            })

        class OpenAIClient:
            def __init__(self, *, timeout):
                timeouts.append(timeout)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                closed.append(True)

            def post(self, url, *, headers, json):
                assert url == module.OPENAI_RESPONSES_URL
                assert json["store"] is False
                text = response_text()
                return SimpleNamespace(status_code=200, json=lambda: {
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
                })

        class GeminiClient:
            def __init__(self, *, api_key, http_options):
                timeouts.append(http_options.timeout)
                assert http_options.retry_options.attempts == 1
                self.models = self

            def generate_content(self, **kwargs):
                return SimpleNamespace(parsed=None, text=response_text())

            def close(self):
                closed.append(True)

        monkeypatch.setattr(module.httpx, "Client", OpenAIClient)
        monkeypatch.setattr(genai, "Client", GeminiClient)
        with SessionLocal() as db:
            result = RecommendationService().run(db=db, session_id=session_id)
            db.commit()
        item = result.recommendations[0].model_dump(mode="json")
        expected_mode = provider if outcome == "success" else "fallback"
        assert item["explanation"]["generation_mode"] == expected_mode
        for key in ("price", "rating", "review_count", "specifications", "score", "confidence", "evidence"):
            assert item[key] == original[key]
        assert calls == [provider] * (1 if outcome == "success" else 2)
        assert timeouts and all(t == (7 if provider == "openai" else 7000) for t in timeouts)
        assert closed

        # Serializing and reading OpenAI mode must be accepted by the public schema.
        loaded = client.get(f"/api/search/{session_id}")
        assert loaded.status_code == 200
        assert loaded.json()["recommendations"][0] == item
        assert len(calls) == (1 if outcome == "success" else 2)
