# Enablement activities

## 1. Freeze the release and execution procedure

Record operator acceptance of the revised Zen-first scope and name the promotion
approver. Capture the actual environment baseline read-only; the required final
pool set is that baseline plus the approved additions, never a replacement list.
Prepare an exact redacted diff covering models, backends, prices, account/quota
membership and supported operations. Check absent collisions with aliases.
Staging adds three pools; production adds only `gpt-5.4-mini-zen`.

Pin one tested image digest containing the required adapter fixes and verify its
source/build provenance and existing CI evidence. Do not assume the currently
deployed production image contains them. Preserve unrelated deployed features
and configuration. Build/deploy work, if required, must follow normal verification
and review; an unknown or untested digest blocks staging.

Prepare environment-specific secret bundles and the exact version-selection and
rollback procedure for the existing app. Validate JSON with the target image's
configuration parser, preserving existing auth. All changed secret bindings must
resolve to the intended versions together. The root templates do not currently
pin every secret by version; verify a supported narrow configuration update and
its persistence against future deployment drift, or obtain a reviewed template
amendment before proceeding. No resources, grants or ingress rules change here.

Revalidate price provenance, paid model identities and production data-use terms.
Prepare current per-account balances and reserve a non-overlapping staging budget.
Review the concrete configuration, release, version-selection and bounded-check
harness before any staging write. Missing input leaves that gate open.

## 2. Establish maintenance and deploy staging

Use the approved intake-stop procedure without changing ingress rules. Drain all
writers and background reconciliation, confirm zero unsettled reservations, and
capture current canonical group balances. Keep admissions stopped across revision
replacement; verify a single serving worker/revision before resuming. If intake
cannot be stopped or unresolved charges remain, halt for an operator decision.

Prepare and pin a fresh conservative initial-credit version for **all** retained
accounts on each restart; do not replenish used allowance. Recheck prior-version
rollback availability and image compatibility. Apply only the reviewed staging
bundle/image, then verify liveness, readiness, baseline preservation, the three
new pool memberships, exact prices, unique account totals and auth separation.
Readiness alone is not provider or inference validation. Keep staging limited to
the operator-controlled test client; OpenRouter streaming is not tested here.

## 3. Run the bounded staging checks

Before dispatch, commit immutable manifests and allocate new canonical durable
run identities and files distinct from all historical harness/probe ledgers.
Review the harness that enforces the following contract; this plan does not
assume those new identities or tools already exist. Transport/client/router retry
behavior must be checked to ensure each case can issue at most one provider POST,
without changing existing production retry policy. Unproven enforcement blocks
inference. Never reset a completed, failed or unresolved slot.

| Order | Case | Target | Mode |
| --- | --- | --- | --- |
| 1 | Staging Zen nonstream | `gpt-5.4-mini-zen` | Nonstreaming |
| 2 | Staging Zen stream | `gpt-5.4-mini-zen` | Streaming |
| 3 | Staging OpenAI nonstream | `gpt-4o-mini-or` | Nonstreaming |
| 4 | Staging Haiku nonstream | `claude-haiku-4.5-or` | Nonstreaming |
| 5 | Production Zen nonstream, only after promotion approval | `gpt-5.4-mini-zen` | Nonstreaming |
| 6 | Production Zen stream | `gpt-5.4-mini-zen` | Streaming |

At most six provider POSTs across this phase; no automatic retry, model
substitution, direct diagnostic probe or request to a pre-existing Azure pool.
Use the fixed nonsensitive input `Reply with the word ready.`, `store: false`,
`max_output_tokens: 128`, a 120-second whole-request deadline, 1 MiB response
limit and 256 KiB SSE frame limit. Do not set unsupported provider-specific
fields. Use 512 input tokens and 128 output tokens per case as conservative
preflight accounting assumptions; unexpected observed usage above either bound
halts successors. The six-case configured-price estimate must fit a USD 0.01
aggregate test allowance before dispatch. This is an estimated allowance, not a
guaranteed provider billing ceiling; enforce an account-side cap where available.
Price/charge-policy changes require the budget calculation to be re-reviewed.

Durably reserve before egress, retain dispatch intent through exceptions, validate
and atomically persist each redacted outcome before the next case, and halt the
whole sequence on failure, missing evidence, state mismatch or write failure.
Resume only verified completed state; reserved-without-outcome blocks dispatch.
No production case runs before all staging cases pass and the operator approves
promotion. Existing historical runs remain closed.

For each case require public/provider success, completion and valid usage;
compare independent upstream observation where supported with public usage and
canonical group debit at configured prices, and verify zero retained
reservations/inflight credit. If deployed observation cannot support that proof,
record the limitation and leave the gate open rather than calling HTTP 200 a pass.
Streaming additionally requires complete frames, terminal `response.completed`
usage, clean EOF and no failure event. Record metadata/counts only, never bodies,
prompts, output values or credentials. Verify settlement while unrelated account
traffic is stopped; otherwise attribution is not proved.

## 4. Promote Zen only

Review staging results and explicit operator production approval. Promote the
same tested image digest and Zen provider/model/pricing delta into the production
baseline using its own auth, provider credentials and account seed. OpenRouter
models/backends/aliases must be absent from production. Recheck production
provider credential validity and account policy; staging keys need not be the
same and cannot prove production credential validity.

Repeat maintenance, drain, fresh balance seed and version-selection checks for
all production groups. Keep existing ingress, auth, pools, aliases and other
settings unchanged. Verify readiness, exact baseline-plus-Zen catalog and group
membership, one worker/replica and the intended active revision. Run only cases
5–6, then release normal intake after all checks and monitoring pass.

Before normal intake, verify the existing monitoring path receives per-model
final request outcomes and unique credit-group balances. Validate alert/query
behavior with synthetic monitoring fixtures, not additional paid calls: HTTP
200 with a failed/incomplete stream must be actionable. Check terminal usage,
failed/missing completion, retained reservations and unexpectedly high local
debits, alongside HTTP 5xx. Any failed validation case blocks release; the named
operator handles an observed production terminal failure or stuck reservation
without waiting for an unproven aggregate error-rate threshold. If monitoring
requires new infrastructure, stop for an amendment.

## 5. Failure and rollback

Halt further tests and normal admissions on any failed gate. Capture current
state and inspect; no automatic restart or rollback. The approved rollback
procedure restores the retained image/topology/auth bundle, but uses fresh
conservative balances reflecting all completed and uncertain spend. Never reuse
old initial-credit versions or reactivate stale memory state. Quiesce all writers
and verify the target's configuration/seed compatibility before replacement.
If safe balances or drain cannot be established, keep the change halted and
escalate to the operator; do not manufacture zero spend or reset budgets.

Rollback verification is read-only health/readiness/catalog/auth/group checks;
additional inference or a second rollout attempt requires a reviewed budget and
new identities. Remove only temporary permissions explicitly granted for this
execution, if any. Record deployment status and remaining gates without claiming
production inference, provider billing or Table/replica behavior not established.
