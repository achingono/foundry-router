"""Opt-in bounded OTLP cumulative metrics; no global provider or ambient resource."""

from __future__ import annotations

import asyncio
import math
import os
import threading
import time
import uuid
from typing import Any

import httpx
import structlog
from google.protobuf.message import DecodeError  # type: ignore[import-untyped]
from opentelemetry.exporter.otlp.proto.common.metrics_encoder import encode_metrics
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceResponse,
)
from opentelemetry.sdk.metrics import AlwaysOffExemplarFilter, MeterProvider
from opentelemetry.sdk.metrics._internal.instrument import Counter, Histogram
from opentelemetry.sdk.metrics.export import (
    AggregationTemporality,
    MetricExporter,
    MetricExportResult,
    MetricsData,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource

from foundry_router.metrics import LATENCY_BUCKETS_SECONDS, InMemoryMetricsStore

MAX_REQUEST_BYTES = 1024 * 1024
MAX_ACK_BYTES = 64 * 1024
MAX_LABEL_BYTES = 128
HTTP_OK = 200
MAX_STATUS = 599
MIN_STATUS = 100
_logger = structlog.get_logger(__name__)


class ConfinedMetricExporter(MetricExporter):
    """Official protobuf encoding with one bounded, configured HTTP dispatch per export."""

    def __init__(
        self,
        endpoint: str,
        *,
        authorization: str | None,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            preferred_temporality={
                Counter: AggregationTemporality.CUMULATIVE,
                Histogram: AggregationTemporality.CUMULATIVE,
            }
        )
        self._endpoint = endpoint
        self._timeout = timeout
        self._transport = transport
        self._headers = {"content-type": "application/x-protobuf"}
        if authorization is not None:
            self._headers["authorization"] = authorization
        self._closed = False
        self._lock = threading.Lock()
        self.state = "not_exported"
        self.rejected_points = 0

    def _failure(self, category: str, rejected: int = 0) -> MetricExportResult:
        self.state, self.rejected_points = category, rejected
        _logger.warning("otlp_export_failed", category=category, rejected_points=rejected)
        return MetricExportResult.FAILURE

    async def _dispatch(self, payload: bytes, duration: float) -> tuple[str | None, int]:
        async with (
            asyncio.timeout(duration),
            httpx.AsyncClient(
                transport=self._transport,
                trust_env=False,
                follow_redirects=False,
                verify=True,
                timeout=duration,
            ) as client,
            client.stream(
                "POST", self._endpoint, headers=self._headers, content=payload
            ) as response,
        ):
            if response.status_code != HTTP_OK:
                return "http_status", 0
            acknowledgement = bytearray()
            async for chunk in response.aiter_bytes():
                if len(acknowledgement) + len(chunk) > MAX_ACK_BYTES:
                    return "ack_capacity", 0
                acknowledgement.extend(chunk)
        result = ExportMetricsServiceResponse()
        result.ParseFromString(bytes(acknowledgement))
        rejected = result.partial_success.rejected_data_points
        if rejected or result.partial_success.error_message:
            return "partial", max(0, rejected)
        return None, 0

    def export(
        self, metrics_data: MetricsData, timeout_millis: float = 10000, **kwargs: Any
    ) -> MetricExportResult:
        _ = kwargs
        with self._lock:
            if self._closed:
                return self._failure("closed")
            category, rejected = None, 0
            started = time.monotonic()
            try:
                payload = encode_metrics(metrics_data).SerializeToString()
                if len(payload) > MAX_REQUEST_BYTES:
                    category = "payload_capacity"
                else:
                    duration = min(self._timeout, max(0.001, timeout_millis / 1000)) - (
                        time.monotonic() - started
                    )
                    if duration <= 0:
                        category = "deadline"
                    else:
                        category, rejected = asyncio.run(self._dispatch(payload, duration))
            except DecodeError:
                category = "invalid_ack"
            except TimeoutError:
                category = "deadline"
            except httpx.HTTPError:
                category = "transport"
            except (ValueError, TypeError):
                category = "encoding"
            if category is not None:
                return self._failure(category, rejected)
            self.state, self.rejected_points = "acknowledged", 0
            return MetricExportResult.SUCCESS

    def force_flush(self, timeout_millis: float = 10000) -> bool:
        _ = timeout_millis
        return True

    def shutdown(self, timeout_millis: float = 30000, **kwargs: Any) -> None:
        _ = timeout_millis, kwargs
        with self._lock:
            if not self._closed:
                self._closed = True
                self._headers.clear()
                self._transport = None


class OtlpMetricsStore:
    """Local Prometheus plus bounded per-lifetime OTel counters/histogram."""

    def __init__(
        self, settings: Any, *, reader: Any = None, exporter: ConfinedMetricExporter | None = None
    ) -> None:
        if os.environ.get("OTEL_SDK_DISABLED", "").strip().lower() == "true":
            raise ValueError("Enabled telemetry cannot use a disabled OpenTelemetry SDK")
        self._local = InMemoryMetricsStore()
        self._pairs = {
            (model, backend) for model, pool in settings.models.items() for backend in pool.backends
        }
        self._pairs.update((model, "none") for model in settings.models)
        self._pairs.add(("other", "none"))
        self._backends = set(settings.backends)
        self._series_budget = settings.telemetry_series_budget
        self._series: set[tuple[Any, ...]] = set()
        self._dropped = 0
        self._closed = False
        self._shutdown_lock = asyncio.Lock()
        self._exporter = exporter
        if reader is None:
            self._exporter = exporter or ConfinedMetricExporter(
                settings.telemetry_endpoint,
                authorization=settings.telemetry_authorization.get_secret_value()
                if settings.telemetry_authorization
                else None,
                timeout=settings.telemetry_timeout_seconds,
            )
            reader = PeriodicExportingMetricReader(
                self._exporter,
                export_interval_millis=settings.telemetry_interval_seconds * 1000,
                export_timeout_millis=settings.telemetry_timeout_seconds * 1000,
            )
        self._reader = reader
        self.instance_id = str(uuid.uuid4())
        try:
            self._provider = MeterProvider(
                metric_readers=[reader],
                resource=Resource(
                    {
                        "service.name": settings.telemetry_service_name,
                        "service.instance.id": self.instance_id,
                        "process.pid": os.getpid(),
                        "foundry.replica": settings.telemetry_replica_id,
                        "foundry.revision": settings.telemetry_revision_id,
                    }
                ),
                shutdown_on_exit=False,
                exemplar_filter=AlwaysOffExemplarFilter(),
                views=[
                    View(
                        instrument_name="foundry_router_latency_seconds",
                        attribute_keys={"model", "backend"},
                        aggregation=ExplicitBucketHistogramAggregation(LATENCY_BUCKETS_SECONDS),
                    )
                ],
            )
            meter = self._provider.get_meter("foundry_router", "0.1.0")
            self._requests = meter.create_counter("foundry_router_requests_total")
            self._latency = meter.create_histogram("foundry_router_latency_seconds", unit="s")
            self._cost = meter.create_counter("foundry_router_estimated_cost_usd_total", unit="USD")
            self._entries = meter.create_counter("combination_exclusion_entries_total")
            self._resets = meter.create_counter("combination_exclusion_resets_total")
        except BaseException:
            try:
                if hasattr(self, "_provider"):
                    self._provider.shutdown(timeout_millis=5000)
                else:
                    reader.shutdown(timeout_millis=5000)
            except BaseException as cleanup_error:
                _logger.warning(
                    "otlp_construction_cleanup_failed", error_type=type(cleanup_error).__name__
                )
            raise

    def _admit_series(self, key: tuple[Any, ...]) -> bool:
        if self._closed:
            return False
        if key not in self._series:
            if len(self._series) >= self._series_budget:
                self._dropped += 1
                return False
            self._series.add(key)
        return True

    async def observe_request(
        self,
        *,
        model: str,
        backend: str,
        status_code: int,
        latency_seconds: float,
        estimated_cost_usd: float | None,
    ) -> None:
        if (model, backend) not in self._pairs:
            model, backend = "other", "none"
        status = str(status_code) if MIN_STATUS <= status_code <= MAX_STATUS else "other"
        await self._local.observe_request(
            model=model,
            backend=backend,
            status_code=status_code,
            latency_seconds=latency_seconds,
            estimated_cost_usd=estimated_cost_usd,
        )
        attrs = {"model": model, "backend": backend}
        try:
            if self._admit_series(("requests", model, backend, status)):
                self._requests.add(1, {**attrs, "status": status})
            if self._admit_series(("latency", model, backend)):
                self._latency.record(
                    latency_seconds
                    if math.isfinite(latency_seconds) and latency_seconds >= 0
                    else 0,
                    attrs,
                )
            if (
                estimated_cost_usd is not None
                and math.isfinite(estimated_cost_usd)
                and estimated_cost_usd >= 0
                and self._admit_series(("cost", model, backend))
            ):
                self._cost.add(estimated_cost_usd, attrs)
        except Exception as exc:
            _logger.warning("otlp_observation_failed", error_type=type(exc).__name__)

    async def observe_combination_exclusion(
        self, *, backend: str, operation: str, stream: str, cleared: bool
    ) -> None:
        await self._local.observe_combination_exclusion(
            backend=backend, operation=operation, stream=stream, cleared=cleared
        )
        if (
            backend not in self._backends
            or operation not in {"responses", "embeddings"}
            or stream not in {"stream", "nonstream"}
        ):
            self._dropped += 1
            return
        try:
            if self._admit_series(("reset" if cleared else "entry", backend, operation, stream)):
                instrument = self._resets if cleared else self._entries
                instrument.add(1, {"backend": backend, "operation": operation, "stream": stream})
        except Exception as exc:
            _logger.warning("otlp_observation_failed", error_type=type(exc).__name__)

    async def render_prometheus(self, **kwargs: Any) -> str:
        return await self._local.render_prometheus(**kwargs)

    async def reset(self) -> None:
        """Reset diagnostic local counters; exported cumulative instruments stay monotonic."""
        await self._local.reset()

    def export_status(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "state": self._exporter.state if self._exporter else "injected_reader",
            "rejected_points": self._exporter.rejected_points if self._exporter else 0,
            "dropped_observations": self._dropped,
            "series": len(self._series),
        }

    async def shutdown(self) -> None:
        async with self._shutdown_lock:
            if self._closed:
                return
            self._closed = True
            # Reader shutdown stops the ticker and performs its serialized final collection.
            # No separate force_flush: it would duplicate/race that final export.
            timeout = 2 * self._exporter._timeout + 2 if self._exporter else 5
            task = asyncio.create_task(
                asyncio.to_thread(self._provider.shutdown, timeout_millis=timeout * 1000)
            )
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
            task.result()
