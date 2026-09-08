# Phase 08 Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | F1 change misses a code path that still uses the client correlation ID as the reservation key | Credit accounting remains corruptible | Trace the identity end to end (route → routing → credit → streaming); add the concurrent duplicate-ID regression test as the gate | Open |
| R2 | Body-size limit set too low breaks legitimate large but valid requests | False `413` rejections | Choose a generous default, make it configurable, and document it; test a just-under-limit valid body | Open |
| R3 | F3 hard config-load failure is too strict for partial local testing | Blocks developers running subsets locally | Decide between fail-fast config validation and a readiness check; record the decision; prefer readiness if partial local runs are required | Open |
| R4 | Reservation reaper reclaims a still-inflight streaming request that legitimately runs long | Premature credit release and possible double accounting | Set max age to backend timeout plus margin; only reap strictly older reservations; add a long-running-stream test that is not reaped | Open |
| R5 | Removing per-request `sync_from_settings` (F6) breaks a test that relied on its side effect | Test regressions | Confirm startup/lifespan sync covers the need; update tests to not depend on per-request sync | Open |
| R6 | F7 pre-filter accidentally skips a valid usage event with unusual formatting | Under-charged streaming cost | Pre-filter on a substring guaranteed present in usage events; keep full parse when the guard matches; test terminal usage extraction | Open |
| R7 | Documentation drifts ahead of implementation (present-tense claims) | Violates repository status-labelling rule | Update docs only after verification; use the four status labels consistently | Open |

## Open Decisions
- F3 enforcement location: fail-fast at config load versus reported at `/health/ready`. Record the chosen approach and rationale before implementation.
- Whether to expose oldest-reservation age (not only count) in `/admin/status`, subject to cost under the existing lock.
- Default values for `max_request_body_bytes` and `reservation_max_age_seconds`, aligned to the backend client timeout.
