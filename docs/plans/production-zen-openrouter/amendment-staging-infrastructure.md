# Staging infrastructure amendment and independent review

Date: 2026-10-12. Status: **Implemented locally; staging execution operator-reported.**
Independent code review complete for `c10c071` and `9deeb8e`. This retrospective
record makes the staging deviation explicit; it does not claim the required
review occurred before execution. Production deployment approval remains open.

## Narrow scope

Accept at planning/code-review level the staging-only need for a separate app,
vault and runtime identity in a separate resource group, attached to the existing
managed environment, and a staging-specific reserve override. Retain the
operator-reported temporary secret grant/removal in the execution evidence;
this review neither issues grants nor independently attests their removal.

`environmentMode=existing` selects the supplied managed-environment ID and skips
new environment and observability deployment. It does not establish an isolated
managed environment or provision separate logging controls. The operator must
record existing logging/cost/monitoring coverage, shared-environment capacity and
impact, intended target ID/region and actual resource effects. Those operational
assertions remain open before using this as production release evidence.

`minCreditReserveUsd` and `minCreditReservePercent` are app-wide policy inputs.
Staging's reported USD 0.05 / 5% setting is accepted for the bounded staging scope
only. Preserve the actual production reserve policy; defaults remain USD 10 /
5%. This amendment does not approve lowering production reserves, adding a new
production app or replacing the Azure topology.

## Independent implementation review

- `c10c0716a6030d9805e681a0dfdb1a4021b6393f`: both environment and observability
  modules share the `new` condition; the app receives the supplied ID on the
  `existing` branch without dereferencing the skipped environment output.
  Workspace output is empty on attach, not a fabricated identifier. The new
  assertion rejects an empty attach ID; actual resource type, existence,
  authorization and location compatibility remain deployment checks.
- `9deeb8e2fa4f87f59aca42fd697631c0bb0f3548`: the two flat inputs propagate through
  typed `RouterConfig` to their environment variables. Omitted optional module
  fields retain USD 10 / 5%. Runtime settings validate finite, nonnegative
  reserves and percentage at most 100. Invalid strings therefore fail at runtime,
  not ARM compilation; validate concrete inputs before rollout.
- No blocking implementation defect found for the reviewed flat-template paths.
  Source/compiled assertions retain memory/one-replica defaults, Single revision
  mode and the existing container resources. This is not evidence of deployed
  replica count or proof that a rollout cannot overlap writers.
- **Suggestion:** Document that these four new inputs are available only through
  `infra/main.bicep`. `infra/typed.bicep` does not expose them and retains `new`
  environment/default reserve behavior. Do not switch the deployment entry point
  for an attached app without explicitly reviewing parameter equivalence.

## Verification

Bicep 0.47.16 built both `infra/main.bicep` and `infra/typed.bicep`; root lint
completed. Existing experimental-assertion notices and the unchanged CPU string
BCP036 warning remain; these checks were not warning-free. Compiler extraction
and generated ARM files were placed under `/tmp`, with no repository build output.
Compiled-template checks verified conditions, attach selection, reserve propagation,
defaults and unchanged memory/replica/resource settings. All 25 tests in
`tests/unit/test_credit.py` passed. No deployment, Azure validation/what-if,
provider call, full suite or Docker build was performed by the reviewer.

## Production boundary

The agreed production target remains the **existing app with its complete Azure
baseline plus `gpt-5.4-mini-zen`**. Independent pools and credit groups already
support this. No migration to a Zen-only topology or new production app is
required by the runtime. A new app would require a separate scope, auth, ingress,
monitoring, cost and shared-account allocation decision.

Adding Zen to the existing memory-backed app requires fresh conservative seeds
for every retained account after quiescence, not just the new Zen account. A
small Zen balance cannot justify silently changing the global reserve for all
accounts. Keep production on hold until verified account headroom supports the
existing policy or a separate production reserve-policy amendment is reviewed.
