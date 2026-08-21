# Phase 06 Activities

## Step-By-Step Activities

1. **State Store Abstractions & Redis Adapter**:
   - Define `CreditStore` and `HealthStore` abstract protocols in dedicated state/domain modules (`src/foundry_router/state/` or domain packages).
   - Implement `InMemoryCreditStore` and `InMemoryHealthStore` as default single-process implementations.
   - Implement `RedisCreditStore` and `RedisHealthStore` using atomic Lua scripts for atomic reservation assignment, release, and cooldown window enforcement.

2. **Live Admin Diagnostic Introspection**:
   - Enhance `GET /admin/status` to report real-time live diagnostics:
     - Per-backend live `BackendHealthState` and `cooldown_remaining_seconds`.
     - Live `available_credit_usd`, `reserved_inflight_usd`, and `CreditState`.
     - Next billing cycle reset timestamp (`next_reset_utc`).

3. **Metrics, Multi-Worker Aggregation & OpenTelemetry Export**:
   - Maintain Prometheus `/metrics` endpoint with counters, histograms, and gauges (secured via admin authentication):
     - `foundry_router_requests_total{model, backend, status}`
     - `foundry_router_latency_seconds{model, backend}`
     - `foundry_router_estimated_cost_usd_total{model, backend}`
     - `foundry_router_backend_health_state{backend}`
     - `foundry_router_credit_available_usd{backend}`
   - Support multi-worker (`--workers > 1`) metric scraping via `prometheus_client` multiprocess directory aggregation or an OpenTelemetry exporter.
   - Refine streaming telemetry lifecycle to cleanly differentiate client-side disconnects/cancellations (`asyncio.CancelledError`), mid-stream upstream errors (`502`), and complete streams (`200`).

4. **Multi-Worker Concurrency Testing**:
   - Add integration tests running multi-threaded / multi-process simulation against state store adapters (`RedisCreditStore`, `RedisHealthStore`).
   - Verify metric scrape monotonicity across concurrent worker processes.

## Review Focus
- Atomicity of distributed credit reservations under high concurrency.
- Zero secret leakage in `/admin/status` and `/metrics`.
- Process-independent metric scraping in multi-worker environments.
- Minimal latency overhead on request hot path.

