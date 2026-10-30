# Production Table Migration Mechanics

**Status: Read-only implementation investigation; migration remains Planned.** Inspected the
current working tree and relevant source/tests on 2026-10-30. No Azure calls, deployments,
inference, test runs, or runtime/script edits were performed. This note is implementation guidance
for the future Phase 2/3 packet, not an execution approval. The coordinator's read-only discovery
reports reusable hardened cross-RG storage (`frcrossrg261004`) and compatible isolated tables;
those live facts were not independently checked here and do not authorize creating or changing
anything now.

## Recommendation

Use the existing Table startup path, with **two new, dedicated production tables** (credit and
health) on the already-discovered hardened shared Storage account, and the existing production
user-assigned managed identity granted `Storage Table Data Contributor` at each table resource
scope. Keep the production app single-worker, `maxReplicas: 1`, original providers/pools/prices,
and original ingress policy except during the reviewed acceptance fence. Do not enable Table quota,
change payload behavior, scale out, create another storage account, or hand-write balance rows.

Fence and drain every memory writer first. Take a fresh, canonical four-account snapshot from that
same fenced process. Put the four conservative remaining estimates in a new versioned secret used
by `FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON`. Then start the sole Table revision
against the *empty, new* tables. Its lifespan calls `sync_from_settings`; this creates each missing
canonical `balance` row with the current configured cycle and allowance, the snapshot seed,
zero in-flight reservations, and zero debit/recovery counters. This is the smallest mechanism
supported by current code and deliberately establishes a **new Table counter lifetime**. Preserve
the old memory counter values in the private cutover record, but do not claim cumulative debit
continuity or try to inject historical counters.

## What the current code does (and does not do)

| Boundary | Current behavior and migration consequence |
| --- | --- |
| Canonical accounts | `credit_membership()` maps each backend to its canonical group and `metered_credit_groups()` returns the unique metered partitions (`src/foundry_router/credit_groups.py:36-69`). Table `PartitionKey` is that group, not each backend alias. Inspect the refreshed loaded configuration; do not hard-code the historical 22-backend/14-pool/four-account inventory as current without rediscovery. |
| Startup and creation | `main.lifespan()` builds the stores and awaits credit sync before serving (`src/foundry_router/main.py:370-409`, especially 392-396). `AzureTableCreditStore.sync_from_settings()` loops canonical metered groups, obtains allowance/seed/cycle day, calculates the current cycle, and create-if-absent initializes balance with `min(seed, allowance)`, zero reservations, and the current cycle start (`src/foundry_router/state/table.py:363-435`). A failed/incomplete sync raises; startup must not be treated as ready. |
| Create-if-absent | `_create_balance_if_absent()` first reads `RowKey="balance"`, then uses `try_create_entity()`; after a create race it rereads the winner (`src/foundry_router/state/table.py:437-465`; SDK implementation in `src/foundry_router/state/azure.py:209-232`). A restart against an existing matching row does **not** reload the configured starting amount. |
| Existing-row drift | If an existing row's allowance or cycle-start day differs, sync ETag-merges those fields, clamps remaining to the new allowance, and preserves in-flight amount, `cycle_start_utc`, and counters (`src/foundry_router/state/table.py:465-537`). The row does not contain a persisted membership/config fingerprint. In-process aliases/metered groups are compared, with a pending-reservation guard (`:374-390`), but that is not a cross-restart migration lock. **Do not reuse old/partial/unknown production partitions or allow config drift through this path.** |
| Counters and row schema | `_BalanceRow` defaults `debited_usd_total` and `recovered_debit_usd_total` to `0.0` (`src/foundry_router/state/table.py:283-295`); `_balance_to_entity()` writes both values (`:1490-1503`). New rows therefore start at zero. There is no settings field or initialization API for seeding historical counter totals. Missing counter properties on legacy rows decode as zero (`:1505-1554`), so do not use legacy rows as proof of historical continuity. |
| Reserves | Reserve policy is configuration, not part of the Table balance entity. Group overrides and inherited settings are parsed/frozen by `Settings` (`src/foundry_router/config/__init__.py:1098-1119`; `src/foundry_router/config/group_reserves.py:47-83`) and applied when assessing credit (`src/foundry_router/state/table.py:1443-1459`). Preserve and hash the exact effective reserve configuration; do not describe reserves as Table-seeded fields. |
| Cycle rollover | Table rollover resets remaining to the configured cycle allowance when its computed cycle start advances (`src/foundry_router/state/table.py:1436-1441`). A stale snapshot crossing a reset can therefore create the wrong starting balance or later replenish to the allowance. Gate on current/next cycle timestamps before and after the fence; see below. |
| Readiness | `/health/ready` requires complete credit configuration/pricing (`src/foundry_router/api/routes/health.py:24-55`). In Table mode, `_probe_state_stores()` requires a balance entity for each unique *routable metered* group, and probes health-table reachability (`src/foundry_router/main.py:141-185, 188-212`). It is not proof that every expected account/config fingerprint is correct: compare the exact expected four canonical groups separately. Health probe allows a missing health entity; `AzureTableHealthStore` treats a missing backend row as ACTIVE and writes health state only when needed (`src/foundry_router/state/table.py:178-215`). No health-row seeding step is needed. |
| Identity and client | `build_stores()` creates identity-only clients for the configured endpoint and credit/health table names (`src/foundry_router/main.py:95-131`). In Container Apps, `select_credential()` chooses managed identity and honors **`FOUNDRY_AZURE_CLIENT_ID`** for the user-assigned identity (`src/foundry_router/state/azure.py:31-53`). The app client does not create tables; tables/grants must exist before its first Table startup. |
| Status API | Authenticated `/admin/status` calls `sync_from_settings()` and returns unique `credit_groups` (`src/foundry_router/api/routes/admin.py:166-225`). Canonical group `live.estimated_remaining_usd`, debit/recovery totals, in-flight, active count, age, and cycle timestamps are the snapshot inputs. The group-level numeric values are emitted directly; the legacy per-backend live balance is rounded to six decimals (`admin.py:83-118`) and is a duplicated, nonadditive view. Never derive the seed from backend mirrors or `available_credit_usd` (which already subtracts reserve and in-flight). |

## Phase 2 initialization sequence

1. **Refresh and bind the baseline.** Re-discover the exact production app/revision, current immutable
   image, effective environment/secret versions, identity, original ingress, 22/14 roster if still
   current, four canonical account mapping, cycles/allowances/reserves, prices, aliases, and shared
   storage resource. Keep full resource IDs, principal/client IDs, secret material, and hashes in
   the private packet; commit only redacted evidence. The existing storage account is a coordinator-
   reported reuse candidate, not something this note verified.
2. **Prepare only two new tables.** Use the existing typed cross-RG table resource module
   (`infra/modules/storageTableResources.bicep:31-67`) and reviewed finite what-if. Create dedicated
   production credit and health tables, each distinct from isolated/test tables and any old rows;
   grant the production UAMI the existing table-scoped `Storage Table Data Contributor` role on
   those two table resources only. Verify current account hardening, HTTPS, shared-key/SAS-free
   endpoint, network path, exact role scopes, and parent-resource preservation. Do not create a
   storage account or widen grants. Keep `FOUNDRY_RATE_LIMIT_BACKEND=memory`; no quota table or
   quota grant is part of this migration.
3. **Prove target tables empty before the first app sync.** Prefer an authenticated read-only query
   performed inside the existing production app/container with the production UAMI and exact
   endpoint/table names. `az containerapp exec` requires its normal Container Apps control-plane
   permission; the query itself uses the app UAMI's table-scoped data role, so the operator does
   not need a separate Storage Table Data role. A direct SDK `TableClient.query_entities()` scan
   can verify there are no entities (including unexpected partitions); a four-partition query is
   insufficient to prove global emptiness. This is a proposed packet check, not tested here.
4. **Fence and drain memory.** Deny public intake; prove denial and unchanged same old process. Wait
   beyond the configured intake deadline plus margin; take repeated same-process snapshots until all
   four canonical groups have no active reservations and no meaningful in-flight amount. Check the
   reconciliation/reaper is not mid-update. Require current/next cycle timestamps to leave more than
   the packet's maximum fence-to-Table-readiness window plus a stated safety margin. If a boundary
   is too close, wait/replan before freezing. If a boundary passes before the old process is stopped,
   take a fresh snapshot. If one passes after stop, do **not** promote the stale seed or restart old
   memory; stop and obtain a fresh-state recovery decision.
5. **Snapshot and seed.** Read `admin.credit_groups`, not `admin.backends`. Bind the exact set of
   four expected canonical metered groups to the loaded membership/config fingerprint. For each
   group capture `live.estimated_remaining_usd`, `reserved_inflight_usd`, active count, oldest age,
   debit/recovery counters, `current_cycle_start_utc`/`next_reset_utc`, configured start day,
   allowance, and effective `reserve_policy`. Require no pending reservations, stable consecutive
   snapshots, and unchanged same-process/revision identity. Use remaining minus any bounded
   floating-point in-flight residue (the prior handoff guard allowed `<1e-9`; abort above the
   reviewed threshold), **not** spendable `available_credit_usd`. Convert the raw canonical group
   value with decimal `ROUND_FLOOR` to six places (`floor(x * 1_000_000) / 1_000_000`); never use
   round-to-nearest. Assert finite/nonnegative seed and `seed <= cycle_allowance`. Record old debit
   totals as history only. Create a unique, version-pinned Key Vault secret for the four-key JSON
   seed map; do not reuse the prior memory-restart seed secret/version.
6. **Exclude the old writer, then start Table once.** Deactivate the old revision and verify no active
   old revision/replicas/workers/background writers. Promote the reviewed one-worker immutable image
   and otherwise unchanged production config, changing only the approved state/table/identity
   settings and the new seed reference. First Table startup will create rows from the seed. It is a
   per-partition create, not a four-account atomic transaction; keep ingress fenced until all four
   rows/config values are verified.
7. **Verify before any paid call.** Require exactly one healthy active Table revision and one replica;
   loaded env/config hashes match the packet; `FOUNDRY_STATE_BACKEND=table`; endpoint/table names and
   identity are exact; `/health/ready` is 200 with all checks true; and `/admin/status` reports the
   exact four account groups. For each row require allowance, cycle day/start, seed remaining,
   zero reservations/inflight, `debited_usd_total=0`, `recovered_debit_usd_total=0`, and expected
   reserve policy. Confirm current cycle timestamp is the bound cycle. No public ingress yet.
8. **Handle partial init conservatively.** If startup/readiness fails, keep ingress denied and all
   old writers stopped. Inspect actual table contents read-only; do not delete rows, change the seed,
   switch table names, or blindly retry a fresh migration. A restart with the identical pinned
   config may idempotently fill an absent row, but any pre-existing/unexpected row, mixed seed,
   changed membership/cycle fingerprint, or uncertain write acknowledgement requires inspection
   and a fresh reviewed recovery decision. Because sync has no persisted full config fingerprint,
   the external packet must bind and compare the effective membership, cycles, allowances, reserves,
   table identity, and seed. Pin table names permanently after initialization; changing to a new
   empty table later can replay the still-configured initial seed.

### Exact effective settings to preserve or add

| Setting | Phase 2 value/handling |
| --- | --- |
| `FOUNDRY_STATE_BACKEND` | Set to `table` only in the reviewed successor. |
| `FOUNDRY_TABLE_ENDPOINT` | Existing hardened account's HTTPS Table endpoint; no SAS/key/query string. |
| `FOUNDRY_TABLE_CREDIT_NAME`, `FOUNDRY_TABLE_HEALTH_NAME` | Exact names of the two newly created, dedicated production tables. |
| `FOUNDRY_AZURE_CLIENT_ID` | Production user-assigned identity client ID; source uses this exact env name. |
| `FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON` | New version-pinned secret reference containing only the four canonical groups' fresh floored estimates. Never treat it as a live balance source after rows exist. |
| `FOUNDRY_BACKEND_CYCLE_START_DAY_JSON`, `FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON` | Preserve current loaded canonical-group maps exactly; verify all four expected groups. |
| `FOUNDRY_MIN_CREDIT_RESERVE_USD`, `FOUNDRY_MIN_CREDIT_RESERVE_PERCENT`, `FOUNDRY_CREDIT_GROUP_RESERVES_JSON` | Preserve and compare exact effective per-group reserve policies; reserves are configuration, not seeded Table row fields. |
| `FOUNDRY_BACKENDS_JSON`, `FOUNDRY_MODELS_JSON`, `FOUNDRY_MODEL_ALIASES_JSON`, `FOUNDRY_PRICING_JSON` | Preserve exact current loaded values/hashes, including non-Azure providers, all pools/aliases, and prices. Do not change routing or provider roster as part of migration. |
| `FOUNDRY_RATE_LIMIT_BACKEND` | Keep current `memory`; no Table quota migration or table grant is required for Phase 2/3. |

## Phase 3 production acceptance recommendation

After Table/one initialization is fully verified, retain executor-only ingress and allocate four
fresh, single-dispatch Azure Responses cases: non-stream and stream through one available Azure
Responses deployment in each of **two distinct active Azure canonical credit groups**. Prefer the
current `gpt-6.1-sol` pool if a fresh loaded-config check confirms it is an Azure Responses model,
streaming is enabled, and the exact two selected deployments really map to those two groups; do not
force a pool or assume the model/account mapping. Use a minimal one-line prompt, `max_output_tokens`
128, and low reasoning effort if that exact deployment supports the field. Keep automatic retries
at zero and `store:false` where accepted. Reserve the exact current configured local estimate before
each case; the prior pricing evidence's two-call `gpt-6.1-sol` estimate was at most USD 0.00512 for
input/output bounded at 128 tokens, but refresh rates and estimate in the packet. Four such cases
would be at most USD 0.01024 only under those same ceilings; this is a local estimate, not an
invoice ceiling. If either group cannot be targeted without failover or the 128-token result is
incomplete/truncated, stop without replay or increasing limits.

For each case require HTTP 200, completed terminal response (for SSE, correct terminal events),
verified usage, one matching debit on the expected canonical group, and no new active/in-flight
reservations. Do not count HTTP 200 alone or infer streaming success from nonstream. No paid
Anthropic, MAI, embeddings, Google, or other-provider traffic is necessary for this narrow migration
gate; record those operation/provider exclusions rather than implying acceptance.

With intake still fenced, perform one bounded targeted restart of the Table worker after the four
cases. Verify actual changed replica/container identity or restart count, readiness recovery, and
the same four persisted balances/counters/reservation state. Confirm the new Table seed was not
reloaded: debited totals remain at the post-call values and remaining balances do not increase.
Restore the exact original ingress only after this check. On failure, never reactivate the old
memory revision with stale pre-cutover seeds. A memory emergency recovery needs every Table writer
drained first, a new snapshot from current Table state, a new versioned seed, and a separately
reviewed recovery packet; retain Table rows.

## Minimum changes to the prior memory handoff harness

The prior `router-pricing-503-handoff.py` is a useful structural reference only; its consumed run,
private paths, hard-coded resource bindings, image/revision suffix, and seed secret are not reusable.
The minimum Table migration delta for a new independently approved harness is:

1. Split its current memory-only `invariant()` into an old-writer guard (`memory`, one replica) and a
   successor Table guard (`table`, one replica), retaining single revision/worker, image/command,
   and no-overlap assertions. Bind the exact Table endpoint/names, UAMI client/principal IDs, and
   cross-RG storage resource privately.
2. Extend prepared/consumed artifacts and finite what-if to include the two table resources, the
   two table-scoped role assignments, parent-storage before/after fields, exact app `state_backend`
   environment diff, and a read-only whole-table emptiness result. Do not make a broad ARM body
   replacement that drops unowned app settings or ingress properties.
3. Replace memory post-promotion checks with Table checks: readiness's
   `state_store_reachable`, exact four canonical groups, exact seed/allowance/cycle/reserve config,
   zero Table counter baseline, no reservations, and one healthy Table writer. Keep the old memory
   debit counters in a separately labelled pre-cutover audit snapshot. Do not claim counter
   continuity.
4. Keep its use of canonical `admin.credit_groups.live.estimated_remaining_usd` and decimal
   `ROUND_FLOOR`; tighten it to bind the exact expected group set, use raw group-level values (not
   six-decimal backend mirrors), validate finite inputs/allowance bounds and cycle-window freshness,
   and refuse if membership, cycles, reserve policy, table identity, or quiet snapshots drift.
   Require the same process across all pre-freeze snapshots; re-snapshot after any pre-freeze cycle
   boundary. Once the old writer is stopped, any boundary/ambiguous Table init consumes the attempt
   and cannot fall back to stale memory seeds.
5. Add the targeted Table restart branch and prove persisted row values/counters rather than
   requiring the same process across restart. Preserve executor-only ingress, one-shot acceptance
   consumption, no retries/replay, exact original-ingress restoration, version-pinned existing
   secrets, and fail-closed recovery. Use a new run-specific seed secret/version; never overwrite or
   reuse the prior seed version.

## Local verification needed before the exact packet

No tests were run for this investigation. Existing relevant coverage includes
`tests/unit/test_state.py:310-323` (balance initialization),
`tests/unit/test_credit_accounting_correction.py:94-141` (counter persistence and cycle rollover),
`tests/unit/test_shared_resource_credit.py:438-461` (unique routable metered readiness probes),
`tests/unit/test_credit_follow_up.py:20-42` (failed initialization blocks egress and can retry),
`tests/integration/test_azurite_distributed_state.py:171-198` (concurrent create/shared account/restart),
and `tests/integration/test_azurite_distributed_state.py:562-585` (missing-table probe behavior).
These exercise adapter primitives, not the current production four-account config, migration
fencing, or current image against Azure.

Before an exact migration packet is approved, add/extend local no-Azure tests at the harness boundary
to demonstrate:

- exact four-canonical-group snapshot/seed map (no backend alias duplication, unknown/missing group
  refusal, raw API precision and conservative floor);
- cycle-reset proximity/drift refusal and stable same-process quiet snapshots;
- new empty-table `sync_from_settings` rows have the expected cycle/allowance/seed, zero reservations,
  and zero counters; retries/create races do not overwrite any existing balance;
- partial initialization or unexpected existing rows prevent ingress/promotion and never rotate or
  replay a seed; config/membership/table-identity fingerprint drift refuses before mutation;
- readiness requires all expected balance rows and Table reachability; health absence remains valid;
- post-acceptance Table restart preserves balances and debit/recovery counters without reading the
  initial seed as a reset; memory rollback requires a new Table-derived snapshot.

Then run the repository-required focused/full suite, coverage, Ruff, formatting, mypy, applicable
Azurite and Docker checks, Sonar if present, deep review, link checks, and a separate exact packet
review. Synthetic/local passes cannot establish production Azure behavior. Production remains
memory/one and Table migration remains **Planned** until separately executed and evidenced.
