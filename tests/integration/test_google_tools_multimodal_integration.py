"""HTTP round trips and feature admission through the actual router and stores."""

import asyncio
import io
import json
import time
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx
from openai.types.responses import ResponseFunctionToolCall
from starlette.requests import Request
from test_google_adapter_integration import _settings, _wire, client

from foundry_router.api.common import api_error, request_body
from foundry_router.config import Settings
from foundry_router.credit import InMemoryCreditStore
from foundry_router.health import InMemoryHealthStore
from foundry_router.ratelimit import InMemoryRateLimitStore
from foundry_router.routing import execute_with_single_failover

SCHEMA = {
    "type": "object",
    "properties": {"x": {"type": "integer"}},
    "required": ["x"],
    "additionalProperties": False,
}
TOOL = {"type": "function", "name": "local_fixture", "strict": True, "parameters": SCHEMA}
PROFILE = {
    "features": ["function_tools", "json_schema", "inline_images"],
    "combinations": [
        ["function_tools", "json_schema", "inline_images"],
        ["function_tools", "inline_images"],
    ],
    "continuation_policy": "unsigned",
    "image_input_tokens": 258,
    "image_token_pricing": True,
}
URL = "https://provider.example.test/v1beta/openai/chat/completions"
HEADERS = {"api-key": "client-key"}


def backend(profile=None, metered=False):
    return {
        "provider": "google_ai_studio",
        "endpoint": "https://provider.example.test",
        "credential": "PRIVATE_KEY",
        "deployment": "configured-model",
        "quota_group": "p",
        "credit_metered": metered,
        "google_features": profile or {},
    }


def provider(calls=None, text=None, usage=True):
    result = {
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text, "tool_calls": calls or []},
                "finish_reason": "tool_calls" if calls else "stop",
            }
        ]
    }
    if usage:
        result["usage"] = {"prompt_tokens": 40, "completion_tokens": 10}
    return result


def tool_call(arguments='{"x":1}'):
    return {
        "id": "call_fixture",
        "type": "function",
        "function": {"name": "local_fixture", "arguments": arguments},
    }


@respx.mock
def test_http_tool_round_trip_two_independently_authenticated_requests(monkeypatch):
    settings = _settings(
        {"g": backend(PROFILE)},
        {"m": {"backends": {"g": 1}}},
        quota_group_rate_limits_json='{"p":{"rpm":100,"tpm":100000}}',
    )
    _wire(monkeypatch, settings)
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(200, json=provider([tool_call()])),
            httpx.Response(200, json=provider(text="done")),
        ]
    )
    request = {"model": "m", "input": "synthetic", "tools": [TOOL]}
    first = client.post("/openai/v1/responses", headers=HEADERS, json=request)
    assert first.status_code == 200
    item = ResponseFunctionToolCall.model_validate(first.json()["output"][0]).model_dump(
        exclude_none=True
    )
    second_request = {
        **request,
        "input": [
            {"role": "user", "content": "synthetic"},
            item,
            {
                "type": "function_call_output",
                "call_id": item["call_id"],
                "output": "PRIVATE_RESULT",
            },
        ],
    }
    unauth = client.post("/openai/v1/responses", json=second_request)
    assert unauth.status_code == 401
    second = client.post("/openai/v1/responses", headers=HEADERS, json=second_request)
    assert second.status_code == 200
    assert route.call_count == 2
    assert json.loads(route.calls[1].request.content)["messages"][-1]["role"] == "tool"
    assert (
        route.calls[0].request.headers["x-request-id"]
        != route.calls[1].request.headers["x-request-id"]
    )
    admin = client.get("/admin/status", headers={"x-admin-key": "admin-key"})
    assert admin.json()["backends"]["g"]["live"]["rate_limit"]["rpm_used_60s"] == 2
    assert "PRIVATE_KEY" not in first.text + second.text + admin.text
    assert "PRIVATE_RESULT" not in second.text + admin.text


@respx.mock
@pytest.mark.parametrize(
    "patch",
    [
        {"tools": [{"type": "web_search"}]},
        {"input": [{"type": "function_call_output", "call_id": "bad", "output": "PRIVATE_RESULT"}]},
        {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_image", "image_url": "https://secret.test/a"}],
                }
            ]
        },
        {
            "input": [
                {"role": "user", "content": [{"type": "input_file", "file_data": "PRIVATE_MEDIA"}]}
            ]
        },
    ],
)
def test_invalid_features_leave_quota_unreserved(monkeypatch, patch):
    settings = _settings(
        {"g": backend(PROFILE)},
        {"m": {"backends": {"g": 1}}},
        quota_group_rate_limits_json='{"p":{"rpm":100,"tpm":100000}}',
    )
    _wire(monkeypatch, settings)
    response = client.post(
        "/openai/v1/responses",
        headers=HEADERS,
        json={"model": "m", "input": "x", "tools": [TOOL], **patch},
    )
    assert response.status_code == 422
    assert not respx.calls
    assert "PRIVATE" not in response.text


@respx.mock
def test_capability_failover_rechecks_profile(monkeypatch):
    backends = {
        "a": backend(PROFILE),
        "incapable": backend(),
        "c": {**backend(PROFILE), "quota_group": "q"},
    }
    settings = _settings(backends, {"m": {"backends": {"a": 3, "incapable": 2, "c": 1}}})
    _wire(monkeypatch, settings)
    route = respx.post(URL).mock(
        side_effect=[
            httpx.Response(429, json={"error": {}}),
            httpx.Response(200, json=provider([tool_call()])),
        ]
    )
    response = client.post(
        "/openai/v1/responses", headers=HEADERS, json={"model": "m", "input": "x", "tools": [TOOL]}
    )
    assert response.status_code == 200
    assert route.call_count == 2
    assert all("tools" in json.loads(entry.request.content) for entry in route.calls)


@respx.mock
@pytest.mark.parametrize("usage", [True, False])
def test_invalid_generated_schema_is_billable_without_retry(monkeypatch, usage):
    settings = _settings(
        {"g": backend({"features": ["json_schema"]}, metered=True)},
        {"m": {"backends": {"g": 1}}},
        pricing_json='{"m":{"input_per_million":10,"output_per_million":30}}',
        backend_cycle_start_day_json='{"g":1}',
        backend_cycle_allowance_usd_json='{"g":200}',
        backend_initial_estimated_remaining_usd_json='{"g":200}',
    )
    _wire(monkeypatch, settings)
    route = respx.post(URL).mock(
        return_value=httpx.Response(200, json=provider(text='{"x":"PRIVATE_OUTPUT"}', usage=usage))
    )
    response = client.post(
        "/openai/v1/responses",
        headers=HEADERS,
        json={
            "model": "m",
            "input": "x",
            "max_output_tokens": 100,
            "text": {
                "format": {"type": "json_schema", "name": "s", "strict": True, "schema": SCHEMA}
            },
        },
    )
    assert response.status_code == 502
    assert route.call_count == 1
    assert "PRIVATE_OUTPUT" not in response.text
    status = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    assert status["estimated_remaining_usd"] < 200
    assert status["reserved_inflight_usd"] == 0


async def test_expired_intake_returns_before_reservation_or_dispatch():
    settings = Settings(
        backends_json=json.dumps({"g": backend(PROFILE)}),
        models_json='{"m":{"backends":{"g":1}}}',
        client_api_keys_json='["c"]',
        admin_api_keys_json='["a"]',
    )
    credit = InMemoryCreditStore()
    credit.sync_from_settings = AsyncMock()
    dispatch = AsyncMock()
    response = await execute_with_single_failover(
        settings,
        "m",
        operation="responses",
        body={"model": "m", "input": "x", "tools": [TOOL]},
        request_id="r",
        execute_backend=dispatch,
        health_store=InMemoryHealthStore(),
        credit_store=credit,
        rate_limit_store=InMemoryRateLimitStore(),
        metrics_store=MagicMock(observe_request=AsyncMock()),
        logger=MagicMock(),
        api_error=api_error,
        finalize_non_streaming_credit=AsyncMock(),
        intake_deadline_monotonic=time.monotonic() - 1,
    )
    assert response.status_code == 408
    credit.sync_from_settings.assert_not_awaited()
    dispatch.assert_not_awaited()


@respx.mock
def test_combined_image_tool_mapping_and_media_quota(monkeypatch):
    import base64

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (8, 8)).save(out, format="PNG")
    uri = "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()
    settings = _settings(
        {"g": backend(PROFILE)},
        {"m": {"backends": {"g": 1}}},
        quota_group_rate_limits_json='{"p":{"rpm":100,"tpm":200}}',
    )
    _wire(monkeypatch, settings)
    response = client.post(
        "/openai/v1/responses",
        headers=HEADERS,
        json={
            "model": "m",
            "tools": [TOOL],
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "before"},
                        {"type": "input_image", "image_url": uri},
                        {"type": "input_text", "text": "after"},
                    ],
                }
            ],
        },
    )
    assert response.status_code == 429
    assert not respx.calls


@respx.mock
@pytest.mark.parametrize("kind", ["jpeg", "webp"])
@pytest.mark.parametrize("usage", [True, False])
def test_new_image_formats_billable_schema_failure_no_retry(monkeypatch, kind, usage):
    import base64

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (8, 8)).save(
        out, format=kind, **({"lossless": True} if kind == "webp" else {})
    )
    uri = f"data:image/{kind};base64," + base64.b64encode(out.getvalue()).decode()
    configured = {
        **PROFILE,
        "image_formats": [kind],
        "combinations": [["inline_images", "json_schema"]],
    }
    settings = _settings(
        {"g": backend(configured, metered=True)},
        {"m": {"backends": {"g": 1}}},
        pricing_json='{"m":{"input_per_million":10,"output_per_million":30}}',
        backend_cycle_start_day_json='{"g":1}',
        backend_cycle_allowance_usd_json='{"g":200}',
        backend_initial_estimated_remaining_usd_json='{"g":200}',
    )
    _wire(monkeypatch, settings)
    route = respx.post(URL).mock(
        return_value=httpx.Response(200, json=provider(text='{"x":"PRIVATE_OUTPUT"}', usage=usage))
    )
    response = client.post(
        "/openai/v1/responses",
        headers=HEADERS,
        json={
            "model": "m",
            "input": [{"role": "user", "content": [{"type": "input_image", "image_url": uri}]}],
            "text": {
                "format": {"type": "json_schema", "name": "s", "strict": True, "schema": SCHEMA}
            },
        },
    )
    assert response.status_code == 502
    assert route.call_count == 1
    assert (
        json.loads(route.calls[0].request.content)["messages"][0]["content"][0]["image_url"]["url"]
        == uri
    )
    status = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    assert status["reserved_inflight_usd"] == 0
    assert status["estimated_remaining_usd"] < 200
    assert "PRIVATE_OUTPUT" not in response.text


async def test_admission_storage_latency_expires_before_reservation():
    settings = _settings({"g": backend(PROFILE)}, {"m": {"backends": {"g": 1}}})
    health = InMemoryHealthStore()

    async def delayed(_ids):
        await asyncio.sleep(1)

    health.snapshot_backend_health = delayed
    credit = InMemoryCreditStore()
    credit.try_assign_reservation = AsyncMock()
    dispatch = AsyncMock()
    response = await execute_with_single_failover(
        settings,
        "m",
        operation="responses",
        body={"model": "m", "input": "x"},
        request_id="delayed",
        execute_backend=dispatch,
        health_store=health,
        credit_store=credit,
        metrics_store=MagicMock(observe_request=AsyncMock()),
        logger=MagicMock(),
        api_error=api_error,
        finalize_non_streaming_credit=AsyncMock(),
        intake_deadline_monotonic=time.monotonic() + 0.01,
    )
    assert response.status_code == 408
    dispatch.assert_not_awaited()
    credit.try_assign_reservation.assert_not_awaited()


async def test_body_read_intake_timeout():
    async def receive():
        await asyncio.sleep(1)
        return {"type": "http.request", "body": b"{}", "more_body": False}

    request = Request(
        {"type": "http", "headers": [(b"content-type", b"application/json")]}, receive
    )
    response = await request_body(
        request, "responses", max_body_bytes=2048, deadline_monotonic=time.monotonic() + 0.01
    )
    assert response.status_code == 408


@respx.mock
@pytest.mark.parametrize("bad_input", [None, 123])
def test_malformed_input_shape_returns_controlled_error_not_500(monkeypatch, bad_input):
    settings = _settings({"g": backend(PROFILE)}, {"m": {"backends": {"g": 1}}})
    _wire(monkeypatch, settings)
    response = client.post(
        "/openai/v1/responses",
        headers=HEADERS,
        json={"model": "m", "input": bad_input},
    )
    assert response.status_code == 422
    assert not respx.calls


@respx.mock
def test_duplicate_outer_schema_keys_rejected_before_egress(monkeypatch):
    settings = _settings({"g": backend(PROFILE)}, {"m": {"backends": {"g": 1}}})
    _wire(monkeypatch, settings)
    response = client.post(
        "/openai/v1/responses",
        headers={**HEADERS, "content-type": "application/json"},
        content='{"model":"m","input":"x","tools":[{"type":"function","name":"f","strict":true,"parameters":{"type":"object","properties":{},"required":[],"additionalProperties":true,"additionalProperties":false}}]}',
    )
    assert response.status_code == 400
    assert not respx.calls


@respx.mock
def test_invalid_first_stream_chunk_retains_reservation_estimate(monkeypatch):
    settings = _settings(
        {
            "g": backend(
                {"features": ["function_tools"], "continuation_policy": "unsigned"}, metered=True
            )
        },
        {"m": {"backends": {"g": 1}}},
        pricing_json='{"m":{"input_per_million":10,"output_per_million":30}}',
        backend_cycle_start_day_json='{"g":1}',
        backend_cycle_allowance_usd_json='{"g":200}',
        backend_initial_estimated_remaining_usd_json='{"g":200}',
    )
    _wire(monkeypatch, settings)
    payload = {
        "choices": [
            {
                "index": 0,
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "c",
                            "function": {"name": "local_fixture", "arguments": []},
                        }
                    ]
                },
            }
        ],
        "usage": {"prompt_tokens": 17, "completion_tokens": 8},
    }
    route = respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            content=f"data: {json.dumps(payload)}\n\n".encode(),
            headers={"content-type": "text/event-stream"},
        )
    )
    body = {"model": "m", "input": "x", "tools": [TOOL], "stream": True}
    from foundry_router.credit import estimate_request_cost

    estimate = estimate_request_cost(
        model="m", operation="responses", body=body, pricing=settings.pricing, settings=settings
    )
    response = client.post(
        "/openai/v1/responses",
        headers=HEADERS,
        json=body,
    )
    assert response.status_code == 502
    assert route.call_count == 1
    status = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    assert status["estimated_remaining_usd"] == pytest.approx(200 - estimate.estimated_cost_usd)
    assert status["reserved_inflight_usd"] == 0
