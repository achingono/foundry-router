# Phase 09 Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | The Google OpenAI-compatibility base URL or auth header name is assumed incorrectly | Requests fail or hit the wrong host; broken provider support | Confirmed against Google's OpenAI compatibility and API key REST documentation; recorded in ADR-007; allow-list and backend tests cover URL/header construction | Mitigated |
| R2 | Proactive rate-limit estimates diverge from Google's actual free-tier counting (token accounting, window boundaries, per-model vs per-key limits) | Either premature skipping (wasted capacity) or overshoot into 429s | Treat limits as configurable inputs; reserve on estimate and finalize on actual usage; keep the reactive `429`/`Retry-After` cooldown as the backstop; add rollover and reconciliation tests | Mitigated; residual estimate variance documented in ADR-007 |
| R3 | Free-tier backends have no dollar credit, conflicting with the Phase 08 readiness completeness checks | Free backends flagged unroutable, or the check is weakened for metered backends | `credit_metered: false` excludes only homogeneous non-metered model pools from credit completeness; they receive zero pricing; tests preserve strict metered readiness and reject mixed pools | Mitigated |
| R4 | Rate-limit reservation leaks on client disconnect during streaming (mirrors the Phase 08 credit-leak class) | Keys appear busier than they are; reduced effective capacity | Server-owned request reservations transfer on failover, finalize from JSON/SSE usage, and expire via a bounded monotonic-age sweep | Mitigated |
| R5 | Quota-health scoring de-tunes existing credit-aware routing or makes decisions non-deterministic | Regressions in credit routing or flaky selection | Quota health is a bounded headroom fraction in ADR-006's existing 0.2 component; deterministic score/weight/backend-ID ordering and focused selection tests | Mitigated |
| R6 | Single-replica in-memory rate-limit state is inaccurate across multiple replicas | Over- or under-counting under horizontal scaling | Scope this phase to single-replica accounting; document multi-replica accounting as `Planned`, consistent with ADR-005 and the existing credit state boundary; do not claim distributed correctness | By design; distributed support remains Planned |
| R7 | Accidental logging of an API key via headers, admin output, metric labels, or error text | Credential disclosure | Google auth headers are sanitized; admin/status and metrics expose backend/group IDs only; credential-absence regression and backend sanitization tests | Mitigated |
| R8 | Adding `provider` and provider-specific validation breaks the many existing `Settings(...)` test fixtures (see repo memory on validator strictness) | Broad test breakage | Default `provider` to `azure_foundry` and keep Azure validation unchanged; gate new required fields behind the Google provider only; run the full suite early | Mitigated; full suite passes |
| R9 | A mid-stream 429 or budget exhaustion triggers a failover after output has begun | Violates the streaming contract | Reuse the existing "no retry/failover after meaningful streaming output" guard; add a mid-stream 429 test asserting no failover | Mitigated; streaming contract tests pass |
| R10 | Operators assume multiple keys in one Google Cloud project multiply quota, but Google enforces limits per project, not per key | No real throughput gain; keys share one budget and all cool down together | Rate state and reactive cooldown are keyed by configured `quota_group`; same-group reservation and cooldown tests cover shared behavior | Mitigated |
| R11 | RPD reset implemented as a rolling 24-hour window or fixed UTC offset instead of midnight Pacific with DST | Keys return to service at the wrong time; premature exhaustion or wasted capacity | Reset uses `America/Los_Angeles`; midnight and fall-DST boundary tests cover Pacific-day behavior | Mitigated |

## Decisions Recorded in ADR-007
- Google OpenAI-compatibility is the chosen surface; native `generateContent` remains out of scope.
- Free-tier credit uses `credit_metered: false`.
- Quota health is the minimum projected remaining fraction and uses ADR-006's existing 0.2 weight.
- RPM/TPM use a monotonic trailing-60-second window; RPD uses midnight Pacific with DST.
- Rate state lives in `src/foundry_router/ratelimit.py` and is single-process; distributed state is Planned.
- `quota_group` is explicitly configured (default backend ID). Project lookup is not a runtime dependency.
