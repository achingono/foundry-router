# Phase 04 Activities

## Step-By-Step Activities
1. Confirm Phase 03 gates and document the exact API-to-credit boundary; keep backend transport and health state separate from credit state.
2. Define a credit domain model for cycle windows, backend credit snapshots, request estimates, reservations, and derived states behind an abstract `CreditStore` / `ReservationManager` interface with an `InMemoryCreditStore` implementation for Phase 04 (ADR-005 single-replica alignment). Add validated per-backend local estimates for cycle allowance (`cycle_allowance_usd`) and initial remaining credit (`initial_estimated_remaining_usd`), initialize them from configuration at startup, decrement by completed request usage estimates, and reset to the configured allowance when the calculated UTC cycle rolls over. Mark every locally derived balance and cost as an estimate. Missing credit estimates make a candidate ineligible rather than silently treating it as unlimited; restart behavior is documented as reinitialization from configuration.
3. Implement pure calendar cycle calculations in UTC using each backend's configured start day. Cover month lengths, February, leap years, month/year boundaries, current-cycle start, next reset, and days remaining: `days_remaining = max(1, ceil((next_reset_utc - now_utc).total_seconds() / 86400))` without assuming invoice dates.
4. Implement a deterministic pricing-driven request estimator for supported request shapes:
   - For Responses: estimate input tokens using a conservative upper bound $\lceil\text{len}(\text{text}) / 3\rceil$, recursively extracting string values from structured input (`role`, `content`, `tool_calls`); reserve `max_output_tokens` when specified or fallback to a documented bounded default of `4096` tokens; reject unsupported binary/multimodal content unless a configured bound exists.
   - For embeddings: count input strings or each element of string arrays with the same $\lceil\text{len} / 3\rceil$ bound.
   - Missing pricing configuration makes candidate ineligible (fails closed); zero pricing (`$0.00`) is valid and results in `$0.00` reservation; malformed, non-finite, negative, or unbounded estimates are rejected safely without outbound dispatch.
5. Implement effective reserve, spendable-credit, and burn rate calculations:
   - `safety_reserve = max(min_credit_reserve_usd, cycle_allowance * min_credit_reserve_percent / 100)` (percentage denominator is configured cycle allowance).
   - `available_credit = estimated_remaining_credit - reserved_inflight_cost - safety_reserve`.
   - `estimated_daily_burn = max(0.0, (cycle_allowance - estimated_remaining_credit) / max(1, days_elapsed))` where `days_elapsed` is whole days in UTC since cycle start.
   - `projected_unused_credit = max(0.0, estimated_remaining_credit - estimated_daily_burn * days_remaining)`.
   - Clamp usable credit to zero and never intentionally route across the safety reserve.
6. Define cross-backend reservation ownership:
   - Initial dispatch: atomically check and reserve estimated cost on the selected Backend A.
   - Retries on the same backend: reuse existing reservation.
   - Failover to Backend B: atomically release Backend A's reservation and reserve the estimated cost computed under Backend B's pricing. If Backend B lacks sufficient credit, fail over to the next candidate or return safe-capacity error without dispatching.
   - Idempotent release occurs exactly once when the logical request terminates.
7. Add an in-memory reservation manager with fine-grained concurrency locks (`asyncio.Lock`) protecting check-and-reserve, release, and actual-usage reconciliation. Ensure cleanup covers:
   - Early validation/dispatch rejection and backend acquisition failure.
   - Non-streaming success/error (reconciling actual token usage from response if present, or decrementing reserved estimate).
   - Streaming completion (reconciling usage from final chunk if present, or decrementing reserved estimate upon stream finish or client disconnect).
   - Upstream 429/5xx retry/failover and client cancellation.
8. Integrate credit checks into model-specific candidate selection after health/cooldown filtering. Keep health state (`ACTIVE`, cooldown, `DISABLED`) separate from derived credit state (`USABLE`, `CONSERVATION`, `PROTECTED`, `INSUFFICIENT_CAPACITY`); health/cooldown filtering has precedence, then credit safety filters candidates. When all candidates lack capacity, return `503 Service Unavailable` with `insufficient_credit_capacity` error code without leaking backend names or internal balances.
9. Implement the Phase 04 explainable composite score for remaining candidates using ADR-006's components:
   - Availability: `1.0` if `ACTIVE`, `0.5` if `CONSERVATION`, `0.0` otherwise.
   - Quota Health: `1.0` if healthy, `0.0` if in cooldown.
   - Credit Health: `min(1.0, available_credit / max(estimated_request_cost, 0.0001))`.
   - Cycle Urgency: `clamp(projected_unused_credit / max(cycle_allowance, 0.0001), 0.0, 1.0)`.
   - Error Health: `1.0` if healthy, `0.0` if in error cooldown.
   - Composite Score: `(w1 * availability) + (w2 * quota) + (w3 * credit) + (w4 * urgency) + (w5 * error_health)` with default weights `[0.3, 0.2, 0.2, 0.2, 0.1]`.
   - Deterministic tie-breaking uses configured backend weights / weighted round-robin. Structured decision data logs component scores, estimate age, and reason without exposing secrets.
10. Add conservative state transitions: exclude protected or insufficient-credit candidates, use conservation behavior when projected cycle-end waste meets the documented threshold, and retain the configured emergency fallback semantics without silently crossing the reserve.
11. Preserve existing retry/failover semantics. Failovers release upstream reservation and re-reserve on target; streaming must not retry or fail over after meaningful SSE output.
12. Add focused unit tests for cycle math (UTC, leap years, Feb 28/29, month boundaries), pricing estimates (character token bounds, structured inputs, embeddings, zero pricing), reserves, daily burn rate, cycle urgency, protected/conservation states, large requests, and concurrent reservation contention.
13. Add mocked-backend integration tests for successful accounting, insufficient capacity 503 without outbound egress, A-to-B failover reservation lifecycle (release A, reserve B), non-streaming failure cleanup, streaming completion/failure/cancellation cleanup, unknown models, and interaction with cooldown filtering.
14. Update `README.md`, `docs/index.md`, `docs/features/index.md`, `docs/features/routing.md`, `docs/configuration/index.md`, `docs/api/index.md`, `docs/architecture/solution-structure.md`, `docs/operations/index.md`, `docs/operations/observability.md`, and `docs/decisions/requirements-traceability.md` as applicable. Document local-credit initialization/reset, estimate age/source, safe-capacity errors, and the fact that authoritative reconciliation, distributed reservations, and multi-replica correctness remain Planned. Update Phase 04 evidence without claiming authoritative Azure balances or reconciliation is implemented.

## Review Focus
- Credit and quota remain distinct; health/cooldown state is not used as a credit balance.
- Cycle calculations are calendar-correct and use configured reset periods rather than invoice assumptions.
- Every backend has a documented local credit-estimate initialization path; absent estimates fail closed for credit-aware routing.
- Reserve-percent semantics use configured estimated cycle allowance as the denominator and are consistent across code and documentation.
- Reservations are conservative, atomic within the supported single-replica boundary, and released exactly once on every path.
- Local cost and remaining-credit values are explicitly estimates and cannot be presented as authoritative Azure data.
- No request is intentionally routed when estimated spendable credit cannot cover its reservation.
- Routing remains explainable, model-specific, arbitrary-backend-count compatible, and deterministic for ties.
- The ADR-006 composite score and equal-score weighted selection behavior are either implemented as specified or explicitly documented as deferred before the phase gate.
- Existing streaming SSE boundaries, retry limits, failover limits, safe headers, and credential isolation remain unchanged.
- Tests prove no outbound call occurs for unknown models, malformed requests, or insufficient safe capacity.
