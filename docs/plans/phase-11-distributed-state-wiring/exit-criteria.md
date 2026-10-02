# Phase 11 Exit Criteria

## Gate Checklist

### Template
- [ ] `az bicep build` and `az bicep lint` introduce no new errors or warnings against the committed `infra/bicepconfig.json`.
- [ ] `az deployment group validate` passes for `stateBackend: memory`, `table` + `storageMode: new`, and `table` + `storageMode: existing` (cross-resource-group).
- [ ] `stateBackend: memory` emits no Storage account, table or storage role assignment.
- [ ] `maxReplicas: 2` with `stateBackend: memory`, an invalid account name, and an invalid table prefix each fail validation with an actionable message.
- [ ] `new` accounts deploy with shared-key access disabled, TLS 1.2 minimum, HTTPS only and blob public access off; `existing` accounts are not mutated.
- [ ] `Storage Table Data Contributor` is scoped to each router table, not the account or resource group, and assignments are idempotent on redeploy.
- [ ] The role definition is resolved from the verified built-in GUID, recorded in evidence with the `az role definition list` confirmation.
- [ ] For `existing` accounts in another resource group, tables and role assignments deploy through a module scoped to that group, and cross-group validation passes.
- [ ] `FOUNDRY_TABLE_ENDPOINT` is derived from `primaryEndpoints.table`; no storage key, SAS token or connection string exists in the template, parameter files or workflows.

### Application
- [ ] The concrete client authenticates with a token credential only; `src/` contains no shared-key, SAS or connection-string code path.
- [ ] SDK ETags are normalised for the adapter; a balance `Update`/`Delete` without an ETag raises; tests use real SDK entity and error types.
- [ ] Only `UpdateConditionNotSatisfied` on the balance row and `EntityAlreadyExists` on a reservation `Create` map to `False`, matched on error code and operation index; every other storage error fails closed.
- [ ] Settle and reaper retries recompute from freshly read balance and reservation rows; failed transactions invalidate the cache; no write is fed from the cache; interleaving tests show no lost update and `reserved_inflight_usd` equals the sum of live reservations.
- [ ] `query_entities` prefix filtering is parameterised and covered at the prefix boundary.
- [ ] Balance sync is create-if-absent; a second instance starting against a populated store leaves reservations and spend unchanged (unit and Azurite tests).
- [ ] Routing, reconciliation and `/admin/status` share the same store instances; the client closes after graceful-shutdown drain.
- [ ] `/health/ready` returns 503 with `state_store_reachable: false` for a missing table, a missing role assignment, and a timeout, within the documented cache bound (at most 5 seconds); requests fail closed during an outage regardless of the cached readiness result.
- [ ] Decision D6 option B is implemented through one effective-limit contract; repeated routing and admin calls keep the per-replica share; a zero share fails readiness; ordinary admissions across replicas cannot exceed the configured provider quota, with the protected-fallback and rollout-overlap exemptions tested and documented.
- [ ] Existing `Settings(...)` fixtures pass unchanged with the default `memory` backend.

### Verification
- [ ] `azurite`-marked integration tests pass locally and in the dedicated CI job with the `azure` extra installed: concurrent reservations across two instances never oversubscribe; a mid-load second instance, concurrent reapers and storage-stopped fail-closed cases all pass.
- [ ] A two-replica deployment to a disposable resource group converges without manual restart; both replicas report identical reservation counts under load; restarting one replica does not reset shared credit.
- [ ] Coverage stays at or above 80% overall and for each new or changed module.
- [ ] Focused tests, the full suite, lint, format, type check and Docker build pass.
- [ ] `scripts/quality/sonarqube-scan.sh` was run if present, with all `Blocker`, `Critical` and `Major` findings addressed.
- [ ] The deep review was run if the prompt exists, with findings addressed.

### Documentation
- [ ] The template/app contract table is published in `infra/README.md`.
- [ ] ADR-005 Phase 2, the requirements traceability matrix and every document corrected in Phase 10 reach `Implemented` only for behaviour proven above.
- [ ] `infra/parameters.prod.json` moves to `stateBackend: table` and `maxReplicas: 2` only after the deployment criterion passes and the cut-over runbook has run: a recorded go decision, reconciled starting balances, no memory-backed revision active or receiving traffic, and a documented rollback.
- [ ] A diff scan finds no live-environment name, ID, tenant, endpoint, key or connection string.
- [ ] The plan was reviewed by an independent session before implementation began.

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Owner | | Pending | |
| Reviewer | | Pending | |
| Approver | | Pending | |
