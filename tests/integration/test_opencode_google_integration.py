"""OpenCode native routing, thought-inclusive settlement and single-shot errors."""

import json

import httpx
import pytest
import respx
from test_google_adapter_integration import (  # noqa: F401 -- fixture registration
    _clean,
    _settings,
    _wire,
    client,
)

from foundry_router.backends import AllowedBackendClient, SecurityError

pytestmark = pytest.mark.usefixtures("_clean")
URL = "https://opencode.example.test/inference/v1/models/physical-model:generateContent"
STREAM_URL = (
    "https://opencode.example.test/inference/v1/models/physical-model:streamGenerateContent?alt=sse"
)
BACKEND = {
    "provider": "opencode_google",
    "api_surface": "native",
    "endpoint": "https://opencode.example.test/inference/v1",
    "credential": "synthetic-provider-key",
    "deployment": "physical-model",
    "credit_group": "account",
    "google_features": {"native_thinking_level": "low", "thought_token_pricing": True},
}


def settings(*, second=False):
    backends = {"a": BACKEND}
    if second:
        backends["b"] = {**BACKEND, "endpoint": "https://second.example.test/root"}
    return _settings(
        backends,
        {"logical": {"backends": dict.fromkeys(backends, 1)}},
        pricing_json='{"logical":{"input_per_million":4,"output_per_million":20}}',
        backend_cycle_start_day_json='{"account":1}',
        backend_cycle_allowance_usd_json='{"account":100}',
        backend_initial_estimated_remaining_usd_json='{"account":100}',
        model_aliases_json='{"alias":"logical"}',
        retry_attempts=3,
    )


def envelope():
    return {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [{"text": "synthetic answer", "thoughtSignature": "opaque"}],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 5,
            "thoughtsTokenCount": 3,
            "totalTokenCount": 18,
        },
    }


def live():
    return client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()[
        "credit_groups"
    ]["account"]["live"]


@respx.mock
@pytest.mark.parametrize("stream", [False, True])
def test_native_alias_route_bearer_thought_settlement(monkeypatch, stream):
    _wire(monkeypatch, settings())
    upstream = (
        httpx.Response(200, json=envelope())
        if not stream
        else httpx.Response(
            200,
            content=f"data: {json.dumps(envelope())}\n\n".encode(),
            headers={"content-type": "text/event-stream"},
        )
    )
    route = respx.post(STREAM_URL if stream else URL).mock(return_value=upstream)
    response = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key", "x-goog-api-key": "caller-key"},
        json={"model": "alias", "input": "hello", "max_output_tokens": 128, "stream": stream},
    )
    assert response.status_code == 200
    assert route.call_count == 1
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer synthetic-provider-key"
    assert "x-goog-api-key" not in request.headers and "api-key" not in request.headers
    body = json.loads(request.content)
    assert "model" not in body and "stream" not in body
    assert body["contents"] == [{"role": "user", "parts": [{"text": "hello"}]}]
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}
    assert body["generationConfig"]["maxOutputTokens"] == 128
    if stream:
        assert '"type":"response.completed"' in response.text
        assert '"output_tokens":8' in response.text
    else:
        assert response.json()["usage"] == {
            "input_tokens": 10,
            "output_tokens": 8,
            "total_tokens": 18,
        }
    assert "opaque" not in response.text
    account = live()
    assert account["reserved_inflight_usd"] == 0
    assert 100 - account["estimated_remaining_usd"] == pytest.approx(0.0002)
    assert "synthetic-provider-key" not in response.text


@respx.mock
@pytest.mark.parametrize(
    "field,value",
    [
        ("tools", [{"type": "function", "name": "f"}]),
        ("contents", []),
        ("previous_response_id", "r"),
        ("generationConfig", {}),
    ],
)
def test_unsupported_requests_fail_before_admission(monkeypatch, field, value):
    _wire(monkeypatch, settings())
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=envelope()))
    response = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "x", field: value},
    )
    assert response.status_code == 422 and route.call_count == 0
    assert live()["estimated_remaining_usd"] == 100
    assert live()["reserved_inflight_usd"] == 0


@respx.mock
@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
@pytest.mark.parametrize("stream", [False, True])
def test_native_errors_are_sanitized_single_shot(monkeypatch, status, stream):
    _wire(monkeypatch, settings())
    route = respx.post(STREAM_URL if stream else URL).mock(
        return_value=httpx.Response(status, json={"error": {"message": "PRIVATE_PROVIDER_BODY"}})
    )
    response = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "x", "max_output_tokens": 128, "stream": stream},
    )
    assert response.status_code >= 400
    assert route.call_count == 1
    assert "PRIVATE_PROVIDER_BODY" not in response.text
    account = live()
    assert account["reserved_inflight_usd"] == 0
    if status in {401, 403, 429}:
        assert account["estimated_remaining_usd"] == 100
    else:
        assert account["estimated_remaining_usd"] < 100


@respx.mock
def test_preoutput_429_admits_second_backend(monkeypatch):
    _wire(monkeypatch, settings(second=True))
    first = respx.post(URL).mock(return_value=httpx.Response(429, headers={"Retry-After": "60"}))
    second = respx.post(
        "https://second.example.test/root/models/physical-model:generateContent"
    ).mock(return_value=httpx.Response(200, json=envelope()))
    response = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "x"},
    )
    assert response.status_code == 200 and first.call_count == second.call_count == 1
    assert live()["reserved_inflight_usd"] == 0


@respx.mock
def test_partial_stream_never_fails_over(monkeypatch):
    _wire(monkeypatch, settings(second=True))
    partial = {"candidates": [{"content": {"parts": [{"text": "partial"}]}}]}
    first = respx.post(STREAM_URL).mock(
        return_value=httpx.Response(
            200,
            content=f"data: {json.dumps(partial)}\n\n".encode(),
            headers={"content-type": "text/event-stream"},
        )
    )
    second = respx.post(
        "https://second.example.test/root/models/physical-model:streamGenerateContent?alt=sse"
    ).mock(return_value=httpx.Response(200))
    response = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "logical", "input": "x", "stream": True},
    )
    assert first.call_count == 1 and second.call_count == 0
    assert "response.completed" not in response.text
    assert live()["reserved_inflight_usd"] == 0
    assert live()["estimated_remaining_usd"] < 100


async def test_transport_confines_operations_and_redirects():
    backend = AllowedBackendClient(settings=settings())
    try:
        with pytest.raises(ValueError, match="only Responses"):
            backend._backend_url("a", "embeddings")
        with pytest.raises(SecurityError):
            backend._validate_url("https://opencode.example.test/escape", "a")
        with pytest.raises(SecurityError):
            await backend.request_backend("a", "responses", follow_redirects=True)
    finally:
        await backend.aclose()
