"""Cumulative lifetime, bounded transport and accounting aggregation."""

import asyncio

import httpx
import pytest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceResponse,
)
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, MetricExportResult

from foundry_router.config import Settings
from foundry_router.metrics.otlp import ConfinedMetricExporter, OtlpMetricsStore
from tests.integration.test_compatible_provider_integration import settings as provider_settings


def settings(**overrides):
    base = provider_settings().model_dump()
    return Settings(
        **{
            **base,
            "telemetry_enabled": True,
            "telemetry_endpoint": "https://collector.example.test/v1/metrics",
            **overrides,
        }
    )


def points(reader):
    data = reader.get_metrics_data()
    return data, {
        metric.name: metric.data
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
    }


async def test_two_lifetimes_cumulative_and_local_reset():
    readers = [InMemoryMetricReader() for _ in range(2)]
    stores = [OtlpMetricsStore(settings(), reader=reader) for reader in readers]
    for i, store in enumerate(stores):
        for _ in range(i + 1):
            await store.observe_request(
                model="logical",
                backend="a",
                status_code=200,
                latency_seconds=0.2,
                estimated_cost_usd=0.5,
            )
    assert stores[0].instance_id != stores[1].instance_id
    _data, first = points(readers[0])
    _, second = points(readers[1])
    assert (
        sum(
            point.value
            for metrics in (first, second)
            for point in metrics["foundry_router_requests_total"].data_points
        )
        == 3
    )
    histogram = first["foundry_router_latency_seconds"].data_points[0]
    assert histogram.count == 1 and sum(histogram.bucket_counts) == 1
    assert histogram.explicit_bounds == (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    assert first["foundry_router_requests_total"].aggregation_temporality == 2
    await stores[0].reset()
    await stores[0].observe_request(
        model="logical", backend="a", status_code=200, latency_seconds=0.2, estimated_cost_usd=0.5
    )
    _, later = points(readers[0])
    assert later["foundry_router_requests_total"].data_points[0].value == 2
    await asyncio.gather(*(store.shutdown() for store in stores))


@pytest.mark.parametrize(
    "status,ack,expected",
    [
        (200, b"", "acknowledged"),
        (302, b"", "http_status"),
        (429, b"", "http_status"),
        (503, b"", "http_status"),
        (200, b"\xff", "invalid_ack"),
        (200, b"x" * 70000, "ack_capacity"),
    ],
)
async def test_single_shot_confined_acknowledgement(monkeypatch, status, ack, expected):
    monkeypatch.setenv("HTTPS_PROXY", "http://outside.invalid")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://outside.invalid")
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "service.instance.id=hostile")
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, content=ack, headers={"location": "https://outside.invalid"})

    exporter = ConfinedMetricExporter(
        "https://collector.example.test/v1/metrics",
        authorization="Bearer synthetic",
        timeout=1,
        transport=httpx.MockTransport(handle),
    )
    reader = InMemoryMetricReader()
    store = OtlpMetricsStore(settings(), reader=reader)
    await store.observe_request(
        model="logical", backend="a", status_code=200, latency_seconds=0.1, estimated_cost_usd=1
    )
    data, _ = points(reader)
    result = await asyncio.to_thread(exporter.export, data)
    assert result == (
        MetricExportResult.SUCCESS if expected == "acknowledged" else MetricExportResult.FAILURE
    )
    assert exporter.state == expected and len(calls) == 1
    assert str(calls[0].url) == "https://collector.example.test/v1/metrics"
    assert calls[0].headers["authorization"] == "Bearer synthetic"
    assert store.instance_id != "hostile"
    exporter.shutdown()
    await store.shutdown()


async def test_partial_rejection_safe_status(caplog):
    ack = ExportMetricsServiceResponse()
    ack.partial_success.rejected_data_points = 2
    ack.partial_success.error_message = "private-collector-marker"
    exporter = ConfinedMetricExporter(
        "https://collector.example.test/v1/metrics",
        authorization=None,
        timeout=1,
        transport=httpx.MockTransport(
            lambda _r: httpx.Response(200, content=ack.SerializeToString())
        ),
    )
    reader = InMemoryMetricReader()
    store = OtlpMetricsStore(settings(), reader=reader)
    await store.observe_request(
        model="logical", backend="a", status_code=200, latency_seconds=0.1, estimated_cost_usd=1
    )
    data, _ = points(reader)
    assert await asyncio.to_thread(exporter.export, data) == MetricExportResult.FAILURE
    assert exporter.state == "partial" and exporter.rejected_points == 2
    assert "private-collector-marker" not in caplog.text
    exporter.shutdown()
    await store.shutdown()


async def test_series_budget_and_unknown_labels_are_bounded():
    reader = InMemoryMetricReader()
    store = OtlpMetricsStore(settings(telemetry_series_budget=20), reader=reader)
    for i in range(1000):
        await store.observe_request(
            model=f"unknown-{i}",
            backend=f"other-{i}",
            status_code=i,
            latency_seconds=0.1,
            estimated_cost_usd=1,
        )
    assert len(store._series) <= 20 and store.export_status()["dropped_observations"] > 0
    _, metrics = points(reader)
    assert sum(len(metric.data_points) for metric in metrics.values()) <= 20
    await store.shutdown()


@pytest.mark.parametrize(
    "overrides",
    [
        {"telemetry_endpoint": "http://collector.test/v1/metrics"},
        {"telemetry_endpoint": "https://collector.test/../v1/metrics"},
        {"telemetry_endpoint": "https://collector.test/v1/metrics?key=x"},
        {"telemetry_series_budget": 1},
    ],
)
def test_config_rejects_unsafe_or_insufficient(overrides):
    with pytest.raises(ValueError):
        settings(**overrides)


def test_enabled_sdk_disabled_is_explicit(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    with pytest.raises(ValueError):
        OtlpMetricsStore(settings(), reader=InMemoryMetricReader())


async def test_slow_trickle_total_deadline_and_reader_shutdown():
    import time

    class Trickle(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(100):
                await asyncio.sleep(0.1)
                yield b"\x00"

    exporter = ConfinedMetricExporter(
        "https://collector.example.test/v1/metrics",
        authorization=None,
        timeout=0.2,
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, stream=Trickle())),
    )
    reader = InMemoryMetricReader()
    store = OtlpMetricsStore(settings(), reader=reader)
    await store.observe_request(
        model="logical", backend="a", status_code=200, latency_seconds=0.1, estimated_cost_usd=1
    )
    data, _ = points(reader)
    started = time.monotonic()
    assert await asyncio.to_thread(exporter.export, data) == MetricExportResult.FAILURE
    assert exporter.state == "deadline" and time.monotonic() - started < 1
    exporter.shutdown()
    await store.shutdown()


async def test_constructor_failure_closes_started_reader(monkeypatch):
    import threading

    from foundry_router.metrics import otlp

    original = otlp.MeterProvider
    monkeypatch.setattr(
        otlp,
        "MeterProvider",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError("synthetic construction failure")),
    )
    before = {
        thread.ident
        for thread in threading.enumerate()
        if thread.name == "OtelPeriodicExportingMetricReader"
    }
    with pytest.raises(ValueError):
        OtlpMetricsStore(settings())
    assert {
        thread.ident
        for thread in threading.enumerate()
        if thread.name == "OtelPeriodicExportingMetricReader"
    } == before
    monkeypatch.setattr(otlp, "MeterProvider", original)


async def test_lifespan_startup_failure_always_stops_metrics(monkeypatch):
    import threading
    from unittest.mock import AsyncMock

    from foundry_router import main

    config = settings()
    monkeypatch.setattr(main, "_metrics_store", main._metrics_store)
    monkeypatch.setattr(main, "load_settings", lambda: config)
    monkeypatch.setattr(main, "get_backend_client", lambda: None)
    monkeypatch.setattr(
        main, "build_stores", lambda _s: (_ for _ in ()).throw(ValueError("startup-marker"))
    )
    monkeypatch.setattr(
        main, "close_backend_client", AsyncMock(side_effect=RuntimeError("close-marker"))
    )
    before = {
        thread.ident
        for thread in threading.enumerate()
        if thread.name == "OtelPeriodicExportingMetricReader"
    }
    with pytest.raises(ValueError, match="startup-marker"):
        async with main.lifespan(main.app):
            pytest.fail("Startup should fail")
    assert {
        thread.ident
        for thread in threading.enumerate()
        if thread.name == "OtelPeriodicExportingMetricReader"
    } == before
    assert main._metrics_store._closed


async def test_api_live_proxy_records_into_enabled_store(monkeypatch):
    import json

    import respx
    from fastapi.testclient import TestClient

    from foundry_router.main import app
    from tests.integration.test_google_adapter_integration import _wire

    config = settings()
    # Existing fixture helper is synchronous; invoke outside the running loop.
    await asyncio.to_thread(_wire, monkeypatch, config)
    reader = InMemoryMetricReader()
    store = OtlpMetricsStore(config, reader=reader)
    monkeypatch.setattr("foundry_router.main._metrics_store", store)
    with respx.mock:
        respx.post("https://a.compatible.test/api/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "synthetic"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                },
            )
        )
        response = await asyncio.to_thread(
            TestClient(app).post,
            "/openai/v1/responses",
            headers={"api-key": "client-key"},
            json={"model": "alias", "input": "hi", "max_output_tokens": 8},
        )
    assert response.status_code == 200
    _, metrics = points(reader)
    assert metrics["foundry_router_requests_total"].data_points[0].value == 1
    status = await asyncio.to_thread(
        TestClient(app).get, "/admin/status", headers={"x-admin-key": "admin-key"}
    )
    assert status.json()["telemetry"]["enabled"] is True
    assert "collector.example.test" not in json.dumps(status.json())
    await store.shutdown()
