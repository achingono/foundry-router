# Shared Resource Credit Operations

## Status: Implemented (runtime and production configuration)

Credit-group membership is explicit configuration on each deployment backend. Balances, safety
reserves, inflight reservations, cycle resets and reconciliation are account-owned in memory and
Azure Table adapters. Health and request/cost telemetry retain deployment backend identity. All
values remain local estimates, not authoritative Azure balances.

## Migrating Existing Credit State

1. Stop intake and drain **all** writers, workers and replicas, including background reconciliation.
   Confirm no pending reservations remain in the old partitions.
2. Choose safe canonical group IDs with no backend-alias collision. Assign every deployment of
   the account to its group and provide one operator-approved cycle/allowance/remaining estimate.
3. Initialize new group partitions from those estimates. There is **no automatic migration or
   sum** of old backend partitions: duplicated historical balances must never create extra credit.
4. Restart writers together with consistent membership; verify readiness, canonical admin groups,
   account-level available credit and reservation counts before enabling intake.

Default membership retains existing backend-named Table partitions and reservation `backend_id`
properties. Persisted reservation ownership is its PartitionKey, even for legacy properties.
Changing membership while pending reservations exist is refused by local store sync; this is a
guardrail, not a distributed configuration rollout protocol. A restarted writer cannot safely infer
old membership from new settings; drained and reinitialized migration is mandatory. Failed sync
retries the same Settings object. Memory restart loses estimates and reservations as before.

## Failure Handling and Diagnostics

### Conservative recovery (Implemented; independently approved amendment)

Expiry settles **every pending reservation**, including legacy and abandoned pre-egress rows, for
the full reserved estimate unless valid retained settlement intent supplies its charge. Age is not
proof that no provider work occurred. Confirmed explicit release still charges zero. Memory retains
intent before applying settlement; Table persists `settlement_charge_usd` with the reservation ETag
before the balance transaction. If that intent write fails, recovery falls back conservatively to
the reserved estimate; if it commits but acknowledgement is lost, the stored intent wins. Existing
intent is not overwritten by later free-release attempts. Reconciliation can correct overestimates.

Azure write bodies exclude read-only `odata.etag`, `odata.metadata` and `Timestamp`;
ETags remain conditional request headers. Application fields, including `metadata`, are
preserved. The [metadata correction](../plans/table-write-metadata/evidence.md) passes
local SDK wire and strict Azurite checks plus both supplemental isolated Azure streaming
settlements. Original full nonstream/restart acceptance remains open.

Finalization and recovery guard fresh **balance and reservation ETags in one batch**, rereading and
recomputing after conflicts. Confirmed missing rows prevent double debit after commit-then-timeout.
Table admission exceptions and exhausted conflicts raise typed errors, never `False`; possible
ownership is retained before transaction dispatch and uncertain IDs cannot be admitted again before
confirmed finalization. Only confirmed capacity rejection/non-admission permits another candidate.

Metering is part of the membership fingerprint. Local sync, admission, finalization and recovery
are serialized; aliases publish only on completed sync, and old/attempted partitions stay discoverable.
Incomplete Table initialization/config merge now raises a typed error. Routing cannot dispatch new
Settings through retained old aliases after failed sync; the same Settings object retries after
initialization recovers. The retained map remains available only for existing-account recovery.
Unknown ownership requires complete discovery; failure is not absence and multiple owners are an
explicit ambiguity. Memory refuses cross-group reuse until release. Table tracks at most 4,096
active/uncertain request owners, rejects at capacity without eviction, and uses the local store lock
instead of an unbounded per-ID lock cache. Server-owned unique request IDs and consistent drained
writer rollout are still required across replicas; no distributed cross-partition identity index exists.
The reconciliation loop periodically checks tracked IDs against **all** known partitions before
calling the balance provider, so provider outages do not prevent retirement. Confirmed absent or
finalized IDs release local ownership/uncertainty slots; live, ambiguous or incompletely discovered
IDs stay tracked. This handles timeouts without a commit, other-writer recovery and locally lost
reaper acknowledgements without evicting uncertain owners or fabricating absence.

Stream close, credit, quota and metrics cleanup receive independent shielded tasks and five-second
deadlines. Financial tasks start before close; repeated caller cancellation cannot interrupt their
opportunity. Timeout cancellation joins for at most 0.1 seconds. Non-cooperative dependency tasks
remain explicitly tracked within a 64-task limit until completion; additional tasks are rejected,
never evicted or created unboundedly. Deadline/capacity failures surface and retain conservative
credit recovery. All cleanup failures are preserved as exception notes; no retry after SSE output.
After meaningful stream output, HTTPError/502 or cancellation is never a free release: valid known
usage wins (including zero actual cost), otherwise settle the full reserved estimate. No zero intent
is persisted solely because the upstream stream failed. Confirmed pre-egress/rejected requests still
release without charging. The earlier opposite midstream-failure test expectation was incorrect.

Google and compatible translated streams distinguish available cumulative counts from verified
completion. Until clean upstream EOF and successful decoder finish, cancellation/error/unstarted
cleanup keeps the full request estimate, even with both numeric dimensions present. Observed
valid input usage still reconciles quota. Fully validated signed complete-body prefetch is
already complete. See the [local correction plan](../plans/google-stream-settlement-integrity/index.md);
the retained live cancellation failed settlement validation and is not reclassified.

Table finalization raises `TableEntityCreditStoreError` when reads/transactions fail, bounded
conflicts exhaust, or pending reservation/balance data is invalid. Confirmed absent or finalized
reservations are idempotent. Failed release prevents second selection and upstream egress; routing
reports `503 credit_store_unavailable`. Failed settlement is never followed by a free release.
Quota and telemetry cleanup still run independently of credit settlement. After streaming output,
credit failures propagate at completion and cannot trigger failover or replace delivered bytes.

`/admin/status.credit_groups` is the canonical unique account view. Backend entries retain their
compatibility live view and add `credit_group`; never sum those duplicated backend balances.
Each group entry also exposes its effective `reserve_policy` (`min_credit_reserve_usd`,
`min_credit_reserve_percent`, `source: inherited|override`); admin reads each distinct
effective policy once per request under a common timestamp, so mixed-policy balances stay
consistent without per-backend rereads. A failed group read fails the diagnostic request
rather than reporting partial balances. Use `foundry_router_credit_group_available_usd{credit_group}` for account-level metrics. The
existing `foundry_router_credit_available_usd{backend}` is nonadditive. Request/cost metrics remain
backend-labelled. Opt-in multi-worker OTLP aggregation is implemented locally; deployed
collector acceptance remains unverified. See [observability](observability.md).

Request-cost counters do not account for every credit-ledger debit. Azure streams
without terminal usage settle the full reservation but contribute no cost to the request-cost
counter; expiry recovery also has no corresponding request-cost observation. The canonical
`foundry_router_credit_group_debited_usd_total` counter is **Implemented and deployed in production memory mode** and includes
every actual settlement/recovery reduction; `foundry_router_credit_group_recovered_debit_usd_total`
is its expiry-recovery subset. Admin credit-group `live` exposes `debited_usd_total` and
`recovered_debit_usd_total`. Counters exclude reconciliation/config changes and starting-seed
deductions. They remain cumulative across cycle rollover and reconciliation, start at zero on
memory process startup, and persist in Table balance transactions. Missing historical Table
fields start at zero without reconstructing past debits; invalid fields fail closed. Drain old
Table writers before upgrading because their replacement writes do not preserve new fields.
Shared Table counter views across workers are nonadditive; OTLP still exports per-worker request
telemetry, not these shared ledger counters.

Cached Azure input uses optional `cached_input_per_million` only with valid explicit provider
cache usage; omission or malformed/ambiguous cache details retains ordinary input pricing.
Admission retains full input pricing before cache hits are known. Use canonical group snapshots to assess
admission, and compare provider charts over the verified subscription billing period and currency.
The [October 29 production investigation](../plans/production-credit-discrepancy/evidence.md)
records the reproduced discrepancy and verified billing dates. Correction rollout status is in the
[accounting correction evidence](../plans/credit-accounting-correction/evidence.md).

Reconciliation providers should supply canonical group updates once. Direct store calls also accept
backend aliases, normalize the complete input before writes, coalesce equal amounts and reject
conflicting values for one group. `last_updated_credit_groups` is the unique-account count;
`last_updated_backends` remains a compatibility alias for that count. Reconciliation is not a
cross-account atomic transaction; storage failures mark the attempt failed even if earlier account
updates committed. The opt-in Azure Cost Management provider is implemented locally, with live Azure acceptance
unverified. It supplies cycle-bound downward-only billing ceilings, never replacement promotional
balances: atomic memory/Table updates retain concurrent debits and inflight reservations.
Reported costs can be delayed/incomplete; repeated/lower reported cost cannot replenish local
credit. Query success does not establish billing completeness. Scope/resource/cycle policy changes
invalidate old results. Provider failures preserve estimates, and ownership/reaper maintenance
still runs. See the [reconciliation plan](../plans/azure-cost-reconciliation/index.md).

## Production Gate

The staging roster harness and group-specific reserve deployment have fresh
[completion evidence](../plans/production-zen-openrouter/completion-2026-10-12.md).
That historical roster run halted after two passes and one HTTP 502; it did not qualify production. The later two-model rollout below records separate acceptance.
Preserve consumed identities/results and require a reviewed bounded amendment
before more inference. Current admin quietness does not establish historical
failed-request settlement.

The earlier production baseline deployed twelve backends, six pools and two credit accounts using operator inputs. All six pools passed production nonstream/stream Responses through fs-swarm with usage-matched local debit; a follow-up bounded run verified admission rejections and single-pool settlement with both dispatches served by the pool's fs-openclaw backend. The later OpenRouter rollout below expands this to fourteen backends, eight pools and three credit accounts, with fs-openclaw disabled. Production stays memory/one. Live upstream 429/5xx failover, remaining-pool coverage, authoritative reconciliation and Table cut-over remain unverified. Prices and credit values are local estimates, not authoritative balances.

See [implementation evidence](../plans/shared-resource-credit/evidence.md).

Quota ownership is independent of account credit. The opt-in Table quota store uses distinct
attempt IDs during failover while credit/telemetry retain logical request identity. Cleanup
after possible dispatch now settles the full credit estimate and retains quota usage on
uncaught cancellation/exception; only confirmed non-dispatch permits zero-charge release.
This conservative recovery also applies when credit state remains in memory.

The [skip-DeepSeek continuation](../plans/roster-skip-deepseek/evidence.md) retained staging deployment but could not validate MiMo/Spark due intermittent health timeouts before inference. Preserve the unresolved continuation slot; no further attempt is authorized by that amendment.

For the accepted new OpenRouter staging roster, use [`gpt-6-luna-or` and `claude-haiku-5.5-or`](../plans/passed-openrouter-staging/accepted-models.md) with non-streaming Responses. The selection is not an enforced runtime allow-list; other configured staging pools remain.

Pool `streaming_enabled:false` rejects Responses stream requests before quota/credit admission and provider preparation; aliases inherit the canonical pool policy. Set this only for pools qualified for nonstream use. This does not stop all intake or isolate shared account wallets.

The [two-model OpenRouter production rollout](../plans/openrouter-production-two/deployment-evidence.md) is deployed: `gpt-6-luna-or` and `claude-haiku-5.5-or` accept non-streaming Responses only. The existing six Azure pools and aliases were retained; the disabled fs-openclaw group has zero allowance. Staging is stopped for the exclusive OpenRouter handoff; do not restart its stale credit allocation. Production remains memory/one. Four new staging/production checks passed; the operator controls intake reopening.


## October 29 accounting correction

The [credit accounting correction](../plans/credit-accounting-correction/evidence.md)
release is deployed in production memory/one mode. It adds complete canonical
ledger debit/recovery counters and explicit cached-input settlement prices.
`fs-openclaw` is enabled with operator-authorized CAD 200 allowance / CAD 180
remaining converted conservatively to USD 142.49 / USD 128.24 at 1.4036 CAD/USD.
The inherited reserve leaves USD 118.24 available before acceptance costs.
Other accounts' drained remaining estimates were preserved; historical debit
estimates were not refunded. Azure subscription billing periods verified cycle
start days 2 for swarm and 26 for openclaw. Pricing uses documented conservative
meter ceilings, so local estimates can exceed actual billed cost.
Production acceptance and ingress-restoration details and limits are recorded
in the linked evidence; Table cut-over and live nonzero-cache validation remain
unverified.


## MAI image ceiling accounting (Implemented and deployed)

The azure_mai provider reserves one configured positive image estimate and
retains it through non-streaming forwarding. This operator-owned estimate
represents bounded prompt plus image generation; it is not a verified Azure
billing ceiling. Unverified provider usage
cannot imply zero cost. Confirmed pre-dispatch rejection releases the reserve;
post-dispatch cancellation, malformed/oversized output and worker failures
retain conservative charging. Successful image delivery charges the same local
ceiling once. Billable token usage has not been established, so later authoritative cost
reconciliation remains the way to adjust the estimate. The existing canonical
ledger debit counters expose these charges. See [live enablement gates](../plans/foundry-three-models/evidence.md).

The three-model production handoff preserved live balances and separately deducted one native diagnostic estimate; see [production evidence](../plans/foundry-three-models/production-evidence.md).
