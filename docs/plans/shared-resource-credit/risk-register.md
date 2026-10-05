# Risks

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Wrong group at settlement/failover | Lost reservation or incorrect debit | Central store membership normalization, captured ownership and typed failures; failure regressions pass | Mitigated locally |
| R2 | Legacy data implicitly merged | Duplicated budget | No group-ID migration without drained writers/new estimates; documented rollout requirement | Mitigated; operator rollout gate |
| R3 | Group balance duplicated in dashboards | Overstated credit | Canonical unique group view; backend compatibility views nonadditive; diagnostics tested | Mitigated locally |
| R4 | Shared Table contention | Admission degradation | Bounded ETag retry and real Azurite contention tested; production load unverified | Mitigated locally; live load pending |
| R5 | Missing production inputs | Unsafe estimates | No deployment with nulls or test placeholders | Open |
