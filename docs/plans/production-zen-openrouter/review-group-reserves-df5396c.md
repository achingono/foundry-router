# Independent review: group reserve policy amendment

Date: 2026-10-12. Reviewed draft: `df5396c99be7790b9583af443e7bc09b0d031547`.
Scope: proposed configuration, ownership/resolution, routing and diagnostics,
sealing, template propagation and staging/promotion implications. Existing
uncommitted review documentation was preserved. No implementation was performed.

## Disposition

**Revised plan approved for local implementation.** The canonical group-keyed map
is the right boundary: one balance receives one policy, with unchanged app-wide
inheritance elsewhere. Two Major planning gaps and two clarifications below are
addressed in the [revised amendment](amendment-per-backend-reserves.md). This
closes the plan-review gate only. Implementation review, a separately bounded
live re-validation amendment and production approval remain required.

### GR-1 — Major: Mixed-policy diagnostics need an explicit aggregation contract

- **File/Module:** Draft call-site proposal; `api/routes/admin.py`,
  `CreditStore.live_snapshot`, routing context/scalar assessment and reservation.
- **Issue:** Each admin endpoint currently supplies one pair to a snapshot of all
  groups. Merely resolving a group at existing call sites cannot produce correct
  mixed-policy status/metrics in that single call while leaving the core API
  unchanged. The draft also leaves effective-policy visibility unspecified.
- **Why Static Analysis Missed It:** Each policy and result can be valid while
  the reported account headroom disagrees with the admission policy.
- **Impact:** Zen can be routable yet reported protected, or Azure headroom can
  be reported using Zen's lower reserve. Per-backend reads can duplicate group
  work and evidence.
- **Resolution:** Added one shared snapshot helper, partitioning unique groups
  by policy, common observation time, disjoint merge and failure propagation.
  Canonical group entries show effective policy. Both assessment/assignment and
  context/scalar paths must use the shared resolver. Core algorithms stay intact.
- **Disposition:** Addressed at plan level; implementation tests/review pending.

### GR-2 — Major: Re-validation and promotion are still bound to consumed evidence

- **File/Module:** Draft acceptance; `scripts/quality/staging_validation.py`,
  current committed manifests and original six-case execution contract.
- **Issue:** “Staging re-validation” gives no fresh identity/request budget or
  replacement promotion predicate. The harness currently binds the original IDs
  and accepted four-case staging evidence, which predates this runtime change.
- **Why Static Analysis Missed It:** This is temporal release/evidence binding
  across a configuration change, not malformed input or a failed test.
- **Impact:** Reusing the run cannot verify the new image and can either refuse,
  return old results or permit promotion based on the prior release. New paid
  calls without an amendment exceed the reviewed execution scope.
- **Resolution:** Added offline mixed-account verification first. Live validation
  remains a separate gate requiring reviewed fresh manifests/identities, explicit
  call/cost bounds, exact new release binding and a promotion prerequisite that
  consumes the new staging evidence. Old files remain closed and unchanged.
- **Disposition:** Addressed by separating local implementation clearance from
  the still-open live harness/execution amendment; no new dispatch is authorized.

### GR-3 — Suggestion: Make configuration and unchanged behavior testable

Require both numeric fields, strict finite/range/type checks, explicit zero,
unknown/duplicate-field rejection and canonical metered-group keys. Resolve
membership once and preserve non-metered bypass. Add explicit Google effective-
policy fingerprint invariants and flat/typed/module propagation. These revisions
remove silent partial inheritance and clarify what “unchanged” means. The
existing group-unaware `from_settings` constructor is not used by current runtime
admission; it must not become a bypass during implementation.

**Disposition:** Incorporated into the revised contract and test matrix.

### GR-4 — Suggestion: Correct the USD 210 example

The reserve formula is the maximum of the flat amount and the percentage of
cycle allowance. Five percent of USD 210 is USD 10.50, so lowering the flat
amount from USD 10 to USD 0.05 does not change that example's effective reserve.
The group-map justification is preservation of per-account policy across
allowances, not an asserted immediate weakening of a USD 210 allowance.

**Disposition:** Corrected without assuming current live account balances.

## Verification and limits

Reviewed canonical shared-credit operations and source ownership helpers,
Settings parsing, every runtime reserve consumer, memory/Table snapshot contracts,
Google fingerprinting and existing routing/credit/sealing tests. Checked that
store APIs already accept explicit reserve pairs and current runtime admission
constructs its contexts directly. The design can keep accounting core unchanged.

No tests were run for these documentation-only changes; proposed implementation
checks are requirements, not claimed results. No credential files, live resources
or durable inference ledgers were accessed in this review. No runtime/template
changes, deployments or requests were made. Relative links, heading anchors,
whitespace and final documentation changes checked.
