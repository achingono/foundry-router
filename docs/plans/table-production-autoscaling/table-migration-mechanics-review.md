# Independent Table Migration Mechanics Review

Date: 2026-10-30. Reviewer: independent GPT 6 Astra session. Research author: Luna
(coordinator attribution). Reviewed [migration mechanics](table-migration-mechanics.md)
against owning source, tests, [AGENTS.md](../../../AGENTS.md), canonical
[shared-credit operations](../../operations/shared-resource-credit.md), and the owning
[activities](activities.md), [exit criteria](exit-criteria.md), and [plan review](plan-review.md).

## Verdict

**Approve the research direction with gates; no execution approval.** Existing store
primitives support the smallest proposed migration: two new dedicated production
credit/health tables on the discovered shared storage account, table-scoped managed
identity access, and startup create-if-absent initialization from four fresh canonical
seeds. No required new runtime code was identified for these migration mechanics.

**One Major packet-level gap remains: M1 below.** Close it in the future production
acceptance design and independently review the actual executable before mutation or
paid calls. Complete Phase 1 current-image isolated acceptance first. Local baseline
passes and image agreement do not satisfy that Azure gate.

Table credit/health with a single worker and `maxReplicas: 1` is a valid intermediate
outcome. Table quota, metrics aggregation, payload redesign and autoscaling are later
gates, not prerequisites for this migration.

## Source-confirmed mechanics

- **Initialization:** `main.py:392-396` awaits store sync before serving;
  `state/table.py:363-435` initializes unique metered groups with the configured
  allowance, `min(seed, allowance)`, current cycle start and zero reservations.
  `_BalanceRow` defaults both debit counters to zero (`:283-295`). This establishes a
  **new Table counter lifetime, explicitly not cumulative pre-cutover history**.
  Preserve old counters in the private audit record; no historical-counter importer
  is needed.
- **Restart and partial initialization:** `state/table.py:437-537` creates absent rows
  and preserves matching existing rows. It can merge allowance/cycle-day drift and
  has no persisted full configuration fingerprint. Four-account initialization is
  not atomic. The proposed external fingerprint, fenced inspection, fixed table
  identity, and refusal to reset/reseed unknown partial state are therefore necessary.
  An identical-config restart may finish confirmed missing rows; it is not permission
  to discard existing rows or replay a consumed migration.
- **Snapshot precision and cycles:** `api/routes/admin.py:204-225` emits raw canonical
  group values; backend mirrors at `:92-118` are rounded/nonadditive. Capture exactly
  four canonical groups and decimal-floor raw remaining estimates to six places,
  accounting conservatively for any explicitly bounded positive in-flight residue.
  Do not seed from available credit. Keep the same configured cycle and prove the
  snapshot/startup cycle matches; startup computes the cycle rather than importing
  an arbitrary old timestamp. The note correctly refuses stale post-stop seeds.
- **Identity and infrastructure:** `main.py:95-131` independently selects shared
  credit/health and shared quota. `state/azure.py:36-53` honors
  `FOUNDRY_AZURE_CLIENT_ID`. `infra/modules/storageTableResources.bicep:31-67` declares
  two tables and their table-scoped grants while referencing the existing parent.
  Preserve memory quota and verify whole-table emptiness before the first sync.
- **Readiness and health:** readiness probes only routable metered balance groups
  (`main.py:141-185`), so separately compare all four expected canonical accounts.
  Missing health rows are valid; no health-row seeding is required. Reserve policies
  remain configuration, not balance-row fields.
- **Existing tests:** inspected balance initialization in `tests/unit/test_state.py`,
  failed-sync refusal in `tests/unit/test_credit_follow_up.py`, and restart/counter/
  rollover coverage in `tests/unit/test_credit_accounting_correction.py`. These support
  reuse of the current store primitives, not acceptance of an unwritten cutover harness.

## Major — M1: Bind account targeting and prevent a second dispatch

**Location:** migration mechanics lines 126-138, production acceptance recommendation.

**Issue:** The note calls for four single-dispatch cases across two active Azure
accounts, preferably using one named pool, with automatic retries zero. It correctly
says to stop if targeting is impossible, but does not establish how this is enforced
before dispatch. Public callers select a logical model/pool, not a backend or canonical
credit account (`api/routes/openai.py:325-394`). Repeating one multi-backend pool does
not establish coverage of two accounts.

More importantly, `FOUNDRY_RETRY_ATTEMPTS=0` only limits per-backend forwarding
(`forwarding/__init__.py:509`). `routing/__init__.py:1348-1438` can still select a
second backend after a retryable first failure, independently of that setting.
Checking the eventual debit or stopping after the response cannot prevent that
second upstream dispatch.

**Impact:** Four client requests could exceed four reserved dispatches or reach an
unselected account/provider. A successful response could also be incorrectly counted
as evidence for the intended account.

**Required closure before executable approval:** Bind each case's resolved logical
pool, complete candidate set, operation/stream capability, selected Azure deployment
and canonical group from fresh effective configuration. Prefer existing suitable
single-backend pools, with zero per-backend retries, to prove targeting and absence
of a second candidate without changing production routing. Prove the actual chosen
path with local no-egress failure tests, including a retryable pre-output failure.
If current pools cannot provide both account targets under the unchanged-config
constraint, stop preparation and obtain a separately reviewed targeting disposition;
do not invent a client backend selector, silently rewrite pools, manipulate balances/
health to steer calls, or claim that zero retries disables failover. No runtime change
is prescribed by this finding.

## Required gates for the later packet

1. **G1 first:** attach completed current-image isolated four-case settlement and
   actual restart evidence, with its approved liability/restoration disposition.
   The coordinator-reported fresh baseline and all 76 runtime Python files matching
   the immutable image are accepted as attributed inputs, not reviewer reruns.
   See [evidence](evidence.md) and [Phase 1 verification](phase1-verification.md).
2. **Exact cutover binding:** bind fresh source/image/configuration/secret versions,
   tables/grants, four-account ownership, allowance/reserve/cycle values, original
   ingress and run identity. Review the finite infrastructure diff, exclusive lock,
   durable consume-before-mutation records and bounded failure recovery.
3. **Quiet migration:** prove denied public intake, full intake/forwarding/background
   drainage and repeated same-process quiet snapshots. Stop every old memory writer
   before starting the Table successor. Verify all four rows and their zero-counter
   lifetime baseline under the fence. Ambiguous partial initialization remains
   fail-closed; no reset, table rotation or stale-memory rollback.
4. **Limited production coverage approved:** two distinct active Azure accounts,
   each nonstream plus stream, is adequate representative migration acceptance once
   M1 closes. Allocate four fresh slots within the remaining whole-program USD 1/
   16-attempt bounds, use current prices and at most 128 output tokens, retain unknown
   liability, and require completed terminal usage with the expected single-group
   debit and quiet reservations. Preserve every provider's configuration and all
   four balances. Anthropic, MAI, embeddings and other providers need not receive
   paid calls for this narrow gate; record exclusions explicitly.
5. **Restart and restoration:** after the four cases, explicitly reapply deny-all
   intake (executor-only ingress is not a quietness proof), prove drainage and stable
   same-process post-call snapshots, and check cycle freshness before the one bounded
   restart. Verify actual changed worker identity/count and unchanged persisted
   balances/counters across all four accounts. Restore the exact original ingress
   only after acceptance and verify sole healthy Table/one/public readiness. Failure
   retains the fence and durable rows pending fresh-state reviewed recovery.
6. **Verification:** test the new harness's precision, drift, partial-init, targeting,
   consumption and restoration boundaries. Attach applicable repository checks and
   independent deep/exact-packet review. Reuse the verified immutable runtime when
   unchanged; this review does not require a new build or store implementation solely
   to migrate state.

## Review limits

Performed local source/document/test inspection and `git status`; existing dirty
files are user/coordinator work. Authored only this review. No Azure requests, paid
calls, tests, builds, runtime edits, packet implementation, staging or commits were
performed. Live storage suitability, grants, process state and account mappings remain
fresh execution-packet checks. Production migration remains **Planned**.
