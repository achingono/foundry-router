# Quota evidence

**Planned**, 2026-10-08. Six planning templates copied before drafting. Inspected
RateLimitStore, memory accounting, Table CAS client, startup/readiness, routing sync and
admission/settlement call sites. Runtime changes have not started.

Independent review identified Major gaps in midnight quota accounting, logical-ID reuse
across 429 attempts and the UTF-16 property bound. The plan now blocks midnight clock
uncertainty, carries a separate quota ID for every admitted candidate, and bounds the exact
Edm.String UTF-16 storage bytes. Re-review also tightened retention to ≤3,600 seconds and
made drained fingerprint-transition CAS predicates explicit. Final re-review cleared implementation with no remaining Critical/Major issues.
Admission, finalization, release and initialization lost acknowledgements remain explicit
implementation-review cases; no runtime or live verification is claimed yet.
