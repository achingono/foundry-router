"""Synthetic SDK image output integration; application startup gate remains closed."""

import json

import httpx
import pytest
import respx
from openai import OpenAI
from test_google_adapter_integration import _settings, _wire, client

from foundry_router.config.google_features import GoogleFeatureProfile
from foundry_router.credit import estimate_request_cost
from tests.unit.test_google_image_output import FakeLease, artifact, native
from tests.unit.test_google_image_output_config import profile

URL = "https://generated.example.test/v1beta/models/configured:generateContent"
BODY = {
    "model": "m",
    "input": "synthetic",
    "tools": [{"type": "image_generation", "output_format": "png", "size": "1024x1024"}],
}


def wire(monkeypatch):
    # Only this synthetic fixture bypasses Settings enablement; no runtime switch exists.
    settings = _settings(
        {
            "g": {
                "provider": "google_ai_studio",
                "api_surface": "native",
                "endpoint": "https://generated.example.test",
                "deployment": "configured",
                "credential": "PRIVATE_KEY",
                "google_features": {"native_thinking_disabled": True},
            }
        },
        {"m": {"backends": {"g": 1}}},
        pricing_json='{"m":{"input_per_million":10,"output_per_million":30,"image_output_per_image":0.2}}',
        backend_cycle_start_day_json='{"g":1}',
        backend_cycle_allowance_usd_json='{"g":200}',
        backend_initial_estimated_remaining_usd_json='{"g":200}',
        quota_group_rate_limits_json='{"g":{"rpm":10,"tpm":100000}}',
    )
    settings.backends["g"].google_features = GoogleFeatureProfile(**profile())
    _wire(monkeypatch, settings)
    monkeypatch.setattr("foundry_router.api.routes.openai.sys.platform", "linux")

    class Lease(FakeLease):
        closed = False

        def __init__(self, *, slots=1):
            self.slots = slots

        async def ready(self, *, deadline):
            return True

        def close(self):
            self.closed = True

    monkeypatch.setattr("foundry_router.api.routes.openai.OutputInspectionLease", Lease)
    return settings


@respx.mock
@pytest.mark.parametrize(
    "parts",
    [[artifact()], [{"text": "before"}, artifact(), {"text": "after"}], [{"text": "auto text"}]],
)
def test_sdk_image_only_order_and_auto_text_keep_full_reserve(monkeypatch, parts):
    settings = wire(monkeypatch)
    raw = native(parts)
    raw["usageMetadata"] = {"promptTokenCount": 4, "candidatesTokenCount": 2, "totalTokenCount": 6}
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=raw))
    sdk = OpenAI(api_key="client-key", base_url="http://testserver/openai/v1", http_client=client)
    result = sdk.responses.create(**BODY, metadata={"fixture": "owned"})
    assert result.status == "completed" and result.metadata == {"fixture": "owned"}
    expected = ["message" if "text" in p else "image_generation_call" for p in parts]
    assert [item.type for item in result.output] == expected
    for item in result.output:
        if item.type == "image_generation_call":
            assert item.result == artifact()["inlineData"]["data"]
    upstream = json.loads(route.calls[0].request.content)
    assert upstream["generationConfig"] == {
        "maxOutputTokens": 2048,
        "candidateCount": 1,
        "thinkingConfig": {"thinkingBudget": 0},
        "responseModalities": ["TEXT", "IMAGE"],
        "imageConfig": {"aspectRatio": "1:1", "imageSize": "1K"},
    }
    assert "tools" not in upstream
    expected_cost = estimate_request_cost(
        model="m",
        operation="responses",
        body={**BODY, "metadata": {"fixture": "owned"}},
        pricing=settings.pricing,
        settings=settings,
    ).estimated_cost_usd
    live = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    assert 200 - live["estimated_remaining_usd"] == pytest.approx(expected_cost)
    assert live["reserved_inflight_usd"] == 0
    from foundry_router import main

    assert main._active_requests == 0


@respx.mock
@pytest.mark.parametrize(
    "finish,parts,status",
    [
        ("MAX_TOKENS", [artifact()], 200),
        ("SAFETY", [], 200),
        ("STOP", [{"inlineData": {"mimeType": "image/png", "data": "PRIVATE_OUTPUT"}}], 502),
        ("STOP", [{"text": "PRIVATE_OUTPUT", "thoughtSignature": "PRIVATE_STATE"}], 502),
    ],
)
def test_billable_length_refusal_and_invalid_keep_reserve(monkeypatch, finish, parts, status):
    settings = wire(monkeypatch)
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=native(parts, finish)))
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    assert response.status_code == status and route.call_count == 1
    if status == 200:
        assert not any(i["type"] == "image_generation_call" for i in response.json()["output"])
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
    "patch",
    [
        {"stream": True},
        {"max_output_tokens": 1024},
        {"tool_choice": "required"},
        {"parallel_tool_calls": True},
    ],
)
def test_ineligible_request_has_no_egress(monkeypatch, patch):
    wire(monkeypatch)
    route = respx.post(URL).mock(return_value=httpx.Response(500))
    response = client.post(
        "/openai/v1/responses", headers={"api-key": "client-key"}, json={**BODY, **patch}
    )
    assert response.status_code == 422 and route.call_count == 0


@respx.mock
def test_output_capacity_is_acquired_before_quota_credit_or_egress(monkeypatch):
    wire(monkeypatch)
    route = respx.post(URL).mock(return_value=httpx.Response(500))

    def busy(**_kwargs):
        raise ValueError("busy")

    monkeypatch.setattr("foundry_router.api.routes.openai.OutputInspectionLease", busy)
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    assert response.status_code == 503 and route.call_count == 0
    live = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    assert live["estimated_remaining_usd"] == 200 and live["reserved_inflight_usd"] == 0


@respx.mock
@pytest.mark.parametrize("status", [400, 403, 500])
def test_provider_failure_refund_or_full_billable_settlement(monkeypatch, status):
    settings = wire(monkeypatch)
    route = respx.post(URL).mock(
        return_value=httpx.Response(status, json={"error": {"message": "PRIVATE_OUTPUT"}})
    )
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    assert response.status_code >= 400 and route.call_count == 1
    assert "PRIVATE_OUTPUT" not in response.text
    live = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    expected = (
        estimate_request_cost(
            model="m", operation="responses", body=BODY, pricing=settings.pricing, settings=settings
        ).estimated_cost_usd
        if status == 500
        else 0
    )
    assert 200 - live["estimated_remaining_usd"] == pytest.approx(expected)
    assert live["reserved_inflight_usd"] == 0


@respx.mock
def test_ipm_and_input_tpm_are_admitted_before_provider(monkeypatch):
    settings = wire(monkeypatch)
    settings.quota_group_rate_limits["g"] = {"rpm": 1, "tpm": 100000}
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=native([{"text": "auto"}])))
    first = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    second = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    assert first.status_code == 200 and second.status_code == 429 and route.call_count == 1
    wire(monkeypatch).quota_group_rate_limits["g"] = {"rpm": 10, "tpm": 1}
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    assert response.status_code == 429 and route.call_count == 1


@respx.mock
def test_unavailable_inspector_fails_before_admission(monkeypatch):
    wire(monkeypatch)
    route = respx.post(URL).mock(return_value=httpx.Response(500))

    class Unavailable(FakeLease):
        closed = False

        def __init__(self, **_kwargs):
            pass

        async def ready(self, *, deadline):
            return False

        def close(self):
            self.closed = True

    monkeypatch.setattr("foundry_router.api.routes.openai.OutputInspectionLease", Unavailable)
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    assert response.status_code == 503 and route.call_count == 0
    live = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"][
        "g"
    ]["live"]
    assert live["estimated_remaining_usd"] == 200 and live["reserved_inflight_usd"] == 0


@respx.mock
@pytest.mark.parametrize(
    "patch",
    [
        {"store": True},
        {"unknown": 1},
        {"input": [{"type": "image_generation_call", "id": "old", "result": "retained"}]},
    ],
)
def test_invalid_semantics_never_acquire_output_lease(monkeypatch, patch):
    wire(monkeypatch)
    route = respx.post(URL).mock(return_value=httpx.Response(500))

    def forbidden(**_kwargs):
        pytest.fail("Invalid semantics must reject before worker lease")

    monkeypatch.setattr("foundry_router.api.routes.openai.OutputInspectionLease", forbidden)
    result = client.post(
        "/openai/v1/responses", headers={"api-key": "client-key"}, json={**BODY, **patch}
    )
    assert result.status_code == 422 and route.call_count == 0
    from foundry_router import main

    assert main._active_requests == 0


@respx.mock
def test_429_failover_reuses_request_owned_output_lease(monkeypatch):
    settings = wire(monkeypatch)
    from foundry_router.config import BackendConfig

    first = settings.backends["g"]
    settings.backends["h"] = BackendConfig(
        **{
            **first.model_dump(),
            "endpoint": "https://second.example.test",
            "credential": "second",
            "quota_group": "h",
            "credit_group": "h",
        }
    )
    settings.models["m"].backends = {"g": 100, "h": 1}
    settings.backend_cycle_start_day["h"] = 1
    settings.backend_cycle_allowance_usd["h"] = 200
    settings.backend_initial_estimated_remaining_usd["h"] = 200
    settings.quota_group_rate_limits["h"] = {"rpm": 10, "tpm": 100000}
    _wire(monkeypatch, settings)
    leases = []

    class Lease(FakeLease):
        def __init__(self, **_kwargs):
            leases.append(self)
            self.closed = False

        async def ready(self, *, deadline):
            return True

        def close(self):
            self.closed = True

    monkeypatch.setattr("foundry_router.api.routes.openai.OutputInspectionLease", Lease)
    rejected = respx.post(URL).mock(return_value=httpx.Response(429, headers={"Retry-After": "1"}))
    accepted = respx.post(
        "https://second.example.test/v1beta/models/configured:generateContent"
    ).mock(return_value=httpx.Response(200, json=native([artifact()])))
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    assert response.status_code == 200 and rejected.call_count == 1 and accepted.call_count == 1
    assert len(leases) == 1 and leases[0].closed
    assert rejected.calls[0].request.content == accepted.calls[0].request.content
    status = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()["backends"]
    assert status["g"]["live"]["estimated_remaining_usd"] == 200
    assert status["h"]["live"]["estimated_remaining_usd"] < 199.8
    assert status["g"]["live"]["reserved_inflight_usd"] == 0
    assert status["h"]["live"]["reserved_inflight_usd"] == 0


@respx.mock
def test_combined_capable_pool_reserves_both_slots_for_auto_text(monkeypatch):
    settings = wire(monkeypatch)
    settings.backends["g"].google_features = settings.backends["g"].google_features.model_copy(
        update={
            "features": ("image_output", "inline_images"),
            "combinations": (("image_output", "inline_images"),),
            "image_input_tokens": 258,
            "image_token_pricing": True,
        }
    )
    capacities = []

    class Lease(FakeLease):
        def __init__(self, *, slots):
            capacities.append(slots)

        async def ready(self, *, deadline):
            return True

        def close(self):
            pass

    monkeypatch.setattr("foundry_router.api.routes.openai.OutputInspectionLease", Lease)
    route = respx.post(URL).mock(
        return_value=httpx.Response(200, json=native([{"text": "auto text"}]))
    )
    response = client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=BODY)
    assert response.status_code == 200 and route.call_count == 1 and capacities == [2]


@pytest.mark.parametrize("block_start", [False, True])
@pytest.mark.parametrize("cancel", [False, True])
@respx.mock
def test_actual_middleware_stack_holds_capacity_until_send_deadline(
    monkeypatch, block_start, cancel
):
    import asyncio
    import time

    from foundry_router.api.google_output_work import OutputInspectionLease
    from foundry_router.main import app

    settings = wire(monkeypatch)
    settings.reservation_max_age_seconds = 0.3
    settings.backends["g"].google_features = settings.backends["g"].google_features.model_copy(
        update={
            "features": ("image_output", "inline_images"),
            "combinations": (("image_output", "inline_images"),),
            "image_input_tokens": 258,
            "image_token_pricing": True,
        }
    )

    class RealCapacity(OutputInspectionLease):
        async def ready(self, *, deadline):
            return True

        async def inspect(self, raw, *, deadline):
            return await FakeLease().inspect(raw, deadline=deadline)

    monkeypatch.setattr("foundry_router.api.routes.openai.OutputInspectionLease", RealCapacity)
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=native([artifact()])))

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
