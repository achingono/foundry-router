"""Native route integration with real parser/serializer and mocked provider transport."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, Request
from structlog import get_logger

from foundry_router.api import azure_intake_worker as worker
from foundry_router.api.azure_intake import (
    AzureIntakeDeliveryMiddleware,
    AzureIntakeError,
    AzureIntakeLease,
    AzureIntakePolicy,
    AzureIntakeRequest,
    AzureIntakeResources,
    AzureIntakeRuntime,
)
from foundry_router.api.routes.openai import build_router
from foundry_router.auth import verify_client_auth
from foundry_router.backends import AllowedBackendClient
from foundry_router.config import Settings
from foundry_router.credit import InMemoryCreditStore, estimate_request_cost_checked
from foundry_router.health import InMemoryHealthStore
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.ratelimit import InMemoryRateLimitStore

MIB = 1024 * 1024


def configuration(**overrides):
    values = {
        "_env_file": None,
        "client_api_keys_json": '["test-client"]',
        "admin_api_keys_json": '["test-admin"]',
        "backends_json": json.dumps(
            {
                name: {
                    "endpoint": f"https://{name}.invalid",
                    "credential": "test-secret",
                    "deployment": f"physical-{name}",
                }
                for name in ("a", "b")
            }
        ),
        "models_json": json.dumps({"logical": {"backends": {"a": 1, "b": 0.8}}}),
        "model_aliases_json": '{"alias":"logical"}',
        "pricing_json": '{"logical":{"input_per_million":10,"output_per_million":30}}',
        "backend_cycle_start_day_json": '{"a":1,"b":1}',
        "backend_cycle_allowance_usd_json": '{"a":200,"b":200}',
        "backend_initial_estimated_remaining_usd_json": '{"a":200,"b":200}',
        "azure_intake_enabled": True,
        "azure_max_request_body_bytes": 16 * MIB,
        "azure_intake_child_address_space_bytes": 8 * 1024 * MIB,
        "azure_intake_scratch_bytes": 64 * MIB,
        "retry_attempts": 2,
        "retry_max_delay_seconds": 0.01,
    }
    values.update(overrides)
    return Settings(**values)


async def harness(tmp_path, monkeypatch, config=None, handler=None):
    config = config or configuration()
    scratch = tmp_path / "scratch"
    scratch.mkdir(mode=0o700)
    runtime = AzureIntakeRuntime(config)
    runtime.policy = AzureIntakePolicy.from_settings(config, native_only=False)
    runtime.resources = AzureIntakeResources(scratch, runtime.policy.document.limits)
    runtime._available = True
    controls = []

    async def child(lease, control, deadline):
        controls.append(control)
        assert control.deadline_monotonic <= deadline
        return worker.run(control, lease.input_path, lease.output_path)

    monkeypatch.setattr(AzureIntakeLease, "_child", child)
    requests = []

    async def transport(request):
        wire = await request.aread()
        requests.append((request, wire))
        if handler:
            return await handler(request, wire, len(requests))
        return httpx.Response(
            200, json={"usage": {"input_tokens": 5, "output_tokens": 2}, "ok": True}
        )

    client = AllowedBackendClient(settings=config)
    await client._client.aclose()
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
    credit, health, quota = InMemoryCreditStore(), InMemoryHealthStore(), InMemoryRateLimitStore()
    metrics = InMemoryMetricsStore()
    app = FastAPI()
    app.state.azure_intake_runtime = runtime
    app.dependency_overrides[verify_client_auth] = lambda: None
    app.include_router(
        build_router(
            load_settings_fn=lambda: config,
            get_backend_client_fn=lambda: client,
            sleep_fn=AsyncMock(),
            health_store=health,
            credit_store=credit,
            rate_limit_store=quota,
            metrics_store=metrics,
            logger=get_logger(),
        )
    )
    app.add_middleware(AzureIntakeDeliveryMiddleware)

    class RequestIdentity:
        async def __call__(self, scope, receive, send):
            scope.setdefault("state", {}).update(
                request_key="test-request", correlation_id="test-correlation"
            )
            await app(scope, receive, send)

    return SimpleNamespace(
        app=RequestIdentity(),
        fastapi=app,
        runtime=runtime,
        config=config,
        client=client,
        requests=requests,
        controls=controls,
        credit=credit,
        health=health,
        metrics=metrics,
        quota=quota,
    )


async def post(case, raw, operation="responses", headers=None):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=case.app), base_url="http://test"
    ) as client:
        return await client.post(
            f"/openai/v1/{operation}",
            content=raw,
            headers=headers or {"content-type": "application/json"},
        )


async def assert_clean(case):
    assert case.runtime.resources.active == 0
    assert case.runtime.resources.scratch_reserved == 0
    assert not case.runtime.resources.leases
    assert list(case.runtime.resources.root.iterdir()) == []
    await case.client.aclose()


@pytest.mark.parametrize("operation", ["responses", "embeddings"])
async def test_ordinary_capture_replays_existing_flow(tmp_path, monkeypatch, operation):
    case = await harness(tmp_path, monkeypatch)
    raw = b'{ "model" : "alias", "input" : "caf\\u00e9", "max_output_tokens": 8 }'
    result = await post(case, raw, operation)
    assert result.status_code == 200
    assert len(case.requests) == 1 and case.controls == []
    outgoing = json.loads(case.requests[0][1])
    assert outgoing["input"] == "café"
    assert outgoing["model"] == ("physical-a" if operation == "responses" else "logical")
    await assert_clean(case)


@pytest.mark.parametrize("operation", ["responses", "embeddings"])
@pytest.mark.parametrize("size", [2 * MIB + 100, 8 * MIB])
async def test_oversized_native_uses_bound_estimate_and_exact_transport(
    tmp_path, monkeypatch, operation, size
):
    case = await harness(tmp_path, monkeypatch)
    body = {
        "input": ("x" * size if size == 8 * MIB else "é" * (size // 2)),
        "model": "alias",
        "max_output_tokens": 8,
    }
    if operation == "embeddings":
        body["stream"] = "ignored ordinary extra"
    raw = json.dumps(body, ensure_ascii=False).encode()
    expected = estimate_request_cost_checked(
        model="logical",
        operation=operation,
        body={**body, "model": "logical"},
        pricing=case.config.pricing,
        settings=case.config.model_copy(
            update={"max_request_body_bytes": case.config.azure_effective_max_request_body_bytes}
        ),
    )
    result = await post(case, raw, operation)
    assert result.status_code == 200, result.text
    assert [control.stage for control in case.controls] == ["prepare", "encode"]
    assert case.controls[1].prepared.estimate.request_estimate() == expected
    assert case.controls[1].backend_id == "a"
    request, wire = case.requests[0]
    assert int(request.headers["content-length"]) == len(wire)
    assert len(request.headers.get_list("content-type")) == 1
    assert len(request.headers.get_list("content-length")) == 1
    assert json.loads(wire)["input"] == body["input"]
    assert case.controls[1].prepared.input_digest == hashlib.sha256(raw).hexdigest()
    await assert_clean(case)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"model":"unknown","input":"' + b"x" * (2 * MIB) + b'"}',
        b'{"model":"alias","input":"' + b"x" * (2 * MIB) + b'", "stream":"bad"}',
        b"[" + b" " * (2 * MIB) + b"]",
    ],
)
async def test_invalid_oversized_retains_413_before_dispatch(tmp_path, monkeypatch, raw):
    case = await harness(tmp_path, monkeypatch)
    result = await post(case, raw)
    assert result.status_code == 413 and not case.requests
    assert not case.credit._reservations
    await assert_clean(case)


async def test_mixed_pool_cannot_drop_candidate_to_enlarge(tmp_path, monkeypatch):
    config = configuration(
        backends_json=json.dumps(
            {
                "a": {
                    "endpoint": "https://a.invalid",
                    "credential": "test-secret",
                    "deployment": "physical-a",
                },
                "b": {
                    "endpoint": "https://b.invalid",
                    "credential": "test-secret",
                    "deployment": "other",
                    "provider": "opencode_zen",
                },
            }
        )
    )
    case = await harness(tmp_path, monkeypatch, config)
    result = await post(case, json.dumps({"model": "alias", "input": "x" * (2 * MIB)}).encode())
    assert result.status_code == 413 and not case.requests
    await assert_clean(case)


@pytest.mark.parametrize("ready", [False, True])
async def test_unavailable_or_policy_drift_fail_closed(tmp_path, monkeypatch, ready):
    case = await harness(tmp_path, monkeypatch)
    case.runtime._available = ready
    if ready:
        changed = json.loads(case.runtime.policy.wire)
        changed["models"]["logical"]["price"]["input_per_million"] = 12
        case.runtime.policy = AzureIntakePolicy(
            json.dumps(changed, sort_keys=True, separators=(",", ":")).encode()
        )
    result = await post(case, b'{"model":"alias","input":"hello"}')
    assert result.status_code == 503 and not case.requests and not case.credit._reservations
    await assert_clean(case)


async def test_retry_identical_wire_retains_unknown_cost_and_counts_quota(tmp_path, monkeypatch):
    async def handler(request, _wire, count):
        if count == 1:
            raise httpx.ReadError("test uncertain response", request=request)
        return httpx.Response(200, json={"usage": {"input_tokens": 5, "output_tokens": 2}})

    config = configuration(
        quota_group_rate_limits_json='{"a":{"rpm":10,"tpm":3000000},"b":{"rpm":10,"tpm":3000000}}'
    )
    case = await harness(tmp_path, monkeypatch, config, handler)
    raw = json.dumps({"model": "alias", "input": "x" * (2 * MIB), "max_output_tokens": 8}).encode()
    estimate = estimate_request_cost_checked(
        model="logical",
        operation="responses",
        body=json.loads(raw),
        pricing=config.pricing,
        settings=config,
    )
    result = await post(case, raw)
    assert result.status_code == 200
    assert len(case.requests) == 2 and case.requests[0][1] == case.requests[1][1]
    assert [control.stage for control in case.controls] == ["prepare", "encode"]
    snapshots = await case.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total == pytest.approx(estimate.estimated_cost_usd + 0.00011)
    quota = await case.quota.snapshot_quota_groups(["a"])
    assert (
        quota["a"].rpm_used_60s == 2 and quota["a"].input_tpm_used_60s == estimate.input_tokens + 5
    )
    await assert_clean(case)


async def test_retry_quota_denial_does_not_upload_again(tmp_path, monkeypatch):
    async def handler(request, _wire, _count):
        raise httpx.ReadError("test uncertain response", request=request)

    case = await harness(
        tmp_path,
        monkeypatch,
        configuration(
            quota_group_rate_limits_json='{"a":{"rpm":1,"tpm":3000000},"b":{"rpm":1,"tpm":3000000}}'
        ),
        handler,
    )
    result = await post(case, json.dumps({"model": "alias", "input": "x" * (2 * MIB)}).encode())
    assert result.status_code == 429 and len(case.requests) == 1
    assert not case.credit._reservations
    await assert_clean(case)


async def test_failover_prepares_selected_second_backend_and_settles_first(tmp_path, monkeypatch):
    async def handler(request, _wire, _count):
        if request.url.host == "a.invalid":
            raise httpx.ReadError("test uncertain response", request=request)
        return httpx.Response(200, json={"usage": {"input_tokens": 5, "output_tokens": 2}})

    case = await harness(tmp_path, monkeypatch, configuration(retry_attempts=1), handler)
    result = await post(case, json.dumps({"model": "alias", "input": "x" * (2 * MIB)}).encode())
    assert result.status_code == 200
    assert [control.backend_id for control in case.controls if control.stage == "encode"] == [
        "a",
        "b",
    ]
    assert json.loads(case.requests[0][1])["model"] == "physical-a"
    assert json.loads(case.requests[1][1])["model"] == "physical-b"
    snapshots = await case.credit.live_snapshot(
        ["a", "b"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total > 1 and snapshots[
        "b"
    ].debited_usd_total == pytest.approx(0.00011)
    await assert_clean(case)


async def test_actual_asgi_send_owns_lease_until_finalization(tmp_path, monkeypatch):
    case = await harness(tmp_path, monkeypatch)
    raw = b'{"model":"alias","input":"hello"}'
    sent = asyncio.Event()
    release = asyncio.Event()
    receives = 0

    async def receive():
        nonlocal receives
        receives += 1
        if receives == 1:
            return {"type": "http.request", "body": raw, "more_body": False}
        await asyncio.Event().wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body":
            assert case.runtime.resources.active == 1
            sent.set()
            await release.wait()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/openai/v1/responses",
        "raw_path": b"/openai/v1/responses",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "client": ("test", 1),
        "server": ("test", 80),
    }
    task = asyncio.create_task(case.app(scope, receive, send))
    await asyncio.wait_for(sent.wait(), 2)
    assert receives == 1 and case.runtime.resources.active == 1
    release.set()
    await task
    await assert_clean(case)


async def test_late_encode_uses_reservation_deadline(tmp_path, monkeypatch):
    case = await harness(tmp_path, monkeypatch)
    lease = case.runtime.resources.acquire()
    await lease.write(json.dumps({"model": "alias", "input": "x" * (2 * MIB)}).encode())
    lease.started = time.monotonic() - 0.05
    prepared = await lease.prepare(
        case.runtime.policy, "responses", deadline=time.monotonic() + 0.01
    )
    intake = AzureIntakeRequest(lease, case.runtime.policy, time.monotonic() - 1, prepared=prepared)
    await asyncio.sleep(0.02)
    attempt = await intake.encode("a", time.monotonic() + 2)
    assert (
        attempt.output_bytes > 2 * MIB
        and case.controls[-1].deadline_monotonic > intake.intake_deadline
    )
    await lease.close()
    await assert_clean(case)


async def test_runtime_unavailable_start_keeps_safe_status(monkeypatch):
    config = configuration()
    runtime = AzureIntakeRuntime(config)
    monkeypatch.setattr("foundry_router.api.azure_intake.sys.platform", "darwin")
    await runtime.start(config)
    assert not runtime.matches(config)
    status = runtime.status(config)
    assert status["enabled"] and not status["ready"] and "root" not in status
    await runtime.close()


@pytest.mark.parametrize("operation", ["responses", "embeddings"])
async def test_8mib_literal_unicode_with_explicit_encoding_capacity(
    tmp_path, monkeypatch, operation
):
    case = await harness(
        tmp_path,
        monkeypatch,
        configuration(azure_max_request_body_bytes=32 * MIB, azure_intake_scratch_bytes=96 * MIB),
    )
    body = {"model": "alias", "input": "é" * (4 * MIB), "max_output_tokens": 8}
    raw = json.dumps(body, ensure_ascii=False).encode()
    assert len(raw) > 8 * MIB
    result = await post(case, raw, operation)
    assert result.status_code == 200, result.text
    assert json.loads(case.requests[0][1])["input"] == body["input"]
    assert len(case.requests[0][1]) > 24 * MIB
    assert len(case.controls) == 2
    await assert_clean(case)


async def test_unicode_encoding_cap_refuses_without_reservation(tmp_path, monkeypatch):
    case = await harness(tmp_path, monkeypatch)
    result = await post(
        case, json.dumps({"model": "alias", "input": "é" * (4 * MIB)}, ensure_ascii=False).encode()
    )
    assert result.status_code == 413 and not case.requests
    assert not case.credit._reservations
    await assert_clean(case)


class EventStream(httpx.AsyncByteStream):
    def __init__(self, fail=False):
        self.fail = fail
        self.closed = False

    async def __aiter__(self):
        if self.fail:
            raise httpx.ReadError("test pre-output uncertainty")
        yield b'data: {"type":"response.output_text.delta","delta":"hello"}\n\n'
        yield b'data: {"type":"response.completed","response":{"usage":{"input_tokens":5,"output_tokens":2}}}\n\n'
        yield b"data: [DONE]\n\n"

    async def aclose(self):
        self.closed = True


@pytest.mark.parametrize("retry", [False, True])
async def test_stream_preserves_sse_and_settles_actual_plus_unknown(tmp_path, monkeypatch, retry):
    streams = []

    async def handler(_request, _wire, count):
        stream = EventStream(fail=retry and count == 1)
        streams.append(stream)
        return httpx.Response(200, stream=stream, headers={"content-type": "text/event-stream"})

    case = await harness(tmp_path, monkeypatch, handler=handler)
    raw = json.dumps(
        {"model": "alias", "input": "x" * (2 * MIB), "stream": True, "max_output_tokens": 8}
    ).encode()
    result = await post(case, raw)
    assert result.status_code == 200 and result.content.endswith(b"data: [DONE]\n\n")
    assert result.content.count(b"response.output_text.delta") == 1
    assert len(case.requests) == 1 + int(retry)
    assert all(stream.closed for stream in streams)
    snapshot = await case.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    estimate = case.controls[-1].prepared.estimate.estimated_cost_usd
    assert snapshot["a"].debited_usd_total == pytest.approx(0.00011 + (estimate if retry else 0))
    assert not case.credit._reservations
    await assert_clean(case)


def request_scope(headers=None):
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/openai/v1/responses",
        "raw_path": b"/openai/v1/responses",
        "query_string": b"",
        "headers": headers or [(b"content-type", b"application/json")],
        "client": ("test", 1),
        "server": ("test", 80),
    }


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("stage", ["http.response.start", "http.response.body"])
async def test_actual_downstream_cancel_releases_lease_and_settles(
    tmp_path, monkeypatch, stream, stage
):
    streams = []

    async def handler(_request, _wire, _count):
        if stream:
            upstream = EventStream()
            streams.append(upstream)
            return httpx.Response(
                200, stream=upstream, headers={"content-type": "text/event-stream"}
            )
        return httpx.Response(200, json={"usage": {"input_tokens": 5, "output_tokens": 2}})

    case = await harness(tmp_path, monkeypatch, handler=handler)
    raw = json.dumps(
        {"model": "alias", "input": "x" * (2 * MIB), "stream": stream, "max_output_tokens": 8}
    ).encode()
    reached = asyncio.Event()
    receives = 0

    async def receive():
        nonlocal receives
        receives += 1
        if receives == 1:
            return {"type": "http.request", "body": raw, "more_body": False}
        await asyncio.Event().wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == stage:
            assert case.runtime.resources.active == 1
            reached.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(case.app(request_scope(), receive, send))
    await asyncio.wait_for(reached.wait(), 3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert all(upstream.closed for upstream in streams)
    assert not case.credit._reservations
    await assert_clean(case)


async def test_declared_large_cannot_extend_ordinary_intake_deadline(tmp_path, monkeypatch):
    case = await harness(
        tmp_path,
        monkeypatch,
        configuration(intake_timeout_seconds=0.1, azure_intake_timeout_seconds=1),
    )
    sent = []

    async def receive():
        await asyncio.sleep(0.15)
        return {
            "type": "http.request",
            "body": b'{"model":"alias","input":"hello"}',
            "more_body": False,
        }

    async def send(message):
        sent.append(message)

    await case.app(
        request_scope([(b"content-type", b"application/json"), (b"content-length", b"3000000")]),
        receive,
        send,
    )
    assert sent[0]["status"] == 408 and not case.requests and not case.controls
    await assert_clean(case)


async def test_child_b_timeout_before_dispatch_has_zero_cost(tmp_path, monkeypatch):
    case = await harness(tmp_path, monkeypatch)
    original = AzureIntakeLease._child

    async def timeout(lease, control, deadline):
        if control.stage == "encode":
            raise AzureIntakeError(408, "request_timeout")
        return await original(lease, control, deadline)

    monkeypatch.setattr(AzureIntakeLease, "_child", timeout)
    result = await post(case, json.dumps({"model": "alias", "input": "x" * (2 * MIB)}).encode())
    assert result.status_code == 408 and not case.requests and not case.credit._reservations
    snapshots = await case.credit.live_snapshot(
        ["a", "b"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total == snapshots["b"].debited_usd_total == 0
    await assert_clean(case)


async def test_preparation_failure_after_failover_preserves_prior_charge(tmp_path, monkeypatch):
    async def handler(request, _wire, _count):
        raise httpx.ReadError("test uncertain dispatch", request=request)

    case = await harness(tmp_path, monkeypatch, configuration(retry_attempts=1), handler)
    original = AzureIntakeLease._child

    async def fail_second(lease, control, deadline):
        if control.backend_id == "b":
            raise AzureIntakeError(503, "router_intake_unavailable")
        return await original(lease, control, deadline)

    monkeypatch.setattr(AzureIntakeLease, "_child", fail_second)
    result = await post(case, json.dumps({"model": "alias", "input": "x" * (2 * MIB)}).encode())
    assert result.status_code == 503 and len(case.requests) == 1
    snapshots = await case.credit.live_snapshot(
        ["a", "b"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total > 1 and snapshots["b"].debited_usd_total == 0
    await assert_clean(case)


@pytest.mark.parametrize(
    "provider", ["google_ai_studio", "opencode_zen", "openai_compatible", "azure_anthropic"]
)
async def test_enabled_ordinary_provider_keeps_existing_forwarding_body(
    tmp_path, monkeypatch, provider
):
    from fastapi.responses import JSONResponse

    from foundry_router.forwarding import BackendRequestResult

    endpoint = (
        "https://generativelanguage.googleapis.com"
        if provider == "google_ai_studio"
        else "https://a.invalid"
    )
    config = configuration(
        models_json=json.dumps(
            {
                "logical": {
                    "backends": {"a": 1, "b": 0.8},
                    "streaming_enabled": provider != "azure_anthropic",
                }
            }
        ),
        backends_json=json.dumps(
            {
                name: {
                    "endpoint": endpoint,
                    "credential": "test-secret",
                    "deployment": "test-model",
                    "provider": provider,
                }
                for name in ("a", "b")
            }
        ),
    )
    forwarded = []

    async def forward(**kwargs):
        forwarded.append(kwargs)
        return BackendRequestResult(
            response=JSONResponse({"usage": {"input_tokens": 5, "output_tokens": 2}}),
            retryable_failure=False,
        )

    monkeypatch.setattr(
        "foundry_router.api.routes.openai.forward_non_streaming_with_retries", forward
    )
    case = await harness(tmp_path, monkeypatch, config)
    result = await post(case, b'{ "model":"alias", "input":"hello", "max_output_tokens":8 }')
    assert result.status_code == 200, result.text
    assert len(forwarded) == 1 and forwarded[0]["body"]["model"] == "logical"
    assert "azure_intake" not in forwarded[0]
    assert not case.controls and not case.requests
    await assert_clean(case)


async def test_enabled_ordinary_spool_preserves_signed_json_offload(tmp_path, monkeypatch):

    from foundry_router.api import common
    from foundry_router.api.common import azure_request_body

    case = await harness(tmp_path, monkeypatch)
    original = common.request_body
    calls = []

    async def parse(*args, **kwargs):
        calls.append(kwargs["offload_json"])
        return await original(*args, **kwargs)

    monkeypatch.setattr(common, "request_body", parse)

    @case.fastapi.post("/capture")
    async def capture(request: Request):
        started = time.monotonic()
        context = await azure_request_body(
            request,
            "responses",
            settings=case.config,
            started=started,
            ordinary_deadline=started + 3,
            offload_json=True,
        )
        try:
            return context.body
        finally:
            await context.lease.close()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=case.app), base_url="http://test"
    ) as client:
        result = await client.post(
            "/capture",
            content=b'{ "model":"alias", "input":"hello" }',
            headers={"content-type": "application/json"},
        )
    assert result.status_code == 200 and result.json() == {"model": "alias", "input": "hello"}
    assert calls and all(calls)
    await assert_clean(case)


@pytest.mark.parametrize("stream", [False, True])
async def test_slow_downstream_send_is_bounded_by_reservation(tmp_path, monkeypatch, stream):
    streams = []

    async def handler(_request, _wire, _count):
        if stream:
            upstream = EventStream()
            streams.append(upstream)
            return httpx.Response(200, stream=upstream)
        return httpx.Response(200, json={"usage": {"input_tokens": 5, "output_tokens": 2}})

    case = await harness(
        tmp_path, monkeypatch, configuration(reservation_max_age_seconds=1), handler
    )
    raw = json.dumps(
        {"model": "alias", "input": "x" * (2 * MIB), "stream": stream, "max_output_tokens": 8}
    ).encode()
    receives = 0

    async def receive():
        nonlocal receives
        receives += 1
        if receives == 1:
            return {"type": "http.request", "body": raw, "more_body": False}
        await asyncio.Event().wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body":
            await asyncio.Event().wait()

    started = time.monotonic()
    with pytest.raises((TimeoutError, BaseExceptionGroup)):
        await asyncio.wait_for(case.app(request_scope(), receive, send), 2)
    assert time.monotonic() - started < 1.5
    assert all(upstream.closed for upstream in streams)
    assert not case.credit._reservations
    await assert_clean(case)


@pytest.mark.parametrize(
    "field,value",
    [
        ("azure_intake_scratch_bytes", True),
        ("azure_intake_scratch_bytes", 1048576.0),
        ("azure_intake_child_wall_timeout_seconds", True),
        ("azure_intake_child_wall_timeout_seconds", float("inf")),
        ("azure_intake_child_wall_timeout_seconds", 0.01),
    ],
)
def test_new_resource_budgets_reject_invalid_types(field, value):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        configuration(**{field: value})


async def test_one_recovery_task_returns_only_proven_capacity(tmp_path, monkeypatch):
    case = await harness(tmp_path, monkeypatch)
    lease = case.runtime.resources.acquire()
    await lease.write(b"temporary")
    case.runtime._probe_verified = True
    case.runtime._available = False
    case.runtime.resources.uncertain.add(lease)
    case.runtime.recover()
    recovery = case.runtime._recovery
    case.runtime.recover()
    assert case.runtime._recovery is recovery
    await recovery
    assert case.runtime.matches(case.config)
    await assert_clean(case)


@pytest.mark.parametrize("operation", ["responses", "embeddings"])
@pytest.mark.parametrize("stage", ["health", "combination"])
@pytest.mark.parametrize("usage", [False, True])
async def test_completed_success_cancellation_retains_billable_amount(
    tmp_path, monkeypatch, operation, stage, usage
):
    async def handler(_request, _wire, _count):
        return httpx.Response(
            200, json={"usage": {"input_tokens": 5, "output_tokens": 2}} if usage else {"ok": True}
        )

    case = await harness(
        tmp_path,
        monkeypatch,
        configuration(
            quota_group_rate_limits_json='{"a":{"rpm":10,"tpm":3000000},"b":{"rpm":10,"tpm":3000000}}'
        ),
        handler,
    )
    reached = asyncio.Event()

    async def block(*_args, **_kwargs):
        reached.set()
        await asyncio.Event().wait()

    if stage == "health":
        monkeypatch.setattr(case.health, "set_backend_active", block)
    else:
        monkeypatch.setattr("foundry_router.routing._record_combination_attempt", block)
    raw = json.dumps({"model": "alias", "input": "x" * (2 * MIB), "max_output_tokens": 8}).encode()
    task = asyncio.create_task(post(case, raw, operation))
    await asyncio.wait_for(reached.wait(), 3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(case.requests) == 1 and not case.credit._reservations
    frozen = case.controls[-1].prepared.estimate
    snapshots = await case.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total == pytest.approx(
        0.00011 if usage else frozen.estimated_cost_usd
    )
    quotas = await case.quota.snapshot_quota_groups(["a"])
    assert quotas["a"].rpm_used_60s == 1
    assert quotas["a"].input_tpm_used_60s == (5 if usage else frozen.input_tokens)
    await assert_clean(case)


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("stage", ["credit", "quota", "metrics"])
async def test_cancellation_during_success_financial_awaits_keeps_usage(
    tmp_path, monkeypatch, stream, stage
):
    streams = []

    async def handler(_request, _wire, _count):
        if stream:
            events = EventStream()
            streams.append(events)
            return httpx.Response(200, stream=events)
        return httpx.Response(200, json={"usage": {"input_tokens": 5, "output_tokens": 2}})

    case = await harness(
        tmp_path,
        monkeypatch,
        configuration(
            quota_group_rate_limits_json='{"a":{"rpm":10,"tpm":3000000},"b":{"rpm":10,"tpm":3000000}}'
        ),
        handler,
    )
    reached = asyncio.Event()
    release = asyncio.Event()
    target = case.credit if stage == "credit" else case.quota if stage == "quota" else case.metrics
    name = "observe_request" if stage == "metrics" else "finalize_request"
    original = getattr(target, name)

    async def block(*args, **kwargs):
        reached.set()
        await release.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(target, name, block)
    raw = json.dumps(
        {"model": "alias", "input": "x" * (2 * MIB), "stream": stream, "max_output_tokens": 8}
    ).encode()
    task = asyncio.create_task(post(case, raw))
    await asyncio.wait_for(reached.wait(), 3)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert all(events.closed for events in streams)
    snapshots = await case.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total == pytest.approx(0.00011)
    quotas = await case.quota.snapshot_quota_groups(["a"])
    assert quotas["a"].rpm_used_60s == 1 and quotas["a"].input_tpm_used_60s == 5
    assert not case.credit._reservations
    await assert_clean(case)


@pytest.mark.parametrize("stage", ["health", "combination"])
async def test_prefetched_stream_cancel_closes_upstream_before_lease_release(
    tmp_path, monkeypatch, stage
):
    streams = []

    async def handler(_request, _wire, _count):
        events = EventStream()
        streams.append(events)
        return httpx.Response(200, stream=events)

    case = await harness(tmp_path, monkeypatch, handler=handler)
    reached = asyncio.Event()

    async def block(*_args, **_kwargs):
        reached.set()
        await asyncio.Event().wait()

    if stage == "health":
        monkeypatch.setattr(case.health, "set_backend_active", block)
    else:
        monkeypatch.setattr("foundry_router.routing._record_combination_attempt", block)
    raw = json.dumps(
        {"model": "alias", "input": "x" * (2 * MIB), "stream": True, "max_output_tokens": 8}
    ).encode()
    task = asyncio.create_task(post(case, raw))
    await asyncio.wait_for(reached.wait(), 3)
    assert case.runtime.resources.active == 1 and not streams[0].closed
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert streams[0].closed
    snapshots = await case.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total == pytest.approx(
        case.controls[-1].prepared.estimate.estimated_cost_usd
    )
    await assert_clean(case)


async def test_zero_price_uploaded_timeout_keeps_quota_consumption(tmp_path, monkeypatch):
    async def handler(_request, _wire, _count):
        await asyncio.Event().wait()

    config = configuration(
        pricing_json='{"logical":{"input_per_million":0,"output_per_million":0}}',
        quota_group_rate_limits_json='{"a":{"rpm":10,"tpm":3000000},"b":{"rpm":10,"tpm":3000000}}',
        reservation_max_age_seconds=1,
    )
    case = await harness(tmp_path, monkeypatch, config, handler)
    result = await post(case, json.dumps({"model": "alias", "input": "x" * (2 * MIB)}).encode())
    assert result.status_code == 502 and len(case.requests) == 1
    quotas = await case.quota.snapshot_quota_groups(["a"])
    assert quotas["a"].rpm_used_60s == 1
    assert quotas["a"].input_tpm_used_60s == case.controls[-1].prepared.estimate.input_tokens
    snapshots = await case.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total == 0 and not case.credit._reservations
    await assert_clean(case)


@pytest.mark.parametrize("shared,limited", [(False, "a"), (False, "b"), (True, "a")])
async def test_failover_quota_binding_counts_only_the_selected_group(
    tmp_path, monkeypatch, shared, limited
):
    from foundry_router.health import BackendHealthState

    values = {}
    if shared:
        values["backends_json"] = json.dumps(
            {
                name: {
                    "endpoint": f"https://{name}.invalid",
                    "credential": "test-secret",
                    "deployment": f"physical-{name}",
                    "quota_group": "shared",
                }
                for name in ("a", "b")
            }
        )
        values["quota_group_rate_limits_json"] = '{"shared":{"rpm":20,"tpm":3000000}}'
    else:
        values["quota_group_rate_limits_json"] = json.dumps({limited: {"rpm": 20, "tpm": 3000000}})

    async def handler(request, _wire, count):
        if count < 4:
            if count == 2:
                await case.health.set_backend_active("b")
            raise httpx.ReadError("test uncertain dispatch", request=request)
        return httpx.Response(200, json={"usage": {"input_tokens": 5, "output_tokens": 2}})

    case = await harness(tmp_path, monkeypatch, configuration(**values), handler)
    await case.health.set_backend_cooldown(
        "b", state=BackendHealthState.ERROR_COOLDOWN, cooldown_seconds=30
    )
    result = await post(
        case,
        json.dumps({"model": "alias", "input": "x" * (2 * MIB), "max_output_tokens": 8}).encode(),
    )
    assert result.status_code == 200
    assert [request.url.host for request, _wire in case.requests] == [
        "a.invalid",
        "a.invalid",
        "b.invalid",
        "b.invalid",
    ]
    group = "shared" if shared else limited
    quotas = await case.quota.snapshot_quota_groups([group])
    frozen = case.controls[-1].prepared.estimate
    assert quotas[group].rpm_used_60s == (4 if shared else 2)
    assert quotas[group].input_tpm_used_60s == (
        3 * frozen.input_tokens + 5
        if shared
        else 2 * frozen.input_tokens
        if limited == "a"
        else frozen.input_tokens + 5
    )
    await assert_clean(case)


@pytest.mark.parametrize("operation", ["responses", "embeddings"])
@pytest.mark.parametrize("enabled", [False, True])
async def test_empty_body_keeps_ordinary_400_parity(tmp_path, monkeypatch, operation, enabled):
    case = await harness(tmp_path, monkeypatch, configuration(azure_intake_enabled=enabled))
    result = await post(case, b"", operation)
    assert result.status_code == 400 and result.json()["error"]["type"] == "invalid_request"
    assert not case.requests and not case.controls
    await assert_clean(case)


async def test_recovery_cannot_reopen_closed_runtime(tmp_path, monkeypatch):
    case = await harness(tmp_path, monkeypatch)
    case.runtime._probe_verified = True
    case.runtime._recovery = asyncio.create_task(case.runtime._recover())
    await case.runtime.close()
    assert not case.runtime.ready and not case.runtime.matches(case.config)
    with pytest.raises(AzureIntakeError):
        case.runtime.resources.acquire()
    recovery = case.runtime._recovery
    case.runtime.recover()
    await case.runtime.start(case.config)
    assert case.runtime._recovery is recovery and not case.runtime.ready
    await assert_clean(case)


async def test_uncertain_delivery_cleanup_retains_capacity_until_proved(tmp_path, monkeypatch):
    case = await harness(tmp_path, monkeypatch)
    lease = case.runtime.resources.acquire()
    await lease.write(b"temporary")
    attempts = 0

    async def cleanup():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("test unproved response close")

    lease.delivery_cleanup = cleanup
    assert not await lease.close()
    assert case.runtime.resources.active == 1 and not case.runtime.matches(case.config)
    assert await lease.close() and attempts == 2
    await assert_clean(case)


async def test_failed_recovery_during_shutdown_stays_unavailable(tmp_path, monkeypatch):
    case = await harness(tmp_path, monkeypatch)
    case.runtime._root = case.runtime.resources.root
    lease = case.runtime.resources.acquire()
    await lease.write(b"temporary")
    entered = asyncio.Event()
    release = asyncio.Event()
    confirmed = False

    async def cleanup():
        if not confirmed:
            entered.set()
            await release.wait()
            raise RuntimeError("test unproved response close")

    lease.delivery_cleanup = cleanup
    case.runtime.resources.uncertain.add(lease)
    case.runtime._probe_verified = True
    case.runtime.recover()
    await asyncio.wait_for(entered.wait(), 2)
    shutdown = asyncio.create_task(case.runtime.close())
    await asyncio.sleep(0)
    assert not case.runtime.matches(case.config)
    with pytest.raises(AzureIntakeError):
        case.runtime.resources.acquire()
    release.set()
    await shutdown
    assert not case.runtime.ready and case.runtime.resources.active == 1
    assert case.runtime._root.exists()
    recovery = case.runtime._recovery
    case.runtime.recover()
    await case.runtime.start(case.config)
    assert case.runtime._recovery is recovery and not case.runtime.ready
    confirmed = True
    await case.runtime.close()
    assert case.runtime.resources.active == 0 and not case.runtime.resources.leases
    assert case.runtime.resources.scratch_reserved == 0
    assert not case.runtime.resources.root.exists() and case.runtime._root is None
    await case.client.aclose()
