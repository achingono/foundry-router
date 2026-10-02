# Phase 11 Inputs

## Required Inputs

| Input | Source | Owner |
|---|---|---|
| State management decision | `docs/decisions/adr/005-state-management.md` | Project maintainer |
| Table adapters and client protocol | `src/foundry_router/state/table.py` (`TableEntityClient` at line 66, `AzureTableHealthStore`, `AzureTableCreditStore`, `sync_from_settings` at line 313) | Implementation agent |
| Store construction | `src/foundry_router/main.py:55-58` (module-level in-memory stores) | Implementation agent |
| Rate-limit store | `src/foundry_router/ratelimit.py` (`RateLimitStore` protocol line 50, `InMemoryRateLimitStore` line 76) | Implementation agent |
| Reaper invocation | `src/foundry_router/reconciliation/__init__.py` (explicit `reap_expired_reservations`) | Implementation agent |
| Readiness checks | `src/foundry_router/api/routes/health.py` | Implementation agent |
| Settings model | `src/foundry_router/config/` | Implementation agent |
| Phase 10 template patterns | `infra/main.bicep`, `infra/bicepconfig.json`, `docs/plans/phase-10-bicep-existing-resource-support/` | Implementation agent |
| Existing adapter tests | `tests/unit/test_state.py` | Implementation agent |
| Azure Tables SDK and RBAC behaviour | Microsoft `azure-data-tables` (async), `azure-identity`, Storage built-in roles, Table naming rules | Implementation agent |
| Local emulator | Azurite (Table service) | Implementation agent |

## Optional Inputs

- Which Storage account, if any, each environment should attach to in `existing` mode. Supplied only through gitignored `*.local.json` overrides, never committed.
- A measured request-rate baseline from Phase 10, used to estimate Table transaction volume and per-partition contention.

## Input Validation Checklist
- [ ] All required inputs are current (not from a superseded version)
- [ ] No required input is missing or in draft state
- [ ] No subscription-specific resource name, ID, or tenant appears in any input or output artefact
