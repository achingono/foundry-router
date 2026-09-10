# Phase 09 Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | The Google OpenAI-compatibility base URL or auth header name is assumed incorrectly | Requests fail or hit the wrong host; broken provider support | Confirm against current Google documentation before coding; record in the ADR; drive from configuration and allow-list validation; add tests asserting the constructed URL/header | Open |
| R2 | Proactive rate-limit estimates diverge from Google's actual free-tier counting (token accounting, window boundaries, per-model vs per-key limits) | Either premature skipping (wasted capacity) or overshoot into 429s | Treat limits as configurable inputs; reserve on estimate and finalize on actual usage; keep the reactive `429`/`Retry-After` cooldown as the backstop; add rollover and reconciliation tests | Open |
| R3 | Free-tier backends have no dollar credit, conflicting with the Phase 08 readiness completeness checks | Free backends flagged unroutable, or the check is weakened for metered backends | Add an explicit per-backend credit opt-out (`credit_metered: false`) that excludes only that backend from the completeness check; keep the check strict for metered backends; test both paths | Open |
| R4 | Rate-limit reservation leaks on client disconnect during streaming (mirrors the Phase 08 credit-leak class) | Keys appear busier than they are; reduced effective capacity | Release rate-limit reservations on failover and finalize; reuse the Phase 08 reservation-reaper pattern / age bound for rate-limit reservations; add a leak test | Open |
| R5 | Quota-health scoring de-tunes existing credit-aware routing or makes decisions non-deterministic | Regressions in credit routing or flaky selection | Add quota health as a bounded, conservatively weighted term consistent with ADR-006; keep the scorer a pure function; add determinism tests and keep existing routing tests green | Open |
| R6 | Single-replica in-memory rate-limit state is inaccurate across multiple replicas | Over- or under-counting under horizontal scaling | Scope this phase to single-replica accounting; document multi-replica accounting as `Planned`, consistent with ADR-005 and the existing credit state boundary; do not claim distributed correctness | Open |
| R7 | Accidental logging of an API key via headers, admin output, metric labels, or error text | Credential disclosure | Strip the Google auth header in `_sanitize_headers`; identify keys only by backend ID everywhere; add a redaction test asserting no credential appears in logs/admin/metrics | Open |
| R8 | Adding `provider` and provider-specific validation breaks the many existing `Settings(...)` test fixtures (see repo memory on validator strictness) | Broad test breakage | Default `provider` to `azure_foundry` and keep Azure validation unchanged; gate new required fields behind the Google provider only; run the full suite early | Open |
| R9 | A mid-stream 429 or budget exhaustion triggers a failover after output has begun | Violates the streaming contract | Reuse the existing "no retry/failover after meaningful streaming output" guard; add a mid-stream 429 test asserting no failover | Open |
| R10 | Operators assume multiple keys in one Google Cloud project multiply quota, but Google enforces limits per project, not per key | No real throughput gain; keys share one budget and all cool down together | Model rate limits per configurable `quota_group` (project) set on each Google backend; two keys sharing a project set the same value and share one budget; document that added throughput requires distinct projects; test that same-group keys share a budget and cool down together | Open |
| R11 | RPD reset implemented as a rolling 24-hour window or fixed UTC offset instead of midnight Pacific with DST | Keys return to service at the wrong time; premature exhaustion or wasted capacity | Compute the reset at midnight Pacific honouring PDT/PST (07:00/08:00 UTC); test across a DST boundary | Open |

## Open Decisions
- Google request surface: use the Google **OpenAI-compatibility** endpoint (chosen, to reuse
  forwarding/streaming/usage extraction) versus the native `generateContent` API (out of scope).
- Free-tier credit opt-out mechanism: per-backend `credit_metered: false` flag (preferred) versus
  requiring zero-pricing plus unlimited-allowance entries. Decide and record in the ADR.
- Quota-health scoring shape and weight: how remaining RPM/TPM/RPD headroom maps to a `0.0–1.0`
  term, and whether the weight is configurable. Decide with conservative defaults.
- RPD reset boundary and timezone semantics: implement at **midnight Pacific Time** (07:00 UTC PDT /
  08:00 UTC PST) as a fixed daily quota, honouring DST; confirmed against Google documentation.
- RPM/TPM window: computed over the trailing 60 seconds as a prudent assumption, since Google
  documents only "within a minute" and does not commit to rolling versus calendar-minute.
- Where the rate-limit state lives (`src/foundry_router/state/` versus a new
  `src/foundry_router/ratelimit/` module) for consistency with ADR-005.
- Project association source: taken from an explicit per-backend `quota_group` value (source of
  truth), since AI Studio `AIza…` keys do not embed a decodable project. Optional best-effort
  lookup via the Cloud API Keys API (with separately authorized credentials) may default or
  cross-check the configured value but must not be a dependency. Target deployment is one key per
  project, so each key is its own group by default.
