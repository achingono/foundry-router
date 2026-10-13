# Roster staging execution amendment

Date: 2026-10-12. Status: **Implemented; staging deployed; execution halted at case 3.**
See [harness review closure](review-harness-e34b506.md) and the
[retained execution evidence](evidence-roster-2026-10-12.md). The requirements below
are the reviewed historical run contract. They do not authorize replay or a
new identity; further inference requires a separately reviewed bounded amendment.
See [independent review of 3bd4010](review-roster-execution-3bd4010.md). No vault
write, rollout or live dispatch is cleared until implementation and concrete
execution inputs pass the gates below. This is a staging-only amendment; it does
not enable OpenRouter production or qualify streaming.

## Exact request scope and allowance

Run ID: `staging-or-roster-2026-10-12`; environment: `staging`.
Exactly five sequential, non-streaming `responses` cases, all provider `openrouter`:

| Case ID | Pool | Deployment | USD/M input / output |
| --- | --- | --- | --- |
| `roster-luna-nonstream` | `gpt-6-luna-or` | `openai/gpt-6-luna` | 0.10 / 0.50 |
| `roster-haiku-nonstream` | `claude-haiku-5.5-or` | `anthropic/claude-haiku-5.5` | 0.10 / 0.50 |
| `roster-deepseek-nonstream` | `deepseek-v4.1-flash-or` | `deepseek/deepseek-v4.1-flash` | 0.15 / 0.60 |
| `roster-mimo-nonstream` | `mimo-v2.6-flash-or` | `xiaomi/mimo-v2.6-flash` | 0.14 / 0.28 |
| `roster-spark-nonstream` | `muse-spark-1.3-contributor-or` | `meta/muse-spark-1.3-contributor` | 0.10 / 0.20 |

Use `Reply with the word ready.`, `store: false`, `max_output_tokens: 128`, and
non-streaming mode. The existing builder may omit `stream` for this default mode;
never set it true. Preserve the existing 512-input/128-output token assumptions,
120-second whole-case deadline, 1 MiB response bound, 256 KiB frame bound and
small bounded setup/admin reads. Usage above either token assumption fails and
halts successors. No tools, images, model substitution, embeddings, retries,
direct probes, failure experiments, Azure inference or Zen inference are added.

At most five additional router inference POSTs and one OpenRouter API POST per
case, using one backend per pool and the reviewed single-shot provider path.
Preserve reserve-before-egress, conservative entry accounting, response close-on-
exit, strict completion/usage, settlement and cleanup checks; halt on first
failure, uncertain reservation or persistence mismatch. No replay of any slot.

Using the [retained catalog rates](catalog-openrouter-excerpt-2026-10-12.json),
these five cases have a conservative configured-price estimate of USD 0.00056832.
The original six-case estimate was USD 0.0051456; both specifications together
are USD **0.00571392**, within the existing **USD 0.01 combined inference allowance**.
Count the original specifications conservatively without refunding consumed
slots or resetting their state. This does not release the original production
slots or allocate another USD 0.01. Any subsequent production/re-validation scope
needs its own reviewed aggregate calculation. These are input/output estimates,
not a guaranteed provider charge cap; other charge categories need verification.
ACR build/storage and other infrastructure costs are outside this inference allowance.

## Immutable files and harness contract

- Commit `manifest.roster.json` for the exact case order, model/provider/mode,
  prices, bounds, group-policy contract and evidence scope
  `deployed-public-admin-v1`. Bind the reviewed release digest and sanitized
  configuration fingerprint, including the policy/topology assertions below.
  An unavailable final digest leaves the executable manifest/release gate open;
  offline implementation fixtures can use clearly synthetic digest values.
- Use `ledger-roster.json`, `ledger-roster.json.identity` and
  `results-roster.json` in the canonical staging directory under the existing
  stage/ledger locks. Keep all previous ledgers, identities and results unchanged.
  Missing-after-initialization state and unresolved attempts refuse. No reset.
- Update all relevant mappings and entry points, including `RUN_ENVIRONMENTS`,
  `RUN_SPECS`, `RUN_CASES`, `RUN_FILES`, the actual `_run_files` dispatcher and CLI
  validation. The current `_run_files` uses its own literal map; changing the
  module constant alone is insufficient. Only this new staging run is added.
- New-run manifest fingerprint and bounded result validation must retain and
  enforce release/configuration binding and expected/observed reserve evidence;
  current fingerprint filtering otherwise drops new metadata. Strictly validate
  this evidence on persistence, resume and acceptance. Missing, contradictory or
  changed binding must refuse before a successor dispatch. Preserve old formats
  and original run-spec bindings; do not retrofit or rewrite historical evidence.
- Keep `independent_upstream_observed=false`. Bind the supplied release metadata
  to a separately reviewed deployment record showing the tested revision/digest
  and loaded configuration. A manifest assertion is not independent observation
  of the deployed binary; the public/admin acceptance limitation remains explicit.
- Do not make the roster a production prerequisite automatically or relax the
  old predicate. A future production amendment must explicitly consume this
  run's fully reconciled evidence with the correct release scope. The current
  roster run cannot authorize either OpenRouter production or Zen re-validation.

## Concrete staging policy and topology

Use app-wide USD **10.0 / 5.0%** with exactly one override for this staged
experiment: `or-shared` = USD **0.05 / 5.0%**. `zen-staging` inherits the app-wide
pair and has no override. Preserve its backend, deployment, model and pricing
entries; do not send Zen inference. This deliberate staging policy contrast is
not a production policy change or a claim that Zen remains usable for requests.

Retain the existing two staging OpenRouter pools and Zen topology, adding the
five named pools and their one-backend memberships. All OpenRouter backends use
`or-shared` only with confirmed common account ownership. No new aliases, Azure
fallback, production credentials/topology or resource additions. Verify actual
quota/account ownership separately; pool separation does not isolate wallets.

After quiescence and a drained restart, pin fresh conservative seeds for **all**
staging groups. Review current allowance/cycle/remaining values and disjoint
staging allocation or controlled handoff; never copy a whole shared account into
multiple live memory ledgers. Do not fabricate balances to make the test pass.

Before the first inference, and with each case's bounded admin evidence:

1. Verify global USD 10 / 5% settings; `or-shared` reports source `override` and
   0.05 / 5%; `zen-staging` reports `inherited` and 10 / 5%. Check the distinct
   policies, canonical membership and exact single-backend candidate bindings.
2. Confirm zero inflight credit/reservations. Verify the current OR allocation
   has positive usable headroom under its override, but would have zero headroom
   under the USD 10 inherited floor. If this contrast cannot be established,
   halt before inference and revise/review the setup; do not dispatch a negative
   control request or alter an authoritative balance.
3. Reconcile each OR debit from public usage at the pinned rates and verify
   cleanup. Compare group identity/policy before and after; changes halt the run.
   Retain bounded structural/numeric evidence only, never raw configuration,
   credentials, prompts or output values. Inherited Zen evidence is read-only.

The original recorded staging deployment used USD 0.05 / 5% globally and could
admit OR without group overrides. A pass under those old global settings would
not prove this feature. Under the newly specified global USD 10 floor, a build
without group-reserve support cannot satisfy the policy/admission acceptance.

## Image/configuration and verification gates

Build from the reviewed group-reserve implementation (48012df or an independently
reviewed successor), record source/build provenance and final immutable digest,
and prepare the exact deployment delta and supported coherent secret-version
selection. Builds may proceed as preparation; their completion does not clear
rollout. The group reserve map is a non-secret environment/object parameter;
provider/auth/topology secrets stay vault-backed. Preserve ingress, memory state,
one worker/replica, unrelated settings and the approved staging infrastructure
boundary. Temporary grants need explicit scope and removal evidence.

Before live changes, independently review the harness diff and offline tests:
exact manifest pinning; both file-routing maps/CLI paths; five-case pass and
halt; crash/resume/no-replay; release or policy mutation/omission refusal;
wrong global floor, absent OR override or identical policies refused before
inference; changed group binding after response halts; actual new-format results
revalidate; old records remain unchanged and cannot satisfy the new run.

Operator quiescence, named execution/monitoring owners, fresh seeds, current
prices/terms, tested digest, secret bindings and the concrete staging delta must
then be reviewed and approved before vault writes, rollout or dispatch.

## Meaning of success

A reconciled 5/5 pass establishes non-streaming public/admin acceptance for the
five exact models on the tested staging release, with OR override admission and
an inherited-group diagnostic comparison. It does not establish inherited-group
inference, Zen streaming on this image, OpenRouter streaming, provider billing,
Table behavior or production readiness. The group-reserve code-review gate was
already cleared; this is deployment evidence with narrower scope.

OR-1 remains a production enforcement/qualification gate. OR-2's staging policy
is specified here, but fresh allocation and any production policy remain separate.
OR-3's staging plan is specified here; harness implementation, live execution and
evidence review remain pending, followed by a separate production-execution
amendment and all existing release/seed/owner approvals.
