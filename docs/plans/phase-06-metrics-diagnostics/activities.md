# Phase 06 Activities

## Step-By-Step Activities

1. **State Store Abstractions & Redis Adapter**:
   - Define `CreditStore` and `HealthStore` abstract protocols in domain packages.
   - Implement `InMemoryCreditStore` and `InMemoryHealthStore` as default single-process implementations.
   - Implement `RedisCreditStore` and `RedisHealthStore` using atomic Lua scripts for atomic reservation assignment, release, and cooldown window enforcement.

2. **Live Admin Diagnostic Introspection**:
   - Enhance `GET /admin/status` to report real-time live diagnostics:
     - Per-backend live `BackendHealthState` and `cooldown_remaining_seconds`.
     - Live `available_credit_usd`, `reserved_inflight_usd`, and `CreditState`.
     - Next billing cycle reset timestamp (`next_reset_utc`).

3. **Metrics & OpenTelemetry Export**:
   - Add Prometheus `/metrics` endpoint with counters and histograms:
     - `foundry_router_requests_total{model, backend, status}`
     - `foundry_router_latency_seconds{model, backend}`
     - `foundry_router_estimated_cost_usd_total{model, backend}`
     - `foundry_router_backend_health_state{backend}`
     - `foundry_router_credit_available_usd{backend}`

4. **Multi-Worker Concurrency Testing**:
   - Add integration tests running multi-threaded / multi-process simulation against state store adapters.

## Review Focus
- Atomicity of distributed credit reservations under high concurrency.
- Zero secret leakage in `/admin/status` and `/metrics`.
- Minimal latency overhead on request hot path.
