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

Table finalization raises `TableEntityCreditStoreError` when reads/transactions fail, bounded
conflicts exhaust, or pending reservation/balance data is invalid. Confirmed absent or finalized
reservations are idempotent. Failed release prevents second selection and upstream egress; routing
reports `503 credit_store_unavailable`. Failed settlement is never followed by a free release.
Quota and telemetry cleanup still run independently of credit settlement. After streaming output,
credit failures propagate at completion and cannot trigger failover or replace delivered bytes.

`/admin/status.credit_groups` is the canonical unique account view. Backend entries retain their
compatibility live view and add `credit_group`; never sum those duplicated backend balances.
Use `foundry_router_credit_group_available_usd{credit_group}` for account-level metrics. The
existing `foundry_router_credit_available_usd{backend}` is nonadditive. Request/cost metrics remain
backend-labelled, and multi-worker aggregation remains Planned.

Reconciliation providers should supply canonical group updates once. Direct store calls also accept
backend aliases, normalize the complete input before writes, coalesce equal amounts and reject
conflicting values for one group. `last_updated_credit_groups` is the unique-account count;
`last_updated_backends` remains a compatibility alias for that count. Reconciliation is not a
cross-account atomic transaction; storage failures mark the attempt failed even if earlier account
updates committed. Live Azure Cost Management integration remains Planned.

## Production Gate

Production configuration now deploys twelve backend deployments, six model pools and two credit accounts using completed operator inputs. Discovery, shared-group diagnostics and cross-subscription image pull passed; see [production evidence](../plans/production-foundry/evidence.md). Production stays memory-backed with maxReplicas 1. Production inference, live failure/admission traffic, authoritative reconciliation and Table cut-over remain pending. Prices and credit values are operator-supplied local estimates, not authoritative balances.

See [implementation evidence](../plans/shared-resource-credit/evidence.md).
