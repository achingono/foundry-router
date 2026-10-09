"""End-to-end Zen pass-through and OpenRouter translation behavior."""

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
from tests.integration.test_google_adapter_integration import _wire


@pytest.fixture(autouse=True)
def reset():
    yield
    asyncio.run(_reset_backend_health_state())
    asyncio.run(_reset_credit_state())
    asyncio.run(_reset_metrics_state())
    asyncio.run(_reset_rate_limit_state())


def zen_settings(*, second=False, metered=False):
    ids = ["zen_a", "zen_b"] if second else ["zen_a"]
    backends = {
        key: {
            "provider": "opencode_zen",
            "endpoint": "https://opencode.ai/zen/v1",
            "credential": f"server-{key}",
            "deployment": "gpt-5.4",
            "credit_metered": metered,
            # Distinct quota groups: a 429 cools its own group, so failover
            # can admit the second backend fresh.
            "quota_group": f"{key}-project",
        }
        for key in ids
    }
    quota_limits = {f"{key}-project": {"rpm": 20, "tpm": 10000} for key in ids}
    return Settings(
        backends_json=json.dumps(backends),
        models_json=json.dumps({"logical": {"backends": dict.fromkeys(ids, 1)}}),
        model_aliases_json='{"alias":"logical"}',
        client_api_keys_json='["client-key"]',
        admin_api_keys_json='["admin-key"]',
        pricing_json='{"logical":{"input_per_million":1.0,"output_per_million":2.0}}'
        if metered
        else "{}",
        backend_cycle_start_day_json=json.dumps(dict.fromkeys(ids, 1)) if metered else "{}",
        backend_cycle_allowance_usd_json=json.dumps(dict.fromkeys(ids, 1000))
        if metered
        else "{}",
        backend_initial_estimated_remaining_usd_json=json.dumps(dict.fromkeys(ids, 1000))
        if metered
        else "{}",
        retry_attempts=2,
        quota_group_rate_limits_json=json.dumps(quota_limits),
    )


def openrouter_settings(*, operations=None, metered=False):
    backends = {
        "or_a": {
            "provider": "openrouter",
            "endpoint": "https://openrouter.ai/api/v1",
            "credential": "server-or",
            "deployment": "organization/model",
            "credit_metered": metered,
            "quota_group": "or-project",
            "supported_operations": operations or ["responses"],
        }
    }
    return Settings(
        backends_json=json.dumps(backends),
        models_json=json.dumps({"logical": {"backends": {"or_a": 1}}}),
        client_api_keys_json='["client-key"]',
        admin_api_keys_json='["admin-key"]',
        pricing_json="{}",
        backend_cycle_start_day_json="{}",
        retry_attempts=2,
        quota_group_rate_limits_json='{"or-project": {"rpm": 20, "tpm": 10000}}',
    )


def zen_ok() -> dict:
    return {
        "id": "resp_zen_1",
        "object": "response",
        "created_at": 1700000000,
        "model": "gpt-5.4",
        "status": "completed",
        "output": [],
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }


def chat_ok() -> dict:
    return {
        "choices": [
            {"message": {"role": "assistant", "content": "answer"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
    }


@respx.mock
@pytest.mark.parametrize("stream", [False, True])
def test_zen_alias_responses_bearer_and_usage(monkeypatch, stream):
    _wire(monkeypatch, zen_settings())
    if stream:
        payload = (
            b'data: {"type":"response.created"}\n\n'
            b'data: {"type":"response.completed","response":{"usage":{"input_tokens":10,"output_tokens":5,"total_tokens":15}}}\n\n'
        )
        upstream = httpx.Response(
            200, content=payload, headers={"content-type": "text/event-stream"}
        )
    else:
        upstream = httpx.Response(200, json=zen_ok())
    route = respx.post("https://opencode.ai/zen/v1/responses").mock(return_value=upstream)
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key", "authorization": "Bearer caller-secret"},
        json={"model": "alias", "input": "synthetic", "stream": stream},
    )
    assert response.status_code == 200
    assert route.call_count == 1
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer server-zen_a"
    assert "api-key" not in request.headers
    body = json.loads(request.content)
    assert body["model"] == "gpt-5.4" and body["input"] == "synthetic"
    assert "max_completion_tokens" not in body and "stream_options" not in body
    if stream:
        assert response.text == payload.decode()
    else:
        assert response.json()["usage"]["total_tokens"] == 15
    status = TestClient(app).get("/admin/status", headers={"x-admin-key": "admin-key"}).json()
    assert "server-zen_a" not in json.dumps(status)


@respx.mock
def test_zen_foreign_fields_rejected_before_egress(monkeypatch):
    _wire(monkeypatch, zen_settings())
    route = respx.post("https://opencode.ai/zen/v1/responses").mock(
        return_value=httpx.Response(200, json=zen_ok())
    )
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={
            "model": "logical",
            "input": "synthetic",
            "messages": [{"role": "user", "content": "foreign"}],
        },
    )
    assert response.status_code == 422
    assert route.call_count == 0


@respx.mock
def test_zen_ambiguous_5xx_never_retries_upstream(monkeypatch):
    _wire(monkeypatch, zen_settings())
    route = respx.post("https://opencode.ai/zen/v1/responses").mock(
        return_value=httpx.Response(500, content=b"boom")
    )
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "synthetic"},
    )
    assert response.status_code == 500
    assert route.call_count == 1


@respx.mock
def test_zen_429_failover_counts_both_quota_attempts(monkeypatch):
    _wire(monkeypatch, zen_settings(second=True))
    limited = respx.post("https://opencode.ai/zen/v1/responses").mock(
        side_effect=[
            httpx.Response(429, content=b"slow"),
            httpx.Response(200, json=zen_ok()),
        ]
    )
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "synthetic"},
    )
    assert response.status_code == 200
    assert limited.call_count == 2
    assert [call.request.headers["authorization"] for call in limited.calls] == [
        "Bearer server-zen_a",
        "Bearer server-zen_b",
    ]


@respx.mock
@pytest.mark.parametrize("stream", [False, True])
def test_openrouter_translated_responses_and_bearer(monkeypatch, stream):
    _wire(monkeypatch, openrouter_settings())
    if stream:
        payload = b'data: {"choices":[{"delta":{"content":"answer"},"finish_reason":"stop"}]}\n\ndata: {"choices":[],"usage":{"prompt_tokens":4,"completion_tokens":2}}\n\ndata: [DONE]\n\n'
        upstream = httpx.Response(
            200, content=payload, headers={"content-type": "text/event-stream"}
        )
    else:
        upstream = httpx.Response(200, json=chat_ok())
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=upstream
    )
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "synthetic", "stream": stream},
    )
    assert response.status_code == 200
    assert route.call_count == 1
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer server-or"
    body = json.loads(request.content)
    assert body["model"] == "organization/model"
    assert body["max_completion_tokens"] > 0
    if stream:
        assert body["stream_options"] == {"include_usage": True}
        assert '"response.completed"' in response.text
    else:
        assert response.json()["usage"]["total_tokens"] == 6


@respx.mock
def test_openrouter_routing_extras_rejected_before_egress(monkeypatch):
    _wire(monkeypatch, openrouter_settings())
    route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=chat_ok())
    )
    response = TestClient(app).post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "synthetic", "provider": {"order": ["x"]}},
    )
    assert response.status_code == 422
    assert route.call_count == 0


@respx.mock
def test_mixed_pool_embeddings_skips_zen_backend(monkeypatch):
    backends = {
        "zen_a": {
            "provider": "opencode_zen",
            "endpoint": "https://opencode.ai/zen/v1",
            "credential": "server-zen",
            "deployment": "gpt-5.4",
            "credit_metered": False,
            "quota_group": "zen-project",
        },
        "or_e": {
            "provider": "openrouter",
            "endpoint": "https://openrouter.ai/api/v1",
            "credential": "server-or",
            "deployment": "organization/embed",
            "credit_metered": False,
            "quota_group": "or-project",
            "supported_operations": ["embeddings"],
        },
    }
    settings = Settings(
        backends_json=json.dumps(backends),
        models_json=json.dumps({"logical-embed": {"backends": {"zen_a": 1, "or_e": 1}}}),
        client_api_keys_json='["client-key"]',
        admin_api_keys_json='["admin-key"]',
        pricing_json="{}",
        backend_cycle_start_day_json="{}",
        retry_attempts=2,
        quota_group_rate_limits_json=json.dumps(
            {"zen-project": {"rpm": 20, "tpm": 10000}, "or-project": {"rpm": 20, "tpm": 10000}}
        ),
    )
    _wire(monkeypatch, settings)
    zen_route = respx.post("https://opencode.ai/zen/v1/responses").mock(
        return_value=httpx.Response(200, json=zen_ok())
    )
    or_route = respx.post("https://openrouter.ai/api/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.5]}],
                "model": "organization/embed",
                "usage": {"prompt_tokens": 3, "total_tokens": 3},
            },
        )
    )
    response = TestClient(app).post(
        "/openai/v1/embeddings",
        headers={"api-key": "client-key"},
        json={"model": "logical-embed", "input": "synthetic"},
    )
    assert response.status_code == 200
    assert zen_route.call_count == 0
    assert or_route.call_count == 1
    assert response.json()["data"][0]["embedding"] == [0.5]
