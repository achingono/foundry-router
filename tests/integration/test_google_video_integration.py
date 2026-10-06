"""Native video actual SDK HTTP ordering/replay/admission with synthetic provider."""

import json

import httpx
import respx
from openai import OpenAI
from test_google_adapter_integration import _settings, _wire, client

from foundry_router.credit import estimate_request_cost
from tests.unit.test_google_video import video_body, video_part, video_profile

URL = "https://video.example.test/v1beta/models/configured:generateContent"


@respx.mock
def test_sdk_native_video_metadata_order_replay_and_accounting(monkeypatch):
    backend = {
        "provider": "google_ai_studio",
        "api_surface": "native",
        "endpoint": "https://video.example.test",
        "credential": "synthetic",
        "deployment": "configured",
        "credit_metered": False,
        "google_features": {**video_profile().model_dump(), "native_thinking_disabled": True},
    }
    settings = _settings({"g": backend}, {"m": {"backends": {"g": 1}}})
    _wire(monkeypatch, settings)
    raw = {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": "answer"}]}, "finishReason": "STOP"}
        ]
    }
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=raw))
    part = video_part()
    body = video_body(part, {"type": "input_text", "text": "describe"})
    sdk = OpenAI(api_key="client-key", base_url="http://testserver/openai/v1", http_client=client)
    response = sdk.responses.create(**body, max_output_tokens=10)
    assert response.output_text == "answer"
    upstream = json.loads(route.calls[0].request.content)
    assert upstream["contents"][0]["parts"] == [
        {
            "inlineData": {"mimeType": "video/avi", "data": part["file_data"].split(",", 1)[1]},
            "videoMetadata": {"fps": 1},
        },
        {"text": "describe"},
    ]
    estimate = estimate_request_cost(
        model="m", operation="responses", body=body, pricing=settings.pricing
    )
    assert 66632 < estimate.input_tokens < 68000 and estimate.estimated_cost_usd == 0
    replay = [
        *body["input"],
        {"role": "assistant", "content": response.output_text},
        {"role": "user", "content": "next"},
    ]
    assert (
        sdk.responses.create(model="m", input=replay, max_output_tokens=10).output_text == "answer"
    )
    settings.backends["g"].google_features = settings.backends["g"].google_features.model_copy(
        update={"max_video_frames": 3}
    )
    rejection = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=body)
    assert rejection.status_code == 422 and route.call_count == 2


@respx.mock
def test_sdk_video_stream_and_audio_combination(monkeypatch):
    from tests.unit.test_google_audio import audio_profile, wav_part

    profile = {
        **audio_profile().model_dump(),
        **video_profile().model_dump(),
        "features": ["inline_audio", "inline_video"],
        "combinations": [["inline_audio", "inline_video"]],
        "audio_input_tokens_per_second": 32,
        "audio_token_pricing": True,
        "audio_tpm_tokens": True,
        "native_thinking_disabled": True,
    }
    backend = {
        "provider": "google_ai_studio",
        "api_surface": "native",
        "endpoint": "https://video.example.test",
        "credential": "synthetic",
        "deployment": "configured",
        "credit_metered": False,
        "google_features": profile,
    }
    settings = _settings({"g": backend}, {"m": {"backends": {"g": 1}}})
    _wire(monkeypatch, settings)
    raw = {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": "answer"}]}, "finishReason": "STOP"}
        ]
    }
    route = respx.post(
        "https://video.example.test/v1beta/models/configured:streamGenerateContent?alt=sse"
    ).mock(
        return_value=httpx.Response(
            200,
            content=f"data: {json.dumps(raw)}\n\n",
            headers={"content-type": "text/event-stream"},
        )
    )
    sdk = OpenAI(api_key="client-key", base_url="http://testserver/openai/v1", http_client=client)
    body = video_body(video_part(), wav_part())
    with sdk.responses.stream(**body, max_output_tokens=10) as stream:
        list(stream)
        assert stream.get_final_response().output_text == "answer"
    parts = json.loads(route.calls[0].request.content)["contents"][0]["parts"]
    assert [p["inlineData"]["mimeType"] for p in parts] == ["video/avi", "audio/wav"]
    assert parts[0]["videoMetadata"] == {"fps": 1} and "videoMetadata" not in parts[1]
    estimate = estimate_request_cost(
        model="m", operation="responses", body=body, pricing=settings.pricing
    )
    assert estimate.input_tokens > 66632 + 384


@respx.mock
def test_video_three_project_caps_failover_and_free_tpm(monkeypatch):
    profile = {**video_profile().model_dump(), "native_thinking_disabled": True}
    backends = {
        name: {
            "provider": "google_ai_studio",
            "api_surface": "native",
            "endpoint": f"https://{name}.example.test",
            "credential": "synthetic",
            "deployment": "configured",
            "credit_metered": False,
            "quota_group": name,
            "google_features": profile,
        }
        for name in ("a", "b", "c")
    }
    backends["a"]["google_features"] = {**profile, "max_video_frames": 1}
    settings = _settings(
        backends,
        {"m": {"backends": {"a": 100, "b": 10, "c": 1}}},
        quota_group_rate_limits_json='{"a":{"tpm":1000000},"b":{"tpm":1000000},"c":{"tpm":1000000}}',
    )
    _wire(monkeypatch, settings)
    a = respx.post("https://a.example.test/v1beta/models/configured:generateContent").mock(
        return_value=httpx.Response(500)
    )
    b = respx.post("https://b.example.test/v1beta/models/configured:generateContent").mock(
        return_value=httpx.Response(429)
    )
    raw = {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": "answer"}]}, "finishReason": "STOP"}
        ]
    }
    c = respx.post("https://c.example.test/v1beta/models/configured:generateContent").mock(
        return_value=httpx.Response(200, json=raw)
    )
    body = video_body(video_part())
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=body)
    assert (
        response.status_code == 200
        and a.call_count == 0
        and b.call_count >= 1
        and c.call_count == 1
    )
    assert b.calls[0].request.content == c.calls[0].request.content
    for name in ("a", "b", "c"):
        settings.quota_group_rate_limits[name] = {"tpm": 100}
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=body)
    assert response.status_code in (429, 503) and a.call_count == 0 and c.call_count == 1
