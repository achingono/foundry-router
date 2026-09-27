"""Unit tests for Prometheus metrics aggregation."""

from __future__ import annotations

import asyncio

from foundry_router.metrics import InMemoryMetricsStore
from foundry_router.ratelimit import QuotaGroupSnapshot


def _metric_value(payload: str, prefix: str) -> float:
    for line in payload.splitlines():
        if line.startswith(prefix):
            return float(line.split()[-1])
    raise AssertionError(f"metric line not found: {prefix}")


class TestInMemoryMetricsStore:
    def test_rate_limit_gauges_use_only_backend_and_group_ids(self) -> None:
        store = InMemoryMetricsStore()
        snapshot = QuotaGroupSnapshot(
            quota_group="project-a",
            remaining_rpm=4,
            remaining_input_tpm=500,
            remaining_rpd=20,
            exhausted=False,
            configured_limits=("rpm", "tpm", "rpd"),
        )

        payload = asyncio.run(
            store.render_prometheus(
                backend_health_states={"gemini-key-1": "ACTIVE"},
                backend_available_credit_usd={},
                backend_rate_limit_snapshots={"gemini-key-1": snapshot},
            )
        )

        assert (
            'foundry_router_rate_limit_remaining{backend="gemini-key-1",'
            'quota_group="project-a",limit="rpm"} 4'
        ) in payload
        assert (
            'foundry_router_rate_limit_remaining{backend="gemini-key-1",'
            'quota_group="project-a",limit="input_tpm"} 500'
        ) in payload
        assert "synthetic-key" not in payload

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
