# Production enablement for Zen/OpenRouter backends

**Staging case validation passed; production planned.** Independent plan review
is recorded in [review.md](review.md).
The draft has been revised at planning level; no staging or production change,
secret provisioning, image rollout or live dispatch is authorized by this record.
Execution prerequisites and operator approvals remain open. The
[final harness review](review-staging-harness-9a763c7.md#follow-up-review-of-82c7d09)
closes all seven Majors and the Suggestion; the independent harness review gate
is cleared for the six committed cases under the
[narrowed deployment-acceptance contract](amendment-black-box-acceptance.md).
This does not clear the separate staging/production execution gates or establish
independent provider/billing evidence.

The [staging evidence review](review-staging-evidence-be1f2c0.md) accepts all four
case records under that contract. Production remains blocked on the recorded
remaining infrastructure operational evidence and immutable release binding,
plus fresh all-account seeds and the existing operator gates. The group reserve
design is [reviewed for implementation](review-group-reserves-df5396c.md);
the [implementation follow-up](review-group-reserves-f891d06.md#follow-up-review-of-48012df)
closes GI-1/GI-2 and clears independent implementation review.
New-release validation remains pending. The release contract below
remains the reviewed baseline; staging deviations are recorded as SE-1, not
implicitly approved by the case pass.

## Companion documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risk register](risk-register.md)
- [Evidence](evidence.md)
- [Independent review](review.md)
- [Independent staging evidence review](review-staging-evidence-be1f2c0.md)
- [Independent staging harness review](review-staging-harness-9a763c7.md)
- [Staging infrastructure amendment and review](amendment-staging-infrastructure.md)
- [Per-group reserve policy amendment (reviewed)](amendment-per-backend-reserves.md)
- [OpenRouter production roster amendment (draft)](amendment-openrouter-roster.md)
- [Independent group reserve plan review](review-group-reserves-df5396c.md)
- [Independent group reserve implementation review](review-group-reserves-f891d06.md)
- [Scoped black-box acceptance amendment](amendment-black-box-acceptance.md)

## Decision and rollout scope

Proceed with a **Zen-first production rollout**. Keep OpenRouter absent from
production model, backend and alias configuration for this phase. Validate its
paid nonstreaming paths only in operator-controlled staging. Client guidance
alone cannot enforce a nonstreaming-only production pool: the router has no
per-pool streaming disable or per-client model ACL. OpenRouter production needs
a separately reviewed amendment with either an enforced restriction before
provider admission or successful end-to-end streaming evidence and an accepted
operating policy. This plan accepts neither a silent partial result nor a
known failing production stream.

Existing evidence establishes Zen nonstreaming/streaming success and OpenRouter
nonstreaming success on the exact tested models. OpenRouter router streams
failed with public/provider HTTP 200 and missing terminal usage. Later direct
provider streams were clean; those separate requests neither validate router
streaming nor prove the cause of earlier failures. A post-header failure may
leave partial events and a sanitized failure event under HTTP 200. Internal
request metrics can record 502 independently of the public status. Monitoring
must check final stream outcomes, not only HTTP 5xx. See the
[live evidence](../zen-openrouter-live-verification/evidence.md).

## Pools, prices and account ownership

| Logical pool | Provider / exact deployment | Configured USD/M input / output | This phase |
| --- | --- | --- | --- |
| `gpt-5.4-mini-zen` | `opencode_zen` / `gpt-5.4-mini` | 0.75 / 4.50 | Staging, then production after gates |
| `gpt-4o-mini-or` | `openrouter` / `openai/gpt-4o-mini` | 0.15 / 0.60 | Staging nonstreaming only |
| `claude-haiku-4.5-or` | `openrouter` / `anthropic/claude-haiku-4.5` | 1.00 / 5.00 | Staging nonstreaming only |

These retain the [reviewed list-price inputs](../zen-openrouter-live-verification/amendment-paid-models.md).
They are provisional configured estimates, not authoritative balances or
measured provider charges. Before provisioning, recheck each exact paid model,
currency, units, source date, cache/reasoning accounting and applicable fees;
record discrepancies and re-review changed prices/budget. Synthetic $1000 test
prices and free/training-data-bearing offers are excluded. Paid status alone
does not establish acceptable retention/training terms: account/provider policy
must be verified before production use. Never infer compliance from the price.

Each pool has one explicit backend and only `responses` support, with no Azure
fallback or new aliases. Preserve every existing pool, alias, membership, weight
and price. Separate logical pools prevent cross-pool selection; they do not
isolate shared account credit, provider outages, or caller access. Configure one
credit group per actual billed account: both OpenRouter backends share a group
when they spend the same account; Zen has its own account group. Configure each
group's cycle, allowance and conservative remaining estimate once. Quota groups
remain independent and reflect documented shared limits, never guessed capacity.

## Release and state contract

- Keep memory state, one worker and one replica, existing ingress, identities,
  registry, resources and unrelated settings. No resource additions are planned
  for production. The [group reserve amendment](amendment-per-backend-reserves.md)
  permits the narrowly scoped template/configuration work for local implementation;
  it does not clear deployment or the new live validation gate. The retrospective
  [staging infrastructure amendment](amendment-staging-infrastructure.md) records
  the staging exception; it does not approve new production resources or reserve
  changes. Review any further scope change first.
- Promote the tested image digest and reviewed provider configuration delta.
  Staging and production use separate environment bundles, auth and state seeds;
  do not promote an entire staging topology or its balances into production.
  Preserve existing production client/admin keys; credential rotation is outside
  this phase. New staging auth is generated only if absent and kept disjoint.
- Resolve explicit versioned Key Vault references for every changed secret as a
  coherent bundle, and retain the previous topology/image bundle. Existing root
  templates normally use versionless references except the optional initial-credit
  version. Merely retaining old versions does not select them for rollback.
  Prove a supported, reviewable version-selection procedure before staging;
  if that requires a template change, stop for a scoped amendment. Keep actual
  vault/resource/version mappings in operator-held storage, not this plan.
- Before **every** memory restart, promotion or rollback, stop admissions by an
  approved operational procedure, drain all writers/background work, confirm no
  unsettled reservations, and capture conservative current balances for all
  groups, including existing Azure accounts. Pin a fresh initial-credit version.
  Single revision/maxReplicas=1 alone does not rule out rollout overlap.
  Unprovable quiescence or unresolved accounting blocks rollout. Do not add or
  change ingress restrictions under this plan.
- Rollback restores the previous image/topology/auth bindings with a **fresh**
  reviewed balance seed, never an old remaining-credit snapshot or stale memory
  revision. On failure, halt admissions and inspect; do not automatically restart
  or roll back. See [shared-credit operations](../../operations/shared-resource-credit.md)
  and the [deployment contract](../../../infra/README.md).

## Scope limits

The [activities](activities.md) define six maximum inference checks and the
prerequisites for staging and production. OpenRouter production, free models,
embeddings, client migration, new alias mappings, billing reconciliation changes,
Table cut-over, added replicas/workers and provider failure/admission experiments
are outside this phase. Any further probe or replay needs a reviewed amendment.
