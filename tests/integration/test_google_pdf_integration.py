"""Public PDF admission, native forwarding, usage and independent billing."""

import base64
import hashlib
import json
import sys

import httpx
import pytest
import respx
from openai import omit
from openai._models import construct_type
from openai.lib.streaming.responses._responses import ResponseStreamState
from openai.types.responses import ResponseStreamEvent
from test_google_adapter_integration import _settings, _wire, client

from foundry_router.api.google_pdf import PreparedGoogleMedia, PreparedPdf
from foundry_router.credit import estimate_request_cost
from tests.unit.google_pdf_fixtures import document

URL = "https://pdf.example.test/v1beta/models/configured:generateContent"
PROFILE = {
    "features": ["inline_pdfs"],
    "native_thinking_disabled": True,
    "pdf_input_tokens_per_page": 258,
    "pdf_native_text_tokens_per_page": 65536,
    "pdf_token_pricing": True,
}
BACKEND = {
    "provider": "google_ai_studio",
    "api_surface": "native",
    "endpoint": "https://pdf.example.test",
    "credential": "PRIVATE_KEY",
    "deployment": "configured",
    "google_features": PROFILE,
}
RAW = b"synthetic parser boundary fixture"
PART = {
    "type": "input_file",
    "filename": "fixture.pdf",
    "file_data": "data:application/pdf;base64," + base64.b64encode(RAW).decode(),
}


def prepared(body):
    return PreparedGoogleMedia(
        (
            PreparedPdf(
                (0, 1),
                hashlib.sha256(body["input"][0]["content"][1]["file_data"].encode()).hexdigest(),
                len(RAW),
                1,
            ),
        )
    )


def body():
    return {
        "model": "m",
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "before"},
                    dict(PART),
                    {"type": "input_text", "text": "after"},
                ],
            }
        ],
        "max_output_tokens": 10,
    }


def wire(monkeypatch, *, metered=False, usage=True):
    settings = _settings(
        {"g": {**BACKEND, "credit_metered": metered}},
        {"m": {"backends": {"g": 1}}},
        pricing_json='{"m":{"input_per_million":10,"output_per_million":30}}',
        backend_cycle_start_day_json='{"g":1}',
        backend_cycle_allowance_usd_json='{"g":200}',
        backend_initial_estimated_remaining_usd_json='{"g":200}',
        quota_group_rate_limits_json='{"g":{"rpm":100,"tpm":1000000}}',
    )
    _wire(monkeypatch, settings)

    async def prepare(self, request, *, deadline):
        _ = self, deadline
        return prepared(request)

    monkeypatch.setattr("foundry_router.api.google_pdf.PdfPreparer.prepare", prepare)
    raw = {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": "answer"}]}, "finishReason": "STOP"}
        ]
    }
    if usage:
        raw["usageMetadata"] = {
            "promptTokenCount": 40,
            "candidatesTokenCount": 5,
            "totalTokenCount": 45,
        }
    return settings, raw


@respx.mock
def test_pdf_prepared_order_and_no_reparse_or_metadata_egress(monkeypatch):
    settings, raw = wire(monkeypatch)
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=raw))
    result = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=body())
    assert result.status_code == 200 and route.call_count == 1
    upstream = json.loads(route.calls[0].request.content)
    assert upstream["contents"][0]["parts"] == [
        {"text": "before"},
        {"inlineData": {"mimeType": "application/pdf", "data": PART["file_data"].split(",", 1)[1]}},
        {"text": "after"},
    ]
    assert "digest" not in str(upstream) and "fixture.pdf" not in str(upstream)
    estimate = estimate_request_cost(
        model="m", operation="responses", body=body(), pricing=settings.pricing
    )
    assert estimate.input_tokens > 4 * (258 + 65536) and estimate.estimated_cost_usd == 0


@respx.mock
@pytest.mark.parametrize("usage", [True, False])
def test_pdf_known_or_missing_usage_charges_once(monkeypatch, usage):
    settings, raw = wire(monkeypatch, metered=True, usage=usage)
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=raw))
    result = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=body())
    assert result.status_code == 200 and route.call_count == 1
    live = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    expected = (
        (40 * 10 + 5 * 30) / 1000000
        if usage
        else estimate_request_cost(
            model="m", operation="responses", body=body(), pricing=settings.pricing
        ).estimated_cost_usd
    )
    assert 200 - live["estimated_remaining_usd"] == pytest.approx(expected)
    assert live["reserved_inflight_usd"] == 0


@respx.mock
def test_pdf_without_profile_or_changed_preparation_no_egress(monkeypatch):
    settings, _ = wire(monkeypatch)

    async def prepare(self, request, *, deadline):
        _ = self, request, deadline
        return PreparedGoogleMedia(())

    monkeypatch.setattr("foundry_router.api.google_pdf.PdfPreparer.prepare", prepare)
    result = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=body())
    assert result.status_code == 422
    assert not respx.calls
    assert settings.backends["g"].api_surface == "native"


@respx.mock
def test_azure_native_file_input_retains_passthrough(monkeypatch):
    settings = _settings(
        {
            "a": {
                "endpoint": "https://azure.example.test",
                "credential": "synthetic",
                "deployment": "configured",
                "credit_metered": False,
            }
        },
        {"m": {"backends": {"a": 1}}},
    )
    _wire(monkeypatch, settings)
    route = respx.post("https://azure.example.test/openai/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json={"id": "resp_fixture", "object": "response", "status": "completed", "output": []},
        )
    )
    request = {
        "model": "m",
        "input": [{"role": "user", "content": [{"type": "input_file", "file_id": "file_fixture"}]}],
    }
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=request)
    assert response.status_code == 200 and route.call_count == 1
    assert json.loads(route.calls[0].request.content)["input"] == request["input"]


@respx.mock
def test_pdf_tool_stream_sdk_replay_and_independent_reservations(monkeypatch):
    settings, _ = wire(monkeypatch, metered=True)
    schema = {
        "type": "object",
        "properties": {"x": {"type": "integer"}},
        "required": ["x"],
        "additionalProperties": False,
    }
    tool = {"type": "function", "name": "fixture", "strict": True, "parameters": schema}
    features = ["inline_pdfs", "function_tools", "json_schema"]
    updated = {
        **PROFILE,
        "features": features,
        "combinations": [features],
        "continuation_policy": "unsigned",
    }
    settings.backends["g"].google_features = type(settings.backends["g"].google_features)(**updated)
    first = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "id": "call_fixture",
                                "name": "fixture",
                                "args": {"x": 1},
                            }
                        }
                    ],
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 5, "totalTokenCount": 45},
    }
    stream_url = URL.replace(":generateContent", ":streamGenerateContent?alt=sse")
    route = respx.post(stream_url).mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=("data: " + json.dumps(first) + "\n\n").encode(),
        )
    )
    request = {
        **body(),
        "stream": True,
        "tools": [tool],
        "text": {"format": {"type": "json_schema", "name": "s", "strict": True, "schema": schema}},
    }
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=request)
    assert response.status_code == 200
    state = ResponseStreamState(input_tools=omit, text_format=omit)
    for event in response.text.split("\n\n"):
        if event.startswith("data: "):
            state.handle_event(
                construct_type(type_=ResponseStreamEvent, value=json.loads(event[6:]))
            )
    completed = state._completed_response
    assert completed.status == "completed" and completed.output[0].call_id == "call_fixture"
    request["stream"] = False
    request["input"].extend([item.model_dump(exclude_none=True) for item in completed.output])
    request["input"].append(
        {"type": "function_call_output", "call_id": "call_fixture", "output": "caller fixture"}
    )
    second = {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": '{"x":2}'}]}, "finishReason": "STOP"}
        ],
        "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 6, "totalTokenCount": 56},
    }
    final_route = respx.post(URL).mock(return_value=httpx.Response(200, json=second))
    result = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=request)
    assert result.status_code == 200 and route.call_count == final_route.call_count == 1
    replay = json.loads(final_route.calls[0].request.content)
    assert (
        replay["contents"][0]["parts"][1]["inlineData"]["data"]
        == PART["file_data"].split(",", 1)[1]
    )
    assert replay["contents"][-1]["parts"][0]["functionResponse"]["id"] == "call_fixture"
    live = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    assert live["reserved_inflight_usd"] == 0
    assert 200 - live["estimated_remaining_usd"] == pytest.approx((90 * 10 + 11 * 30) / 1000000)


@respx.mock
@pytest.mark.parametrize("real_worker", [False, True])
def test_three_project_pdf_failover_preserves_one_preparation(monkeypatch, real_worker):
    if real_worker and sys.platform != "linux":
        pytest.skip("Enforced PDF worker requires Linux")
    backends = {
        name: {
            **BACKEND,
            "endpoint": f"https://{name}.example.test",
            "quota_group": f"project-{name}",
            "credit_metered": False,
            "google_features": {**PROFILE, **({"max_pdf_pages": 1} if name == "small" else {})},
        }
        for name in ("small", "first", "second")
    }
    settings = _settings(
        backends,
        {"m": {"backends": dict.fromkeys(backends, 1)}},
        quota_group_rate_limits_json=json.dumps(
            {f"project-{name}": {"rpm": 100, "tpm": 2000000} for name in backends}
        ),
    )
    _wire(monkeypatch, settings)
    request = body()
    raw_pdf = document(2)
    request["input"][0]["content"][1]["file_data"] = (
        "data:application/pdf;base64," + base64.b64encode(raw_pdf).decode()
    )
    from foundry_router.api.google_pdf import PdfPreparer, pdf_preparer

    original = PdfPreparer.prepare
    preparations = []

    async def prepare(self, supplied, *, deadline):
        preparations.append(1)
        if real_worker:
            return await original(self, supplied, deadline=deadline)
        return PreparedGoogleMedia(
            (
                PreparedPdf(
                    (0, 1),
                    hashlib.sha256(
                        supplied["input"][0]["content"][1]["file_data"].encode()
                    ).hexdigest(),
                    len(raw_pdf),
                    2,
                ),
            )
        )

    monkeypatch.setattr(PdfPreparer, "prepare", prepare)
    first = respx.post("https://first.example.test/v1beta/models/configured:generateContent").mock(
        return_value=httpx.Response(
            429, headers={"retry-after": "1"}, json={"error": {"code": 429}}
        )
    )
    second = respx.post(
        "https://second.example.test/v1beta/models/configured:generateContent"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "answer"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 40,
                    "candidatesTokenCount": 5,
                    "totalTokenCount": 45,
                },
            },
        )
    )
    result = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=request)
    assert result.status_code == 200
    assert first.call_count == second.call_count == 1 and preparations == [1]
    assert pdf_preparer.active == 0
    assert (
        json.loads(first.calls[0].request.content)["contents"]
        == json.loads(second.calls[0].request.content)["contents"]
    )
    live = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"]
    assert all(item["live"]["reserved_inflight_usd"] in (None, 0) for item in live.values())
    assert live["small"]["live"]["rate_limit"]["rpm_used_60s"] == 0
