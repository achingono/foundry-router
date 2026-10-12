# Independent production enablement plan review

Date: 2026-10-11.
Reviewed input: the seven-file uncommitted production enablement draft, against
repository HEAD `61ee9d02a46e60b53e56358650220c5504734307`.

Scope: plan/risk register and canonical routing, configuration, API, operations,
credit, monitoring and deployment contracts; current live evidence and relevant
runtime/IaC source. The reviewing assistant did not implement the original draft.
This session revised the plan and recorded its independent findings. No execution
or account data was needed to conduct the review.

## Disposition

**Commit the revised plan for operator approval and execution preparation.**
Do not execute the original three-pool production rollout. Four Major planning
findings and two Suggestions below are addressed in the revised contract; their
mitigations still require execution evidence. The independent plan-review step
is complete. It does not approve live spending, secret changes or deployment.
Material changes to these decisions require another independent review.

The recommendation is Zen-first production, OpenRouter staging nonstreaming only.
A future OpenRouter production amendment needs an enforceable pre-admission
nonstreaming restriction or successful router streaming verification with an
accepted operating policy. Monitoring and client guidance alone are insufficient
to release the currently unverified streaming path to all production callers.

## Findings and revisions

### PE-1 — Major: Streaming behavior and access controls do not support the proposed limitation

- **File/Module:** Original index contract item 5, activities 4–5 and risk R5;
  [backend configuration](../../../src/foundry_router/config/__init__.py),
  [translated forwarding](../../../src/foundry_router/forwarding/__init__.py),
  [live evidence](../zen-openrouter-live-verification/evidence.md).
- **The Issue:** The draft characterized failures as sanitized 502s and offered
  nonstreaming clients as an alternative control. Recorded router failures had
  HTTP 200 and missing terminal usage. Post-header translation failure cannot
  replace the public status, though internal final request metrics may record
  502. There is no per-model streaming-disable setting or per-client pool ACL.
  Direct stream probe success does not establish router streaming or the cause
  of the earlier failure.
- **Why Static Analysis Missed It:** This is a mismatch between live evidence,
  operational claims and configuration capabilities, not a source type error.
- **Impact:** Ordinary clients can request unsupported streams, receive partial
  output/failure events under HTTP 200, and evade HTTP-only error monitoring.
- **Recommended Fix / Revision:** Hold OpenRouter out of production; permit only
  operator-controlled staging nonstream checks. Require future independently
  reviewed enforcement or full streaming proof. Monitor terminal completion,
  failures, usage and reservations as well as status. Revised index, activities,
  exit criteria and R5/R14 adopt this decision.
- **Disposition:** Addressed at planning level; OpenRouter production remains out
  of scope. This is not operator risk acceptance on the user's behalf.

### PE-2 — Major: Blind version rollback restores stale memory credit

- **File/Module:** Original activities 3/5/6 and R6;
  [shared-credit operations](../../operations/shared-resource-credit.md),
  [deployment guidance](../../../infra/README.md).
- **The Issue:** Restarting/promoting and automatically returning to prior secret
  versions does not carry forward in-memory debits or reservations. Old startup
  estimates can replenish already-spent balances, including existing Azure
  groups. Single-revision mode with maxReplicas=1 can still overlap revisions.
- **Why Static Analysis Missed It:** The lost state crosses process lifetimes and
  operator actions outside an individual configuration validation.
- **Impact:** Overspend, duplicate admission budgets, lost unsettled accounting
  and disruption to otherwise unchanged Azure pools.
- **Recommended Fix / Revision:** Require approved intake stop, drain of all
  writers/background work, no unsettled reservations, fresh conservative seeds
  and explicit seed versions on every restart, promotion and rollback. Restore
  old topology/image with current balances; never blindly reactivate old memory
  state. If quiescence or balances cannot be established, halt for the operator.
  Do not change ingress rules. Revised activities and R6/R9/R13 make these gates
  explicit and remove automatic rollback.
- **Disposition:** Addressed at planning level; maintenance and seed procedures
  must be proved before execution.

### PE-3 — Major: Identical environment secrets are neither safe promotion nor a pinned release

- **File/Module:** Original index items 4/6, activities 2/5 and R7;
  [root secret URL construction](../../../infra/main.bicep),
  [container secret bindings](../../../infra/modules/containers/router.bicep).
- **The Issue:** Whole staging topology/auth/balance secrets cannot safely
  replace production values. Generating new production auth would break callers.
  The root constructs versionless secret references except for optional
  initial-credit pinning; retaining a secret version does not ensure it is used.
  The draft also did not bind the staging-tested image to an immutable production
  digest or establish that the existing production image has the adapter changes.
- **Why Static Analysis Missed It:** Each secret and deployment parameter can be
  valid individually while the environment bundle or release selection is wrong.
- **Impact:** Wrong topology, unexpected auth rotation, mixed configuration,
  stale balances or an untested image despite a nominal staging pass.
- **Recommended Fix / Revision:** Promote the tested digest and reviewed provider
  delta with separate environment bundles and fresh seeds. Preserve production
  auth and every unrelated setting. Review the actual version-selection/load and
  rollback procedure before staging; require a scoped amendment if existing
  tooling cannot implement it without template changes. Keep sensitive exact
  mappings operator-held. R4/R7/R8/R12 and preparation gates now cover this.
- **Disposition:** Addressed at planning level; actual binding mechanism, release
  provenance and environment validation remain mandatory open inputs.

### PE-4 — Major: Paid validation lacked an executable request budget and acceptance contract

- **File/Module:** Original activity 4 and exit criteria for staging verification.
- **The Issue:** 'Bounded' checks had no case count, identities, time/size limits,
  budget or durable replay protection. Streaming could be run merely to confirm
  failure; usage presence and zero reservations did not establish complete stream
  delivery or correct account debit. Production health alone was not inference.
- **Why Static Analysis Missed It:** The unspecified behavior lives in future
  operator/harness execution, so existing unit tests cannot enforce it.
- **Impact:** Repeated paid attempts, consumed diagnostic budgets, incorrect
  settlement or premature promotion on HTTP-only success.
- **Recommended Fix / Revision:** Define four staging and two Zen production
  cases, the fixed input, output/time/body/frame bounds, USD 0.01 aggregate
  configured-price allowance and observed-usage stop conditions. Require new
  reviewed immutable manifests and durable reserve-before-egress tooling, one
  provider POST per case, no retries, halt-on-failure and independent usage/debit
  checks. Explicitly gate production cases on staging success and approval.
- **Disposition:** Addressed at planning level; the concrete manifests/harness and
  offline enforcement review are still prerequisites, not implemented artifacts.

### PE-5 — Suggestion: Make pool version and price provenance explicit

- **File/Module:** Original pool names/prices in index and R3.
- **The Issue:** `claude-haiku-or` hid the selected 4.5 model version; 'real list
  prices' could be read as exact provider costs without dates, units or fee/cache
  qualifications. Separate pools do not imply separate credit accounts.
- **Why Static Analysis Missed It:** Naming and financial evidence interpretation
  are operational semantics rather than schema errors.
- **Impact:** Future model substitution or double-counted OpenRouter credit,
  and overclaiming the precision of local accounting.
- **Recommended Fix / Revision:** Use `claude-haiku-4.5-or`, retain the other two
  proposed names and prior reviewed price values provisionally, link provenance
  and require a fresh check. Group both OpenRouter deployments under the same
  credit account when applicable. Pricing and quotas remain separate estimates.
- **Disposition:** Addressed in the table, input gates and R3/R10. No fresh price
  lookup or provider billing verification was performed by this reviewer.

### PE-6 — Suggestion: Paid status is not a data-use policy guarantee

- **File/Module:** Original paid-model contract and R2.
- **The Issue:** Excluding free offers alone does not verify retention/training
  terms for the selected account and provider route.
- **Why Static Analysis Missed It:** Account terms and operator policy are
  external facts, not properties of the model string or price.
- **Impact:** A paid model can still violate the intended production data policy.
- **Recommended Fix / Revision:** Require exact account/provider policy evidence
  before production use; keep staging prompts fixed and nonsensitive. Do not
  assume that unsupported per-request OpenRouter routing/preferences can enforce
  those controls. Inadequate policy evidence blocks enablement.
- **Disposition:** Addressed as a production input/exit gate, not asserted proven.

## Verification and limits

The review followed the repository deep-review focus on business logic, state,
trust boundaries and resource economics. Source confirms `responses` operation
support is distinct from streaming mode, translated stream failures may follow
public response start, credit is group-owned and memory-local, and most root
secret URLs are versionless. Existing operational evidence separately documents
revision overlap and the fresh-seed rollback requirement.

The existing public price-source records were inspected; no current prices,
account policies, deployment topology or vault contents were fetched. No code,
IaC, credentials, live ledgers or deployment settings were changed. No tests,
Docker build or static scan were run for this documentation-only review. Relative
file links, table structure, whitespace, budget arithmetic and the final plan
were checked. All eight plan files remain uncommitted for the user to commit.
