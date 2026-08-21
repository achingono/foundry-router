# Phase 04 Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | In-memory reservations diverge across replicas or are lost on restart | Concurrent replicas could overspend estimated credit | Keep this phase single-replica only; document the limit and require shared authoritative state before scaling beyond one | Open |
| R2 | Token or output estimates understate actual usage | A request may consume more than the protected estimate | Use the documented conservative text bound and output limit/default, reject unsupported or unbounded content when unsafe, and label results as estimates | Open |
| R3 | Calendar cycle math mishandles short months or leap years | Incorrect urgency and spendable-credit decisions | Use date-based calculations with exhaustive boundary tests and no invoice-date assumptions | Open |
| R4 | Reservation leaks on streaming cancellation or failover | Capacity remains incorrectly unavailable | Centralize ownership, make release idempotent, and test every terminal path | Open |
| R5 | Credit logic accidentally conflates quota, health, or authoritative cost | Unsafe or misleading routing decisions | Keep separate health and credit dimensions, define score precedence, and review status/API wording for estimate labels | Open |
| R6 | Missing or stale local credit estimates are mistaken for a current balance | Routing confidence is overstated or capacity is oversubscribed | Require configured local allowance/remaining estimates, fail closed when absent, expose source/age internally, and defer authoritative reconciliation to later work | Open |
| R7 | Credit filtering changes existing retry/failover behavior | Availability or streaming regressions | Preserve Phase 03 seams and run the full regression suite, including stream cleanup and no-retry tests | Open |
| R8 | Lock contention during in-memory reservations under high concurrency | Latency spikes or serialization bottleneck | Use fine-grained per-backend async locks and minimize critical section work to pure dictionary lookups | Open |

## Open Decisions
- Exact token-estimation strategy for structured Responses input (resolved: conservative 1:3 char-to-token ratio on extracted text strings with default 4096 output tokens fallback).
- Whether conservation affects only score weighting or also applies a configurable traffic cap; default to score weighting (ADR-006 availability score 0.5) for safety without extra knobs.
- The authoritative shared-state design and multi-replica enablement gate, deferred to a later phase (ADR-005 Phase 2).
