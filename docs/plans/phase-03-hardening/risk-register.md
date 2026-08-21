# Phase 03 Hardening Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Stream pre-output bound changes backend compatibility | Slow backends may fail over sooner than before | Use an explicit bounded empty-chunk budget and test the boundary explicitly | Mitigated |
| R2 | Header forwarding leaks backend metadata | Clients may receive sensitive or hop-by-hop headers | Copy only the documented `Retry-After` and `Cache-Control` allowlist | Mitigated |
| R3 | Refactor changes single-failover semantics | Requests may receive the wrong final response | Preserve existing candidate exclusion and add regression tests | Mitigated |

## Open Decisions
- Whether a dedicated pre-first-byte timeout is needed should be decided with production latency data; this hardening pass does not add a new setting.
