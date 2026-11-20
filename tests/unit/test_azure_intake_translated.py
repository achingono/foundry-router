"""Prepared Azure translated input budgets, response bindings and financial ownership."""

import asyncio
import base64
import dataclasses
import hashlib
import json
from types import SimpleNamespace
from typing import ClassVar

import httpx
import pytest
from pydantic import ValidationError

from foundry_router.api.adapters import get_adapter
from foundry_router.api.azure_intake import (
    METADATA_BYTES,
    POLICY_BYTES,
    AzureIntakeLease,
    AzureIntakePolicy,
    _WorkerControl,
    _WorkerReply,
)
from foundry_router.api.azure_intake_context import PreparedAzureResponseContext
from foundry_router.api.google_output_delivery import GeneratedOutputDeliveryMiddleware
from foundry_router.api.google_output_png import inspect_output_png
from tests.unit.test_azure_intake_runtime import MIB, assert_clean, configuration, harness, post
from tests.unit.test_google_output_png import png


def config(provider, **overrides):
    values = {
        "models_json": '{"logical":{"backends":{"a":1,"b":1},"streaming_enabled":false}}',
        "backends_json": json.dumps(
            {
                name: {
                    "endpoint": f"https://{name}.invalid",
                    "credential": "test-secret",
                    "deployment": f"physical-{name}",
                    "provider": provider,
                }
                for name in ("a", "b")
            }
        ),
    }
    if provider == "azure_mai":
        values["pricing_json"] = (
            '{"logical":{"input_per_million":0,"output_per_million":0,"image_output_per_image":0.1}}'
        )
    values.update(overrides)
    return configuration(**values)


def body(provider, *, text=None, metadata=None):
    value = {
        "input": text or "x" * (2 * MIB),
        "metadata": metadata or {"note": "ok"},
        "model": "alias",
    }
    if provider == "azure_mai":
        value["tools"] = [{"type": "image_generation", "output_format": "png", "size": "1024x1024"}]
    else:
        value["max_output_tokens"] = 8
    return value


def anthropic(*, refusal=False, text="ok", usage=True):
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "physical-a",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "refusal" if refusal else "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 5, "output_tokens": 2} if usage else None,
    }


class Inspector:
    instances: ClassVar[list] = []

    def __init__(self, **_kwargs):
        self.closed = False
        self.delivery_deadline = None
        self.inspected = []
        self.instances.append(self)

    async def ready(self, **_kwargs):
        return True

    def bind_delivery_deadline(self, deadline):
        self.delivery_deadline = deadline

    async def inspect(self, raw, **_kwargs):
        self.inspected.append(raw)
        return SimpleNamespace(
            **{
                **inspect_output_png(raw),
                "decoded_bytes": len(raw),
                "digest": hashlib.sha256(raw).hexdigest(),
            }
        )

    def close(self):
        self.closed = True


def inspect_fixture(monkeypatch):
    Inspector.instances = []
    monkeypatch.setattr("foundry_router.api.routes.openai.sys.platform", "linux")
    monkeypatch.setattr("foundry_router.api.routes.openai.OutputInspectionLease", Inspector)


@pytest.mark.parametrize("provider", ["azure_anthropic", "azure_mai"])
@pytest.mark.parametrize("unicode", [False, True])
async def test_above_limit_translated_bytes_and_bounded_response_context(
    tmp_path, monkeypatch, provider, unicode
):
    inspect_fixture(monkeypatch)
    raw_png = png()

    async def handler(_request, _wire, _count):
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(raw_png).decode()}]}
            if provider == "azure_mai"
            else anthropic(),
        )

    case = await harness(tmp_path, monkeypatch, config(provider), handler)
    case.fastapi.add_middleware(GeneratedOutputDeliveryMiddleware)
    metadata = {str(index) + "😀" * 62: "😀" * 512 for index in range(16)}
    payload = body(provider, text="é" * (MIB + 10) if unicode else None, metadata=metadata)
    result = await post(case, json.dumps(payload, ensure_ascii=False).encode())
    assert result.status_code == 200, result.text
    assert result.json()["metadata"] == metadata and result.json()["model"] == "logical"
    request, wire = case.requests[0]
    assert int(request.headers["content-length"]) == len(wire)
    expected = get_adapter(
        provider, azure_request_text_budget=case.config.azure_effective_max_request_body_bytes
    ).build_upstream_body(
        "responses",
        {**payload, "model": "logical"},
        deployment="physical-a",
        default_output_tokens=4096,
    )
    assert wire == json.dumps(expected).encode()
    prepared = case.controls[0].prepared or case.controls[1].prepared
    context = prepared.response_context
    assert (
        context.model == "logical"
        and context.input_digest
        == hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()
    )
    assert len(context.model_dump_json().encode()) < 65536
    assert len(context.metadata) == 16 and "input" not in context.model_dump()
    snapshots = await case.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total == pytest.approx(
        0.1 if provider == "azure_mai" else 0.00011
    )
    if provider == "azure_mai":
        assert Inspector.instances[0].inspected == [raw_png] and Inspector.instances[0].closed
        assert result.json()["output"][0]["result"] == base64.b64encode(raw_png).decode()
    await assert_clean(case)


@pytest.mark.parametrize("provider", ["azure_anthropic", "azure_mai"])
def test_effective_budget_is_immutable_and_all_rechecks_use_it(provider):
    large = body(provider)
    large["model"] = "logical"
    ordinary = get_adapter(provider)
    small = get_adapter(provider, azure_request_text_budget=64)
    large_adapter = get_adapter(provider, azure_request_text_budget=4 * MIB)
    assert ordinary.check_request("responses", large) is not None
    assert small.check_request("responses", large) is not None
    with pytest.raises(ValueError):
        small.build_upstream_body("responses", large, deployment="d", default_output_tokens=8)
    assert large_adapter.check_request("responses", large) is None
    assert (
        large_adapter.build_upstream_body(
            "responses", large, deployment="d", default_output_tokens=8
        )["model"]
        == "d"
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        large_adapter.request_text_budget = 99
    assert (
        get_adapter(provider) is ordinary and ordinary.check_request("responses", large) is not None
    )


@pytest.mark.parametrize(
    "provider",
    ["azure_foundry", "openai_compatible", "opencode_anthropic", "opencode_google", "openrouter"],
)
def test_other_provider_budget_override_refused(provider):
    with pytest.raises(ValueError):
        get_adapter(provider, azure_request_text_budget=4 * MIB)


@pytest.mark.parametrize("provider", ["azure_anthropic", "azure_mai"])
@pytest.mark.parametrize("feature", ["stream", "media", "tool"])
async def test_enlargement_preserves_unsupported_feature_refusal(
    tmp_path, monkeypatch, provider, feature
):
    case = await harness(tmp_path, monkeypatch, config(provider))
    payload = body(provider)
    if feature == "stream":
        payload["stream"] = True
    elif feature == "media":
        payload["input"] = [
            {
                "role": "user",
                "content": [{"type": "input_image", "image_url": "data:image/png;base64,eA=="}],
            }
        ]
        payload["metadata"] = {"padding": "x" * (2 * MIB)}
    else:
        payload["tools"] = [{"type": "function", "name": "test", "parameters": {}}]
    result = await post(case, json.dumps(payload).encode())
    assert result.status_code == 413 and not case.requests and not case.credit._reservations
    await assert_clean(case)


@pytest.mark.parametrize("field", ["policy_digest", "input_digest", "model", "policies"])
async def test_prepared_context_tampering_refused_before_reservation(tmp_path, monkeypatch, field):
    case = await harness(tmp_path, monkeypatch, config("azure_anthropic"))
    child = AzureIntakeLease._child

    async def tamper(lease, control, deadline):
        reply = await child(lease, control, deadline)
        if control.stage == "prepare":
            context = reply.prepared.response_context
            changed = (
                "0" * 64
                if field.endswith("digest")
                else "wrong"
                if field == "model"
                else tuple(
                    policy.model_copy(update={"provider": "azure_mai", "kind": "one_png"})
                    for policy in context.policies
                )
            )
            context = context.model_copy(update={field: changed})
            return reply.model_copy(
                update={"prepared": reply.prepared.model_copy(update={"response_context": context})}
            )
        return reply

    monkeypatch.setattr(AzureIntakeLease, "_child", tamper)
    result = await post(case, json.dumps(body("azure_anthropic")).encode())
    assert result.status_code == 503 and not case.requests and not case.credit._reservations
    await assert_clean(case)


async def test_selected_attempt_context_digest_tampering_refused(tmp_path, monkeypatch):
    case = await harness(tmp_path, monkeypatch, config("azure_anthropic"))
    child = AzureIntakeLease._child

    async def tamper(lease, control, deadline):
        reply = await child(lease, control, deadline)
        if control.stage == "encode":
            return reply.model_copy(
                update={
                    "attempt": reply.attempt.model_copy(
                        update={"response_context_digest": "0" * 64}
                    )
                }
            )
        return reply

    monkeypatch.setattr(AzureIntakeLease, "_child", tamper)
    result = await post(case, json.dumps(body("azure_anthropic")).encode())
    assert result.status_code == 503 and not case.requests and not case.credit._reservations
    await assert_clean(case)


@pytest.mark.parametrize("refusal,invalid", [(False, False), (True, False), (False, True)])
async def test_anthropic_usage_refusal_and_invalid_output_keep_actual_charge(
    tmp_path, monkeypatch, refusal, invalid
):
    async def handler(_request, _wire, _count):
        return httpx.Response(200, json=anthropic(refusal=refusal, text="" if invalid else "ok"))

    case = await harness(tmp_path, monkeypatch, config("azure_anthropic"), handler)
    result = await post(case, json.dumps(body("azure_anthropic")).encode())
    assert result.status_code == (502 if invalid else 200)
    snapshots = await case.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total == pytest.approx(0.00011)
    await assert_clean(case)


async def test_translated_success_cancellation_at_health_keeps_charge_and_closes_context(
    tmp_path, monkeypatch
):
    async def handler(_request, _wire, _count):
        return httpx.Response(200, json=anthropic())

    case = await harness(tmp_path, monkeypatch, config("azure_anthropic"), handler)
    entered = asyncio.Event()

    async def block(*_args):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(case.health, "set_backend_active", block)
    task = asyncio.create_task(post(case, json.dumps(body("azure_anthropic")).encode()))
    await asyncio.wait_for(entered.wait(), 3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    snapshots = await case.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total == pytest.approx(0.00011)
    await assert_clean(case)


async def test_nonbmp_context_and_near_limit_policy_fit_complete_child_envelopes(
    tmp_path, monkeypatch
):
    case = await harness(tmp_path, monkeypatch, config("azure_anthropic"))
    document = case.runtime.policy.document.model_dump()
    document["aliases"].update({f"alias{index}" + "x" * 240: "logical" for index in range(120)})
    policy = AzureIntakePolicy(json.dumps(document, sort_keys=True, separators=(",", ":")).encode())
    assert 30000 < len(policy.wire) < POLICY_BYTES
    lease = case.runtime.resources.acquire()
    metadata = {str(index) + "😀" * 62: "😀" * 512 for index in range(16)}
    await lease.write(
        json.dumps(body("azure_anthropic", metadata=metadata), ensure_ascii=False).encode()
    )
    prepared = await lease.prepare(policy, "responses", deadline=lease.started + 5)
    control = lease._control(policy, "responses", lease.started + 5, backend_id="a")
    raw = control.model_dump_json().encode()
    assert 65536 < len(raw) < METADATA_BYTES
    assert _WorkerControl.model_validate_json(raw) == control
    reply = _WorkerReply(prepared=prepared).model_dump_json().encode()
    assert (
        len(reply) < METADATA_BYTES and _WorkerReply.model_validate_json(reply).prepared == prepared
    )
    await lease.close()
    await assert_clean(case)


@pytest.mark.parametrize(
    "metadata", [[("x", "a" * 513)], [("x" * 65, "a")], [("x", "a"), ("x", "b")]]
)
def test_response_context_keeps_metadata_shape_limits(metadata):
    with pytest.raises(ValidationError):
        PreparedAzureResponseContext.model_validate(
            {
                "policy_digest": "0" * 64,
                "input_digest": "1" * 64,
                "model": "logical",
                "operation": "responses",
                "metadata": tuple(metadata),
                "policies": ({"backend_id": "a", "provider": "azure_anthropic", "kind": "text"},),
            }
        )


@pytest.mark.parametrize("provider", ["azure_anthropic", "azure_mai"])
async def test_translated_unknown_retry_failover_retains_each_upload_liability(
    tmp_path, monkeypatch, provider
):
    from foundry_router.health import BackendHealthState

    inspect_fixture(monkeypatch)

    async def handler(request, _wire, count):
        if count <= 2:
            if count == 2:
                await case.health.set_backend_active("b")
            raise httpx.ReadError("synthetic uncertain upload", request=request)
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(png()).decode()}]}
            if provider == "azure_mai"
            else anthropic(),
        )

    case = await harness(
        tmp_path,
        monkeypatch,
        config(
            provider,
            quota_group_rate_limits_json='{"a":{"rpm":10,"tpm":3000000},"b":{"rpm":10,"tpm":3000000}}',
        ),
        handler,
    )
    case.fastapi.add_middleware(GeneratedOutputDeliveryMiddleware)
    await case.health.set_backend_cooldown(
        "b", state=BackendHealthState.ERROR_COOLDOWN, cooldown_seconds=30
    )
    result = await post(case, json.dumps(body(provider)).encode())
    assert result.status_code == 200
    assert [request.url.host for request, _wire in case.requests] == [
        "a.invalid",
        "a.invalid",
        "b.invalid",
    ]
    assert case.requests[0][1] == case.requests[1][1] and case.requests[1][1] != case.requests[2][1]
    frozen = case.controls[1].prepared.estimate
    snapshots = await case.credit.live_snapshot(
        ["a", "b"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total == pytest.approx(2 * frozen.estimated_cost_usd)
    assert snapshots["b"].debited_usd_total == pytest.approx(
        0.1 if provider == "azure_mai" else 0.00011
    )
    quotas = await case.quota.snapshot_quota_groups(["a", "b"])
    assert quotas["a"].rpm_used_60s == 2 and quotas["b"].rpm_used_60s == 1
    await assert_clean(case)


@pytest.mark.parametrize("status", [400, 429])
async def test_translated_provider_errors_and_http_retry_keep_correct_charge(
    tmp_path, monkeypatch, status
):
    async def handler(_request, _wire, count):
        if count == 1:
            return httpx.Response(
                status, json={"error": "synthetic rejection"}, headers={"retry-after": "0.001"}
            )
        return httpx.Response(200, json=anthropic())

    case = await harness(
        tmp_path,
        monkeypatch,
        config(
            "azure_anthropic",
            quota_group_rate_limits_json='{"a":{"rpm":10,"tpm":3000000},"b":{"rpm":10,"tpm":3000000}}',
        ),
        handler,
    )
    result = await post(case, json.dumps(body("azure_anthropic")).encode())
    assert result.status_code == (200 if status == 429 else 502)
    snapshots = await case.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total == pytest.approx(0.00011 if status == 429 else 0)
    quotas = await case.quota.snapshot_quota_groups(["a"])
    assert quotas["a"].rpm_used_60s == (2 if status == 429 else 1)
    await assert_clean(case)


async def test_mai_invalid_png_retains_image_liability(tmp_path, monkeypatch):
    inspect_fixture(monkeypatch)

    async def handler(_request, _wire, _count):
        return httpx.Response(
            200, json={"data": [{"b64_json": base64.b64encode(b"not png").decode()}]}
        )

    case = await harness(tmp_path, monkeypatch, config("azure_mai"), handler)
    result = await post(case, json.dumps(body("azure_mai")).encode())
    assert result.status_code == 502 and Inspector.instances[0].closed
    snapshots = await case.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total == pytest.approx(0.1)
    await assert_clean(case)


async def test_mai_probe_cancellation_releases_output_lease_before_credit(tmp_path, monkeypatch):
    inspect_fixture(monkeypatch)
    reached = asyncio.Event()

    async def ready(_self, **_kwargs):
        reached.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(Inspector, "ready", ready)
    case = await harness(tmp_path, monkeypatch, config("azure_mai"))
    task = asyncio.create_task(post(case, json.dumps(body("azure_mai")).encode()))
    await asyncio.wait_for(reached.wait(), 3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert Inspector.instances[0].closed and not case.requests and not case.credit._reservations
    await assert_clean(case)


@pytest.mark.parametrize("mode", ["instructions", "parts"])
def test_inherited_text_aggregation_uses_the_request_budget(mode):
    adapter = get_adapter("azure_anthropic", azure_request_text_budget=64)
    payload = {"model": "logical", "input": "x" * 33}
    if mode == "instructions":
        payload["instructions"] = "y" * 33
    else:
        payload["input"] = [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "x" * 33},
                    {"type": "input_text", "text": "y" * 33},
                ],
            }
        ]
    assert adapter.check_request("responses", payload) is not None
    with pytest.raises(ValueError):
        adapter.build_upstream_body("responses", payload, deployment="d", default_output_tokens=8)


@pytest.mark.parametrize("provider", ["azure_anthropic", "azure_mai"])
@pytest.mark.parametrize("exhausted", [False, True])
async def test_ambiguous_5xx_retains_each_uploaded_estimate(
    tmp_path, monkeypatch, provider, exhausted
):
    inspect_fixture(monkeypatch)

    async def handler(_request, _wire, count):
        if exhausted or count == 1:
            return httpx.Response(500, json={"error": "synthetic ambiguous generation failure"})
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(png()).decode()}]}
            if provider == "azure_mai"
            else anthropic(),
        )

    case = await harness(
        tmp_path,
        monkeypatch,
        config(
            provider,
            quota_group_rate_limits_json='{"a":{"rpm":10,"tpm":3000000},"b":{"rpm":10,"tpm":3000000}}',
        ),
        handler,
    )
    case.fastapi.add_middleware(GeneratedOutputDeliveryMiddleware)
    result = await post(case, json.dumps(body(provider)).encode())
    assert result.status_code == (500 if exhausted else 200)
    assert len(case.requests) == (4 if exhausted else 2)
    frozen = case.controls[1].prepared.estimate
    snapshots = await case.credit.live_snapshot(
        ["a", "b"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    if exhausted:
        assert snapshots["a"].debited_usd_total == pytest.approx(2 * frozen.estimated_cost_usd)
        assert snapshots["b"].debited_usd_total == pytest.approx(2 * frozen.estimated_cost_usd)
    else:
        assert snapshots["a"].debited_usd_total == pytest.approx(
            frozen.estimated_cost_usd + (0.1 if provider == "azure_mai" else 0.00011)
        )
        assert snapshots["b"].debited_usd_total == 0
    quotas = await case.quota.snapshot_quota_groups(["a", "b"])
    assert quotas["a"].rpm_used_60s == 2
    assert quotas["b"].rpm_used_60s == (2 if exhausted else 0)
    assert not case.credit._reservations
    await assert_clean(case)


@pytest.mark.parametrize("provider", ["azure_anthropic", "azure_mai"])
@pytest.mark.parametrize("status", [200, 400, 500])
@pytest.mark.parametrize("error_type", [httpx.ReadError, TimeoutError])
async def test_context_exit_failure_is_terminal_and_retains_owner_until_proof(
    tmp_path, monkeypatch, provider, status, error_type
):
    inspect_fixture(monkeypatch)

    async def handler(_request, _wire, _count):
        payload = (
            {"data": [{"b64_json": base64.b64encode(png()).decode()}]}
            if provider == "azure_mai"
            else anthropic()
        )
        return httpx.Response(
            status, json=payload if status == 200 else {"error": "synthetic rejection"}
        )

    case = await harness(
        tmp_path,
        monkeypatch,
        config(
            provider,
            quota_group_rate_limits_json='{"a":{"rpm":10,"tpm":3000000},"b":{"rpm":10,"tpm":3000000}}',
        ),
        handler,
    )
    case.fastapi.add_middleware(GeneratedOutputDeliveryMiddleware)
    original = case.client.stream_backend
    state = {"proved": False, "calls": 0}

    class ExitFailure:
        def __init__(self, context):
            self.context = context

        async def __aenter__(self):
            return await self.context.__aenter__()

        async def __aexit__(self, *args):
            state["calls"] += 1
            if not state["proved"]:
                raise error_type("synthetic unproved context close")
            return await self.context.__aexit__(*args)

    monkeypatch.setattr(
        case.client,
        "stream_backend",
        lambda *args, **kwargs: ExitFailure(original(*args, **kwargs)),
    )
    result = await post(case, json.dumps(body(provider)).encode())
    assert result.status_code == 502 and len(case.requests) == 1
    resources = case.runtime.resources
    lease = next(iter(resources.leases))
    callback = lease.delivery_cleanup
    assert resources.active == 1 and lease in resources.uncertain
    assert callback is not None and not case.runtime.matches(case.config)
    assert lease.input_path.exists() and lease.output_path.exists()
    assert not case.credit._reservations
    frozen = case.controls[1].prepared.estimate
    snapshots = await case.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    expected = (
        (0.1 if provider == "azure_mai" else 0.00011)
        if status == 200
        else frozen.estimated_cost_usd
        if status == 500
        else 0
    )
    assert snapshots["a"].debited_usd_total == pytest.approx(expected)
    quotas = await case.quota.snapshot_quota_groups(["a"])
    assert quotas["a"].rpm_used_60s == 1
    assert not await lease.close() and lease.delivery_cleanup is callback and resources.active == 1
    state["proved"] = True
    assert await lease.close()
    assert resources.active == 0 and not resources.uncertain
    await assert_clean(case)


@pytest.mark.parametrize("status", [200, 400])
async def test_delayed_unproved_close_keeps_one_exact_producer_task(tmp_path, monkeypatch, status):
    monkeypatch.setattr("foundry_router.forwarding.DEFAULT_CLEANUP_TIMEOUT_SECONDS", 0.01)

    async def handler(_request, _wire, _count):
        return httpx.Response(
            status, json=anthropic() if status == 200 else {"error": "synthetic rejection"}
        )

    case = await harness(tmp_path, monkeypatch, config("azure_anthropic"), handler)
    original = case.client.stream_backend
    release = asyncio.Event()
    calls = 0

    class DelayedExit:
        def __init__(self, context):
            self.context = context

        async def __aenter__(self):
            return await self.context.__aenter__()

        async def __aexit__(self, *args):
            nonlocal calls
            calls += 1
            await release.wait()
            return await self.context.__aexit__(*args)

    monkeypatch.setattr(
        case.client,
        "stream_backend",
        lambda *args, **kwargs: DelayedExit(original(*args, **kwargs)),
    )
    result = await post(case, json.dumps(body("azure_anthropic")).encode())
    assert result.status_code == 502 and len(case.requests) == 1 and calls == 1
    lease = next(iter(case.runtime.resources.leases))
    owner = lease.delivery_cleanup.__self__
    task = owner._task
    assert not task.done() and not owner.closed and case.runtime.resources.active == 1
    assert not await lease.close()
    assert owner._task is task and calls == 1 and case.runtime.resources.active == 1
    assert lease.input_path.exists() and lease.output_path.exists()
    release.set()
    await asyncio.wait_for(asyncio.shield(task), 1)
    assert owner.closed and await lease.close() and calls == 1
    snapshots = await case.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert snapshots["a"].debited_usd_total == pytest.approx(0.00011 if status == 200 else 0)
    await assert_clean(case)


async def test_repeated_cancellation_during_close_retains_actual_settlement_and_owner(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("foundry_router.forwarding.DEFAULT_CLEANUP_TIMEOUT_SECONDS", 0.02)

    async def handler(_request, _wire, _count):
        return httpx.Response(200, json=anthropic())

    case = await harness(tmp_path, monkeypatch, config("azure_anthropic"), handler)
    original = case.client.stream_backend
    entered = asyncio.Event()
    release = asyncio.Event()

    class CancelledExit:
        def __init__(self, context):
            self.context = context

        async def __aenter__(self):
            return await self.context.__aenter__()

        async def __aexit__(self, *args):
            entered.set()
            await release.wait()
            return await self.context.__aexit__(*args)

    monkeypatch.setattr(
        case.client,
        "stream_backend",
        lambda *args, **kwargs: CancelledExit(original(*args, **kwargs)),
    )
    task = asyncio.create_task(post(case, json.dumps(body("azure_anthropic")).encode()))
    await asyncio.wait_for(entered.wait(), 3)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(case.requests) == 1 and case.runtime.resources.active == 1
    lease = next(iter(case.runtime.resources.leases))
    owner = lease.delivery_cleanup.__self__
    assert not owner._task.done()
    snapshots = await case.credit.live_snapshot(
        ["a"], min_credit_reserve_usd=0, min_credit_reserve_percent=0
    )
    assert (
        snapshots["a"].debited_usd_total == pytest.approx(0.00011) and not case.credit._reservations
    )
    release.set()
    await asyncio.wait_for(asyncio.shield(owner._task), 1)
    assert await lease.close()
    await assert_clean(case)
