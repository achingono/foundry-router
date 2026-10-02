# Phase 11 Outputs

## Mandatory Outputs

| Output | Description | Format |
|---|---|---|
| Template/app contract | Table of every value crossing the boundary, with its Bicep source, settings field and default | Markdown (`infra/README.md`, evidence) |
| Storage account modes | `storageMode` `new`/`existing` with cross-resource-group scope, name validation and hardened `new` defaults | Bicep |
| State backend switch | `stateBackend` parameter; storage resources conditional on `table`; `assert` replacing the Phase 10 `@maxValue(1)` | Bicep |
| Provisioned tables | Health and credit tables with a validated, namespaced prefix; cross-resource-group module for `existing` accounts in another group | Bicep |
| Data-plane role assignments | Table-scoped `Storage Table Data Contributor` for the pre-created user-assigned runtime identity, deterministic names | Bicep |
| App settings wiring | Non-secret `env` entries for the contract; endpoint read from `primaryEndpoints.table` | Bicep |
| State settings | `state_backend`, `table_endpoint`, table names, timeouts with conditional validation | Python |
| Concrete Table client | Async `TableEntityClient` on `azure.data.tables.aio` with token credential, SDK ETag normalisation, operation-specific conflict mapping and prefix queries | Python |
| Adapter fixes | Create-if-absent balance sync with config-drift merge; recompute-on-conflict for settle and reaper; cache never feeds writes; `try_create_entity` protocol method; corrected docstring | Python |
| Store factory | Lifespan-built stores shared by routing, reconciliation and admin status; client closed after drain | Python |
| Readiness check | `state_store_reachable` in `/health/ready` when the backend is `table` | Python |
| Rate-limit resolution | D6 option B through one effective-limit contract, zero-share readiness check, documented exemptions | Python, Bicep |
| Production cut-over runbook | Go decision, reconciled starting balances, revision drain, rollback | Markdown (`infra/README.md`, `docs/operations/index.md`) |
| Optional dependency extra | `azure` extra in `pyproject.toml`; installed in the `Dockerfile` | TOML, Dockerfile |
| Tests | Unit tests, `azurite`-marked integration tests (two instances, restart, reaper, fail-closed), CI Azurite job | Python, YAML |
| Deployment evidence | Validation runs, negative cases, two-replica deployment results | Evidence log |
| Documentation | ADR-005 status, architecture, configuration, security, operations, observability, API, AGENTS.md, traceability | Markdown |

## Optional Outputs

- A short ADR-005 addendum recording the D6 per-replica rate-limit share and the separate-table layout (D5).
- A storage-throttling alert (`ServerBusy`/`Throttling` transactions) if the step-16 estimate shows meaningful contention risk.

## Output Quality Checklist
- [ ] All mandatory outputs produced
- [ ] All outputs reviewed before gate
- [ ] Evidence log updated with output references
- [ ] No subscription, tenant, storage account, resource group name, key, SAS token or connection string appears in any output
- [ ] Documentation status labels used consistently (`Implemented`, `Partially implemented`, `Planned`, `Design target`)
