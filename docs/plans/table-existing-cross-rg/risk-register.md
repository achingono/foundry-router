# Risks

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Existing account mutated | Shared-resource drift | Checked properties unchanged; no parent writes | Mitigated |
| R2 | Cross-RG role scope invalid | Runtime forbidden | Scoped MI operations/readiness passed | Mitigated |
| R3 | Test cleanup alters other apps | State loss | Isolated state restored/removed; original smoke passed | Mitigated |
| R4 | Evidence overclaims cut-over | Unsafe production rollout | Production remains memory/one, real traffic gates separate | Mitigated |
