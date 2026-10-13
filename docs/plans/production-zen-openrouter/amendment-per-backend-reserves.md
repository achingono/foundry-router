# Per-group reserve policy amendment

Date: 2026-10-12. Status: **Implemented locally; independently reviewed at `48012df`.**
See [independent review of df5396c](review-group-reserves-df5396c.md).
The [implementation follow-up](review-group-reserves-f891d06.md#follow-up-review-of-48012df)
closes GI-1 and GI-2 and clears the independent implementation-review gate. The legacy
filename is retained for links; policies are keyed only by canonical credit group,
not backend or model. Deployment and live execution gates remain open.

## Purpose and scope

Preserve the existing single endpoint and Azure topology while adding Zen to the
same app. A USD 10 remaining estimate has no usable credit under a USD 10 flat
reserve. A per-group policy lets Zen use USD 0.05 / 5% while Azure groups retain
their existing app-wide USD 10 / 5% settings exactly. These are proposed policy
inputs, not approved current balances or production admission authorization.

Effective reserve remains `max(flat reserve, cycle allowance * percent / 100)`.
For a USD 210 cycle allowance, 5% is USD 10.50 under either USD 10 or USD 0.05
flat settings. Do not claim the lower flat setting reduces that particular
account's effective reserve. Group overrides preserve policy for all other
allowances and future changes without changing app-wide protection.

No change to credit ownership, balance initialization, quota, cycle rollover,
settlement, reconciliation or the reserve formula. No infrastructure resources,
new production app, provider calls, Table cut-over or replica changes are added.

## Configuration contract

- Add optional `FOUNDRY_CREDIT_GROUP_RESERVES_JSON`, default `{}`. It is an object
  keyed by canonical configured **metered credit-group IDs**, with each value
  containing exactly `min_credit_reserve_usd` and `min_credit_reserve_percent`.
  No backend/model aliases as substitute keys. Both fields are required for an
  override; inheritance applies to an absent group, not a partial object.
- Reject malformed/non-object input, duplicate keys (including duplicate policy
  fields), unknown fields, null/boolean/string numeric values, non-finite or
  negative numbers and percentages above 100. Numeric zero is valid; it must
  never fall through to inheritance by truthiness. Use bounded parsing and
  sanitized validation errors without echoing configuration input.
- Validate membership after backend/group normalization. Unknown groups and
  overrides for non-metered groups fail at startup rather than becoming silent
  no-ops. Absent metered groups inherit the existing app-wide numeric settings.
  Non-metered routing continues bypassing credit admission unchanged.
- One shared `Settings.resolve_reserve_policy(credit_group)` resolves validated
  canonical metered groups to an immutable pair. Unknown IDs must not silently
  inherit; callers resolve backend membership exactly once through the existing
  credit-group helpers. Keep the policy definition at the configuration/shared
  boundary without importing routing or store implementations into Settings.
- Settings are startup configuration. No hot reload, per-request override or
  mutation of the policy map; a rollout uses the existing drained restart and
  fresh-seed procedure. Duplicate backend membership never creates extra policy
  or extra balance.

## Call-site integration

1. Routing uses the same effective group policy for candidate assessment and
   reservation assignment, in both context and scalar compatibility paths.
   Multiple backends sharing a group must resolve identically. Reuse validated
   membership within a selection; do not recompute a full backend map per
   candidate. Do not change ranking, quota or failure cleanup semantics.
2. Admin status and Prometheus metrics share one snapshot helper: partition the
   unique metered groups by effective policy, call the existing `live_snapshot`
   once per distinct policy with only its groups, and merge disjoint results.
   Supply a common `now_utc`; do not read once per backend or recompute reserve
   arithmetic in the API. A failure fails the diagnostic request rather than
   reporting fabricated zero/partial balances. Cross-policy reads are not an
   atomic all-account snapshot; quiescence remains required for rollout evidence.
3. Canonical admin group entries expose the effective pair and whether it is
   inherited or overridden. Existing global config fields retain their app-wide
   meaning. Backend alias views refer to their group's snapshot and must not be
   summed; group metrics are emitted once per account. Operators can verify the
   mixed policy without relying on readiness alone.
4. Google sealed-state fingerprints bind the effective pair for the backend's
   own group using the existing reserve fields. Empty-map fingerprints remain
   unchanged; another group's override must not invalidate unrelated bindings.
   A changed effective policy for the bound group must invalidate its binding.
   Non-metered paths remain unchanged.
5. `credit.py` and Table-store accounting algorithms/signatures remain unchanged.
   The existing group-unaware `CreditAssessmentContext.from_settings` constructor
   is not a group-policy resolver; no production admission call may use it to
   bypass the new resolver. Existing runtime call sites construct the resolved
   context explicitly. Verify the complete caller inventory during review.

## Template and documentation contract

Add non-secret object parameter `creditGroupReserves = {}` to the flat root and
public typed adapter, carry it through optional `RouterConfig` with `{}` fallback,
and serialize it once to `FOUNDRY_CREDIT_GROUP_RESERVES_JSON`, following model
aliases. Missing values preserve current behavior for direct module consumers.
No new secret, grant or resource. Verify flat/typed/module default and override
propagation; the existing environment/reserve adapter limitations are separate.

Update configuration, shared-credit operations, admin/observability documentation,
infra input documentation and requirements traceability. Describe configured
policies and local estimates accurately; readiness does not prove version pinning.

## Required verification

- Configuration: empty map, inheritance, explicit pair/zero, both range edges,
  duplicate/unknown keys and fields, malformed types and non-finite inputs;
  unknown/non-metered group and backend-alias rejection; several backends in one
  canonical group. No value-bearing validation logs.
- Routing integration: distinct synthetic Zen/Azure groups under one Settings
  instance, shared backends, assessment **and** actual reservation paths, context
  and scalar APIs; inherited groups match the pre-change decision/headroom at
  reserve boundaries. Non-metered bypass stays unchanged.
- Admin and metrics: correct mixed-policy balances and effective-policy display,
  one read per distinct policy, no duplicated group totals, failure propagation.
- Sealing: unchanged empty-map fingerprint, own-group effective-policy change
  invalidation and unrelated-group override stability.
- Existing memory and Table interfaces: compatible resolved policies without
  store algorithm changes. Full suite, at least 80% new-code coverage, Ruff/format,
  type checks, flat/typed/module Bicep checks and applicable Docker build. Follow
  the repository conditional Sonar and independent deep-review requirements.

## Re-validation and release gates

The four staging passes belong to the old image/configuration. Keep their files
and run identities closed and unchanged. First validate the shared-instance
shape offline with synthetic account balances and transports; do not copy
production Azure credentials or send Azure inference as a test fixture.

Implementation must receive independent review before deployment. Any subsequent
live staging re-validation needs a separate concrete, reviewed execution amendment
with new immutable identities/manifests, exact cases and request/budget limits,
new image digest/configuration binding, durable no-replay evidence and explicit
promotion prerequisites tied to that new staging evidence. The current harness
binds the original run IDs and would otherwise still accept old staging passes;
updating that gate is part of the future reviewed harness amendment. No paid
staging re-run or extra inference is authorized by this design review.

Production remains blocked until new-release staging evidence is accepted and the
existing release/version, human-owner, quiescence, monitoring and approval gates
pass. Fresh seeds cover **all** retained Azure accounts plus Zen on each memory
restart; shared staging account allocation must remain disjoint or be handed off
under controlled quiescence. The group map does not resolve these accounting gates.
