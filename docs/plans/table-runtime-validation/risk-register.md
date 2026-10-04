# Table Runtime Risks

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Async SDK lacks transport | Startup failure | azure extra plus clean-image SDK test | Open |
| R2 | RBAC propagation | Transient forbidden | Scoped grants and bounded readiness retry | Open |
| R3 | Synthetic data interpreted as Azure balances | Misleading credit claims | Label synthetic/local estimates; no inference | Open |
| R4 | Runtime storage bug | Incorrect state | Concurrent real Table client checks and readiness/persistence verification | Open |
| R5 | One replica overclaimed as production ready | Unsafe cut-over | Keep production memory/one; two-replica gate pending | Open |
