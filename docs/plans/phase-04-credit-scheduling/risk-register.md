# Phase 04 Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | In-memory reservations diverge across replicas or are lost on restart | Concurrent replicas could overspend estimated credit | Keep this phase single-replica only; document the limit and require shared authoritative state before scaling beyond one | Mitigated — Phase 06 added the Azure Table Storage credit/reservation adapter (`src/foundry_router/state/table.py`) enabling multi-replica operation; in-memory mode remains single-replica only |
| R2 | Token or output estimates understate actual usage | A request may consume more than the protected estimate | Use the documented conservative text bound and output limit/default, reject unsupported or unbounded content when unsafe, and label results as estimates | Mitigated — conservative 1:3 char-to-token ratio with 4096 default output-token fallback implemented and tested in `tests/unit/test_credit.py` |
| R3 | Calendar cycle math mishandles short months or leap years | Incorrect urgency and spendable-credit decisions | Use date-based calculations with exhaustive boundary tests and no invoice-date assumptions | Mitigated — `tests/unit/test_credit.py` covers start days 1/20, short months, February, leap years, and boundaries |
| R4 | Reservation leaks on streaming cancellation or failover | Capacity remains incorrectly unavailable | Centralize ownership, make release idempotent, and test every terminal path | Mitigated — hardened further in `phase-04-hardening` (top-level `try...finally` lifecycle) and Phase 08 (bounded reservation reaper, F4) |
| R5 | Credit logic accidentally conflates quota, health, or authoritative cost | Unsafe or misleading routing decisions | Keep separate health and credit dimensions, define score precedence, and review status/API wording for estimate labels | Mitigated — ADR-006 scoring keeps health/cooldown precedence separate from credit-aware scoring layer |
| R6 | Missing or stale local credit estimates are mistaken for a current balance | Routing confidence is overstated or capacity is oversubscribed | Require configured local allowance/remaining estimates, fail closed when absent, expose source/age internally, and defer authoritative reconciliation to later work | Mitigated — Phase 08 F3 added `/health/ready` checks (`backend_credit_config_complete`, `model_pricing_complete`); reconciliation freshness remains Partially implemented (see `docs/configuration/index.md`) |
| R7 | Credit filtering changes existing retry/failover behavior | Availability or streaming regressions | Preserve Phase 03 seams and run the full regression suite, including stream cleanup and no-retry tests | Mitigated — full regression suite (137 tests) passing per `evidence.md`, including streaming no-retry-after-output tests |
| R8 | Lock contention during in-memory reservations under high concurrency | Latency spikes or serialization bottleneck | Use fine-grained per-backend async locks and minimize critical section work to pure dictionary lookups | Mitigated — per-backend async locks implemented in `src/foundry_router/credit.py` with dictionary-lookup-only critical sections |

## Open Decisions
- Exact token-estimation strategy for structured Responses input (resolved: conservative 1:3 char-to-token ratio on extracted text strings with default 4096 output tokens fallback).
- Whether conservation affects only score weighting or also applies a configurable traffic cap; default to score weighting (ADR-006 availability score 0.5) for safety without extra knobs.
- The authoritative shared-state design and multi-replica enablement gate, deferred to a later phase (ADR-005 Phase 2) — resolved by the Phase 06 Azure Table Storage adapter.
