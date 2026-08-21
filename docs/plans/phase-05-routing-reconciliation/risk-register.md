# Phase 05 Risk Register

## Risk Assessment

| Risk ID | Description | Impact | Likelihood | Mitigation |
|---|---|---|---|---|
| R-P05-01 | Circular dependencies between health, routing, and credit modules | Medium | Medium | Strict one-way dependency flow: API -> Routing -> Forwarding -> Backend; Routing -> Credit / Health. |
| R-P05-02 | Reconciliation overwrites active in-flight reservations | High | Low | Reconciliation adjusts base balance while in-flight lock tracker preserves active reservation offsets. |
| R-P05-03 | Azure Cost Management API delay causes stale-cost panic | Medium | Medium | Graceful fallback to local token-burn estimates with clear status flags. |
