"""Deterministic checks for the unreachable Azure intake foundation."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from foundry_router.api import azure_intake_worker as worker
from foundry_router.api.azure_intake import (
    METADATA_BYTES,
    SMALL_INPUT_BYTES,
    AzureIntakeDeliveryMiddleware,
    AzureIntakeDeliveryOwner,
    AzureIntakeError,
    AzureIntakeLimits,
    AzureIntakePolicy,
    AzureIntakeResources,
    PreparedAzureIntake,
    _json_bytes,
    _WorkerReply,
)
from foundry_router.config import Settings
from foundry_router.credit import estimate_request_cost_checked

_SOURCE_ROOT = str(Path(__file__).resolve().parents[2] / "src")


def settings(**overrides):
    values = {
        "_env_file": None,
        "client_api_keys_json": '["foundation-client-key"]',
        "admin_api_keys_json": '["foundation-admin-key"]',
        "backends_json": json.dumps(
            {
                "a": {
                    "endpoint": "https://example.invalid",
                    "credential": "foundation-secret-a",
                    "deployment": "physical-a",
                },
                "b": {
                    "endpoint": "https://second.invalid",
                    "credential": "foundation-secret-b",
                    "deployment": "physical-b",
                },
            }
        ),
        "models_json": json.dumps({"logical": {"backends": {"a": 1, "b": 1}}}),
        "model_aliases_json": '{"alias":"logical"}',
        "pricing_json": json.dumps(
            {
                "logical": {
                    "input_per_million": 10,
                    "output_per_million": 30,
                    "image_input_tokens": 258,
                    "pdf_document_tokens": 1024,
                }
            }
        ),
        "azure_max_request_body_bytes": 5 * 1024 * 1024,
        # Test-only process budget; this is not calibrated production enablement.
        "azure_intake_child_address_space_bytes": 8 * 1024 * 1024 * 1024,
    }
    values.update(overrides)
    return Settings(**values)


def policy(**overrides):
    return AzureIntakePolicy.from_settings(settings(**overrides))


def changed_policy(original, change):
    value = json.loads(original.wire)
    change(value)
    return AzureIntakePolicy(_json_bytes(value))


def resources(tmp_path, snapshot=None, **kwargs):
    tmp_path.chmod(0o700)
    snapshot = snapshot or policy()
    return AzureIntakeResources(tmp_path, snapshot.document.limits, **kwargs)


async def spooled(tmp_path, body=None, snapshot=None):
    snapshot = snapshot or policy()
    manager = resources(tmp_path, snapshot)
    lease = manager.acquire()
    raw = json.dumps(
        body or {"model": "alias", "input": "café 中🙂", "max_output_tokens": 8}, ensure_ascii=False
    ).encode()
    await lease.write(raw)
    return snapshot, manager, lease, raw


def control(lease, snapshot, operation="responses", backend=None):
    return lease._control(snapshot, operation, time.monotonic() + 10, backend_id=backend)


def test_config_defaults_inherit_without_enabling_routes():
    value = settings(
        azure_max_request_body_bytes=None,
        azure_intake_timeout_seconds=None,
        azure_intake_child_address_space_bytes=None,
    )
    assert value.azure_effective_max_request_body_bytes == value.max_request_body_bytes == 2_097_152
    assert value.azure_effective_intake_timeout_seconds == value.intake_timeout_seconds == 30
    from foundry_router import main

    assert value.azure_intake_enabled is False
    assert any(item.cls is AzureIntakeDeliveryMiddleware for item in main.app.user_middleware)


@pytest.mark.parametrize(
    "field,value",
    [
        ("azure_max_request_body_bytes", True),
        ("azure_max_request_body_bytes", 1024.0),
        ("azure_max_request_body_bytes", -1),
        ("azure_max_request_body_bytes", 1_073_741_825),
        ("azure_intake_child_address_space_bytes", False),
        ("azure_intake_child_address_space_bytes", "inf"),
        ("azure_intake_timeout_seconds", True),
        ("azure_intake_timeout_seconds", float("nan")),
        ("azure_intake_timeout_seconds", float("inf")),
        ("azure_intake_timeout_seconds", 121),
    ],
)
def test_bad_config_envelopes_fail(field, value):
    with pytest.raises(ValidationError):
        settings(**{field: value})


def test_config_requires_explicit_child_budget_and_preserves_ordinary_ceiling(monkeypatch):
    with pytest.raises(ValidationError, match="calibrated"):
        settings(azure_intake_child_address_space_bytes=None)
    with pytest.raises(ValidationError):
        settings(max_request_body_bytes=100_000_001)
    with pytest.raises(ValidationError, match="cannot lower"):
        settings(azure_max_request_body_bytes=1024)
    monkeypatch.setenv("FOUNDRY_AZURE_MAX_REQUEST_BODY_BYTES", "5242880")
    monkeypatch.setenv("FOUNDRY_AZURE_INTAKE_CHILD_ADDRESS_SPACE_BYTES", "8589934592")
    assert settings().azure_effective_max_request_body_bytes == 5_242_880


def test_policy_is_secret_free_bound_and_immutable():
    snapshot = policy()
    assert b"foundation-secret" not in snapshot.wire
    assert b"example.invalid" not in snapshot.wire
    assert snapshot.document.models["logical"].price.image_input_tokens == 258
    returned = snapshot.document
    returned.aliases["alias"] = "unknown"
    assert snapshot.document.aliases["alias"] == "logical"
    assert snapshot.digest == hashlib.sha256(snapshot.wire).hexdigest()
    with pytest.raises(ValueError):
        AzureIntakePolicy(b"{}")
    with pytest.raises(ValueError):
        AzureIntakePolicy(b"x" * METADATA_BYTES)
    with pytest.raises(ValueError):
        AzureIntakePolicy.from_settings(
            settings(azure_max_request_body_bytes=None, azure_intake_child_address_space_bytes=None)
        )


@pytest.mark.asyncio
async def test_small_large_scratch_bounds_and_idempotent_release(tmp_path):
    manager = resources(tmp_path, small_slots=2)
    first, second = manager.acquire(), manager.acquire()
    with pytest.raises(AzureIntakeError) as error:
        manager.acquire()
    assert error.value.status == 503
    await first.write(b"x" * (SMALL_INPUT_BYTES + 1))
    assert manager.large_owner is first
    with pytest.raises(AzureIntakeError):
        await second.write(b"y" * (SMALL_INPUT_BYTES + 1))
    assert second.input_bytes == 0 and second._directory is None
    assert manager.scratch_reserved <= manager.limits.scratch_bytes
    assert await first.close()
    assert await first.close()
    await second.write(b"y" * (SMALL_INPUT_BYTES + 1))
    assert manager.large_owner is second
    assert await second.close()
    assert manager.active == manager.scratch_reserved == 0
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_actual_wire_excess_before_allocation_and_private_spools(tmp_path):
    snapshot = policy()
    manager = resources(tmp_path, snapshot)
    lease = manager.acquire()
    with pytest.raises(AzureIntakeError) as error:
        await lease.write(b"x" * (manager.limits.max_input_bytes + 1))
    assert error.value.status == 413 and lease._directory is None
    await lease.write(b"{}")
    assert lease.input_path.stat().st_mode & 0o777 == 0o600
    assert lease.input_path.parent.stat().st_mode & 0o777 == 0o700
    assert await lease.close()


@pytest.mark.asyncio
async def test_real_children_estimator_byte_parity_and_retry_replay(tmp_path, monkeypatch):
    snapshot, manager, lease, raw = await spooled(tmp_path)
    launches = []
    real_launch = asyncio.create_subprocess_exec

    async def launch(*args, **kwargs):
        launches.append((args, kwargs))
        return await real_launch(*args, **kwargs)

    monkeypatch.setenv("FOUNDATION_MUST_NOT_REACH_CHILD", "secret")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    if sys.platform != "linux":

        async def direct(control, _deadline):
            return worker.run(control, lease.input_path, lease.output_path)

        monkeypatch.setattr(lease, "_child", direct)
    prepared = await lease.prepare(snapshot, "responses", deadline=time.monotonic() + 10)
    expected_body = {**json.loads(raw), "model": "logical"}
    expected = estimate_request_cost_checked(
        model="logical",
        operation="responses",
        body=expected_body,
        pricing=settings().pricing,
        settings=settings(),
    )
    assert prepared.estimate.request_estimate() == expected
    for selected in ("a", "b"):
        attempt = await lease.encode(snapshot, selected, deadline=time.monotonic() + 10)
        expected_wire = httpx.Request(
            "POST",
            "https://example.invalid",
            json={
                **expected_body,
                "model": "physical-" + selected,
            },
        ).content
        assert b"".join([chunk async for chunk in lease.output_chunks(attempt)]) == expected_wire
        assert b"".join([chunk async for chunk in lease.output_chunks(attempt)]) == expected_wire
        assert attempt.output_digest == hashlib.sha256(expected_wire).hexdigest()
    assert len(launches) == (3 if sys.platform == "linux" else 0)
    for args, kwargs in launches:
        assert args[1:3] == ("-I", "-c")
        assert _SOURCE_ROOT in args
        assert kwargs["env"] == {"PATH": "", "PYTHONDONTWRITEBYTECODE": "1"}
        assert kwargs["close_fds"] is True and kwargs["start_new_session"] is True
        assert kwargs["stderr"] == asyncio.subprocess.DEVNULL
    assert manager.active == 1 and manager.child_owner is None
    assert await lease.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body,expected_status",
    [
        (b'{"model":"logical","model":"logical"}', 400),
        (b'{"model":"logical","input":NaN}', 400),
        (b'{"model":"logical","input":"\xff"}', 400),
        (b'{"model":"logical","stream":"yes"}', 422),
        (b'{"model":"unknown","input":"ok"}', 404),
        (b"[]", 422),
        (b'{"model":""}', 422),
        (b'{"model":"logical","input":' + b"[" * 33 + b"0" + b"]" * 33 + b"}", 400),
    ],
)
async def test_current_strict_errors_are_controlled(tmp_path, body, expected_status):
    snapshot = policy()
    manager = resources(tmp_path, snapshot)
    lease = manager.acquire()
    await lease.write(body)
    reply = worker.run(control(lease, snapshot), lease.input_path, lease.output_path)
    assert reply.error.status == expected_status
    assert reply.prepared is None and manager.child_owner is None
    assert await lease.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"model": "unknown", "input": "x" * (SMALL_INPUT_BYTES + 1)},
        {"model": "logical", "input": "x" * (SMALL_INPUT_BYTES + 1), "stream": "bad"},
    ],
)
async def test_large_error_precedence(tmp_path, body):
    snapshot, _manager, lease, _ = await spooled(tmp_path, body)
    reply = worker.run(control(lease, snapshot), lease.input_path, lease.output_path)
    assert reply.error.status == 413
    assert await lease.close()


@pytest.mark.asyncio
async def test_embeddings_current_shapes_and_missing_price(tmp_path):
    snapshot, manager, lease, _ = await spooled(tmp_path, {"model": "logical", "input": ["a", "b"]})
    reply = worker.run(control(lease, snapshot, "embeddings"), lease.input_path, lease.output_path)
    assert reply.prepared.operation == "embeddings"
    lease.prepared = reply.prepared
    encoded = worker.run(
        control(lease, snapshot, "embeddings", "a"), lease.input_path, lease.output_path
    )
    assert encoded.attempt is not None
    assert json.loads(lease.output_path.read_text())["model"] == "logical"
    assert await lease.close()
    snapshot = changed_policy(snapshot, lambda value: value["models"]["logical"].update(price=None))
    manager = resources(tmp_path, snapshot)
    lease = manager.acquire()
    await lease.write(b'{"model":"logical","input":"a"}')
    reply = worker.run(control(lease, snapshot), lease.input_path, lease.output_path)
    assert reply.error.status == 503
    assert await lease.close()


@pytest.mark.asyncio
async def test_input_output_and_numeric_metadata_bindings(tmp_path):
    snapshot, _manager, lease, _ = await spooled(tmp_path)
    prepared = worker.run(control(lease, snapshot), lease.input_path, lease.output_path).prepared
    lease._validate_prepared(prepared, snapshot, "responses")
    for update in (
        {"model": "unknown"},
        {"policy_digest": "0" * 64},
        {"input_digest": "0" * 64},
        {"input_bytes": prepared.input_bytes + 1},
        {"backends": ("b", "a")},
        {"accepted_backends": ("outside",)},
        {"estimate": prepared.estimate.model_copy(update={"estimated_cost_usd": 0.0})},
    ):
        with pytest.raises(AzureIntakeError):
            lease._validate_prepared(prepared.model_copy(update=update), snapshot, "responses")
    bad = prepared.model_dump(mode="json")
    for field, value in (
        ("input_tokens", True),
        ("input_tokens", -1),
        ("estimated_cost_usd", float("inf")),
    ):
        modified = {**bad, "estimate": {**bad["estimate"], field: value}}
        with pytest.raises(ValueError):
            PreparedAzureIntake.model_validate_json(json.dumps(modified))
    lease.prepared = prepared
    with pytest.raises(AzureIntakeError):
        await lease.encode(snapshot, "outside", deadline=time.monotonic() + 10)
    lease.input_path.write_bytes(b"x" * lease.input_bytes)
    reply = worker.run(control(lease, snapshot, backend="a"), lease.input_path, lease.output_path)
    assert reply.error.status == 503
    assert await lease.close()


@pytest.mark.asyncio
async def test_policy_binding_output_envelope_and_ownership_rejections(tmp_path):
    snapshot, _manager, lease, _ = await spooled(
        tmp_path, {"model": "logical", "input": "x" * 2000}
    )
    original = control(lease, snapshot)
    assert (
        worker.run(
            original.model_copy(update={"policy_digest": "0" * 64}),
            lease.input_path,
            lease.output_path,
        ).error.status
        == 503
    )
    prepared = worker.run(original, lease.input_path, lease.output_path).prepared
    lease.prepared = prepared
    encoded_control = control(lease, snapshot, backend="a").model_copy(
        update={"output_limit_bytes": 1024}
    )
    assert worker.run(encoded_control, lease.input_path, lease.output_path).error.status == 413
    lease.input_path.chmod(0o644)
    assert worker.run(original, lease.input_path, lease.output_path).error.status == 503
    lease.input_path.chmod(0o600)
    assert await lease.close()


@pytest.mark.asyncio
async def test_cancelled_file_io_retains_capacity_until_real_completion(tmp_path, monkeypatch):
    manager = resources(tmp_path)
    lease = manager.acquire()
    entered, release = threading.Event(), threading.Event()
    real_write = lease._write

    def blocked(chunk):
        entered.set()
        release.wait(5)
        real_write(chunk)

    monkeypatch.setattr(lease, "_write", blocked)
    writing = asyncio.create_task(lease.write(b'{"model":"logical"}'))
    await asyncio.to_thread(entered.wait, 2)
    writing.cancel()
    with pytest.raises(asyncio.CancelledError):
        await writing
    closing = asyncio.create_task(lease.close())
    await asyncio.sleep(0.02)
    assert manager.active == 1 and lease.input_path.exists() and not closing.done()
    release.set()
    assert await closing
    assert manager.active == 0 and list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_io_failure_closes_owned_files_without_reusing_failed_input(tmp_path, monkeypatch):
    manager = resources(tmp_path)
    lease = manager.acquire()

    def partial_failure(chunk):
        lease.input_path.write_bytes(chunk[:1])
        raise OSError("synthetic private write failure")

    monkeypatch.setattr(lease, "_write", partial_failure)
    with pytest.raises(AzureIntakeError) as error:
        await lease.write(b"{}")
    assert error.value.confirmed_pre_dispatch
    with pytest.raises(AzureIntakeError):
        await lease.write(b"{}")
    assert await lease.close() and manager.active == 0


@pytest.mark.asyncio
async def test_unproven_child_reap_keeps_one_waiter_and_capacity(tmp_path):
    manager = resources(tmp_path)
    lease = manager.acquire()
    await lease.write(b"{}")
    done = asyncio.Event()

    class Child:
        returncode = None
        waits = 0

        def terminate(self):
            pass

        def kill(self):
            pass

        async def wait(self):
            self.waits += 1
            await done.wait()
            self.returncode = 0
            return 0

    child = Child()

    async def spawn():
        return child

    lease._spawn = asyncio.create_task(spawn())
    manager.child_owner = lease
    assert await lease.close() is False
    assert child.waits == 1 and manager.active == 1 and not manager.ready
    assert lease.input_path.exists()
    done.set()
    assert await lease.close()
    assert child.waits == 1 and manager.active == 0 and manager.ready


@pytest.mark.asyncio
async def test_spawn_failure_is_proven_and_does_not_orphan_capacity(tmp_path, monkeypatch):
    snapshot, manager, lease, _ = await spooled(tmp_path)

    async def fail(*_args, **_kwargs):
        raise OSError("spawn unavailable")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fail)
    with pytest.raises(AzureIntakeError):
        await lease.prepare(snapshot, "responses", deadline=time.monotonic() + 10)
    assert manager.child_owner is None and manager.ready
    assert await lease.close()


@pytest.mark.asyncio
async def test_delivery_owns_slow_send_and_duplicate_transfer_rejected(tmp_path):
    manager = resources(tmp_path)
    lease = manager.acquire()
    entered, release = asyncio.Event(), asyncio.Event()
    scope = {"type": "http"}

    async def app(scope, _receive, send):
        owner = scope["state"]["_foundry_azure_intake_delivery"]
        owner.transfer(lease, time.monotonic() + 5)
        with pytest.raises(ValueError):
            AzureIntakeDeliveryOwner().transfer(lease, time.monotonic() + 5)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok", "more_body": False})

    async def send(message):
        if message["type"] == "http.response.body":
            entered.set()
            await release.wait()

    delivery = asyncio.create_task(AzureIntakeDeliveryMiddleware(app)(scope, None, send))
    await entered.wait()
    assert manager.active == 1 and not lease.closed
    release.set()
    await delivery
    assert lease.closed and manager.active == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", ["disconnect", "deadline"])
async def test_delivery_disconnect_and_deadline_cleanup(tmp_path, fail):
    manager = resources(tmp_path)
    lease = manager.acquire()

    async def app(scope, _receive, send):
        scope["state"]["_foundry_azure_intake_delivery"].transfer(lease, time.monotonic() + 0.02)
        await send({"type": "http.response.body", "body": b"ok"})

    async def send(_message):
        if fail == "disconnect":
            raise OSError("disconnected")
        await asyncio.sleep(1)

    with pytest.raises((OSError, TimeoutError)):
        await AzureIntakeDeliveryMiddleware(app)({"type": "http"}, None, send)
    assert lease.closed and manager.active == 0


def test_worker_controls_precede_payload_and_stdout_stays_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(worker.sys, "platform", "linux")
    calls = []
    monkeypatch.setattr(
        worker.resource, "setrlimit", lambda kind, limits: calls.append((kind, limits))
    )
    source, output = tmp_path / "input.json", tmp_path / "output.json"
    args = [str(source), str(output), str(8 * 1024**3), "30", "5242880", str(time.monotonic() + 10)]
    assert worker._limits(args)[:2] == (source, output)
    assert [kind for kind, _ in calls] == [
        worker.resource.RLIMIT_AS,
        worker.resource.RLIMIT_CPU,
        worker.resource.RLIMIT_FSIZE,
        worker.resource.RLIMIT_NOFILE,
        worker.resource.RLIMIT_CORE,
    ]
    for broken in (
        [],
        [*args[:2], "0", *args[3:]],
        [*args[:-1], "nan"],
        [str(source), str(source), *args[2:]],
    ):
        with pytest.raises(ValueError):
            worker._limits(broken)


@pytest.mark.asyncio
async def test_worker_main_success_invalid_controls_and_metadata_bound(tmp_path, monkeypatch):
    snapshot, _manager, lease, _ = await spooled(tmp_path)
    request = control(lease, snapshot)
    args = [
        "worker",
        str(lease.input_path),
        str(lease.output_path),
        str(snapshot.document.limits.child_address_space_bytes),
        str(snapshot.document.limits.child_cpu_seconds),
        str(request.output_limit_bytes),
        str(request.deadline_monotonic),
    ]
    monkeypatch.setattr(worker.sys, "platform", "linux")
    monkeypatch.setattr(worker.resource, "setrlimit", lambda *_args: None)
    monkeypatch.setattr(worker.sys, "argv", args)
    output = io.BytesIO()
    monkeypatch.setattr(
        worker.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(request.model_dump_json().encode()))
    )
    monkeypatch.setattr(worker.sys, "stdout", SimpleNamespace(buffer=output))
    assert worker.main() == 0
    assert _WorkerReply.model_validate_json(output.getvalue()).prepared is not None
    monkeypatch.setattr(
        worker.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b"x" * (METADATA_BYTES + 1)))
    )
    assert worker.main() == 2
    modified = request.model_copy(update={"deadline_monotonic": request.deadline_monotonic + 1})
    monkeypatch.setattr(
        worker.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(modified.model_dump_json().encode()))
    )
    assert worker.main() == 2
    assert await lease.close()


@pytest.mark.asyncio
async def test_worker_resource_refusal_is_controlled_before_dispatch(tmp_path, monkeypatch):
    snapshot, _manager, lease, _ = await spooled(tmp_path)

    def fail(*_args):
        raise MemoryError()

    monkeypatch.setattr(worker, "_read_input", fail)
    reply = worker.run(control(lease, snapshot), lease.input_path, lease.output_path)
    assert reply.error.status == 413 and reply.error.code == "router_request_resource_exceeded"
    assert await lease.close()


def test_private_root_and_limits_are_validated(tmp_path):
    tmp_path.chmod(0o755)
    with pytest.raises(ValueError):
        AzureIntakeResources(tmp_path, policy().document.limits)
    tmp_path.chmod(0o700)
    with pytest.raises(ValueError):
        AzureIntakeResources(tmp_path, policy().document.limits, small_slots=0)
    with pytest.raises(ValueError):
        AzureIntakeLimits(
            max_input_bytes=1024,
            max_output_bytes=1024,
            child_address_space_bytes=64 * 1024**2,
            child_cpu_seconds=1,
            scratch_bytes=1024,
        )


@pytest.mark.asyncio
async def test_actual_launch_cleans_environment_and_platform_refusal(tmp_path, monkeypatch):
    snapshot, manager, lease, _ = await spooled(tmp_path)
    real_launch = asyncio.create_subprocess_exec
    recorded = []

    async def launch(*args, **kwargs):
        recorded.append((args, kwargs))
        return await real_launch(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    if sys.platform == "linux":
        assert await lease.prepare(snapshot, "responses", deadline=time.monotonic() + 10)
    else:
        with pytest.raises(AzureIntakeError) as error:
            await lease.prepare(snapshot, "responses", deadline=time.monotonic() + 10)
        assert error.value.status == 503
    assert recorded[0][1]["env"] == {"PATH": "", "PYTHONDONTWRITEBYTECODE": "1"}
    assert recorded[0][1]["close_fds"] and recorded[0][1]["start_new_session"]
    assert _SOURCE_ROOT in recorded[0][0]
    assert manager.child_owner is None and await lease.close()


@pytest.mark.asyncio
async def test_uncertain_io_blocks_new_children_until_io_finishes(tmp_path, monkeypatch):
    snapshot = policy()
    manager = resources(tmp_path, snapshot)
    first, second = manager.acquire(), manager.acquire()
    await second.write(b'{"model":"logical","input":"ok"}')
    entered, release = threading.Event(), threading.Event()
    real_write = first._write

    def blocked(chunk):
        entered.set()
        release.wait(5)
        real_write(chunk)

    monkeypatch.setattr(first, "_write", blocked)
    writing = asyncio.create_task(first.write(b"{}"))
    await asyncio.to_thread(entered.wait, 2)
    writing.cancel()
    with pytest.raises(asyncio.CancelledError):
        await writing
    try:
        assert await first.close() is False
        assert not manager.ready and manager.active == 2

        async def forbidden(*_args, **_kwargs):
            raise AssertionError("Unhealthy controller must not launch another child")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
        with pytest.raises(AzureIntakeError):
            await second.prepare(snapshot, "responses", deadline=time.monotonic() + 10)
    finally:
        release.set()
        if first._io is not None:
            await first._io
        assert await first.close()
        assert await second.close()
    assert manager.ready and manager.active == 0


@pytest.mark.asyncio
async def test_existing_unestimable_utf8_projection_fails_closed(tmp_path):
    body = {
        "model": "alias",
        "input": 'café \\ quote" \ud800',
        "max_output_tokens": 8,
        "tools": [{"type": "function", "name": "x", "parameters": {"type": "object"}}],
    }
    snapshot = policy()
    manager = resources(tmp_path, snapshot)
    lease = manager.acquire()
    await lease.write(json.dumps(body).encode())
    reply = worker.run(control(lease, snapshot), lease.input_path, lease.output_path)
    assert reply.prepared is None
    assert reply.error.status == 422 and reply.error.code == "request_estimation_unavailable"
    assert await lease.close()


@pytest.mark.asyncio
async def test_below_small_wire_unicode_uses_full_configured_output_budget(tmp_path, monkeypatch):
    snapshot = policy(azure_max_request_body_bytes=8 * 1024 * 1024)
    manager = resources(tmp_path, snapshot)
    lease = manager.acquire()
    overhead = len(json.dumps({"model": "logical", "input": ""}, ensure_ascii=False).encode())
    characters = (SMALL_INPUT_BYTES - overhead) // 2
    body = {"model": "logical", "input": "é" * characters}
    raw = json.dumps(body, ensure_ascii=False).encode()
    assert len(raw) <= SMALL_INPUT_BYTES
    await lease.write(raw)
    assert manager.large_owner is None

    async def direct(request, _deadline):
        return worker.run(request, lease.input_path, lease.output_path)

    monkeypatch.setattr(lease, "_child", direct)
    await lease.prepare(snapshot, "responses", deadline=time.monotonic() + 10)
    attempt = await lease.encode(snapshot, "a", deadline=time.monotonic() + 10)
    expected = httpx.Request(
        "POST", "https://example.invalid", json={**body, "model": "physical-a"}
    ).content
    assert 2 * SMALL_INPUT_BYTES < len(expected) < snapshot.document.limits.max_output_bytes
    assert manager.large_owner is lease
    assert (
        lease.reserved
        == snapshot.document.limits.max_input_bytes + snapshot.document.limits.max_output_bytes
    )
    assert b"".join([chunk async for chunk in lease.output_chunks(attempt)]) == expected
    assert await lease.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["partial_write", "cancel", "verification"])
async def test_failed_replacement_revokes_previous_attempt(tmp_path, monkeypatch, failure):
    snapshot, manager, lease, _ = await spooled(tmp_path)

    async def direct(request, _deadline):
        return worker.run(request, lease.input_path, lease.output_path)

    monkeypatch.setattr(lease, "_child", direct)
    await lease.prepare(snapshot, "responses", deadline=time.monotonic() + 10)
    previous = await lease.encode(snapshot, "a", deadline=time.monotonic() + 10)
    assert previous == lease.attempt

    if failure == "partial_write":
        original_open = worker.os.fdopen

        class PartialWriter:
            def __init__(self, handle):
                self.handle = handle
                self.started = False

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.handle.close()

            def write(self, chunk):
                if self.started:
                    raise OSError("synthetic encoded write failure")
                self.started = True
                return self.handle.write(chunk[:3])

        def failing_open(descriptor, mode, *args, **kwargs):
            handle = original_open(descriptor, mode, *args, **kwargs)
            return PartialWriter(handle) if mode == "wb" else handle

        monkeypatch.setattr(worker.os, "fdopen", failing_open)
    else:

        async def changed_child(request, _deadline):
            if failure == "cancel":
                lease.output_path.write_bytes(b"partial")
                raise asyncio.CancelledError()
            reply = worker.run(request, lease.input_path, lease.output_path)
            lease.output_path.write_bytes(b"partial")
            return reply

        monkeypatch.setattr(lease, "_child", changed_child)

    with pytest.raises((AzureIntakeError, asyncio.CancelledError)):
        await lease.encode(snapshot, "b", deadline=time.monotonic() + 10)
    assert lease.attempt is None
    with pytest.raises(AzureIntakeError):
        _ = [chunk async for chunk in lease.output_chunks(previous)]
    assert await lease.close() and manager.active == 0


@pytest.mark.asyncio
async def test_two_small_requests_keep_large_lane_free_through_delivery(tmp_path, monkeypatch):
    snapshot = policy(azure_max_request_body_bytes=8 * 1024 * 1024)
    manager = resources(tmp_path, snapshot)
    first, second = manager.acquire(), manager.acquire()

    def attach(lease):
        async def direct(request, _deadline):
            return worker.run(request, lease.input_path, lease.output_path)

        monkeypatch.setattr(lease, "_child", direct)

    for lease in (first, second):
        attach(lease)
        await lease.write(b'{"model":"logical","input":"hi"}')
        await lease.prepare(snapshot, "responses", deadline=time.monotonic() + 10)
    first_attempt = await first.encode(snapshot, "a", deadline=time.monotonic() + 10)
    owner = AzureIntakeDeliveryOwner()
    owner.transfer(first, time.monotonic() + 20)
    second_attempt = await second.encode(snapshot, "b", deadline=time.monotonic() + 10)
    assert manager.large_owner is None and manager.active == 2
    assert first_attempt.output_bytes < 128 and second_attempt.output_bytes < 128
    assert first.reserved == second.reserved == manager.small_reservation
    await owner.finalize()
    assert await second.close()


@pytest.mark.asyncio
async def test_small_encoding_while_large_delivery_retains_lane(tmp_path, monkeypatch):
    snapshot = policy(azure_max_request_body_bytes=8 * 1024 * 1024)
    manager = resources(tmp_path, snapshot)
    large, small = manager.acquire(), manager.acquire()

    def attach(lease):
        async def direct(request, _deadline):
            return worker.run(request, lease.input_path, lease.output_path)

        monkeypatch.setattr(lease, "_child", direct)

    attach(large)
    attach(small)
    await large.write(
        json.dumps({"model": "logical", "input": "x" * (SMALL_INPUT_BYTES + 1)}).encode()
    )
    await large.prepare(snapshot, "responses", deadline=time.monotonic() + 10)
    await large.encode(snapshot, "a", deadline=time.monotonic() + 10)
    owner = AzureIntakeDeliveryOwner()
    owner.transfer(large, time.monotonic() + 20)
    await small.write(b'{"model":"logical","input":"hi"}')
    await small.prepare(snapshot, "responses", deadline=time.monotonic() + 10)
    attempt = await small.encode(snapshot, "b", deadline=time.monotonic() + 10)
    assert attempt.output_bytes < 128
    assert manager.large_owner is large and not large.closed
    assert small.reserved == manager.small_reservation
    assert await small.close()
    await owner.finalize()
    assert manager.active == 0


@pytest.mark.asyncio
async def test_encoded_bound_is_exact_for_physical_models_and_translated_shape(tmp_path):
    snapshot = changed_policy(
        policy(),
        lambda value: value["backends"]["a"].update(
            deployment='café "\\\\ quoted', provider="azure_anthropic", operations=["responses"]
        ),
    )
    snapshot, _manager, lease, _ = await spooled(tmp_path, snapshot=snapshot)
    prepared = worker.run(control(lease, snapshot), lease.input_path, lease.output_path).prepared
    from foundry_router.api.adapters import get_adapter

    body = {"model": "logical", "input": "café 中🙂", "max_output_tokens": 8}
    expected = []
    for name in prepared.accepted_backends:
        backend = snapshot.document.backends[name]
        payload = get_adapter(backend.provider).build_upstream_body(
            "responses", body, deployment=backend.deployment, default_output_tokens=4096
        )
        expected.append(len(httpx.Request("POST", "https://example.invalid", json=payload).content))
    assert prepared.max_encoded_bytes == max(expected)
    assert await lease.close()
