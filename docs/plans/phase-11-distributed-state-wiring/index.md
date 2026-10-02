# Phase 11 Distributed State Wiring

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective
Make multi-replica deployment actually safe, end to end. The ADR-005 Azure Table Storage adapters (`src/foundry_router/state/table.py`) exist and are unit-tested, but nothing provisions a Storage account and nothing in the app builds a Table client. The app hard-wires in-memory stores (`src/foundry_router/main.py:55-58`). This phase delivers the infrastructure and the application wiring as one contract: a Storage account with `new`/`existing` modes, provisioned tables, a table-scoped data-plane role for the container app identity, identity-only client construction, a startup store factory, readiness checks, and the adapter fixes needed for correctness across replicas. Only after a verified two-replica deployment does this phase lift the Phase 10 `maxReplicas <= 1` guard.

## Scope

### In Scope
- **Template** (`infra/main.bicep`):
  - `Microsoft.Storage/storageAccounts` with `storageMode` (`new` | `existing`), following the Phase 10 mode, cross-resource-group `scope`, name-validation and `assert` patterns.
  - Tables provisioned through `tableServices/tables`; the app never creates tables at runtime. For an `existing` account in another resource group, tables and role assignments deploy through a module scoped to that group.
  - `Storage Table Data Contributor` granted to the pre-created user-assigned runtime identity, scoped to each router table rather than the account or resource group.
  - Hardened `new` accounts: `allowSharedKeyAccess: false`, `minimumTlsVersion: 'TLS1_2'`, `supportsHttpsTrafficOnly: true`, `allowBlobPublicAccess: false`. `existing` accounts are detected and documented, never mutated.
  - A `stateBackend` parameter (`memory` | `table`, default `memory`). An `assert` requires `stateBackend == 'table'` whenever `maxReplicas > 1`, replacing the Phase 10 `@maxValue(1)` decorator.
  - Non-secret app settings (`FOUNDRY_STATE_BACKEND`, `FOUNDRY_TABLE_ENDPOINT`, table names) built from `primaryEndpoints.table` and the table resources, never by string concatenation.
- **Application**:
  - Settings for the state backend, the endpoint and the table names. Cross-field validation applies only when the backend is `table`, so existing `Settings(...)` fixtures are unaffected.
  - A concrete async `TableEntityClient` built on `azure.data.tables.aio`, authenticated with a token credential only. It normalises SDK ETags for the adapter, maps `try_batch_transaction` to `submit_transaction` with ETag match conditions and operation-specific conflict mapping, and implements `query_entities`.
  - A startup store factory that replaces the module-level in-memory globals, with client lifecycle tied to app startup and shutdown.
  - `/health/ready` reports table reachability when the backend is `table`.
  - `azure-data-tables` and `azure-identity` added as an optional `azure` extra and installed in the container image.
- **Adapter correctness fixes** (`src/foundry_router/state/table.py`):
  - Create the balance row only if it is absent, so a starting or restarting replica never resets shared reservations or spend.
  - Recompute settle and reaper deltas from freshly read state on every ETag conflict, and never feed a write from the balance cache, so retries cannot overwrite another replica's update.
  - Correct the stale `query_entities` docstring.
- **Rate-limit state**: implement decision D6 (risk register), option B: a per-replica share of each quota limit, through one effective-limit contract used by startup, routing and admin sync.
- **Production cut-over**: a runbook gate (reconciled starting balances, drained memory-backed revisions, rollback) before production moves to `table`.
- **Verification**: Azurite-backed integration tests under a new `azurite` marker with a dedicated CI job, two app instances sharing one store, and a two-replica deployment to a disposable resource group.
- Documentation, ADR-005 status, and requirements-traceability updates.

### Out of Scope
- Azure Cache for Redis or any hot-state cache (ADR-005 Phase 3).
- Private endpoints, service endpoints, network ACLs, or customer-managed keys on the Storage account.
- Geo-redundant or zone-redundant storage SKUs.
- Multi-worker (`--workers > 1`) metrics aggregation; Prometheus metrics stay per replica.
- Live Azure Cost Management reconciliation.
- Shared-key, SAS or connection-string authentication in application code.
- Migrating in-memory state into the new store; in-memory state cannot be exported, so cut-over starts from reconciled initial balances (activities step 16).

## Entry Criteria
- Phase 10 is `Implemented`: the mode contract, `infra/bicepconfig.json` assertions, the parameter-file split, and the interim `maxReplicas <= 1` guard are merged.
- The Phase 10 documentation status correction is merged, so no document claims deployed multi-replica state.
- Decision D7 (protected-fallback exemption) is confirmed by the maintainer.
- This plan has been reviewed by a different session before implementation.

## Exit Criteria
See [Exit Criteria](exit-criteria.md).

## Roles
- Owner: Implementation agent
- Reviewer: Independent review session
- Approver: Project maintainer
