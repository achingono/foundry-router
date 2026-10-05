# Observability and Troubleshooting

## Status: Implemented (single-process Prometheus + live diagnostics; multi-process aggregation Planned)

Use structured JSON logs with correlation IDs (`x-request-id`). Record request ID, model, backend, endpoint type, status, latency, tokens, estimated cost, retry count, streaming flag, routing state, and routing score. Never record authorization headers, API keys, prompts, or model outputs.

## Structured Decision Logging (Implemented)

The router emits structured `routing_decision` logs on every candidate selection containing:
- `request_id`: Tracing correlation ID
- `model`: Target logical model
- `operation`: `responses` or `embeddings`
- `selected_backend`: Chosen backend ID or `null`
- `reason`: Rationale (`selected`, `all_candidates_in_cooldown_or_disabled`, `insufficient_credit_capacity`, etc.)
- `estimated_request_cost_usd`: Conservative request reservation amount

Per-backend candidate detail (health, cooldown, credit, score, quota headroom) is emitted on a separate `routing_decision_detail` event at `DEBUG` on success and `WARNING` on failure, so production `INFO` carries the decision without the full candidate array (Phase 10 source-volume reduction).

For configured quota groups, candidate details also include the `quota_group`, normalized
`quota_headroom`, and remaining RPM, input TPM, and RPD. These fields identify project groups and
backend IDs only; credentials are not logged.

## Live Administrative Diagnostics (Implemented)

Authenticated administrators can query `GET /admin/status` (requires `x-admin-key`).
- **Configuration snapshot**: Returns configured backends, endpoints, regions, deployments, models, weights, and cycle parameters.
- **Live diagnostics**: Exposes health state, cooldown remaining seconds, credit state, available credit, reserved in-flight amount, active reservation count, oldest active reservation age in seconds, and cycle boundary timestamps without disclosing secrets. Table-backed diagnostics are implemented in code; Azure deployment verification remains pending.
- **Quota diagnostics**: For configured quota groups, each backend includes its group ID, RPM/input-TPM/RPD usage and remaining budget, exhaustion state, and reset delay. Keys sharing a group show the same snapshot. These values are in-process estimates, not authoritative Google counters.
- **Multi-replica support**: Deployed shared state remains **Partially implemented** until Azure validation and a two-replica deployment pass. Table provisioning, identity-only client wiring, startup selection and bounded readiness probes are implemented in the current code; production remains memory-backed with one replica.

## Reservation Lifecycle Safety (Implemented)

Each in-memory credit reservation tracks a monotonic creation timestamp. A bounded lock-protected sweep (from `assess` and `try_assign_reservation`) settles reservations older than `reservation_max_age_seconds` (`FOUNDRY_RESERVATION_MAX_AGE_SECONDS`, default 900 seconds) conservatively: valid retained settlement intent wins; otherwise the full reserved estimate is charged, including legacy/pre-egress rows. Confirmed explicit releases charge zero. The sweep is disabled for a non-finite age; production defaults enable it. Keep the age beyond legitimate stream duration; later authoritative reconciliation can correct overestimated recovery charges.

For `AzureTableCreditStore`, the explicit reaper scans group `req-*` rows and atomically debits retained intent or the full estimate while decrementing inflight reservations and deleting the row. Fresh balance and reservation ETags guard recovery against intent/finalization races. Reconciliation invokes it best-effort; diagnostic scans require `query_entities`. See [recovery and cleanup policy](shared-resource-credit.md) for ambiguous admission, bounded ownership and cancellation handling.

## Credit and Pricing Configuration Completeness (Implemented)

Incomplete Table sync fails explicitly at startup/request admission; retained recovery aliases do
not permit dispatch under new incomplete Settings. Periodic ownership maintenance independently
checks all known partitions, freeing only confirmed absent/finalized slots and preserving incomplete
or ambiguous owners. Post-output stream failures debit known usage or full reserve, including when
the telemetry status is 502. See [operations](shared-resource-credit.md).

`GET /health/ready` reports `backend_credit_config_complete` and `model_pricing_complete`, plus `state_store_reachable` in table mode. The storage check verifies each unique routable metered credit group has a balance row and checks health-table reachability; probes are cached for at most five seconds. `rate_limit_share_valid` and a `rate_limit_share_<group>_<dimension>_valid` check identify any per-replica RPM, input-TPM, or RPD share that floors to zero. Readiness returns `503` for any failed check; this is a readiness-level signal, not a configuration-load failure. Request-time credit and quota admission still fail closed independently of the cached readiness result.

## Prometheus & OpenTelemetry Metrics (Implemented single-process; multi-process aggregation Planned)

The router exposes a Prometheus-compatible `/metrics` endpoint for in-process metrics:
- `foundry_router_requests_total{model, backend, status}`: Request outcome counter.
- `foundry_router_latency_seconds{model, backend}`: Latency and time-to-first-token (TTFT) histogram.
- `foundry_router_estimated_cost_usd_total{model, backend}`: Cumulative estimated request-cost.
- `foundry_router_backend_health_state{backend}`: Current backend health state gauge.
- `foundry_router_credit_available_usd{backend}`: Nonadditive backend view of estimated account credit.
- `foundry_router_credit_group_available_usd{credit_group}`: Canonical unique account spendable estimate.
- `foundry_router_rate_limit_remaining{backend, quota_group, limit}`: Remaining configured RPM, input TPM, or RPD budget.
- `foundry_router_rate_limit_exhausted{backend, quota_group}`: Whether the project quota group is exhausted.
- `foundry_router_rate_limit_cooldown{backend, quota_group}`: Whether the backend is currently in quota cooldown.
- `/metrics` uses admin authentication (`x-admin-key` or Bearer admin token).
- Single-process in-memory collection via `InMemoryMetricsStore` (implemented in Phase 06).

Multi-process metric aggregation (for `--workers > 1` deployments) requires either:
- `prometheus_client` multiprocess mode (file-based metric storage in `PROMETHEUS_MULTIPROC_DIR`)
- OpenTelemetry exporter integration
- Both remain **Planned**; current implementation (`src/foundry_router/metrics/__init__.py:15` `InMemoryMetricsStore`) is single-process only.

## Operator Checks

Shared credit account diagnostics and drained-state migration are described in
[shared-resource credit operations](shared-resource-credit.md). `/admin/status.credit_groups`
exposes each account once; backend entries identify `credit_group` and mirror its snapshot.

When a request fails, inspect model configuration, candidate availability, backend state, cooldown expiry, quota signals, credit estimate and reserve, and retry count. Distinguish upstream errors from router validation errors. Administrative status must never reveal credentials.

## Cost and Credit Warnings

Estimated spend is not authoritative Azure cost. Stale reconciliation state or negative estimates must be visible. If all candidates are protected or a conservative request reservation cannot fit, return an explicit safe-capacity error (`503 insufficient_credit_capacity`) rather than silently routing unsafely.
