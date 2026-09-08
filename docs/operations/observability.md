# Observability and Troubleshooting

## Status: Partially implemented (Phase 06 distributed state adapters complete; multi-process aggregation planned Phase 07)

Use structured JSON logs with correlation IDs (`x-request-id`). Record request ID, model, backend, endpoint type, status, latency, tokens, estimated cost, retry count, streaming flag, routing state, and routing score. Never record authorization headers, API keys, prompts, or model outputs.

## Structured Decision Logging (Implemented)

The router emits structured `routing_decision` logs on every candidate selection containing:
- `request_id`: Tracing correlation ID
- `model`: Target logical model
- `operation`: `responses` or `embeddings`
- `selected_backend`: Chosen backend ID or `null`
- `reason`: Rationale (`selected`, `all_candidates_in_cooldown_or_disabled`, `insufficient_credit_capacity`, etc.)
- `estimated_request_cost_usd`: Conservative request reservation amount
- `candidates`: List of evaluated candidate backends with `health_state`, `cooldown_remaining_seconds`, `credit_state`, `available_credit_usd`, `projected_unused_credit_usd`, and composite `score`.

## Live Administrative Diagnostics (Implemented)

Authenticated administrators can query `GET /admin/status` (requires `x-admin-key`).
- **Configuration snapshot**: Returns configured backends, endpoints, regions, deployments, models, weights, and cycle parameters.
- **Live diagnostics**: Exposes ephemeral health state, cooldown remaining seconds, credit state, available credit, reserved in-flight amount, active reservation count, oldest active reservation age in seconds, and cycle boundary timestamps without disclosing secrets. Backed by Azure Table Storage adapters (`AzureTableCreditStore`, `AzureTableHealthStore`) for multi-replica deployments.
- **Multi-replica support**: Azure Table Storage integration enables consistent credit accounting and health state across multiple container instances.

## Reservation Lifecycle Safety (Implemented)

Each in-memory credit reservation tracks a monotonic creation timestamp. A bounded, lock-protected sweep (triggered lazily from `assess` and `try_assign_reservation`) reclaims reservations older than `reservation_max_age_seconds` (`FOUNDRY_RESERVATION_MAX_AGE_SECONDS`, default 900 seconds) without charging the backend, preventing inflight credit from leaking on client disconnects or abandoned streams. The sweep is disabled (no expiry) when the configured max age is left at its non-finite default state; production defaults enable it. The default is aligned to the backend client's read/connect timeout plus margin so legitimate long-running streams are not reclaimed prematurely.

## Credit and Pricing Configuration Completeness (Implemented)

`GET /health/ready` reports two additional checks: `backend_credit_config_complete` (every backend referenced by a model pool has a cycle start day, cycle allowance, and initial estimated remaining credit) and `model_pricing_complete` (every configured model has a pricing entry). Readiness returns `503` when either check fails, surfacing misconfiguration before it silently manifests as `insufficient_credit_capacity` at request time. This is a readiness-level check rather than a config-load failure, preserving the existing fail-closed request-time behavior for defense in depth.

## Prometheus & OpenTelemetry Metrics (Partially implemented)

The router exposes a Prometheus-compatible `/metrics` endpoint for in-process metrics:
- `foundry_router_requests_total{model, backend, status}`: Request outcome counter.
- `foundry_router_latency_seconds{model, backend}`: Latency and time-to-first-token (TTFT) histogram.
- `foundry_router_estimated_cost_usd_total{model, backend}`: Cumulative estimated request-cost.
- `foundry_router_backend_health_state{backend}`: Current backend health state gauge.
- `foundry_router_credit_available_usd{backend}`: Current spendable balance gauge.
- `/metrics` uses admin authentication (`x-admin-key` or Bearer admin token).
- Single-process in-memory collection via `InMemoryMetricsStore` (implemented in Phase 06).

Multi-process metric aggregation (for `--workers > 1` deployments) requires either:
- `prometheus_client` multiprocess mode (file-based metric storage in `PROMETHEUS_MULTIPROC_DIR`)
- OpenTelemetry exporter integration
- Both are planned for Phase 07 operations hardening.

## Operator Checks

When a request fails, inspect model configuration, candidate availability, backend state, cooldown expiry, quota signals, credit estimate and reserve, and retry count. Distinguish upstream errors from router validation errors. Administrative status must never reveal credentials.

## Cost and Credit Warnings

Estimated spend is not authoritative Azure cost. Stale reconciliation state or negative estimates must be visible. If all candidates are protected or a conservative request reservation cannot fit, return an explicit safe-capacity error (`503 insufficient_credit_capacity`) rather than silently routing unsafely.
