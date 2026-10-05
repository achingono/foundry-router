# Activities

1. Independently review concrete design before implementation.
2. Add optional BackendConfig.credit_group default backend ID; validate safe nonblank group IDs and coherent metering. Existing cycle/allowance/remaining/reconciliation JSON variable names stay compatible but keys become effective credit groups. Unknown/ambiguous map keys rejected, missing values fail readiness/admission.
3. Keep store API backward-compatible backend arguments, normalize membership inside credit stores at sync, and key balances, reservations, caches/locks, reconciliation and Table partitions by group. Preserve default-group Table rows and legacy backend_id reservation properties. Group initialization is once per account; never sum duplicated balances. Health remains backend-specific.
4. Ensure context/scalar assess/reserve and finalize consistently resolve group. Failover retains release-before-reselection; release failure must be explicit and prevent subsequent egress. Avoid changing provider health/metrics backend identity. Group maps can also be accepted as direct store IDs for reconciliation and diagnostics.
5. Admin maps group snapshots to backends, adds canonical credit_groups view and group field; readiness/Table probes check unique metered groups. Reconciliation updates groups once. Add canonical group metric while preserving nonadditive backend view.
6. Meaningful tests: combined cross-model memory/Table capacity, usage settlement, same/different group failover, cancellation and quota failure cleanup, fresh initialization/ETag conflicts, missing group readiness, legacy defaults and non-metered behavior, reconciliation/group gauges. Run Azurite and full suite >=80%, Ruff/format/mypy, Docker build and required contextual review; Sonar if script exists.
7. Document migration: explicit group changes require drained writers and new group starting estimates; no implicit sum/migration of old duplicated partitions. Memory restart loses estimates as before. Configuration inputs are resource-level, production stays memory/one and deploys only after values supplied.
8. Production configuration remains pending operator null completion. Re-discover deployed model metadata at deployment time, restrict model names to gpt-5.6* or gpt-6*, group pools across resources, retrieve keys redacted and generate disjoint production auth. New production RG/vault and chingono registry selected; no placeholder estimates in live deployment.

## Reviewed contract clarifications

The independent review's five Major findings are addressed under the approved
[recovery amendment](recovery-amendment.md), session `ses_ef6422f4effeLjrO87PAowPxJu`.
Its conservative expiry policy supersedes free expiry; verification is recorded in evidence.
The operator approved [the remaining three-Major follow-up](follow-up-amendment.md) under that same
failure contract: failed sync stops routing, complete periodic discovery retires stale owners, and
post-output stream errors charge known usage or the full reserve.

- Reject group IDs overlapping a backend alias mapped elsewhere; resolve aliases once, then canonical groups. Group IDs reject surrounding whitespace, Table-forbidden/control characters and excessive encoded length. Settings credit maps accept canonical groups only. Store reconciliation normalizes all aliases before writes, coalesces equal amounts and rejects conflicting aliases for one group.
- Store sync derives membership from existing config mapping/object stubs with backend-ID fallback, initializes unique metered groups once, rejects mixed metering and live membership changes with pending reservations. Reservation ownership is the captured canonical group, never re-resolved against changed settings. Legacy Table ownership is PartitionKey; regrouping persisted rows remains unsupported until drained and reinitialized. Failed sync must retry with same Settings object.
- Table finalization raises typed credit-store failure for failed/exhausted transactions, malformed pending reservation or missing balance; confirmed absent/finalized is idempotent. Routing must stop second selection/egress after failed release, including quota-failure cleanup. Outer cleanup must not convert failed settlement into free release, and quota/telemetry cleanup still executes independently. Streaming never fails over after output.
- Tests must cover namespace/reconciliation collisions, legacy/default sync, ownership changes, same/different group failover, cancellation and zero subsequent egress after release failure. Readiness checks routable metered groups; health reachability still required for non-metered topology.
