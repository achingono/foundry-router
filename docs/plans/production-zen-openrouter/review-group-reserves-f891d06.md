# Independent implementation review: group reserve policies

Date: 2026-10-12.
Reviewed commit: `f891d06cb261c875b572baa003c465a8c3f81fbc`.
Scope: all 15 changed files, revised group-reserve amendment, complete runtime
reserve-consumer inventory, focused tests and independent offline checks.
Existing reviewer documents and the pre-existing untracked `infra/typed.json`
were preserved. Only review/status documentation was edited.

## Disposition

**Implemented locally; implementation-review gate cleared for `48012df`.**
The [follow-up review](#follow-up-review-of-48012df) closes GI-1 and GI-2 under
the startup-only configuration contract; earlier open dispositions are historical. No Critical finding or incorrect reserve amount was
identified in the exercised paths. The original four staging outcomes remain
accepted for their original release only. No new staging dispatch or production
approval follows from this review.

## GI-1 — Major: Inherited policy resolution rescans every backend per candidate

- **File/Module:** `src/foundry_router/config/__init__.py:1109-1112`,
  `routing/__init__.py` assessment/reservation calls, admin policy resolution.
- **The Issue:** Every inherited-group lookup calls `credit_membership(self)`
  and then `metered_credit_groups(self)`, which calls `credit_membership` again.
  Both walk the full backend map. Routing precomputes membership once, but the
  resolver discards that advantage for every candidate assessment and the final
  reservation. Even the default empty override map takes this path.
- **Why Static Analysis Missed It:** Each helper is bounded and correct alone;
  the quadratic behavior arises from their nesting inside selection and
  diagnostic loops. The two-backend tests check values, not traversal counts.
- **Impact:** A request considering N inherited candidates among B backends adds
  O(N*B) synchronous work on the event loop, including group-name validation and
  allocations. With N proportional to B this is quadratic and affects unchanged
  configurations. This violates the reviewed requirement to reuse validated
  membership and the repository's arbitrary-backend-count contract. The current
  small production topology is not claimed to have experienced an outage.
- **Independent reproduction:** Actual `select_candidate_backend` against
  synthetic Settings and an in-memory store, with all candidates sharing one
  inherited group and no network calls:

  | Candidates | Full membership scans inside resolver | Backend visits in those scans | Observed local duration |
  | --- | --- | --- | --- |
  | 32 | 66 | 2,178 | 0.0030 s |
  | 128 | 258 | 33,282 | 0.0296 s |
  | 256 | 514 | 132,098 | 0.1143 s |

  Each fixture also has one other configured backend. Counts include the direct
  membership scan and the scan inside `metered_credit_groups`, for each candidate
  plus final assignment. Durations are illustrative local measurements, not a
  production benchmark; traversal counts establish the regression.
- **Recommended Fix:** Precompute validated canonical/metered membership and the
  effective policy lookup once per Settings instance, or pass an immutable
  validated lookup through callers. Inherited resolution must be constant-time
  without enumerating backends. Preserve unknown/non-metered refusal, explicit
  zero, provenance and the unchanged accounting core. Add a many-backend,
  shared-group selection regression asserting scan counts do not grow per
  candidate; cover the default empty map as well as overrides.
- **Disposition:** Open; independent follow-up required before implementation
  clearance. No live re-validation is needed to prove this fix.

## GI-2 — Suggestion: Make the validated map read-only

- **File/Module:** `Settings.credit_group_reserves` and the resolver's early
  override return at lines 1106-1108.
- **The Issue:** Individual `GroupReservePolicy` values are frozen, but the map
  remains a writable dictionary. The resolver returns an inserted value before
  checking canonical membership. An in-process insertion of an unconfigured key
  and `GroupReservePolicy(-1, 0)` is therefore returned without validation.
- **Why Static Analysis Missed It:** The dataclass is immutable while its owning
  collection remains mutable; the validation invariant spans both objects.
- **Impact:** Accidental internal mutation can invalidate startup validation or
  change policy between assessment and assignment. No external mutation route
  or current production writer was found, so this is not a demonstrated remote
  bypass and is not the blocking finding.
- **Recommended Fix:** Keep the parsed/effective maps read-only after startup,
  preferably alongside the cached membership required by GI-1. Test attempted
  mutation and unknown-ID refusal without allowing arbitrary map replacement
  through normal application code.
- **Disposition:** Open defensive Suggestion; the plan calls for startup-only
  policies without mutation.

## Verified behavior

- All 38 feature tests passed; the combined feature/shared-credit/core-credit/
  sealing selection passed **129 tests**. The implementation's reported full
  suite and 100% new-module coverage were not rerun or independently measured.
- Independent admin/metrics exercise used three canonical groups, two distinct
  policies and a shared backend alias. Zen headroom was USD 9.50; each synthetic
  USD 210 Azure group retained USD 199.50 headroom. Each endpoint made two policy
  reads under one common timestamp; metrics emitted exactly three group samples.
- Compared empty-map fingerprint output directly to the actual pre-change
  `google_sealing.py` implementation, evaluated in memory: identical. Existing
  feature tests also cover own-group invalidation and unrelated-group stability.
- Source confirms resolved pairs reach context and scalar assessment/assignment
  branches; non-metered paths bypass reserve resolution. Core memory/Table
  files are unchanged, and `CreditAssessmentContext.from_settings` has no runtime
  call sites. These findings do not establish Table deployment readiness.
- Bicep 0.47.16 flat/typed builds and both lints completed. Existing experimental
  assertion notices and CPU BCP036 warnings remain. Compiled JSON assertions
  verified `{}` defaults, typed-to-flat-to-module propagation and optional module
  fallback/environment serialization. Outputs and compiler extraction used `/tmp`.
- Configuration bounds/type/group/duplicate checks and sanitized errors were
  inspected. Policy grouping and explicit admin provenance match the design.
  No runtime or template fix was applied by the reviewer.

## Remaining gates and review limits

Fix GI-1, add its regression and complete the focused/full verification required
for the implementation update, then obtain independent follow-up review. The
separate live execution amendment must still define fresh immutable identities,
request bounds, new-release staging evidence and promotion binding. Old staging
passes cannot qualify this new image. Fresh seeds for all retained accounts,
release/version evidence, named human owners and production approval remain open.

Review followed the repository deep-review focus on ownership, state consistency,
evidence boundaries and resource economics. No live resources, secret files or
historical ledgers were accessed. No deployment/provider calls were made. Full
suite, Docker, Ruff/mypy and coverage were not rerun by this reviewer; the
conditional Sonar script is absent. Documentation links/anchors, whitespace and
the final review diff were checked.

## Follow-up review of 48012df

Date: 2026-10-12.
Reviewed commit: `48012dfe73b065456b902712e46a17c64f22d15f`.
Scope: both changed files, prior GI-1/GI-2 reproductions, cached resolution and
fixture-drift fallback under the amendment's startup-only configuration contract.

**GI-1 and GI-2 closed. Independent implementation-review gate cleared.** No new
Critical or Major finding was identified in this scoped follow-up. This clears
local implementation review, not deployment, live re-validation or production.
Earlier open dispositions in this document are historical and superseded here.

### GI-1 — Closed

Validated canonical membership, metered IDs and effective policies are prepared
at Settings initialization. Both inherited and overridden steady-state policies
are direct lookups. The prior many-backend selection reproduction was repeated
with 32, 128 and 256 candidates sharing one group, under both an empty map and an
explicit override. Patching both resolver scan helpers to raise did not disrupt
any selection: every run performed **zero resolver scans** and exactly one
routing-level membership calculation. The 256-candidate runs took approximately
0.0025 seconds locally versus the prior inherited-path measurement of 0.1143
seconds; counts, not timing, establish that the quadratic work is removed.

### GI-2 — Closed for validated-map contents

The three parsed/derived maps use `MappingProxyType`, metered IDs use a frozenset,
and policy pairs remain frozen. Independent attempted insertions into membership,
overrides and effective policies raised TypeError. Unknown IDs and backend aliases
mapped to other groups still refused. This closes the demonstrated dictionary
mutation issue; it does not claim that the entire Settings object is frozen or
that trusted Python code cannot replace its attributes. No production mutation
path was found, and startup-only configuration remains the supported contract.

### Fixture-drift fallback clarification

Added a synthetic backend/group after initialization and verified app-wide
fallback; flipping that late group's metering off refused, and flipping it back
on restored fallback. This compatibility path is only reached on a cache miss.
It invokes `credit_membership` and `metered_credit_groups`, which itself calls
`credit_membership`: **two full backend scans**, not the reported one. It does
not cache a newly added group's result. Existing cached groups continue using
their startup policies, so this is not general drift detection or hot reload.
These limits do not affect the validated steady-state fix. Actual configuration
changes still require a freshly validated Settings instance and the reviewed
quiescent restart/fresh-seed procedure; do not rely on fixture mutation behavior
for production reconfiguration.

### Verification and remaining gates

- **133 focused tests passed**, including all 42 group-reserve checks and the
  shared-credit, core-credit and sealing tests.
- Independent six-way many-candidate selections, map-mutation/refusal checks and
  late-group/metering compatibility checks above passed using synthetic data and
  in-memory stores. No live requests, secrets or historical ledgers were read.
- No runtime/template code was edited. Full suite, coverage, Ruff/mypy, Bicep and
  Docker were not rerun for this two-file follow-up; implementation-reported
  verification remains separate. Prior template checks remain applicable because
  this follow-up does not change templates.
- Plan links/anchors, whitespace and final documentation changes checked.
- The separate live execution amendment still needs fresh identities/manifests,
  bounded requests and a promotion gate bound to the new release's staging
  evidence. Old staging passes do not validate this image. All-account seeds,
  immutable deployment bindings, human owners and production approval stay open.
