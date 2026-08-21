"""Unit tests for Prometheus metrics aggregation."""

from __future__ import annotations

import asyncio

from foundry_router.metrics import InMemoryMetricsStore


def _metric_value(payload: str, prefix: str) -> float:
    for line in payload.splitlines():
        if line.startswith(prefix):
            return float(line.split()[-1])
    raise AssertionError(f"metric line not found: {prefix}")


class TestInMemoryMetricsStore:
    def test_latency_histogram_uses_discrete_bucket_accumulation(self) -> None:
        store = InMemoryMetricsStore()

        async def exercise() -> str:
            await store.observe_request(
                model="gpt-4",
                backend="backend_a",
                status_code=200,
                latency_seconds=0.01,
                estimated_cost_usd=0.0,
            )
            return await store.render_prometheus(
                backend_health_states={"backend_a": "ACTIVE"},
                backend_available_credit_usd={"backend_a": 1.0},
            )

        payload = asyncio.run(exercise())
        bucket_005 = _metric_value(
            payload,
            'foundry_router_latency_seconds_bucket{model="gpt-4",backend="backend_a",le="0.05"}',
        )
        bucket_01 = _metric_value(
            payload,
            'foundry_router_latency_seconds_bucket{model="gpt-4",backend="backend_a",le="0.1"}',
        )
        bucket_inf = _metric_value(
            payload,
            'foundry_router_latency_seconds_bucket{model="gpt-4",backend="backend_a",le="+Inf"}',
        )

        assert bucket_005 == 1.0
        assert bucket_01 == 1.0
        assert bucket_inf == 1.0
