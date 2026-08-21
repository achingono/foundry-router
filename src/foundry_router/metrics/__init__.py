"""In-process Prometheus metric aggregation and rendering."""

from __future__ import annotations

import asyncio
from collections import defaultdict

LATENCY_BUCKETS_SECONDS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class InMemoryMetricsStore:
    """Thread-safe metric snapshots rendered in Prometheus text format."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._request_totals: dict[tuple[str, str, str], int] = defaultdict(int)
        self._latency_sum_seconds: dict[tuple[str, str], float] = defaultdict(float)
        self._latency_count: dict[tuple[str, str], int] = defaultdict(int)
        self._latency_bucket_counts: dict[tuple[str, str, float], int] = defaultdict(int)
        self._estimated_cost_total_usd: dict[tuple[str, str], float] = defaultdict(float)

    async def observe_request(
        self,
        *,
        model: str,
        backend: str,
        status_code: int,
        latency_seconds: float,
        estimated_cost_usd: float | None,
    ) -> None:
        labels = (model, backend)
        safe_latency_seconds = max(0.0, latency_seconds)
        async with self._lock:
            self._request_totals[(model, backend, str(status_code))] += 1
            self._latency_sum_seconds[labels] += safe_latency_seconds
            self._latency_count[labels] += 1
            for bucket in LATENCY_BUCKETS_SECONDS:
                if safe_latency_seconds <= bucket:
                    self._latency_bucket_counts[(model, backend, bucket)] += 1
                    break
            if estimated_cost_usd is not None and estimated_cost_usd >= 0:
                self._estimated_cost_total_usd[labels] += estimated_cost_usd

    async def reset(self) -> None:
        async with self._lock:
            self._request_totals.clear()
            self._latency_sum_seconds.clear()
            self._latency_count.clear()
            self._latency_bucket_counts.clear()
            self._estimated_cost_total_usd.clear()

    async def render_prometheus(
        self,
        *,
        backend_health_states: dict[str, str],
        backend_available_credit_usd: dict[str, float],
    ) -> str:
        async with self._lock:
            request_totals = dict(self._request_totals)
            latency_sum = dict(self._latency_sum_seconds)
            latency_count = dict(self._latency_count)
            latency_buckets = dict(self._latency_bucket_counts)
            estimated_cost_totals = dict(self._estimated_cost_total_usd)

        lines: list[str] = []
        lines.append(
            "# HELP foundry_router_requests_total Total HTTP requests processed by "
            "model/backend/status"
        )
        lines.append("# TYPE foundry_router_requests_total counter")
        for (model, backend, status), count in sorted(request_totals.items()):
            lines.append(
                "foundry_router_requests_total"
                "{"
                f'model="{_escape_label(model)}",'
                f'backend="{_escape_label(backend)}",'
                f'status="{_escape_label(status)}"'
                "} "
                f"{count}"
            )

        lines.append("# HELP foundry_router_latency_seconds Request latency by model/backend")
        lines.append("# TYPE foundry_router_latency_seconds histogram")
        for model_backend in sorted(latency_count):
            model, backend = model_backend
            cumulative = 0
            for bucket in LATENCY_BUCKETS_SECONDS:
                cumulative += latency_buckets.get((model, backend, bucket), 0)
                lines.append(
                    "foundry_router_latency_seconds_bucket"
                    "{"
                    f'model="{_escape_label(model)}",'
                    f'backend="{_escape_label(backend)}",'
                    f'le="{bucket:g}"'
                    "} "
                    f"{cumulative}"
                )
            lines.append(
                "foundry_router_latency_seconds_bucket"
                f'{{model="{_escape_label(model)}",backend="{_escape_label(backend)}",le="+Inf"}} '
                f"{latency_count[model_backend]}"
            )
            lines.append(
                "foundry_router_latency_seconds_sum"
                f'{{model="{_escape_label(model)}",backend="{_escape_label(backend)}"}} '
                f"{latency_sum[model_backend]:.9f}"
            )
            lines.append(
                "foundry_router_latency_seconds_count"
                f'{{model="{_escape_label(model)}",backend="{_escape_label(backend)}"}} '
                f"{latency_count[model_backend]}"
            )

        lines.append(
            "# HELP foundry_router_estimated_cost_usd_total Estimated request-cost sum by "
            "model/backend"
        )
        lines.append("# TYPE foundry_router_estimated_cost_usd_total counter")
        for (model, backend), total_cost in sorted(estimated_cost_totals.items()):
            lines.append(
                "foundry_router_estimated_cost_usd_total"
                f'{{model="{_escape_label(model)}",backend="{_escape_label(backend)}"}} '
                f"{total_cost:.9f}"
            )

        lines.append(
            "# HELP foundry_router_backend_health_state Backend health state gauge "
            "(1=active,0=not active)"
        )
        lines.append("# TYPE foundry_router_backend_health_state gauge")
        for backend_id, state in sorted(backend_health_states.items()):
            lines.append(
                "foundry_router_backend_health_state"
                f'{{backend="{_escape_label(backend_id)}",state="{_escape_label(state)}"}} '
                "1"
            )

        lines.append(
            "# HELP foundry_router_credit_available_usd Live estimated spendable credit by backend"
        )
        lines.append("# TYPE foundry_router_credit_available_usd gauge")
        for backend_id, available_credit in sorted(backend_available_credit_usd.items()):
            lines.append(
                "foundry_router_credit_available_usd"
                f'{{backend="{_escape_label(backend_id)}"}} '
                f"{available_credit:.9f}"
            )

        return "\n".join(lines) + "\n"
