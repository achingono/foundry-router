# Routing and Scheduling

## Status: Implemented (Core, Credit Scheduling, Reconciliation) / Planned (Distributed Stores)

For each request: identify the model, find its configured candidates, remove disabled and cooldown backends when alternatives exist, estimate request cost, evaluate local credit safety reserve/capacity, score viable candidates, reserve before dispatch, forward, release reservation on completion, and return the response.

## Separate Quota from Credit

Quota represents rate or capacity constraints such as TPM/RPM. Credit represents a dollar or resource allowance. A backend can have high credit and exhausted quota, or available quota and insufficient safe credit. The router considers both independently.

## Backend States

- `ACTIVE`: Healthy, routes normally.
- `CONSERVATION`: Usable under reduced traffic when projected cycle-end utilization is low or reserve pressure is rising.
- `PROTECTED`: Receives no intentional traffic because spendable credit is below safety reserve thresholds.
- `QUOTA_COOLDOWN`: Temporarily removes a backend after HTTP 429 rate limits.
- `ERROR_COOLDOWN`: Temporarily removes a backend after repeated transient 5xx server/transport errors.
- `DISABLED`: Manually disabled by operator configuration.

Protected emergency fallback is configurable if all candidates are in cooldown or protected state.

## Credit and Cycle Policy

```text
spendable_credit = remaining_credit - safety_reserve
projected_unused_credit = remaining_credit - estimated_daily_burn * days_remaining
```

Prefer a usable backend that would otherwise waste more credit before its cycle ends, without crossing its safety reserve. Each backend has an independent cycle start day. Calculations handle month lengths, February 28/29 leap years, month and year boundaries, and represent the actual credit reset period.

## Concurrency and Reservation Lifecycle

Reserve a conservative estimated request cost before dispatch:

```text
available_credit = estimated_remaining_credit - reserved_inflight_cost - safety_reserve
```

### Safety and Cleanup Invariants:
1. **Guaranteed Cleanup**: The entire dispatch and failover lifecycle is enclosed in a `try...finally` block, guaranteeing that `finalize_request` is invoked on normal return, secondary failover exceptions, or client task cancellation (`asyncio.CancelledError`).
2. **Non-2xx Upstream Zero Charge**: When an upstream backend rejects a request with a non-2xx status code (e.g. 400 Bad Request, 422 Unprocessable Entity, or failed 5xx), the reserved in-flight credit is released without debiting the backend balance.
3. **Streaming Terminal Usage Extraction**: During streaming SSE pass-through, the generator parses terminal `usage` events (e.g. `stream_options: {"include_usage": true}`) with a bounded accumulation buffer (`MAX_SSE_EVENT_BUFFER_BYTES`) to settle the final charge against exact actual token usage rather than conservative defaults.
4. **Safe Capacity Rejection**: If no candidate can safely accept the conservative reservation without crossing safety reserves, reject with `503` and `insufficient_credit_capacity` without backend egress.

## Scoring and Explainability

Composite candidate scores combine availability, quota health, credit health, cycle urgency, and error health per ADR-006.

Every routing decision emits a structured `routing_decision` event containing:
- `model`: Requested model identifier
- `operation`: Target operation (`responses` or `embeddings`)
- `request_id`: Request correlation ID
- `selected_backend`: Selected backend ID or `null` if none
- `reason`: Rationale (e.g. `selected`, `all_candidates_in_cooldown_or_disabled`, `insufficient_credit_capacity`)
- `estimated_request_cost_usd`: Conservative calculated cost
- `candidates`: Array of candidate health states, cooldowns, credit states, and computed composite scores.

## Retry and Failover

Retry only transient `429`, `500`, `502`, `503`, and `504` failures by default. Allow one immediate backend failover by default, use bounded exponential backoff, honor `Retry-After` within a maximum delay, and never retry indefinitely. A 429 enters quota cooldown. No retry or failover occurs after streaming has meaningfully started.

## State Store Abstractions (Phases 5–6)

Single-instance deployments use `InMemoryCreditStore` and `InMemoryHealthStore`. `CreditStore` is partially implemented; `HealthStore` and the injected-client Azure Table health boundary are implemented. Before future scale-out (`max_replicas > 1`), both protocols will be backed by Azure Table Storage: same-backend-partition transactional batches protect shared credit reservations, while timestamped health snapshots use ADR-005's eventually consistent semantics. Redis is an optional later cache and cannot replace the authoritative store.
