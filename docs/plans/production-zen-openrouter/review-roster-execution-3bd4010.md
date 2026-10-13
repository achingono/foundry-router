# Independent review: roster staging execution amendment

Date: 2026-10-12.
Reviewed draft: `3bd4010aec9162f1c99e0b5fb410652aa6654f74`.
Scope: new five-case proposal, existing runner dispatch/fingerprint/resume paths,
prior staging reserve settings and open roster/release gates.

## Disposition

**Revised plan cleared for local harness implementation only.** Two Major design
gaps and two clarifications are addressed in the
[revised execution amendment](amendment-roster-execution.md). Harness code review,
concrete release/configuration inputs and operator approval remain required before
any vault write, rollout or inference. No OpenRouter production is cleared.

## RX-1 — Major: The proposed run does not distinguish mixed reserve policies

- **File/Module:** Draft staging configuration and acceptance; prior evidence;
  group policy/admin contract.
- **Issue:** “e.g. 0.05/5.0” and unchanged Zen entries do not bind the global floor,
  effective policies or provenance. The actual earlier staging record used a low
  global reserve. Five successful OR calls under that setting would pass even
  without group override support; identical Zen/OR overrides would not exercise
  the mixed-policy contrast either.
- **Why Static Analysis Missed It:** All settings/calls can be valid while the
  test cannot distinguish the intended feature from old behavior.
- **Impact:** The run could be reported as new reserve-deployment evidence without
  demonstrating override-versus-inheritance behavior. The claim that the prior
  image inherently cannot admit the existing staging account is overbroad.
- **Revision:** Fix staging global policy to 10 / 5%, OR override to 0.05 / 5%,
  and Zen to inheritance without paid Zen calls. Keep backend/model/pricing
  topology; require exact policy/provenance evidence and zero-reservation state.
  Establish override-positive/default-zero OR headroom from real allocated values
  before inference; never send a negative-control POST or invent a seed.
- **Disposition:** Addressed at plan level. Actual inputs and harness enforcement
  remain unverified. Success covers inherited diagnostics, not inherited inference.

## RX-2 — Major: Run-table additions alone lose release and policy binding

- **File/Module:** Draft harness additions; `staging_validation.py` manifest
  fingerprint, result schema, `_run_files`, environment and prerequisite mappings.
- **Issue:** The draft lists run/spec/file constants and a manifest test, but the
  actual file dispatcher is a separate literal mapping. Current fingerprints
  discard new release/policy fields and result validation does not retain the
  mixed-policy evidence this run claims. A pass/failure summary alone cannot
  establish which release/configuration supplied the new evidence.
- **Why Static Analysis Missed It:** This is a mismatch between planned evidence
  and the data retained across execution/resume boundaries.
- **Impact:** The new run may fail to dispatch, or appear to bind a release/policy
  while silently dropping it. Later promotion could rely on mismatched evidence.
- **Revision:** Specify every relevant run entry point, bounded new-run schema,
  immutable release/configuration/policy fingerprints and persistence/resume
  coherence checks. Bind the manifest to a reviewed deployment receipt, without
  claiming the harness observes the image independently. Preserve all historical
  bytes and keep production qualification a separate reviewed predicate.
- **Disposition:** Addressed at plan level; implementation and negative tests are
  required before execution clearance.

## RX-3 — Clarification: Make the combined allowance and request limits explicit

The revised contract adds at most five sequential non-streaming router/OpenRouter
POSTs. Fixed token assumptions, timeout/byte/frame bounds, no retries, halt rules
and no replay carry forward explicitly. Decimal arithmetic gives USD 0.00056832
for the new cases and USD 0.00571392 when conservatively combined with the original
six-case estimate. This is below the existing USD 0.01 allowance, without resetting
old slots or approving outstanding production calls. New production scope must be
budgeted/reviewed separately. ACR build/storage costs are outside this allowance;
“no inference yet” does not mean all preparation is unbillable.

## RX-4 — Clarification: Staging scope and production scope are separate

OR-1 does not require production streaming enforcement before an operator-only
non-streaming staging experiment. It remains a blocker to OpenRouter production.
The revised contract specifies the OR-2 staging policy and OR-3 staging design;
it does not clear account allocation, actual deployment, harness code or live
acceptance. A successful five-model non-streaming run cannot qualify Zen streaming
on the new image or substitute for a production execution amendment.

## Verification and limits

Inspected the committed draft, current immutable manifests/runner, roster review,
group-reserve acceptance and recorded staging settings. Recomputed all budget and
reserve examples with Decimal. No code tests were run for this documentation-only
review. No build was started/polled, no registry or account data queried, and no
secrets, historical ledgers or live endpoints were read. No code/configuration,
vault or deployed resources were changed. Relative documentation links/anchors,
whitespace and final changes checked. Existing reviewer edits were preserved.
