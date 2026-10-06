"""Native fixed transport and conservative accounting through the public HTTP API."""

import json

import httpx
import pytest
import respx
from test_google_adapter_integration import _settings, _wire, client

from foundry_router.backends import AllowedBackendClient
from foundry_router.credit import estimate_request_cost

URL = "https://native.example.test/v1beta/models/configured-model:generateContent"
STREAM_URL = (
    "https://native.example.test/v1beta/models/configured-model:streamGenerateContent?alt=sse"
)
PROFILE = {"native_thinking_disabled": True, "features": ["json_schema"]}
BACKEND = {
    "provider": "google_ai_studio",
    "api_surface": "native",
    "endpoint": "https://native.example.test",
    "credential": "PRIVATE_NATIVE_KEY",
    "deployment": "configured-model",
    "quota_group": "native-project",
    "google_features": PROFILE,
}
SCHEMA = {
    "type": "object",
    "properties": {"x": {"type": "integer"}},
    "required": ["x"],
    "additionalProperties": False,
}


def provider(text, *, thoughts=0, usage=True):
    result = {
        "candidates": [
            {
                "index": 0,
                "content": {"role": "model", "parts": [{"text": text}]},
                "finishReason": "STOP",
            }
        ]
    }
    if usage:
        result["usageMetadata"] = {
            "promptTokenCount": 40,
            "candidatesTokenCount": 10,
            "thoughtsTokenCount": thoughts,
            "totalTokenCount": 50 + thoughts,
        }
    return result


@respx.mock
def test_native_fixed_transport_headers_model_body_and_shared_quota(monkeypatch):
    settings = _settings(
        {"g": {**BACKEND, "credit_metered": False}},
        {"m": {"backends": {"g": 1}}},
        quota_group_rate_limits_json='{"native-project":{"rpm":100,"tpm":100000}}',
    )
    _wire(monkeypatch, settings)
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=provider("answer")))
    response = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "m", "input": "question"},
    )
    assert response.status_code == 200
    request = route.calls[0].request
    assert request.headers["x-goog-api-key"] == "PRIVATE_NATIVE_KEY"
    assert "authorization" not in request.headers and "api-key" not in request.headers
    body = json.loads(request.content)
    assert "model" not in body and body["contents"][0]["parts"] == [{"text": "question"}]
    assert response.json()["usage"] == {"input_tokens": 40, "output_tokens": 10, "total_tokens": 50}
    admin = client.get("/admin/status", headers={"x-admin-key": "admin-key"})
    assert admin.json()["backends"]["g"]["live"]["rate_limit"]["rpm_used_60s"] == 1
    assert "PRIVATE_NATIVE_KEY" not in response.text + admin.text


@respx.mock
@pytest.mark.parametrize("thoughts,usage", [(0, True), (2, True), (0, False)])
def test_native_billable_invalid_schema_or_thoughts_retains_known_usage(
    monkeypatch, thoughts, usage
):
    settings = _settings(
        {"g": BACKEND},
        {"m": {"backends": {"g": 1}}},
        pricing_json='{"m":{"input_per_million":10,"output_per_million":30}}',
        backend_cycle_start_day_json='{"g":1}',
        backend_cycle_allowance_usd_json='{"g":200}',
        backend_initial_estimated_remaining_usd_json='{"g":200}',
    )
    _wire(monkeypatch, settings)
    route = respx.post(URL).mock(
        return_value=httpx.Response(
            200, json=provider('{"x":"PRIVATE_OUTPUT"}', thoughts=thoughts, usage=usage)
        )
    )
    response = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={
            "model": "m",
            "input": "x",
            "max_output_tokens": 100,
            "text": {
                "format": {"type": "json_schema", "name": "s", "strict": True, "schema": SCHEMA}
            },
        },
    )
    assert response.status_code == 502 and route.call_count == 1
    status = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    assert status["reserved_inflight_usd"] == 0
    charged = 200 - status["estimated_remaining_usd"]
    if usage:
        assert charged == pytest.approx((40 * 10 + (10 + thoughts) * 30) / 1000000)
    else:
        assert charged > 0
    assert "PRIVATE_OUTPUT" not in response.text


@respx.mock
def test_native_http_stream_uses_native_path_and_finishes_at_eof(monkeypatch):
    settings = _settings({"g": {**BACKEND, "credit_metered": False}}, {"m": {"backends": {"g": 1}}})
    _wire(monkeypatch, settings)
    route = respx.post(STREAM_URL).mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=f"data: {json.dumps(provider('streamed'))}\n\n".encode(),
        )
    )
    response = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={"model": "m", "input": "x", "stream": True},
    )
    assert response.status_code == 200 and route.call_count == 1
    assert '"type":"response.completed"' in response.text
    assert "[DONE]" not in response.text


def test_native_url_mapping_has_no_caller_override(monkeypatch):
    settings = _settings({"g": {**BACKEND, "credit_metered": False}}, {"m": {"backends": {"g": 1}}})
    monkeypatch.setattr("foundry_router.backends.load_settings", lambda: settings)
    backend_client = AllowedBackendClient()
    assert str(backend_client._backend_url("g", "responses")) == URL
    assert str(backend_client._backend_url("g", "responses", streaming=True)) == STREAM_URL
    with pytest.raises(ValueError):
        backend_client._backend_url("g", "../embeddings")


@respx.mock
@pytest.mark.parametrize("fault", ["invalid_total", "decreasing", "duplicate_json"])
def test_native_late_invalid_usage_charges_full_reservation(monkeypatch, fault):
    settings = _settings(
        {"g": BACKEND},
        {"m": {"backends": {"g": 1}}},
        pricing_json='{"m":{"input_per_million":10,"output_per_million":30}}',
        backend_cycle_start_day_json='{"g":1}',
        backend_cycle_allowance_usd_json='{"g":200}',
        backend_initial_estimated_remaining_usd_json='{"g":200}',
    )
    _wire(monkeypatch, settings)
    late = {
        "usageMetadata": {
            "promptTokenCount": 39 if fault == "decreasing" else 40,
            "candidatesTokenCount": 10,
            "totalTokenCount": 99,
        }
    }
    if fault == "decreasing":
        late["usageMetadata"].pop("totalTokenCount")
    final = (
        json.dumps(late)
        if fault != "duplicate_json"
        else '{"usageMetadata":{"promptTokenCount":40,"candidatesTokenCount":10,"candidatesTokenCount":1}}'
    )
    respx.post(STREAM_URL).mock(
        return_value=httpx.Response(
            200,
            content=f"data: {json.dumps(provider('x'))}\n\ndata: {final}\n\n".encode(),
            headers={"content-type": "text/event-stream"},
        )
    )
    body = {"model": "m", "input": "x", "stream": True, "max_output_tokens": 100}
    estimate = estimate_request_cost(
        model="m", body=body, pricing=settings.pricing, operation="responses"
    )
    result = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=body)
    assert result.status_code == 502 and "response.completed" not in result.text
    status = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    assert 200 - status["estimated_remaining_usd"] == pytest.approx(estimate.estimated_cost_usd)
    assert status["reserved_inflight_usd"] == 0


@respx.mock
def test_native_duplicate_nonstream_arguments_rejected_without_retry(monkeypatch):
    settings = _settings(
        {
            "g": {
                **BACKEND,
                "credit_metered": False,
                "google_features": {
                    "native_thinking_disabled": True,
                    "features": ["function_tools"],
                    "continuation_policy": "unsigned",
                },
            }
        },
        {"m": {"backends": {"g": 1}}},
    )
    _wire(monkeypatch, settings)
    raw = b'{"candidates":[{"content":{"role":"model","parts":[{"functionCall":{"id":"c1","name":"f","args":{"x":1,"x":2}}}]},"finishReason":"STOP"}],"usageMetadata":{"promptTokenCount":40,"candidatesTokenCount":10}}'
    route = respx.post(URL).mock(return_value=httpx.Response(200, content=raw))
    result = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json={
            "model": "m",
            "input": "x",
            "tools": [{"type": "function", "name": "f", "strict": True, "parameters": SCHEMA}],
        },
    )
    assert result.status_code == 502 and route.call_count == 1
