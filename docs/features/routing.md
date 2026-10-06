# Routing and Scheduling

## Status: Implemented (core, credit scheduling, process-local Google quota-aware routing, and operation-aware adapter routing with mocked verification; distributed quota accounting and real Google inference Planned)

For each request: identify the model, filter candidates by declared `supported_operations` and provider request capabilities, find its configured candidates, remove disabled and cooldown backends when alternatives exist, estimate request cost, evaluate local credit safety reserve/capacity, score viable candidates, reserve before dispatch, forward, release reservation on completion, and return the response.

Operation-aware routing applies identically on initial selection and failover, before either store reserves. If no configured candidate supports the operation, routing returns HTTP 422 `unsupported_operation` without egress; if candidates support the operation but none support the request features (for example tools on Google pools without an enabled profile), routing returns the relevant unsupported-field error; capable Azure candidates stay eligible, including during failover. Google embedding models require explicit `supported_operations: ["embeddings"]`.

## Logical Model Aliases (Implemented with mocked verification)

Explicit aliases resolve once to a canonical pool before candidate ranking, cost
estimation, admission, failover, streaming settlement, and metrics. The router keeps
requested, canonical, and physical deployment identities separate: accounting and
policy inherit the target pool, while diagnostics carry `requested_model`,
`resolved_model`, and `alias` alongside the canonical `model`. Resolution is frozen
for in-flight requests, so retargeting or removing an alias only affects later
requests through the normal drain/restart procedure.

## Separate Quota from Credit

Quota represents rate or capacity constraints such as TPM/RPM. Credit represents a dollar or resource allowance. A backend can have high credit and exhausted quota, or available quota and insufficient safe credit. The router considers both independently.

## Google AI Studio Quota Routing (Implemented, Single-Process; Adapter Mock-Verified)

Represent each API key as a backend in the model pool. Routing uses the existing deterministic
score and weight tie-break, not round-robin. A quota-health term is the minimum remaining fraction
after the estimated request across configured RPM, input-TPM, and RPD dimensions, clamped to
`0.0–1.0`; candidates that cannot fit the estimated request are skipped unless the single-candidate
protected emergency fallback applies. The quota-health term uses ADR-006's existing 0.2 score
weight.

Rate state is shared by `quota_group` (normally a Google Cloud project), so keys in one project
share budget and cooldown. The router reserves estimated input usage before dispatch and updates it
from translated response usage or terminal Responses SSE usage when available; embeddings use the
same quota store on selection, failover, and finalization. On failover the dispatched attempt's
quota consumption is retained (finalized into recorded usage) before the second attempt is
admitted, so every upstream dispatch is counted. Estimates cover `instructions` and
supported history plus per-message overhead. Failover transfers the server-owned reservation;
abandoned reservations are reclaimed after the configured age. Exhaustion and pre-output 429s cool
all configured backends in the project group; Google 401/403 enters backend-local `ERROR_COOLDOWN`
without same-request key cycling. Only Google 429 is retryable/failover-eligible; ambiguous
dispatched failures retain conservative quota consumption and settle credit without another
dispatch. The existing no-failover-after-stream-output rule is
unchanged (for Google, latched at the first downstream event, including lifecycle events).

The in-memory quota store is single-process only. Multi-worker and multi-replica quota aggregation
is **Planned**; do not interpret local snapshots as authoritative Google quota counters.

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

Prefer a usable backend whose credit group would otherwise waste more credit before its cycle ends, without crossing that account's safety reserve. Each credit group has an independent cycle start day. Omitted membership defaults to backend ID. All model pools using one group share available credit and inflight capacity. Calculations handle month lengths, February 28/29 leap years, month and year boundaries, and represent the actual credit reset period.

## Concurrency and Reservation Lifecycle

Reserve a conservative estimated request cost before dispatch:

```text
available_credit = estimated_remaining_credit - reserved_inflight_cost - safety_reserve
```

### Safety and Cleanup Invariants:
Expired pending credit reservations are conservatively settled using retained valid intent or the
full reserved estimate. This includes legacy/pre-egress rows; age never proves that work was free.
Table admission exceptions (including commit then timeout) stop selection with a typed failure.
Incomplete Table sync also stops dispatch instead of selecting under retained old membership.
Membership includes metering and publishes under the same local lock as admission. Existing request
IDs cannot move accounts without confirmed release. Stream financial cleanup is bounded and shielded
independently of context close. See [recovery policy](../operations/shared-resource-credit.md).
Post-output streaming failure settles known usage or the full reserved estimate; failure status is
not evidence that provider work was free. Periodic complete ownership discovery frees confirmed
absent/finalized tracking slots even when balance reconciliation is unavailable.
1. **Failure-aware Cleanup**: Dispatch/failover cleanup handles normal return, secondary failures and client cancellation. Failed release hard-stops second selection/egress. Failed settlement preserves the pending reservation and is never converted to a free release; quota/telemetry cleanup runs independently. Streaming never fails over after output.
2. **Non-2xx Upstream Zero Charge**: When an upstream backend rejects a request with a non-2xx status code (e.g. 400 Bad Request, 422 Unprocessable Entity, or failed 5xx), the reserved in-flight credit is released without debiting the backend balance.
3. **Streaming Terminal Usage Extraction**: During streaming SSE pass-through, the generator parses terminal `usage` events (e.g. `stream_options: {"include_usage": true}`) with a bounded accumulation buffer (`MAX_SSE_EVENT_BUFFER_BYTES`) to settle the final charge against exact actual token usage rather than conservative defaults.
4. **Safe Capacity Rejection**: If no candidate can safely accept the conservative reservation without crossing safety reserves, reject with `503` and `insufficient_credit_capacity` without backend egress.

## Scoring and Explainability

Composite candidate scores combine availability, quota health, credit health, cycle urgency, and error health per ADR-006.

Every routing decision emits a structured `routing_decision` event containing:
- `model`: Resolved canonical model identifier
- `requested_model`: Client-supplied model identifier
- `resolved_model`: Canonical target (equals `model`)
- `alias`: Whether the request used a configured alias
- `operation`: Target operation (`responses` or `embeddings`)
- `request_id`: Request correlation ID
- `selected_backend`: Selected backend ID or `null` if none
- `reason`: Rationale (e.g. `selected`, `all_candidates_in_cooldown_or_disabled`, `insufficient_credit_capacity`)
- `estimated_request_cost_usd`: Conservative calculated cost

Per-backend candidate detail (health, cooldown, credit, composite score, quota headroom) is emitted on `routing_decision_detail` at `DEBUG`/`WARNING`, not on the production `INFO` event.

## Retry and Failover

Retry only transient `429`, `500`, `502`, `503`, and `504` failures by default. Allow one immediate backend failover by default, use bounded exponential backoff, honor `Retry-After` within a maximum delay, and never retry indefinitely. A 429 enters quota cooldown. No retry or failover occurs after streaming has meaningfully started. Google attempts are single-shot per backend (no internal sleep/retry): the 429 failover above is the only Google retry, admitted fresh with both attempts counted against project quota.

## State Store Abstractions (Phases 5–6, Implemented)

Single-instance deployments use `InMemoryCreditStore` and `InMemoryHealthStore`; table mode selects `AzureTableCreditStore` and `AzureTableHealthStore` (`src/foundry_router/state/table.py`) through the lifespan store factory. Adapter code, the concrete client, conditional provisioning template, and Azurite tests are **Implemented**; deployed multi-replica shared state is **Partially implemented** until Azure validation and a two-replica deployment pass. Azure Table Storage same-backend-partition transactions (ETag-guarded `balance` + `req-{id}` rows) protect shared credit reservations, while timestamped health snapshots use ADR-005's eventually consistent semantics. Redis remains an optional later cache and cannot replace the authoritative store.

## Configured Google feature admission

Feature/combinations and bounded schema/history/media validation precede reservations on both
selection and failover. Unsigned tools are explicit; signed profiles stay disabled. Admission
includes serialized UTF-8 tool/schema/history/text overhead, instructions and configured small
image token ceilings. Google image profiles require separate Google-only logical pools; quotas
and local dollar estimates stay separate, including on non-metered keys. Valid generated usage
settles schema/tool failures; unknown usage retains the full reserve. Intake/storage waits and
original reservation lifetime are bounded without restarting on failover.
