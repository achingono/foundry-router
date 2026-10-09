# Table real inference Risks

| Risk | Mitigation |
| --- | --- |
| Accidental existing/production state mutation | New app/table names, what-if, exact approval |
| Provider spend amplification | Retry0, four-case durable ledger, maximum-cost pre-reserve |
| Secret/output disclosure | Bounded capture, pinned references, safe summaries only |
| Misattributed backend or stale configuration | Validated exact model pools, immutable digest/config fingerprint |
| Restart erases fresh memory rather than tests Table | Explicit Table readiness/status and persisted estimate comparison |
