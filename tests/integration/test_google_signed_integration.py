"""Signed public HTTP lifecycle under an explicitly test-owned runtime gate."""

import base64
import copy
import json

import httpx
import pytest
import respx
from test_google_adapter_integration import _settings, _wire, client
from test_google_native_integration import BACKEND, URL, provider

from foundry_router.config.google_features import GoogleFeatureProfile
from foundry_router.credit import estimate_request_cost

KEYS = {
    "scope_key": base64.urlsafe_b64encode(b"s" * 32).decode(),
    "keys": {"fixture": base64.urlsafe_b64encode(b"k" * 32).decode()},
    "active": "fixture",
    "generation": "fixture",
}
BODY = {
    "model": "m",
    "input": [{"role": "user", "content": "fixture"}],
    "foundry_provider_state": {"version": 1},
    "max_output_tokens": 10,
}


def settings():
    configured = _settings(
        {"g": BACKEND, "other": {**BACKEND, "quota_group": "other-project"}},
        {"m": {"backends": {"g": 2, "other": 1}}},
        google_state_keys_json=json.dumps(KEYS),
        quota_group_rate_limits_json='{"native-project":{"rpm":100,"tpm":1000000},"other-project":{"rpm":100,"tpm":1000000}}',
        pricing_json='{"m":{"input_per_million":10,"output_per_million":30}}',
        backend_cycle_start_day_json='{"g":1,"other":1}',
        backend_cycle_allowance_usd_json='{"g":200,"other":200}',
        backend_initial_estimated_remaining_usd_json='{"g":200,"other":200}',
    )
    # Startup stays closed pending the complete runtime review. These tests own
    # a validated uniform profile and explicitly exercise the in-flight path.
    # Constructed through real validation (no model_copy bypass): sealed policy
    # requires function tools, enabled thinking with budget/pricing ceilings and
    # a signature bound.
    for backend in configured.backends.values():
        backend.google_features = GoogleFeatureProfile(
            **{
                **backend.google_features.model_dump(),
                "features": ("json_schema", "function_tools"),
                "continuation_policy": "sealed_native",
                "native_thinking_disabled": False,
                "native_thinking_budget": 8,
                "thought_token_pricing": True,
                "signature_input_token_bound": 100000,
            }
        )
    configured.models["m"].continuation_policy = "bound_history_required"
    return configured


def post(body):
    return client.post("/openai/v1/responses", headers={"api-key": "client-key"}, json=body)


@respx.mock
@pytest.mark.parametrize("stream", [False, True])
def test_signed_http_completed_replay_and_repeated_billing(monkeypatch, stream):
    configured = settings()
    _wire(monkeypatch, configured)
    result = provider("answer", thoughts=2)
    result["candidates"][0]["content"]["parts"][0]["thoughtSignature"] = "c2ln"
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=result))
    first = post({**BODY, "stream": stream})
    assert first.status_code == 200, first.text
    if stream:
        events = [
            json.loads(line[6:])
            for line in first.text.splitlines()
            if line.startswith("data: ") and line != "data: [DONE]"
        ]
        completed = [event for event in events if event["type"] == "response.completed"]
        assert len(completed) == 1
        output = completed[0]["response"]["output"]
    else:
        output = first.json()["output"]
    assert "foundry_provider_state" in output[0]
    replay = {**BODY, "input": [*BODY["input"], *output, {"role": "user", "content": "next"}]}
    for _ in range(2):
        response = post(replay)
        assert response.status_code == 200, response.text
    assert len(route.calls) == 3
    wire = json.loads(route.calls[1].request.content)
    assert wire["contents"][1]["parts"] == result["candidates"][0]["content"]["parts"]
    assert "foundry_provider_state" not in str(wire)
    admin = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()
    assert (
        sum(value["live"]["rate_limit"]["rpm_used_60s"] for value in admin["backends"].values())
        == 3
    )
    assert "c2ln" not in response.text


@respx.mock
@pytest.mark.parametrize("change", ["missing", "modified", "caller", "generation"])
def test_invalid_state_before_reservation_or_provider(monkeypatch, change):
    configured = settings()
    _wire(monkeypatch, configured)
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=provider("answer")))
    first = post(BODY)
    assert first.status_code == 200, first.text
    replay = {
        **BODY,
        "input": [*BODY["input"], *first.json()["output"], {"role": "user", "content": "next"}],
    }
    replay = copy.deepcopy(replay)
    if change == "missing":
        replay["input"][1].pop("foundry_provider_state")
    elif change == "modified":
        replay["input"][1]["content"][0]["text"] = "modified"
    elif change == "caller":
        configured.client_api_keys.append("different-client")
    else:
        configured.google_state_keys = configured.google_state_keys.model_copy(
            update={"generation": "new"}
        )
    response = (
        client.post("/openai/v1/responses", headers={"api-key": "different-client"}, json=replay)
        if change == "caller"
        else post(replay)
    )
    assert response.status_code == 422, response.text
    assert len(route.calls) == 1


@respx.mock
@pytest.mark.parametrize("emergency", [False, True])
def test_pinned_provider_429_never_fails_over(monkeypatch, emergency):
    configured = settings()
    configured.protected_emergency_fallback = emergency
    _wire(monkeypatch, configured)
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=provider("answer")))
    first = post(BODY)
    assert first.status_code == 200, first.text
    route.mock(return_value=httpx.Response(429, headers={"retry-after": "30"}))
    replay = {
        **BODY,
        "input": [*BODY["input"], *first.json()["output"], {"role": "user", "content": "next"}],
    }
    response = post(replay)
    assert response.status_code == 429, response.text
    assert len(route.calls) == 2
    assert post(replay).status_code in {429, 503}
    assert len(route.calls) == 2


def test_accounting_uses_server_bounds_excludes_only_public_carriers():
    configured = settings()
    ordinary = estimate_request_cost(
        model="m", operation="responses", body=BODY, pricing=configured.pricing
    )
    bounded = estimate_request_cost(
        model="m", operation="responses", body=BODY, pricing=configured.pricing, settings=configured
    )
    assert bounded.input_tokens >= ordinary.input_tokens + 100000
    assert bounded.output_tokens == ordinary.output_tokens + 8
    body = {
        **BODY,
        "input": [
            {
                "type": "message",
                "id": "fixture",
                "role": "assistant",
                "content": "answer",
                "foundry_provider_state": {"version": 1, "token": "x" * 10000},
            }
        ],
    }
    stripped = {
        **body,
        "input": [
            {
                key: value
                for key, value in body["input"][0].items()
                if key != "foundry_provider_state"
            }
        ],
    }
    assert estimate_request_cost(
        model="m", operation="responses", body=body, pricing=configured.pricing, settings=configured
    ) == estimate_request_cost(
        model="m",
        operation="responses",
        body=stripped,
        pricing=configured.pricing,
        settings=configured,
    )


@respx.mock
@pytest.mark.parametrize("stream", [False, True])
def test_billable_sealing_failure_preserves_known_usage(monkeypatch, stream):
    configured = settings()
    _wire(monkeypatch, configured)
    result = provider("answer", thoughts=2)
    result["candidates"][0]["content"]["parts"][0]["thoughtSignature"] = "INVALID_SECRET_SIGNATURE"
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=result))
    response = post({**BODY, "stream": stream})
    assert response.status_code == 502, response.text
    assert "INVALID_SECRET_SIGNATURE" not in response.text
    assert len(route.calls) == 1
    admin = client.get("/admin/status", headers={"x-admin-key": "admin-key"}).json()
    assert (
        sum(
            value["live"]["rate_limit"]["input_tpm_used_60s"]
            for value in admin["backends"].values()
        )
        == 40
    )
    assert all(value["live"]["reserved_inflight_usd"] == 0 for value in admin["backends"].values())


@respx.mock
def test_fresh_intake_mutation_during_selection_never_dispatches(monkeypatch):
    from foundry_router.main import _health_store as backend_health_store

    configured = settings()
    _wire(monkeypatch, configured)
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=provider("answer")))
    import foundry_router.api.routes.openai as openai_routes

    original = openai_routes.prepare_signed_request
    captured = {}

    async def capture(*args, **kwargs):
        captured["body"] = args[2]
        return await original(*args, **kwargs)

    monkeypatch.setattr(openai_routes, "prepare_signed_request", capture)
    snapshot = backend_health_store.snapshot_backend_health

    async def mutate(*args, **kwargs):
        captured["body"]["instructions"] = "changed after intake"
        return await snapshot(*args, **kwargs)

    monkeypatch.setattr(backend_health_store, "snapshot_backend_health", mutate)
    response = post(BODY)
    assert response.status_code == 502, response.text
    assert len(route.calls) == 0


@respx.mock
@pytest.mark.parametrize("stream", [False, True])
def test_backend_rotation_during_selection_never_dispatches(monkeypatch, stream):
    from foundry_router.main import _health_store

    configured = settings()
    _wire(monkeypatch, configured)
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=provider("answer")))
    snapshot = _health_store.snapshot_backend_health

    async def rotate(*args, **kwargs):
        for backend in configured.backends.values():
            backend.credential = "rotated after intake"
        return await snapshot(*args, **kwargs)

    monkeypatch.setattr(_health_store, "snapshot_backend_health", rotate)
    response = post({**BODY, "stream": stream})
    assert response.status_code == 503, response.text
    assert len(route.calls) == 0


def test_signed_unicode_text_reserves_utf8_ceiling_independently_of_signatures():
    configured = settings()
    body = {
        **BODY,
        "instructions": "😀" * 1000,
        "input": [{"role": "user", "content": "😀" * 1000}],
    }
    estimate = estimate_request_cost(
        model="m", operation="responses", body=body, pricing=configured.pricing, settings=configured
    )
    assert estimate.input_tokens >= 100000 + 8000


@respx.mock
@pytest.mark.parametrize("stream", [False, True])
def test_two_admitted_requests_finish_while_third_rejects_before_dispatch(monkeypatch, stream):
    import asyncio

    from foundry_router.backends import AllowedBackendClient
    from foundry_router.main import app

    configured = settings()
    _wire(monkeypatch, configured)

    async def exercise():
        entered = asyncio.Event()
        release = asyncio.Event()
        dispatches = 0

        async def provider_transport(_request):
            nonlocal dispatches
            dispatches += 1
            if dispatches == 2:
                entered.set()
            await release.wait()
            return httpx.Response(200, json=provider("answer"))

        backend = AllowedBackendClient()
        await backend._client.aclose()
        backend._client = httpx.AsyncClient(transport=httpx.MockTransport(provider_transport))
        monkeypatch.setattr("foundry_router.backends._backend_client", backend)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://fixture.test"
        ) as caller:

            async def request():
                return await caller.post(
                    "/openai/v1/responses",
                    headers={"api-key": "client-key"},
                    json={**BODY, "stream": stream},
                )

            tasks = [asyncio.create_task(request()) for _ in range(2)]
            try:
                await asyncio.wait_for(entered.wait(), timeout=2)
                third = await request()
                assert third.status_code == 503
                assert dispatches == 2
                release.set()
                results = await asyncio.gather(*tasks)
                assert all(result.status_code == 200 for result in results)
                assert all("foundry_provider_state" in result.text for result in results)
                assert dispatches == 2
                assert (await request()).status_code == 200
                assert dispatches == 3
            finally:
                release.set()
                await asyncio.gather(*tasks, return_exceptions=True)
                await backend.aclose()

    asyncio.run(exercise())


@respx.mock
@pytest.mark.parametrize("stream", [False, True])
def test_actual_openai_client_http_snapshot_and_replay(monkeypatch, stream):
    import asyncio

    from openai import AsyncOpenAI

    from foundry_router.main import app

    configured = settings()
    _wire(monkeypatch, configured)
    result = provider("answer")
    result["candidates"][0]["content"]["parts"][0]["thoughtSignature"] = "c2ln"
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=result))

    async def exercise():
        transport = httpx.AsyncClient(transport=httpx.ASGITransport(app=app))
        async with AsyncOpenAI(
            api_key="client-key",
            base_url="http://fixture.test/openai/v1",
            http_client=transport,
            max_retries=0,
        ) as sdk:
            if stream:
                async with sdk.responses.stream(
                    model="m",
                    input=BODY["input"],
                    max_output_tokens=10,
                    extra_body={"foundry_provider_state": {"version": 1}},
                ) as events:
                    async for _event in events:
                        pass
                    first = await events.get_final_response()
            else:
                first = await sdk.responses.create(
                    model="m",
                    input=BODY["input"],
                    max_output_tokens=10,
                    extra_body={"foundry_provider_state": {"version": 1}},
                )
            output = [item.model_dump(exclude_none=True) for item in first.output]
            assert "foundry_provider_state" in output[0]
            replay = [*BODY["input"], *output, {"role": "user", "content": "next"}]
            second = await sdk.responses.create(
                model="m",
                input=replay,
                max_output_tokens=10,
                extra_body={"foundry_provider_state": {"version": 1}},
            )
            assert second.status == "completed"
            assert len(route.calls) == 2
            assert (
                json.loads(route.calls[1].request.content)["contents"][1]["parts"]
                == result["candidates"][0]["content"]["parts"]
            )

    asyncio.run(exercise())


@respx.mock
@pytest.mark.parametrize("transition", ["restart", "overlap", "revoke", "expire"])
def test_signed_state_restart_rotation_and_expiry_at_http_boundary(monkeypatch, transition):
    import time

    from foundry_router.config.google_state import parse_state_keys

    configured = settings()
    _wire(monkeypatch, configured)
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=provider("answer")))
    first = post(BODY)
    assert first.status_code == 200
    replay = {
        **BODY,
        "input": [*BODY["input"], *first.json()["output"], {"role": "user", "content": "next"}],
    }
    if transition == "restart":
        configured = settings()
        _wire(monkeypatch, configured)
    elif transition in {"overlap", "revoke"}:
        rotated = {
            **KEYS,
            "keys": {"next": base64.urlsafe_b64encode(b"n" * 32).decode()},
            "active": "next",
        }
        if transition == "overlap":
            rotated["keys"].update(KEYS["keys"])
        configured.google_state_keys = parse_state_keys(json.dumps(rotated))
    else:
        now = time.time()
        monkeypatch.setattr(time, "time", lambda: now + 901)
    response = post(replay)
    expected = 200 if transition in {"restart", "overlap"} else 422
    assert response.status_code == expected, response.text
    assert len(route.calls) == (2 if expected == 200 else 1)
    if transition == "overlap":
        assert response.json()["output"][0]["foundry_provider_state"]["token"].startswith("next.")


@respx.mock
def test_key_configuration_changes_during_intake_fail_before_admission(monkeypatch):
    import foundry_router.api.routes.openai as route_module
    from foundry_router.config.google_state import parse_state_keys

    configured = settings()
    _wire(monkeypatch, configured)
    native = respx.post(URL).mock(return_value=httpx.Response(200, json=provider("answer")))
    read_body = route_module.request_body

    async def rotate(*args, **kwargs):
        body = await read_body(*args, **kwargs)
        configured.google_state_keys = parse_state_keys(json.dumps(KEYS))
        return body

    monkeypatch.setattr(route_module, "request_body", rotate)
    response = post(BODY)
    assert response.status_code == 503
    assert not native.calls


@respx.mock
@pytest.mark.parametrize("stream", [False, True])
def test_signed_function_round_trip_with_actual_sdk(monkeypatch, stream):
    import asyncio

    from openai import AsyncOpenAI

    from foundry_router.main import app

    configured = settings()
    for backend in configured.backends.values():
        backend.google_features = backend.google_features.model_copy(
            update={"features": ("function_tools",)}
        )
    _wire(monkeypatch, configured)
    tool = {
        "type": "function",
        "name": "fixture",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    }
    result = provider("answer")
    result["candidates"][0]["content"]["parts"] = [
        {
            "functionCall": {"id": "call_fixture", "name": "fixture", "args": {}},
            "thoughtSignature": "c2ln",
        }
    ]
    route = respx.post(URL).mock(
        side_effect=[httpx.Response(200, json=result), httpx.Response(200, json=provider("answer"))]
    )

    async def exercise():
        transport = httpx.AsyncClient(transport=httpx.ASGITransport(app=app))
        async with AsyncOpenAI(
            api_key="client-key",
            base_url="http://fixture.test/openai/v1",
            http_client=transport,
            max_retries=0,
        ) as sdk:
            args = {
                "model": "m",
                "input": BODY["input"],
                "tools": [tool],
                "max_output_tokens": 10,
                "extra_body": {"foundry_provider_state": {"version": 1}},
            }
            if stream:
                async with sdk.responses.stream(**args) as events:
                    async for _event in events:
                        pass
                    first = await events.get_final_response()
            else:
                first = await sdk.responses.create(**args)
            if stream:
                raw_call = first.output[0].model_dump(exclude_none=True)
                assert raw_call["parsed_arguments"] == {}
                rejected = post(
                    {
                        **BODY,
                        "tools": [tool],
                        "input": [
                            *BODY["input"],
                            raw_call,
                            {
                                "type": "function_call_output",
                                "call_id": "call_fixture",
                                "output": "fixture result",
                            },
                        ],
                    }
                )
                assert rejected.status_code == 422
                assert len(route.calls) == 1
            call = first.output[0].model_dump(exclude_none=True, exclude={"parsed_arguments"})
            assert call["type"] == "function_call" and call["call_id"] == "call_fixture"
            assert call["foundry_provider_state"]["version"] == 1
            second = await sdk.responses.create(
                **{
                    **args,
                    "input": [
                        *BODY["input"],
                        call,
                        {
                            "type": "function_call_output",
                            "call_id": call["call_id"],
                            "output": "fixture result",
                        },
                    ],
                }
            )
            assert second.status == "completed"
            wire = json.loads(route.calls[1].request.content)
            assert wire["contents"][1]["parts"] == result["candidates"][0]["content"]["parts"]
            assert wire["contents"][2]["parts"][0]["functionResponse"]["id"] == "call_fixture"
            assert len(route.calls) == 2

    asyncio.run(exercise())


@respx.mock
def test_actual_signed_forwarding_unstarted_asgi_send_settles_known_usage(monkeypatch):
    import asyncio
    import time
    from unittest.mock import AsyncMock

    from foundry_router.api.common import api_error
    from foundry_router.api.google_sealing import build_seal_context
    from foundry_router.api.google_work import SignedWorkLease
    from foundry_router.backends import AllowedBackendClient
    from foundry_router.forwarding import forward_streaming_with_retries

    configured = settings()
    _wire(monkeypatch, configured)
    upstream = httpx.Response(200, json=provider("answer", thoughts=2))
    route = respx.post(URL).mock(return_value=upstream)

    async def exercise():
        backend = AllowedBackendClient()
        lease = SignedWorkLease()
        context = build_seal_context(
            configured, "m", BODY, caller_scope="fixture", work_lease=lease
        )
        credit, quota, metrics = (AsyncMock() for _ in range(3))
        try:
            attempt = await forward_streaming_with_retries(
                settings=configured,
                backend_id="g",
                request_id="fixture",
                headers={},
                body=BODY,
                get_backend_client=lambda: backend,
                set_backend_active=AsyncMock(),
                set_backend_cooldown=AsyncMock(),
                sleep=AsyncMock(),
                api_error=api_error,
                credit_store=credit,
                rate_limit_store=quota,
                metrics_store=metrics,
                reservation_deadline_monotonic=time.monotonic() + 2,
                seal_context=context,
            )
            assert attempt.response.status_code == 200
            lease.close()
            attempt.response.deadline = time.monotonic() + 0.05

            async def blocked_send(_message):
                await asyncio.Event().wait()

            with pytest.raises(TimeoutError):
                await attempt.response.stream_response(blocked_send)
            credit.finalize_request.assert_awaited_once_with(
                "fixture",
                backend_id="g",
                charge_reserved=True,
                charged_cost_usd=pytest.approx(0.00076),
            )
            quota.finalize_request.assert_awaited_once_with("fixture", actual_input_tokens=40)
            assert len(route.calls) == 1
            assert upstream.is_closed
            assert not attempt.response.iterator_started
            replacement = SignedWorkLease()
            replacement.close()
        finally:
            lease.close()
            await backend.aclose()

    asyncio.run(exercise())


@respx.mock
def test_mixed_server_ordinary_responses_share_parser_capacity(monkeypatch):
    from foundry_router.api.google_work import SignedWorkLease
    from foundry_router.config import ModelBackendPool

    configured = settings()
    configured.backends["unsigned"] = configured.backends["g"].model_copy(
        update={
            "google_features": configured.backends["g"].google_features.model_copy(
                update={"continuation_policy": "disabled", "native_thinking_disabled": True}
            )
        }
    )
    configured.models["ordinary"] = ModelBackendPool(backends={"unsigned": 1})
    _wire(monkeypatch, configured)
    native = respx.post(URL).mock(return_value=httpx.Response(200, json=provider("answer")))
    leases = [SignedWorkLease(), SignedWorkLease()]
    try:
        response = post({"model": "ordinary", "input": "fixture"})
        assert response.status_code == 503
        assert not native.calls
    finally:
        for lease in leases:
            lease.close()
