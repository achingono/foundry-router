"""Redaction, queue pressure and metrics/lifecycle isolation."""

import asyncio
import json
import threading
from types import SimpleNamespace

import pytest
import structlog

from foundry_router.config import Settings
from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.metrics import completion as c
from tests.integration.test_compatible_provider_integration import settings as provider_settings


class CapturingDispatcher:
    instance_id = "server-process"

    def __init__(self):
        self.payloads = []

    def submit(self, payload, counts):
        self.payloads.append(json.loads(payload))
        counts.submitted += 1
        counts.written += 1


def sink(dispatcher=None):
    return c.CompletionEventSink(
        provider_settings(), dispatcher=dispatcher or CapturingDispatcher()
    )


def observation(**changes):
    return {
        "model": "logical",
        "backend": "a",
        "status_code": 200,
        "latency_seconds": 0.1,
        "estimated_cost_usd": 0.5,
        **changes,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"status_code": True},
        {"status_code": 99},
        {"status_code": 600},
        {"status_code": 200.0},
        {"latency_seconds": float("nan")},
        {"latency_seconds": float("inf")},
        {"latency_seconds": -1},
        {"latency_seconds": True},
        {"estimated_cost_usd": float("inf")},
        {"estimated_cost_usd": float("nan")},
        {"estimated_cost_usd": -1},
        {"estimated_cost_usd": True},
    ],
)
def test_nonfinite_negative_or_invalid_status_is_not_logged(changes):
    value = sink()
    value.observe(**observation(**changes))
    assert value.status()["invalid"] == 1
    assert value._dispatcher.payloads == []


@pytest.mark.parametrize("label", ["", "x" * 129, "url://hostname", "model\ncontent", "model\x7f"])
def test_config_rejects_unsafe_identifier_when_enabled(label):
    with pytest.raises(ValueError):
        c.validate_labels([label])


def test_event_allowlist_server_ids_and_no_ambient_context():
    value = sink()
    structlog.contextvars.bind_contextvars(request_id="caller-value", prompt="private-prompt")
    try:
        value.observe(**observation())
        value.observe(**observation(backend="none", estimated_cost_usd=None))
        value.observe(**observation(model="caller://host/private", backend="caller-secret"))
    finally:
        structlog.contextvars.clear_contextvars()
    rows = value._dispatcher.payloads
    assert len({row["event_id"] for row in rows}) == 3
    assert all(row["process_instance_id"] == "server-process" for row in rows)
    assert set(rows[0]) == {
        "event",
        "schema_version",
        "event_id",
        "process_instance_id",
        "model",
        "backend",
        "status_code",
        "duration_seconds",
        "estimated_cost_usd",
    }
    assert "estimated_cost_usd" not in rows[1]
    assert (rows[2]["model"], rows[2]["backend"]) == ("other", "none")
    serialized = json.dumps(rows)
    assert all(
        secret not in serialized
        for secret in ["private-prompt", "caller-value", "caller-secret", "caller://host/private"]
    )


async def test_wrapper_preserves_local_metrics_and_failures_do_not_retry(monkeypatch):
    value = sink()
    local = InMemoryMetricsStore()
    store = c.CompletionMetricsStore(local, provider_settings(), sink=value)
    calls = 0

    def fail(**_values):
        nonlocal calls
        calls += 1
        raise OSError("private-logger-error")

    monkeypatch.setattr(value, "observe", fail)
    await store.observe_request(**observation())
    rendered = await store.render_prometheus(
        backend_health_states={}, backend_available_credit_usd={}
    )
    assert 'foundry_router_requests_total{model="logical",backend="a",status="200"} 1' in rendered
    assert (
        'foundry_router_estimated_cost_usd_total{model="logical",backend="a"} 0.500000000'
        in rendered
    )
    assert calls == 1 and store.export_status()["completion_logs"]["observation_errors"] == 1
    await store.shutdown()
    await store.reset()
    assert value.status()["closed"]


async def test_existing_metrics_failure_propagates_without_sink_observation():
    class FailingMetrics:
        async def observe_request(self, **_values):
            raise RuntimeError("existing-metrics-failure")

    value = sink()
    store = c.CompletionMetricsStore(FailingMetrics(), provider_settings(), sink=value)
    with pytest.raises(RuntimeError, match="existing-metrics-failure"):
        await store.observe_request(**observation())
    assert value._dispatcher.payloads == []


async def test_shutdown_keeps_sink_closed_even_if_underlying_shutdown_fails():
    class FailingMetrics:
        async def shutdown(self):
            raise RuntimeError("existing-shutdown-failure")

    value = sink()
    store = c.CompletionMetricsStore(FailingMetrics(), provider_settings(), sink=value)
    with pytest.raises(RuntimeError):
        await store.shutdown()
    value.observe(**observation())
    assert value.status()["closed"] and value.status()["dropped"] == 1


async def test_blocked_writer_bounded_queue_health_and_shutdown(monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def blocked(_payload):
        entered.set()
        release.wait(timeout=5)

    dispatcher = c._Dispatcher(writer=blocked)
    value = sink(dispatcher)
    try:
        value.observe(**observation())
        assert await asyncio.to_thread(entered.wait, 1)
        for _ in range(c.QUEUE_CAPACITY + 20):
            value.observe(**observation())
        assert dispatcher.queue.qsize() == c.QUEUE_CAPACITY
        assert value.status()["dropped"] == 20
        assert value.status()["pending"] == c.QUEUE_CAPACITY + 1
        await asyncio.wait_for(asyncio.sleep(0), timeout=0.1)
        monkeypatch.setattr(c, "SHUTDOWN_GRACE_SECONDS", 0.02)
        await asyncio.wait_for(value.close(), timeout=0.1)
        assert value.status()["closed"] and dispatcher.thread.daemon
    finally:
        release.set()
        await asyncio.to_thread(dispatcher.queue.join)
    assert value.status()["written"] == c.QUEUE_CAPACITY + 1


async def test_writer_failure_is_counted_once_without_echo_or_retry():
    calls = []

    def failing(payload):
        calls.append(payload)
        raise ValueError("private-console-error")

    dispatcher = c._Dispatcher(writer=failing)
    value = sink(dispatcher)
    value.observe(**observation())
    await asyncio.to_thread(dispatcher.queue.join)
    assert len(calls) == 1 and value.status()["failed"] == 1 and value.status()["pending"] == 0
    await value.close()


def test_process_dispatcher_reused_across_lifespans_and_fork_identity(monkeypatch):
    fake = SimpleNamespace(pid=c.os.getpid(), instance_id="old-process")
    monkeypatch.setattr(c, "_DISPATCHER", fake)
    assert c._process_dispatcher() is fake
    made = []

    def create():
        value = SimpleNamespace(pid=c.os.getpid(), instance_id="new-process")
        made.append(value)
        return value

    monkeypatch.setattr(c, "_Dispatcher", create)
    monkeypatch.setattr(c.os, "getpid", lambda: -10)
    assert c._process_dispatcher().instance_id == "new-process"
    assert c._process_dispatcher() is made[0] and len(made) == 1


def test_default_off_builder_avoids_dispatcher(monkeypatch):
    from foundry_router import main

    monkeypatch.setattr(c, "_process_dispatcher", lambda: pytest.fail("default-off worker started"))
    assert provider_settings().completion_logs_enabled is False
    assert isinstance(main._build_metrics_store(provider_settings()), InMemoryMetricsStore)


def test_enabled_builder_and_config_without_otlp_endpoint(monkeypatch):
    from foundry_router import main

    dispatcher = CapturingDispatcher()
    monkeypatch.setattr(c, "_process_dispatcher", lambda: dispatcher)
    base = provider_settings().model_dump()
    settings = Settings(**{**base, "completion_logs_enabled": True})
    store = main._build_metrics_store(settings)
    assert isinstance(store, c.CompletionMetricsStore)
    assert store.export_status()["completion_logs"]["enabled"]
    assert store.export_status()["enabled"] is False


def test_console_writer_does_not_merge_logger_context(capsys):
    c._write_console('{"event":"synthetic"}')
    assert capsys.readouterr().out == '{"event":"synthetic"}\n'


def test_encoded_record_bound_refuses_before_queue(monkeypatch):
    value = sink()
    monkeypatch.setattr(c, "MAX_RECORD_BYTES", 1)
    value.observe(**observation())
    assert value.status()["invalid"] == 1 and value._dispatcher.payloads == []
