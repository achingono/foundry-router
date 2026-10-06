"""Actual SDK versioned audio extension through isolated synthetic native traffic."""

import base64
import json

import httpx
import pytest
import respx
from openai import OpenAI
from test_google_adapter_integration import _settings, _wire, client

from foundry_router.config.google_features import GoogleFeatureProfile
from foundry_router.credit import estimate_request_cost
from tests.unit.test_google_audio_output import BODY, media, native
from tests.unit.test_google_audio_output_config import profile
from tests.unit.test_google_output_wav import wav

URL = "https://generated-audio.example.test/v1beta/models/configured:generateContent"


def wire(monkeypatch):
    settings = _settings(
        {
            "g": {
                "provider": "google_ai_studio",
                "api_surface": "native",
                "endpoint": "https://generated-audio.example.test",
                "deployment": "configured",
                "credential": "PRIVATE_KEY",
                "quota_group": "project",
                "google_features": {"native_thinking_disabled": True},
            }
        },
        {"m": {"backends": {"g": 1}}},
        pricing_json='{"m":{"input_per_million":10,"output_per_million":30,"audio_output_per_second":0.01}}',
        backend_cycle_start_day_json='{"g":1}',
        backend_cycle_allowance_usd_json='{"g":200}',
        backend_initial_estimated_remaining_usd_json='{"g":200}',
        quota_group_rate_limits_json='{"project":{"rpm":10,"tpm":100000}}',
    )
    # Synthetic fixture only; Settings has no enablement bypass.
    settings.backends["g"].google_features = GoogleFeatureProfile(**profile())
    _wire(monkeypatch, settings)
    return settings


@respx.mock
def test_actual_sdk_extra_body_root_audio_consumption_and_full_billing(monkeypatch):
    settings = wire(monkeypatch)
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=native([media()])))
    sdk = OpenAI(api_key="client-key", base_url="http://testserver/openai/v1", http_client=client)
    response = sdk.responses.create(
        model="m",
        input="fixture",
        metadata={"fixture": "owned"},
        extra_body={"foundry_audio_generation": BODY["foundry_audio_generation"]},
    )
    assert response.status == "completed" and response.output == []
    assert base64.b64decode(response.model_extra["foundry_generated_audio"]["data"]) == wav(2)
    assert response.model_dump()["foundry_generated_audio"]["sample_rate_hz"] == 24000
    upstream = json.loads(route.calls[0].request.content)
    assert upstream["generationConfig"]["maxOutputTokens"] == 2048
    assert "thinkingConfig" not in upstream["generationConfig"]
    assert upstream["generationConfig"]["responseFormat"]["audio"]["mimeType"] == "AUDIO_WAV"
    estimate = estimate_request_cost(
        model="m", operation="responses", body=BODY, pricing=settings.pricing, settings=settings
    )
    live = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    assert 200 - live["estimated_remaining_usd"] == pytest.approx(estimate.estimated_cost_usd)
    assert live["reserved_inflight_usd"] == 0
    from foundry_router import main

    assert main._active_requests == 0


@respx.mock
@pytest.mark.parametrize(
    "finish,parts,status",
    [
        ("MAX_TOKENS", [media()], 200),
        ("SAFETY", [], 200),
        ("STOP", [{"inlineData": {"mimeType": "audio/wav", "data": "PRIVATE_OUTPUT"}}], 502),
        ("STOP", [{"text": "PRIVATE_OUTPUT", "thoughtSignature": "PRIVATE_STATE"}], 502),
    ],
)
def test_refusal_length_and_invalid_keep_full_audio_reserve(monkeypatch, finish, parts, status):
    settings = wire(monkeypatch)
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=native(parts, finish)))
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    assert response.status_code == status and route.call_count == 1
    if status == 200:
        assert "foundry_generated_audio" not in response.json()
    assert "PRIVATE_OUTPUT" not in response.text and "PRIVATE_STATE" not in response.text
    estimate = estimate_request_cost(
        model="m", operation="responses", body=BODY, pricing=settings.pricing, settings=settings
    )
    live = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    assert 200 - live["estimated_remaining_usd"] == pytest.approx(estimate.estimated_cost_usd)
    assert live["reserved_inflight_usd"] == 0


@respx.mock
@pytest.mark.parametrize(
    "patch", [{"stream": True}, {"input": "x" * 4097}, {"max_output_tokens": 1024}, {"tools": []}]
)
def test_invalid_audio_request_rejects_before_egress(monkeypatch, patch):
    wire(monkeypatch)
    route = respx.post(URL).mock(return_value=httpx.Response(500))
    response = client.post(
        "/openai/v1/responses", headers={"api-key": "client-key"}, json={**BODY, **patch}
    )
    assert response.status_code == 422 and route.call_count == 0


@respx.mock
def test_audio_decoded_wire_limit_retains_reserve_without_retry(monkeypatch):
    settings = wire(monkeypatch)
    route = respx.post(URL).mock(return_value=httpx.Response(200, content=b"x" * 700001))
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    assert response.status_code == 502 and route.call_count == 1
    estimate = estimate_request_cost(
        model="m", operation="responses", body=BODY, pricing=settings.pricing, settings=settings
    )
    live = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    assert 200 - live["estimated_remaining_usd"] == pytest.approx(estimate.estimated_cost_usd)
    assert live["reserved_inflight_usd"] == 0


@respx.mock
def test_audio_capacity_and_tpm_reject_without_provider_traffic(monkeypatch):
    settings = wire(monkeypatch)
    route = respx.post(URL).mock(return_value=httpx.Response(500))
    settings.quota_group_rate_limits["project"] = {"rpm": 10, "tpm": 1}
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    assert response.status_code == 429 and route.call_count == 0
    from foundry_router.api.google_output_work import OutputInspectionLease

    lease = OutputInspectionLease(slots=2)
    try:
        response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
        assert response.status_code == 503 and route.call_count == 0
    finally:
        lease.close()


@respx.mock
@pytest.mark.parametrize("status", [400, 403, 500])
def test_audio_provider_validation_refund_or_ambiguous_full_charge(monkeypatch, status):
    settings = wire(monkeypatch)
    route = respx.post(URL).mock(
        return_value=httpx.Response(status, json={"error": {"message": "PRIVATE_OUTPUT"}})
    )
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    assert (
        response.status_code >= 400
        and route.call_count == 1
        and "PRIVATE_OUTPUT" not in response.text
    )
    expected = (
        estimate_request_cost(
            model="m", operation="responses", body=BODY, pricing=settings.pricing, settings=settings
        ).estimated_cost_usd
        if status == 500
        else 0
    )
    live = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    assert 200 - live["estimated_remaining_usd"] == pytest.approx(expected)
    assert live["reserved_inflight_usd"] == 0


@pytest.mark.parametrize("block_start", [False, True])
@pytest.mark.parametrize("cancel", [False, True])
@respx.mock
def test_audio_actual_middleware_stack_holds_capacity_until_send_deadline(
    monkeypatch, block_start, cancel
):
    import asyncio
    import time

    from foundry_router.api.google_output_work import OutputInspectionLease
    from foundry_router.main import app

    settings = wire(monkeypatch)
    settings.reservation_max_age_seconds = 0.3

    route = respx.post(URL).mock(return_value=httpx.Response(200, json=native([media()])))

    async def run():
        sent = asyncio.Event()
        received = False
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/openai/v1/responses",
            "raw_path": b"/openai/v1/responses",
            "query_string": b"",
            "headers": [(b"content-type", b"application/json"), (b"api-key", b"client-key")],
            "client": ("synthetic", 123),
            "server": ("testserver", 80),
        }

        async def receive():
            nonlocal received
            if not received:
                received = True
                return {
                    "type": "http.request",
                    "body": json.dumps(BODY).encode(),
                    "more_body": False,
                }
            await asyncio.Event().wait()
            return {"type": "http.disconnect"}

        async def send(message):
            if block_start or message["type"] == "http.response.body":
                sent.set()
                await asyncio.Event().wait()

        started = time.monotonic()
        task = asyncio.create_task(app(scope, receive, send))
        await asyncio.wait_for(sent.wait(), 1)
        with pytest.raises(ValueError, match="busy"):
            OutputInspectionLease()
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(task, 1)
            assert time.monotonic() - started < 0.5
        replacement = OutputInspectionLease(slots=2)
        replacement.close()
        assert route.call_count == 1
        from foundry_router import main

        assert main._active_requests == 0

        snapshots = await main._credit_store.live_snapshot(
            ["g"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
        )
        estimate = estimate_request_cost(
            model="m", operation="responses", body=BODY, pricing=settings.pricing, settings=settings
        )
        assert 200 - snapshots["g"].estimated_remaining_usd == pytest.approx(
            estimate.estimated_cost_usd
        )
        assert snapshots["g"].reserved_inflight_usd == 0

    asyncio.run(run())


@respx.mock
def test_audio_429_failover_reuses_same_capacity_and_native_body(monkeypatch):
    from foundry_router.api.google_output_work import OutputInspectionLease
    from foundry_router.config import BackendConfig

    settings = wire(monkeypatch)
    first = settings.backends["g"]
    settings.backends["h"] = BackendConfig(
        **{
            **first.model_dump(),
            "endpoint": "https://second-audio.example.test",
            "credential": "second",
            "quota_group": "second",
            "credit_group": "h",
        }
    )
    settings.models["m"].backends = {"g": 100, "h": 1}
    settings.backend_cycle_start_day["h"] = 1
    settings.backend_cycle_allowance_usd["h"] = 200
    settings.backend_initial_estimated_remaining_usd["h"] = 200
    settings.quota_group_rate_limits["second"] = {"rpm": 10, "tpm": 100000}
    _wire(monkeypatch, settings)
    leases = []

    class CountedLease(OutputInspectionLease):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            leases.append(self)

    monkeypatch.setattr("foundry_router.api.routes.openai.OutputInspectionLease", CountedLease)
    rejected = respx.post(URL).mock(return_value=httpx.Response(429, headers={"Retry-After": "1"}))
    accepted = respx.post(
        "https://second-audio.example.test/v1beta/models/configured:generateContent"
    ).mock(return_value=httpx.Response(200, json=native([media()])))
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    assert response.status_code == 200 and rejected.call_count == 1 and accepted.call_count == 1
    assert rejected.calls[0].request.content == accepted.calls[0].request.content
    assert len(leases) == 1 and leases[0]._closed
    status = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"]
    assert status["g"]["live"]["estimated_remaining_usd"] == 200
    assert status["h"]["live"]["estimated_remaining_usd"] < 199.9
    assert status["g"]["live"]["reserved_inflight_usd"] == 0
    assert status["h"]["live"]["reserved_inflight_usd"] == 0


@respx.mock
@pytest.mark.parametrize("known_usage", [False, True])
def test_audio_usage_settles_input_quota_without_repricing_output(monkeypatch, known_usage, caplog):
    settings = wire(monkeypatch)
    raw = native([media()])
    if not known_usage:
        raw.pop("usageMetadata")
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=raw))
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    assert response.status_code == 200 and route.call_count == 1
    estimate = estimate_request_cost(
        model="m", operation="responses", body=BODY, pricing=settings.pricing, settings=settings
    )
    live = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    assert 200 - live["estimated_remaining_usd"] == pytest.approx(estimate.estimated_cost_usd)
    assert live["reserved_inflight_usd"] == 0
    assert live["rate_limit"]["input_tpm_used_60s"] == (4 if known_usage else estimate.input_tokens)
    assert "PRIVATE_KEY" not in caplog.text and media()["inlineData"]["data"] not in caplog.text
