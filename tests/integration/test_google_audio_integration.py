"""Real SDK HTTP serialization with synthetic native WAV provider traffic."""

import json

import httpx
import pytest
import respx
from openai import OpenAI
from test_google_adapter_integration import _settings, _wire, client

from foundry_router.credit import estimate_request_cost
from tests.unit.test_google_audio import audio_body, audio_profile, wav_part

URL = "https://audio.example.test/v1beta/models/configured:generateContent"


def wire(monkeypatch, **profile_patch):
    profile = {**audio_profile().model_dump(), "native_thinking_disabled": True, **profile_patch}
    backend = {
        "provider": "google_ai_studio",
        "api_surface": "native",
        "endpoint": "https://audio.example.test",
        "credential": "PRIVATE_KEY",
        "deployment": "configured",
        "google_features": profile,
        "credit_metered": False,
    }
    settings = _settings(
        {"g": backend},
        {"m": {"backends": {"g": 1}}},
        quota_group_rate_limits_json='{"g":{"rpm":100,"tpm":1000000}}',
    )
    _wire(monkeypatch, settings)
    return settings


@respx.mock
def test_sdk_ordered_native_audio_replay_and_token_estimate(monkeypatch):
    settings = wire(monkeypatch)
    raw = {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": "answer"}]}, "finishReason": "STOP"}
        ],
        "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 5, "totalTokenCount": 45},
    }
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=raw))
    part = wav_part(160000)
    body = audio_body(
        {"type": "input_text", "text": "before"}, part, {"type": "input_text", "text": "after"}
    )
    sdk = OpenAI(api_key="client-key", base_url="http://testserver/openai/v1", http_client=client)
    response = sdk.responses.create(**body, max_output_tokens=10)
    assert response.output_text == "answer"
    upstream = json.loads(route.calls[0].request.content)
    assert upstream["contents"][0]["parts"] == [
        {"text": "before"},
        {"inlineData": {"mimeType": "audio/wav", "data": part["file_data"].split(",", 1)[1]}},
        {"text": "after"},
    ]
    assert "fixture.wav" not in str(upstream)
    estimate = estimate_request_cost(
        model="m", operation="responses", body=body, pricing=settings.pricing
    )
    assert 384 < estimate.input_tokens < 1000 and estimate.estimated_cost_usd == 0
    replay = [
        *body["input"],
        {"role": "assistant", "content": response.output_text},
        {"role": "user", "content": "continue"},
    ]
    assert (
        sdk.responses.create(model="m", input=replay, max_output_tokens=10).output_text == "answer"
    )
    assert route.call_count == 2


@respx.mock
@pytest.mark.parametrize("patch", [{"max_audio_seconds": 1}, {"max_audio_files": 1}])
def test_candidate_caps_reject_before_dispatch(monkeypatch, patch):
    wire(monkeypatch, **patch)
    route = respx.post(URL).mock(return_value=httpx.Response(500))
    response = client.post(
        "/openai/v1/responses",
        headers={"api-key": "client-key"},
        json=audio_body(wav_part(32000), wav_part()),
    )
    assert response.status_code == 422 and route.call_count == 0


@respx.mock
def test_free_tpm_admission_and_explicit_combination(monkeypatch):
    settings = wire(monkeypatch)
    settings.quota_group_rate_limits["g"] = {"tpm": 100}
    route = respx.post(URL).mock(return_value=httpx.Response(500))
    response = client.post(
        "/openai/v1/responses", headers={"api-key": "client-key"}, json=audio_body(wav_part())
    )
    assert response.status_code == 429 and route.call_count == 0
    settings.quota_group_rate_limits["g"] = {"tpm": 1000000}
    settings.backends["g"].google_features = settings.backends["g"].google_features.model_copy(
        update={"features": ("inline_audio", "json_object")}
    )
    body = audio_body(wav_part())
    body["text"] = {"format": {"type": "json_object"}}
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=body)
    assert response.status_code == 422 and route.call_count == 0


@respx.mock
@pytest.mark.parametrize("usage", [True, False])
def test_billable_unsupported_output_settles_once(monkeypatch, usage):
    backend = {
        "provider": "google_ai_studio",
        "api_surface": "native",
        "endpoint": "https://audio.example.test",
        "credential": "PRIVATE_KEY",
        "deployment": "configured",
        "google_features": {**audio_profile().model_dump(), "native_thinking_disabled": True},
    }
    settings = _settings(
        {"g": backend},
        {"m": {"backends": {"g": 1}}},
        pricing_json='{"m":{"input_per_million":10,"output_per_million":30}}',
        backend_cycle_start_day_json='{"g":1}',
        backend_cycle_allowance_usd_json='{"g":200}',
        backend_initial_estimated_remaining_usd_json='{"g":200}',
    )
    _wire(monkeypatch, settings)
    raw = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [{"inlineData": {"mimeType": "audio/wav", "data": "PRIVATE_OUTPUT"}}],
                },
                "finishReason": "STOP",
            }
        ]
    }
    if usage:
        raw["usageMetadata"] = {
            "promptTokenCount": 40,
            "candidatesTokenCount": 5,
            "totalTokenCount": 45,
        }
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=raw))
    body = {**audio_body(wav_part()), "max_output_tokens": 10}
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=body)
    assert response.status_code == 502 and route.call_count == 1
    assert "PRIVATE_OUTPUT" not in response.text and "PRIVATE_KEY" not in response.text
    live = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    expected = (
        0.00055
        if usage
        else estimate_request_cost(
            model="m", operation="responses", body=body, pricing=settings.pricing
        ).estimated_cost_usd
    )
    assert 200 - live["estimated_remaining_usd"] == pytest.approx(expected)
    assert live["reserved_inflight_usd"] == 0


@respx.mock
def test_three_project_caps_and_429_failover_preserve_audio(monkeypatch):
    template = {
        "provider": "google_ai_studio",
        "api_surface": "native",
        "credential": "synthetic",
        "deployment": "configured",
        "credit_metered": False,
        "google_features": {**audio_profile().model_dump(), "native_thinking_disabled": True},
    }
    backends = {
        name: {**template, "endpoint": f"https://{name}.example.test", "quota_group": name}
        for name in ("a", "b", "c")
    }
    backends["a"]["google_features"] = {**template["google_features"], "max_audio_seconds": 1}
    settings = _settings(backends, {"m": {"backends": {"a": 100, "b": 10, "c": 1}}})
    _wire(monkeypatch, settings)
    a = respx.post("https://a.example.test/v1beta/models/configured:generateContent").mock(
        return_value=httpx.Response(500)
    )
    b = respx.post("https://b.example.test/v1beta/models/configured:generateContent").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "1"})
    )
    raw = {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": "answer"}]}, "finishReason": "STOP"}
        ]
    }
    c = respx.post("https://c.example.test/v1beta/models/configured:generateContent").mock(
        return_value=httpx.Response(200, json=raw)
    )
    response = client.post(
        "/openai/v1/responses", headers={"api-key": "client-key"}, json=audio_body(wav_part(32000))
    )
    assert response.status_code == 200
    assert a.call_count == 0 and b.call_count >= 1 and c.call_count == 1
    assert b.calls[0].request.content == c.calls[0].request.content


@respx.mock
def test_azure_only_file_passthrough(monkeypatch):
    settings = _settings(
        {
            "az": {
                "endpoint": "https://azure.example.test",
                "deployment": "configured",
                "api_version": "2025-04-01-preview",
                "credential": "synthetic",
                "credit_metered": False,
            }
        },
        {"m": {"backends": {"az": 1}}},
    )
    _wire(monkeypatch, settings)
    route = respx.post("https://azure.example.test/openai/v1/responses").mock(
        return_value=httpx.Response(200, json={"id": "r", "output": []})
    )
    body = audio_body(wav_part())
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=body)
    assert response.status_code == 200 and route.call_count == 1
    assert json.loads(route.calls[0].request.content)["input"] == body["input"]


@respx.mock
def test_actual_sdk_audio_stream_events(monkeypatch):
    wire(monkeypatch)
    raw = {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": "answer"}]}, "finishReason": "STOP"}
        ],
        "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 5, "totalTokenCount": 45},
    }
    route = respx.post(
        "https://audio.example.test/v1beta/models/configured:streamGenerateContent?alt=sse"
    ).mock(
        return_value=httpx.Response(
            200,
            content=f"data: {json.dumps(raw)}\n\n",
            headers={"content-type": "text/event-stream"},
        )
    )
    sdk = OpenAI(api_key="client-key", base_url="http://testserver/openai/v1", http_client=client)
    with sdk.responses.stream(**audio_body(wav_part()), max_output_tokens=10) as stream:
        events = list(stream)
        response = stream.get_final_response()
    assert response.output_text == "answer" and route.call_count == 1
    assert [event.type for event in events][-1] == "response.completed"


@respx.mock
def test_audio_pdf_explicit_combination_order(monkeypatch):
    from test_google_pdf_integration import PART, prepared

    wire(
        monkeypatch,
        features=["inline_audio", "inline_pdfs"],
        combinations=[["inline_audio", "inline_pdfs"]],
        pdf_input_tokens_per_page=258,
        pdf_native_text_tokens_per_page=65536,
        pdf_token_pricing=True,
    )

    async def prepare(self, request, *, deadline):
        _ = self, deadline
        return prepared(request)

    monkeypatch.setattr("foundry_router.api.google_pdf.PdfPreparer.prepare", prepare)
    raw = {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": "answer"}]}, "finishReason": "STOP"}
        ]
    }
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=raw))
    part = wav_part()
    body = audio_body(part, PART)
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=body)
    assert response.status_code == 200 and route.call_count == 1
    parts = json.loads(route.calls[0].request.content)["contents"][0]["parts"]
    assert [item["inlineData"]["mimeType"] for item in parts] == ["audio/wav", "application/pdf"]
