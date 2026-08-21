# Observability and Troubleshooting

## Status: Partially implemented

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

## Live Administrative Diagnostics (Implemented / Planned Phase 06)

Authenticated administrators can query `GET /admin/status` (requires `x-admin-key`).
- **Configuration snapshot**: Returns configured backends, endpoints, regions, deployments, models, weights, and cycle parameters.
- **Live diagnostics (Phase 06 target)**: Exposes real-time ephemeral health states, remaining cooldown seconds, available credit, in-flight reservations, and cycle reset timestamps without disclosing secrets.

## Prometheus & OpenTelemetry Metrics (Planned Phase 06)

Expose standard Prometheus-compatible `/metrics`:
- `foundry_router_requests_total{model, backend, status}`: Request outcome counter.
- `foundry_router_latency_seconds{model, backend}`: Latency and time-to-first-token (TTFT) histogram.
- `foundry_router_estimated_spend_usd_total{model, backend}`: Cumulative estimated spend.
- `foundry_router_backend_health_state{backend}`: Current backend health state gauge.
- `foundry_router_credit_available_usd{backend}`: Current spendable balance gauge.

## Operator Checks

When a request fails, inspect model configuration, candidate availability, backend state, cooldown expiry, quota signals, credit estimate and reserve, and retry count. Distinguish upstream errors from router validation errors. Administrative status must never reveal credentials.

## Cost and Credit Warnings

Estimated spend is not authoritative Azure cost. Stale reconciliation state or negative estimates must be visible. If all candidates are protected or a conservative request reservation cannot fit, return an explicit safe-capacity error (`503 insufficient_credit_capacity`) rather than silently routing unsafely.
