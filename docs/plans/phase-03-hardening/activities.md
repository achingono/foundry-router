# Phase 03 Hardening Activities

## Step-By-Step Activities
1. Review the current Phase 03 routing behavior and identify duplicated failover decisions.
2. Introduce a small helper for all-candidate cooldown responses and preserve only safe upstream response headers.
3. Add retry-delay, same-backend state-race, three-backend exclusion, streaming cancellation/cleanup, and bounded pre-output tests.
4. Apply bounded pre-output stream handling without adding configuration.
5. Run focused tests, full unit tests, linting, formatting, type checks, and coverage where available.
6. Update Phase 03 evidence with current commands and results.

## Review Focus
- No retry or failover after meaningful streaming output.
- Stream contexts close exactly once on success, failure, and cancellation.
- Empty pre-output chunks are limited by an explicit empty-chunk budget and cannot cause an unbounded request.
- Every successfully entered stream context closes exactly once, including cancellation during setup and body draining.
- Safe response headers do not include credentials or hop-by-hop metadata.
- Retry timing remains bounded and respects `Retry-After`.
- Health state remains protected by the existing lock.
