# Phase 06 Activities

## Step-By-Step Activities

1. **State Store Abstractions & Azure Table Storage Adapter**:
    - Define `CreditStore` and `HealthStore` abstract protocols in dedicated state/domain modules (`src/foundry_router/state/` or domain packages).
    - Retain the implemented `InMemoryCreditStore` and `InMemoryHealthStore` as default single-process implementations; add the planned `HealthStore` protocol.
    - Store each backend balance row and its request-reservation rows in one Azure Table partition keyed by backend ID. Use an ETag-guarded transactional batch to create, settle, or release a reservation and update the balance atomically.
    - Make reservation operations idempotent. Persist the reservation state, backend ID, request ID, cost, and expiry; adjust the store API so finalization retains or receives the backend ID needed to address the correct partition.
    - Implement bounded recovery that settles or releases expired unfinished reservations without double charging.
    - Implement Azure Table Storage adapters for reconciliation snapshots using conditional writes and ETags.
    - Store backend health and cooldown snapshots with timestamps and last-write-wins semantics; treat them as eventually consistent as specified by ADR-005.
    - Use unconditional timestamped upserts for health state, invalidate local snapshot cache entries after transitions, and keep shutdown reset local-only.
    - Fail closed when authoritative credit reservation operations cannot complete; do not use a local fallback that could oversubscribe shared credit.

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
    - Parallelize distributed health reads and use a bounded short-lived local snapshot cache for stable `ACTIVE`/`DISABLED` state; evaluate cooldown expiry from timestamped storage reads rather than caching fixed remaining durations.

4. **Multi-Worker Concurrency Testing**:
    - Add integration tests running multi-threaded / multi-process simulation against Azure Table Storage adapters, including ETag conflicts, reservation release, fail-closed storage failures, and recovery after interruption at every reservation state transition.
   - Verify metric scrape monotonicity across concurrent worker processes.

## Review Focus
- Conditional-write correctness of distributed credit reservations under high concurrency.
- Zero secret leakage in `/admin/status` and `/metrics`.
- Process-independent metric scraping in multi-worker environments.
- Minimal latency overhead on request hot path.
