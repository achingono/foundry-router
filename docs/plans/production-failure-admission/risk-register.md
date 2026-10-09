# Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Live probe causes unexpected egress or spend | Unplanned provider usage/credit debit | One-shot admission probes first; counters + reservation checks after each; at most two small inference probes on cheapest `fs-swarm` pool; halt on anomaly | Open |
| R2 | Credential/output leakage via logs or docs | Exposure | Captured reads, metadata-only logging, in-memory references, finally-guarded grant removal, secret scan before close | Open |
| R3 | Probe perturbs production health/cooldown state | Reduced availability | No induced 429/5xx or exhaustion probes; observational failure-state checks only; start/end readiness verification | Open |
| R4 | Overclaiming coverage (fs-swarm only) | Unsupported evidence | Record backend request-counter deltas; explicitly retain `fs-openclaw`/failover-between-resources as unverified | Open |
| R5 | Streaming probe mishandled (retry after output) | Contract violation | Never retry after meaningful stream output; post-start failures observed as SSE events only; bounded deadlines | Open |
| R6 | Reconciliation staleness or pending reservations left behind | Credit-integrity doubt | Before/after canonical group + inflight checks; abort on stale reconciliation unless operator accepts; require zero inflight at close | Open |

## Open Decisions

- Which lowest-cost `fs-swarm` pool hosts the two inference probes (operator confirms at runtime from current prices).
- Whether embeddings admission is explicitly in or out for this run (default: out; remains unverified).
