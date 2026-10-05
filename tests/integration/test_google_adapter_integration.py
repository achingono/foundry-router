"""Integration regressions for Google adapter routing, quota, and retries."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from foundry_router.config import Settings
from foundry_router.main import (
    _reset_backend_health_state,
    _reset_credit_state,
    _reset_metrics_state,
    _reset_rate_limit_state,
    app,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    yield
    asyncio.run(_reset_backend_health_state())
    asyncio.run(_reset_credit_state())
    asyncio.run(_reset_metrics_state())
    asyncio.run(_reset_rate_limit_state())


def _settings(backends, models, **extra):
    return Settings(
        backends_json=json.dumps(backends),
        models_json=json.dumps(models),
        client_api_keys_json='["client-key"]',
        admin_api_keys_json='["admin-key"]',
        **extra,
    )


def _wire(monkeypatch, settings):
    monkeypatch.setattr("foundry_router.main.load_settings", lambda: settings)
    monkeypatch.setattr("foundry_router.auth.load_settings", lambda: settings)
    monkeypatch.setattr("foundry_router.backends.load_settings", lambda: settings)
    monkeypatch.setattr("foundry_router.config.load_settings", lambda: settings)
    monkeypatch.setattr("foundry_router.backends._backend_client", None)
    asyncio.run(_reset_backend_health_state())
    asyncio.run(_reset_credit_state())
    asyncio.run(_reset_metrics_state())
    asyncio.run(_reset_rate_limit_state())


def _chat_ok(text="synthetic", prompt=4, completion=2):
    return {
        "id": "chatcmpl-s",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gemini-2.5-flash",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}
        ],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        },
    }


class TestEmbeddingsQuotaWiring:
    @respx.mock
    def test_embeddings_use_quota_store_and_logical_alias(self, monkeypatch):
        backends = {
            "gm-emb": {
                "provider": "google_ai_studio",
                "endpoint": "https://generativelanguage.googleapis.com",
                "credential": "synthetic-emb-key",
                "deployment": "gemini-embedding-001",
                "quota_group": "emb-project",
                "credit_metered": False,
                "supported_operations": ["embeddings"],
            }
        }
        settings = _settings(
            backends,
            {"emb-alias": {"backends": {"gm-emb": 1.0}}},
            quota_group_rate_limits_json=json.dumps({"emb-project": {"rpm": 10, "tpm": 1000}}),
        )
        _wire(monkeypatch, settings)
        route = respx.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/embeddings"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "object": "list",
                    "data": [
                        {"object": "embedding", "index": 0, "embedding": [0.1, 0.2]},
                        {"object": "embedding", "index": 1, "embedding": [0.3, 0.4]},
                    ],
                    "model": "gemini-embedding-001",
                    "usage": {"prompt_tokens": 6, "total_tokens": 6},
                },
            )
        )
        response = client.post(
            "/openai/v1/embeddings",
            headers={"api-key": "client-key"},
            json={"model": "emb-alias", "input": ["hello", "world"]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["model"] == "emb-alias"
        assert [d["index"] for d in body["data"]] == [0, 1]
        assert route.call_count == 1
        upstream = json.loads(route.calls[0].request.content)
        assert upstream["encoding_format"] == "float"
        status = client.get("/admin/status", headers={"x-admin-key": "admin-key"})
        assert status.status_code == 200
        quota = status.json()["backends"]["gm-emb"]["live"]["rate_limit"]
        assert quota["quota_group"] == "emb-project"
        assert quota["rpm_used_60s"] == 1
        assert "synthetic-emb-key" not in response.text

    @respx.mock
    def test_google_default_operations_reject_embeddings(self, monkeypatch):
        backends = {
            "gm": {
                "provider": "google_ai_studio",
                "endpoint": "https://generativelanguage.googleapis.com",
                "credential": "synthetic-key",
                "deployment": "gemini-2.5-flash",
                "quota_group": "p1",
                "credit_metered": False,
            }
        }
        settings = _settings(backends, {"m": {"backends": {"gm": 1.0}}})
        _wire(monkeypatch, settings)
        response = client.post(
            "/openai/v1/embeddings",
            headers={"api-key": "client-key"},
            json={"model": "m", "input": "hi"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["type"] == "unsupported_operation"
        assert not respx.calls


class TestUnsupportedBeforeEgress:
    @respx.mock
    def test_tools_rejected_without_upstream(self, monkeypatch):
        backends = {
            "gm": {
                "provider": "google_ai_studio",
                "endpoint": "https://generativelanguage.googleapis.com",
                "credential": "synthetic-key",
                "deployment": "gemini-2.5-flash",
                "quota_group": "p1",
                "credit_metered": False,
            }
        }
        settings = _settings(backends, {"m": {"backends": {"gm": 1.0}}})
        _wire(monkeypatch, settings)
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key"},
            json={"model": "m", "input": "hi", "tools": [{"type": "function"}]},
        )
        assert response.status_code == 422
        assert not respx.calls

    @respx.mock
    def test_mixed_pool_prefers_capable_azure(self, monkeypatch):
        backends = {
            "az": {
                "endpoint": "https://az.example",
                "credential": "az-key",
                "deployment": "gpt-4",
                "credit_metered": False,
            },
            "gm": {
                "provider": "google_ai_studio",
                "endpoint": "https://generativelanguage.googleapis.com",
                "credential": "synthetic-key",
                "deployment": "gemini-2.5-flash",
                "quota_group": "p1",
                "credit_metered": False,
            },
        }
        settings = _settings(
            backends,
            {"m": {"backends": {"az": 1.0, "gm": 1.0}}},
        )
        _wire(monkeypatch, settings)
        az_route = respx.post("https://az.example/openai/v1/responses").mock(
            return_value=httpx.Response(
                200, json={"id": "resp_az", "usage": {"input_tokens": 1, "output_tokens": 1}}
            )
        )
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key"},
            json={"model": "m", "input": "hi", "tools": [{"type": "function"}]},
        )
        assert response.status_code == 200
        assert az_route.call_count == 1


class TestAuthCooldownAndFailover:
    @respx.mock
    def test_401_terminal_then_healthy_key(self, monkeypatch):
        backends = {
            "gm-bad": {
                "provider": "google_ai_studio",
                "endpoint": "https://generativelanguage.googleapis.com",
                "credential": "synthetic-bad-key",
                "deployment": "gemini-2.5-flash",
                "quota_group": "p-bad",
                "credit_metered": False,
            },
            "gm-good": {
                "provider": "google_ai_studio",
                "endpoint": "https://generativelanguage.googleapis.com",
                "credential": "synthetic-good-key",
                "deployment": "gemini-2.5-flash",
                "quota_group": "p-good",
                "credit_metered": False,
            },
        }
        settings = _settings(backends, {"m": {"backends": {"gm-bad": 2.0, "gm-good": 1.0}}})
        _wire(monkeypatch, settings)
        respx.post("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions").mock(
            side_effect=[
                httpx.Response(401, json={"error": {"message": "bad key"}}),
                httpx.Response(200, json=_chat_ok("recovered")),
            ]
        )
        first = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key"},
            json={"model": "m", "input": "hi"},
        )
        # 401 is backend-local and terminal for the same request (no same-request key cycling).
        assert first.status_code == 502
        second = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key"},
            json={"model": "m", "input": "hi"},
        )
        assert second.status_code == 200
        assert second.json()["output"][0]["content"][0]["text"] == "recovered"
        assert "synthetic-bad-key" not in first.text
        assert "synthetic-good-key" not in second.text

    @respx.mock
    def test_429_fails_over_with_group_cooldown(self, monkeypatch):
        backends = {
            "gm-a": {
                "provider": "google_ai_studio",
                "endpoint": "https://generativelanguage.googleapis.com",
                "credential": "synthetic-a-key",
                "deployment": "gemini-2.5-flash",
                "quota_group": "pa",
                "credit_metered": False,
            },
            "gm-b": {
                "provider": "google_ai_studio",
                "endpoint": "https://generativelanguage.googleapis.com",
                "credential": "synthetic-b-key",
                "deployment": "gemini-2.5-flash",
                "quota_group": "pb",
                "credit_metered": False,
            },
        }
        settings = _settings(backends, {"m": {"backends": {"gm-a": 2.0, "gm-b": 1.0}}})
        _wire(monkeypatch, settings)
        route = respx.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        ).mock(
            side_effect=[
                httpx.Response(429, json={"error": {"message": "quota"}}),
                httpx.Response(200, json=_chat_ok("via-b")),
            ]
        )
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key"},
            json={"model": "m", "input": "hi"},
        )
        assert response.status_code == 200
        assert response.json()["output"][0]["content"][0]["text"] == "via-b"
        assert route.call_count == 2

    @respx.mock
    def test_500_never_retries_same_request(self, monkeypatch):
        backends = {
            "gm-a": {
                "provider": "google_ai_studio",
                "endpoint": "https://generativelanguage.googleapis.com",
                "credential": "synthetic-a-key",
                "deployment": "gemini-2.5-flash",
                "quota_group": "pa",
                "credit_metered": False,
            },
            "gm-b": {
                "provider": "google_ai_studio",
                "endpoint": "https://generativelanguage.googleapis.com",
                "credential": "synthetic-b-key",
                "deployment": "gemini-2.5-flash",
                "quota_group": "pb",
                "credit_metered": False,
            },
        }
        settings = _settings(backends, {"m": {"backends": {"gm-a": 2.0, "gm-b": 1.0}}})
        _wire(monkeypatch, settings)
        route = respx.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        ).mock(return_value=httpx.Response(500, json={"error": {"message": "overload"}}))
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key"},
            json={"model": "m", "input": "hi"},
        )
        assert response.status_code == 500
        # Ambiguous 5xx must not dispatch a second billable attempt.
        assert route.call_count == 1
        assert "synthetic-a-key" not in response.text

    @respx.mock
    def test_malformed_success_settles_without_retry(self, monkeypatch):
        backends = {
            "gm-a": {
                "provider": "google_ai_studio",
                "endpoint": "https://generativelanguage.googleapis.com",
                "credential": "synthetic-a-key",
                "deployment": "gemini-2.5-flash",
                "quota_group": "pa",
                "credit_metered": False,
            },
            "gm-b": {
                "provider": "google_ai_studio",
                "endpoint": "https://generativelanguage.googleapis.com",
                "credential": "synthetic-b-key",
                "deployment": "gemini-2.5-flash",
                "quota_group": "pb",
                "credit_metered": False,
            },
        }
        settings = _settings(backends, {"m": {"backends": {"gm-a": 2.0, "gm-b": 1.0}}})
        _wire(monkeypatch, settings)
        route = respx.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        ).mock(return_value=httpx.Response(200, json={"id": "bad", "choices": []}))
        response = client.post(
            "/openai/v1/responses",
            headers={"api-key": "client-key"},
            json={"model": "m", "input": "hi"},
        )
        assert response.status_code == 502
        assert route.call_count == 1
