# Independent review: roster harness implementation

Date: 2026-10-12.
Reviewed commit: `e34b506e74da1ce1d088fbbd44b9da3754498e21`.
Scope: harness and test diff, pinned roster manifest, retained catalog rates,
[reviewed execution amendment](amendment-roster-execution.md), prior amendment
review, and existing execution/persistence/acceptance boundaries.

## Disposition

**Original commit: changes required for two Major findings.** Both findings are
closed by the independently reviewed working-tree fixes recorded below. Harness
implementation review is cleared for those exact files; live execution remains
subject to separate deployment/input/owner approvals and verification gates.
The release digest is retained as supplied metadata; this review does not verify
the deployed binary or clear deployment, seed, owner or approval gates.

## HR-1 — Major: Missing inherited Zen evidence is accepted

- **File/Module:** `scripts/quality/staging_validation.py`,
  `_observe_roster_policy`, lines 960–990; `_roster_policy_gate`.
- **The Issue:** The observer validates inherited policy only for names already
  present in `admin["credit_groups"]`. It never requires every manifest-bound
  `inherited_groups` name to exist. A snapshot containing only `or-shared` passes
  both the policy observer and all-group quietness loop. Removing `zen-staging`
  after a response also passes the closing observer and every successor gate.
- **Why Static Analysis Missed It:** Iteration and comparisons are valid; the
  error is the missing completeness condition for normative evidence.
- **Impact:** Five paid slots can be consumed and recorded as passing without
  the inherited-group diagnostic comparison required by the reviewed amendment.
  A disappearing group is silently treated as satisfactory evidence.
- **Recommended Fix:** Require the bound OR group and every inherited group to
  exist before inspecting policies, at both opening and closing observations.
  Validate each required inherited entry explicitly. Add offline cases for Zen
  missing initially (zero POSTs) and disappearing after the first response
  (failed first outcome, one POST, no successor or replay).
- **Reproduction:** Use the existing `roster_app` fixture with `extra_groups={}`.
  `run_roster` returns five `passed` outcomes and makes five fake inference POSTs.
  Alternatively subclass `FakeApp._admin` to remove `zen-staging` whenever
  `self.dispatched > 0`; the run again returns five passes and five POSTs.

## HR-2 — Major: Closing observation does not bind the resolved pool identity

- **File/Module:** `scripts/quality/staging_validation.py`,
  `run_validation_case`, lines 1199–1218; `_resolve_group` interaction.
- **The Issue:** The closing snapshot resolves the current pool, but the policy
  observer receives the old `_group`. The harness never compares
  `resolved_now[0]` with `_group`, `resolved_now[3]` with `_backend`, or the closing
  provider/deployment/operation binding with its opening values. It then uses
  the newly resolved group's balance for settlement. The observer therefore
  verifies the original group's policy while settlement may read another group.
- **Why Static Analysis Missed It:** Both tuple resolutions and numeric
  reconciliation are valid individually; the missing identity comparison spans
  two observations and the experiment's trust boundary.
- **Impact:** Backend or group changes can produce a passing outcome and permit
  successor inference, violating the explicit changed-binding halt contract.
  Matching balances can make settlement against another group appear coherent.
- **Recommended Fix:** Preserve an immutable, sanitized opening binding containing
  group, sole backend ID, provider, deployment and supported operations. Require
  the closing resolution to match that binding before reading its balance, and
  observe policy using the verified closing group. Refuse missing or changed
  bindings immediately. Add offline mutations of group, backend ID, provider,
  deployment and operation after the first response; each must fail the first
  outcome and prevent a second POST. Include a changed-group case with matching
  numeric balances so incidental debit differences cannot mask the defect.
- **Reproduction:** Subclass `FakeApp._admin` so snapshots after dispatch change
  the first pool's backend provider to `azure` and deployment to a different
  value. All five outcomes pass and five POSTs occur. A second reproduction
  changes that backend's `credit_group` to `zen-staging` and supplies the same
  remaining balance as `or-shared`; all five outcomes again pass. The original
  OR policy remains unchanged in both reproductions.

## Verification and limits

- Repository HEAD matches the reviewed commit. Existing uncommitted plan edits
  were inspected as current review context and preserved.
- `.venv/bin/python -m pytest tests/unit/test_staging_validation.py -q`:
  **63 passed**, including all 15 roster tests. Existing deprecation warnings
  were emitted. The reported 2,499-test full-suite result was not rerun.
- Four additional temporary offline reproductions used the existing stateful
  fake transport: Zen absent, Zen disappearing, backend metadata changing, and
  group changing with matching balances. Each incorrectly returned 5/5 passes.
- Recomputed combined configured-price preflight estimate:
  **USD 0.00571392**. The retained five-model prices match the pinned roster.
- Inspected run/file/CLI routing, manifest fingerprints, reserve-before-egress,
  halt/no-replay persistence, bounded response handling and the unchanged
  production prerequisite. No further actionable finding is asserted here.
- No runtime code, existing tests, manifests, historical ledgers, deployed
  resources or secrets were changed. No live endpoint or inference was called.
  This report is the only review artifact added to the repository.


## Follow-up review: HR-1 and HR-2 closed

Date: 2026-10-12. Reviewed changes on top of `e34b506`, subsequently committed
as `2e18d6fd168a80084090f8338b767aa4889a6db9`. Both committed blobs match
the reviewed files exactly. Git blob identities at review time:

- Harness: `262cd3a87cbda4b4e2400d7f7439f9434821da3d`.
- Tests: `e30fbb186d359c0b7b73dd96a928ac1a8d440545`.

**HR-1 closed:** The observer now requires the seen inherited-group set to equal
its manifest-bound required set. Both opening and closing observations enforce
presence. New tests prove initial absence refuses before POST and disappearance
fails after one POST with no successor or replay.

**HR-2 closed:** The opening group, backend ID, provider, deployment and operations
binding is compared with every closing resolution before its live balance is
read. Missing or changed resolutions fail immediately. Independent offline
probes exercised backend ID, provider and deployment separately, with failed
first outcomes, one POST and refused replay. Separate snapshot probes verified
operations changes and a changed group with identical post-debit live balance
and reserve policy each fail after one POST.

Verification: **68/68 harness tests passed**, Ruff lint and format checks passed.
The background full-suite verdict was not independently observed during this
follow-up. Existing full-suite requirements remain in force.
No additional Major or Critical finding was found in the fixes.

### Suggestion: Make operations mutation observable in the test fixture

- **File/Module:** `tests/unit/test_staging_validation.py`, `FakeApp._admin`.
- **The Issue:** The new rebinding option updates `supported_operations` in the
  fake backend, but `_admin` still serializes a constant `["responses"]`. The
  committed tests cover combined provider/deployment, backend ID and group
  mutations; they do not exercise operations independently. A probe using the
  rebinding option for operations therefore still reports passing outcomes.
- **Why Static Analysis Missed It:** The fixture's serialization silently masks
  the intended mutation while producing otherwise valid snapshots.
- **Impact:** Future operations-binding regressions could escape the fixture's
  mutation tests. This does not undermine the runtime fix: a separate snapshot
  mutation independently confirmed the operations refusal.
- **Recommended Fix:** Serialize the configured fake operations and add a focused
  operations-only mutation test; split provider/deployment cases if helpful.

This follow-up updates only the reviewer report. It does not authorize vault
writes, rollout, dispatch or production qualification.
