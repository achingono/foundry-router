# Phase 11 Activities

## Step-By-Step Activities

1. **Fix the template-to-app contract first.** Before any code, record one table in this plan's evidence and in `infra/README.md` listing every value that crosses the template/app boundary: `FOUNDRY_STATE_BACKEND`, `FOUNDRY_TABLE_ENDPOINT`, `FOUNDRY_TABLE_HEALTH_NAME`, `FOUNDRY_TABLE_CREDIT_NAME`, `FOUNDRY_RATE_LIMIT_REPLICA_SHARE`. For each, record the Bicep source (resource property, never concatenation), the settings field, and the default. No value in the contract is secret; credentials never cross it.

2. **Add the Storage account with `new` / `existing` modes.** Add `storageMode` (`new` | `existing`, default `new`), `storageAccountName`, and `storageResourceGroupName` (defaulting to the deployment resource group), reusing the Phase 10 mode and cross-resource-group `scope` patterns. Validate the account name before any resource is created: 3-24 characters, lowercase letters and digits only, enforced with `@minLength`/`@maxLength` plus an `assert` with an actionable message. In `new` mode deploy `StorageV2` / `Standard_LRS` with `allowSharedKeyAccess: false`, `minimumTlsVersion: 'TLS1_2'`, `supportsHttpsTrafficOnly: true`, and `allowBlobPublicAccess: false`. In `existing` mode, never mutate account settings; document that the template does not enforce shared-key disablement on an attached account. When `storageResourceGroupName` differs from the deployment resource group, the `existing` symbol may read across groups, but the tables (step 4) and role assignments (step 5) must deploy through a module scoped to `resourceGroup(storageResourceGroupName)`; the deploying principal needs table-create and `Microsoft.Authorization/roleAssignments/write` permissions on that scope, recorded in `infra/README.md`.

3. **Make storage conditional on the state backend.** Add `stateBackend` (`memory` | `table`, default `memory`). Storage resources, tables and role assignments deploy only when `stateBackend == 'table'`. Replace the Phase 10 `@maxValue(1)` on `maxReplicas` with an `assert` that `maxReplicas <= 1 || stateBackend == 'table'`, with a message naming both parameters. Keep `activeRevisionsMode: 'Single'` from Phase 10; the assert bounds one revision, so cut-over safety for overlapping revisions is handled in step 16.

4. **Provision the tables in Bicep.** Declare `tableServices/default/tables` for the health and credit tables. Table names come from a prefix parameter defaulting to an `appName`-derived alphanumeric value, validated as 3-63 alphanumerics starting with a letter (no hyphens), so shared `existing` accounts stay namespaced. In `existing` mode the tables are still declared as child resources of the attached account; document that this is the only write the template makes to an attached account.

5. **Grant least-privilege data access.** Assign `Storage Table Data Contributor` to a pre-created user-assigned runtime identity, scoped to each router table resource rather than the account or resource group, with deterministic `guid()`-seeded names (identity id, table id, role definition id). Resolve the role definition with `subscriptionResourceId('Microsoft.Authorization/roleDefinitions', <built-in GUID>)`: built-in role GUIDs are tenant-independent, so committing the GUID is allowed. Take it from Microsoft's built-in roles reference, confirm it with `az role definition list --name 'Storage Table Data Contributor' --query '[].name'`, and record both in evidence. An `existing` `roleDefinitions` symbol cannot be looked up by display name. The container app depends on these assignments, and readiness must recover from any remaining RBAC propagation delay without a manual restart.

6. **Wire non-secret app settings.** Add `env` entries for the step-1 contract. Read `FOUNDRY_TABLE_ENDPOINT` from `storageAccount.properties.primaryEndpoints.table` for the mode in use. Emit no storage keys, SAS tokens or connection strings, and add no `secrets` entries for storage.

7. **Add settings.** Extend `src/foundry_router/config/` with `state_backend` (`memory` | `table`, default `memory`), `table_endpoint`, and the table names. When `state_backend == 'table'`, require an `https://` endpoint and valid table names; when it is `memory`, ignore them. Keep this validation conditional so the many existing `Settings(...)` fixtures that omit storage fields keep passing (see repository memory on `Settings` validators). Never log the endpoint with query strings and never accept a key-bearing value.

8. **Implement the concrete client.** Add a module under `src/foundry_router/state/` implementing `TableEntityClient` on `azure.data.tables.aio.TableClient`:
    - Credentials: `ManagedIdentityCredential(client_id=FOUNDRY_AZURE_CLIENT_ID)` when running in Container Apps; `DefaultAzureCredential` only for local developer runs against a real account. Record the selection rule as decision D2.
   - **ETag bridging.** The async SDK returns the ETag in `entity.metadata['etag']`, while the adapter reads `"odata.etag"` (`state/table.py:988`). The client normalises every returned entity so the adapter receives the ETag, and `try_batch_transaction` raises (fails closed) if any `Update` or `Delete` on a balance row arrives without an ETag. Unconditional balance writes are never issued.
   - `try_batch_transaction`: map `_TransactionEntity` operations to `submit_transaction` with `MatchConditions.IfNotModified` and ETags. Catch `TableTransactionError` and inspect both the error code and the failing operation index: return `False` only for `UpdateConditionNotSatisfied` (412) on the balance row and `EntityAlreadyExists` (409) on a reservation `Create`. Raise on every other error, including a 409/412 on an unexpected operation, so the credit store fails closed.
   - `query_entities`: partition filter plus a parameterised `RowKey` range for the prefix (`ge prefix` and `lt` prefix-successor); never interpolate untrusted values into the filter.
   - Bounded per-operation connect/read timeouts as settings, with explicit close on shutdown.
   - Errors logged by type and status code only, never entity bodies.

9. **Fix adapter correctness for multiple replicas.** In `AzureTableCreditStore.sync_from_settings`, replace the unconditional upsert (`state/table.py:313-340`, `_sync_balance_to_storage` at line 896) with create-if-absent. Add `try_create_entity` to the `TableEntityClient` protocol. If the row exists and the configured allowance or cycle-start day differs, apply an ETag-guarded merge of only those configuration fields, preserving `reserved_inflight_usd` and `estimated_remaining_usd`. Correct the stale "no list/query is exposed" docstring at `state/table.py:391`. Add unit tests showing that a second instance starting against a populated store leaves reservations and spend unchanged.
   - **Recompute on conflict.** The settle and reaper retry loops (`state/table.py:613-628`, `:846-862`) refresh only the ETag and resend a balance computed before the competing write, which overwrites another replica's reservation or debit. On every conflict, re-read the balance and the reservation row from storage and recompute the delta from those fresh values before retrying.
   - **No stale inputs to writes.** Invalidate the balance cache entry on any failed transaction. Every read that feeds a write (reserve, settle, reaper, reconciliation override, config merge) bypasses the cache; the short-TTL cache serves read-only assessment and diagnostics only. Without this, retries inside the TTL re-read the same stale ETag and exhaust.
   - **Interleaving tests.** Use a fake client that injects a competing write between read and write. Prove that reserve, settle, reaper, reconciliation override and config merge each preserve the other writer's effect, and that `reserved_inflight_usd` equals the sum of live reservation rows afterwards.

10. **Build stores at startup.** Replace the module-level in-memory globals in `src/foundry_router/main.py:55-58` with a factory called from the app lifespan that builds the in-memory stores (default) or the Table stores from settings. Keep the public attribute names that tests monkeypatch, or update those tests in the same change. The reconciliation loop, routing and `/admin/status` must all receive the same store instances. Close the Table client after graceful shutdown drains in-flight streams.

11. **Extend readiness.** When `state_backend == 'table'`, add a `state_store_reachable` check to `/health/ready` that performs one bounded read per table, cached for at most 5 seconds. A missing table, a 403 from missing RBAC, or a timeout makes readiness return 503 with the check name only. Document the detection delay (cache age plus probe interval). Readiness is not the safety mechanism: the request path fails closed on its own, independent of the cached readiness result. Document that, under ADR-005 fail-closed semantics, a storage outage takes all replicas out of rotation; this is intended.

12. **Implement rate-limit state (D6).** The maintainer has decided on option B: keep `InMemoryRateLimitStore`, and have each replica enforce `floor(limit / maxReplicas)` through a `FOUNDRY_RATE_LIMIT_REPLICA_SHARE` setting emitted by Bicep from `maxReplicas`, at the cost of underuse when traffic is skewed or fewer replicas are running.
    - **One effective-limit contract.** Add a single function that derives per-replica limits from `quota_group_rate_limits` and the share, applied to every dimension (RPM, input TPM, RPD). Startup sync, the routing comparison and re-sync (`routing/__init__.py:118-126`) and admin sync all use it. Today routing compares the store's limits with the unscaled settings and re-syncs on any difference, which would silently revert the share.
    - **Zero share.** If any `floor(limit / share)` is `0`, the group cannot be served safely. Surface a `rate_limit_share_valid` readiness failure naming the group and dimension, rather than a `Settings` validator (see repository memory on fixture breakage).
    - **Protected emergency fallback.** The fallback passes `allow_over_limit=True` (`routing/__init__.py:195`, `:391`), so the guarantee is that ordinary admissions never exceed the provider quota in aggregate; fallback admissions are exempt, as in Phase 09. See D7.
    - **Rollout overlap.** During a single-revision rollout, old and new revisions can briefly both admit traffic, each at its share; document this bounded overshoot.
    - Update the Phase 09 documentation to state the per-replica share and these qualifications.

13. **Package dependencies.** Add `azure-data-tables` and `azure-identity` as an optional `azure` extra in `pyproject.toml`, import them lazily only when `state_backend == 'table'`, and install the extra in the `Dockerfile` runtime image. Keep the import-time independence documented in the `state/table.py` module docstring.

14. **Test.**
    - Unit: client mapping with fakes and with real SDK `TableEntity` / `TableTransactionError` objects (ETag normalisation, missing-ETag fail-closed, error code plus operation-index mapping), prefix query filter construction, settings validation in both modes, factory selection, readiness check including cache expiry, create-if-absent sync, recompute-on-conflict interleavings (step 9), and the D6 effective-limit contract across startup, repeated routing calls and admin calls.
    - Integration (new `azurite` marker registered in `pyproject.toml`; Azurite Table service; test-only fixture credentials that never reach `src/`): two app instances sharing one store issue concurrent reservations, and the sum of reserved plus settled never exceeds allowance minus reserve. Cover a second instance starting mid-load, ETag-conflict retries, concurrent reapers on two instances, and fail-closed behaviour when Azurite is stopped, on the request path as well as readiness.
    - Add a CI job to `.github/workflows/ci.yml` that runs an Azurite service container, installs `.[dev,azure]`, and runs `-m azurite`. The existing jobs keep excluding it, and its coverage is combined with the unit job's report.
    - Keep overall and changed-module coverage at or above 80%.

15. **Verify the deployment.** Run `az bicep build`, `az bicep lint`, and `az deployment group validate` for `stateBackend: memory` (no storage resources emitted), `table` + `storageMode: new`, and `table` + `storageMode: existing` (cross-resource-group). Negative cases: `maxReplicas: 2` with `memory`, an invalid account name, and an invalid table prefix must each fail with an actionable message. Deploy `table` + `new` with `maxReplicas: 2` to a disposable resource group. Then:
    - Force two replicas under load and run the smoke test.
    - Confirm `/admin/status` shows identical reservation counts from both replicas.
    - Restart one replica mid-load and confirm no reset.
    - Confirm the app holds no storage key: shared-key access is disabled on the account and no key-bearing setting exists.

16. **Record operations and cost.** In `infra/README.md` and `docs/operations/index.md`, cover:
    - Estimated Table transactions per routed request and the resulting cost order of magnitude.
    - Per-partition throughput limits versus the measured request rate.
    - A runbook for storage throttling (`503 ServerBusy`), RBAC propagation delay on first deploy, and storage outage (fail-closed 503s).
    - The rule for switching an environment from `memory` to `table` (fresh balances from configuration; no data migration).
    - **Production cut-over runbook**, required before any production parameter change:
      - An environment-specific go decision recorded in evidence.
      - Before switching, set `backend_initial_estimated_remaining_usd` to the current reconciled estimate, so the Table store does not start from stale configured balances (in-memory spend and reservations cannot be carried over).
      - Deploy `table` with `maxReplicas: 1` first, confirm via `az containerapp revision list` that no memory-backed revision remains active or receives traffic, then raise `maxReplicas`.
      - Rollback: return to `memory` with `maxReplicas: 1`. Table data is retained, never deleted, and a later re-cut-over re-reconciles balances first.

17. **Update documentation.**
    - Update ADR-005: Phase 2 is `Implemented` only once the step-15 deployment passes.
    - Update `docs/architecture/index.md`, `docs/architecture/solution-structure.md`, `docs/configuration/index.md` (new settings), `docs/configuration/security.md` (identity-only storage auth, table-scoped role), `docs/features/routing.md`, `docs/operations/observability.md`, `docs/api/index.md`, `AGENTS.md`, and `docs/index.md`.
    - Update the requirements traceability matrix: change the Phase 10 `Partially implemented` labels for multi-replica state to `Implemented` only for behaviour verified in step 15.
    - Set `infra/parameters.prod.json` to `stateBackend: table`, `storageMode: new`, `maxReplicas: 2`, but only after step 15 passes and only through the step-16 cut-over runbook.

18. **Run the required gates.** Run focused tests, the full verification suite including `azurite`-marked tests, lint, format, type check, and the Docker build. Run `scripts/quality/sonarqube-scan.sh` and the deep-review prompt if present. Scan the final diff for subscription-specific names, IDs, endpoints, keys and connection strings.

## Review Focus
- Whether one table-scoped `Storage Table Data Contributor` assignment is truly least privilege, and whether the app needs any control-plane permission (it must not).
- That create-if-absent sync cannot reset shared credit on scale-out or restart, and that configuration-drift merges preserve `reserved_inflight_usd` and `estimated_remaining_usd`.
- That 409/412 mapping to `False` is limited to the expected operation and error code, cannot mask a real failure, and that every other error fails closed.
- That ETags from the SDK reach the adapter and no balance write is ever unconditional.
- That every conflict retry recomputes from freshly read storage state, and that no write is fed from the cache.
- That cross-resource-group tables and role assignments deploy through correctly scoped modules.
- That `query_entities` prefix filtering is parameterised and correct at the prefix boundary.
- That `stateBackend: memory` emits no storage resources and that no template path yields `maxReplicas > 1` with `memory`.
- That the D6 effective-limit contract survives routing and admin re-syncs, that zero shares are rejected, and that the protected-fallback and rollout-overlap exemptions are the only documented ways to exceed provider quota.
- That production cut-over cannot happen without reconciled starting balances and drained memory-backed revisions.
- That no key, SAS token or connection string can reach `src/`, the template, parameter files or workflows.
- That the documentation reaches `Implemented` only for behaviour proven by the step-15 deployment.
