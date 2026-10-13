# Independent staging evidence review

Date: 2026-10-12.
Reviewed commit: `be1f2c015ae39aff47bfad7a6c05e5dbe4cd026c`.
Scope: committed staging summary, locally retained staging manifest/ledger/identity/
results, production manifest, acceptance contract and promotion prerequisites.
The two intervening infrastructure commits were inspected for scope and release
implications; this is not full implementation or Azure validation of them.

## Disposition

**Four staging cases accepted under `deployed-public-admin-v1`. Production
approval withheld pending the release prerequisites below.** No contradiction
was found in the retained case records. This closes the independent review of
staging case outcomes, not all deployment or production gates. Previous harness
findings remain closed. The [release-packet follow-up](#follow-up-supplied-release-packet-2026-10-12)
supersedes the initial release dispositions: SE-1 is partially closed, SE-2
remains partial and SE-3 is open. These do not retroactively invalidate the four
case outcomes or permit replay.

## Evidence checked

The reviewer copied the five files identified below into a temporary directory,
validated both immutable manifests and their combined allowance, and ran the
reviewed whole-prefix reconciliation and staging prerequisite validator on the
copies. Four slots are reserved with matching passed outcomes, the ledger is
not halted, and all four scoped result records are coherent. The original files
remained byte-for-byte unchanged. No production ledger/results were present.

| Case | Input / output tokens | HTTP | Recomputed local debit USD |
| --- | --- | --- | --- |
| staging-zen-nonstream | 12 / 5 | 200 | 0.00003150 |
| staging-zen-stream | 12 / 5 | 200 | 0.00003150 |
| staging-openai-nonstream | 13 / 2 | 200 | 0.00000315 |
| staging-haiku-nonstream | 13 / 5 | 200 | 0.00003800 |

All records contain successful completion, coherent usage, matched settlement,
cleared reservations, dispatch entry and no error category. Each binds the exact
manifest pool/provider/deployment/mode and evidence scope; each explicitly denies
independent upstream observation. Recorded retry configuration is 2 attempts /
30 seconds; this is configuration evidence, not an observed count of provider
POSTs. The reviewed Zen/OpenRouter paths are single-shot.

Decimal recomputation from tokens and configured prices gives **USD 0.00010415**,
or **1.0415%** of the USD 0.01 allowance. This is a local accounting debit, not
verified provider spend. The six-case conservative preflight remains USD
0.0051456. Only the two prescribed Zen production slots remain available after
all promotion gates; no new staging run or diagnostic probe is authorized.

Zen streaming passed the harness's semantic completion checks. OpenRouter router
streaming remains unverified by this run and excluded from production; these
records do not establish a causal explanation for earlier streaming failures.

### Retained artifact identity

These hashes bind this review to the local bytes inspected; they do not attest
the deployed image or replace operator release provenance. Ledger/results are
git-ignored, so commit `be1f2c0` alone contains only the summary, not these records.

| File in this plan directory | SHA-256 |
| --- | --- |
| manifest.staging.json | `edb5d9b3c0c75372bba798e9c7104372f681e52deb0d5c26c50fa1a22e2a26a6` |
| manifest.production.json | `dfe901bc65c5875868a73c4b3c86372770c7138b73765cbe6a60745ec2fd549d` |
| ledger-staging.json | `ae45f0d834b3b7bc4441093eb19874ed77ebbf6336186a561edcedec2f77d62e` |
| ledger-staging.json.identity | `9aca788944b410756911df9f6c3969e1758aee7faed0e3d22a888ceb3bac3921` |
| results-staging.json | `d0becac1337663faa64b5f31cf292f9cf3d9f050aca8037c91fbefdaf34ad58a` |

## Release findings

### SE-1 — Major: Executed infrastructure scope is outside the reviewed contract

- **File/Module:** [Evidence](evidence.md), [release contract](index.md#release-and-state-contract),
  [activities](activities.md); `infra/main.bicep`, `infra/modules/containers/router.bicep`.
- **The Issue:** The plan explicitly excludes resource/template/grant changes
  without a scoped amendment. The staging summary reports a new resource group,
  vault, identity/app, temporary secret grant and attachment to the production
  managed environment. Commits `c10c071` and `9deeb8e` add environment attachment
  and adjustable reserve settings. No corresponding amendment/review record is
  supplied in this plan; the plan still states no such changes are planned.
- **Why Static Analysis Missed It:** This is a mismatch between the approved
  operating boundary and the execution record, not a Bicep syntax defect.
- **Impact:** Staging success can be mistaken for approval to promote different
  infrastructure or reserve policy. Sharing the production managed environment
  also needs an explicit isolation/operational-impact assessment.
- **Recommended Fix:** Record and independently review the exact scope change,
  relevant template validation and deployed-effect evidence. Specify which
  changes are staging-only, what production would actually apply, and how
  existing resources/settings and account reserves are preserved. Do not rerun
  the consumed staging slots merely to repair this documentation gap.
- **Disposition:** Open release gate. No claim is made that a separate operator
  authorization never occurred; it is not established by the supplied record.

### SE-2 — Major: The tested release cannot yet be bound to production

- **File/Module:** [Evidence](evidence.md), [outputs](outputs.md),
  [exit criteria](exit-criteria.md).
- **The Issue:** The staging record names image tag `zen-openrouter-staging-4224eaa`
  but supplies no immutable digest/build binding. The retained harness results
  contain no release identity. The actual version-selection/load assertions,
  production baseline-plus-Zen diff and rollback binding evidence remain absent;
  these are existing plan prerequisites, not facts proved by inference success.
  Infrastructure secret URLs still default to versionless references except for
  the optional initial-credit version, so pinning cannot be inferred from source.
- **Why Static Analysis Missed It:** It depends on deployed release provenance
  and operator-held configuration evidence across environments.
- **Impact:** A passing staging run could be used to promote a different image,
  mixed secret versions or an altered production baseline.
- **Recommended Fix:** Supply a redacted release packet linking the staging
  revision to its image digest and tested source/build, the same intended
  production digest, exact non-secret configuration delta and validation of the
  selected coherent secret versions. Include retained rollback bindings and
  evidence that auth, Azure pools, ingress and memory/one-worker/one-replica
  posture are preserved. Keep secret values and sensitive mappings operator-held.
- **Disposition:** Open release gate. The case-record review is complete; full
  promotion review awaits this concrete packet.

## Credit seeds and remaining operator gates

No production seed values are proposed or approved by this review. Prepare a
fresh per-account allowance/cycle/remaining estimate for **every** retained
production group, including Azure and the new Zen group, after stopping and
draining all writers. Account for completed and uncertain spend and any ongoing
staging allocation on a shared account. The staging balances and four test
debits alone do not establish current production balances. A safety reserve
also does not isolate two independently funded memory ledgers.

Record the production reserve policy with the seed proposal. Usable headroom is
remaining minus inflight reservations minus
`max(flat reserve, cycle allowance * reserve percent / 100)` (floored at zero).
A seed at or below a USD 10 flat reserve cannot fund positive-cost requests.
The template defaults remain USD 10 / 5%; staging's USD 0.05 / 5% override must
not silently lower reserves for existing production accounts. Any necessary
policy change needs explicit scope review before approval.

Named production/monitoring owners, current price/account-policy checks,
quiescence and intake control, fresh pinned seeds, safe rollback and final-stream
monitoring evidence remain required by the existing plan. The staging summary's
quiescence and actual-balance assertions are operator-reported; the reviewer did
not independently query Azure, provider accounts or live admin state. A passing
harness prerequisite Boolean is not operator production authorization.

## Verification and limits

- 48 staging-harness tests passed using the repository virtual environment.
- Offline reconciliation of the actual retained evidence and independent decimal
  debit calculations passed; original artifacts were not modified.
- Review applied the repository deep-review focus to evidence trust, release
  identity, scope drift and credit ownership. No runtime changes were made.
- No live calls, secret access, resource changes, production approval or spending
  occurred. No full suite, infrastructure build/deployment, Docker or static
  scan was run for this evidence/documentation review.
- Relative documentation links, whitespace and final documentation diff checked.

## Follow-up: supplied release packet (2026-10-12)

**Staging outcomes remain accepted; production not approved.** SE-1's code-review
portion is complete under the [staging infrastructure amendment](amendment-staging-infrastructure.md).
Its actual-environment/operational evidence remains open. SE-2 remains partial;
the packet also introduces a Major unsafe production seed/reserve proposal (SE-3).

### SE-1 — Code reviewed; operational scope evidence pending

Both infrastructure commits were independently inspected and compiled; no
blocking implementation defect was found for their flat-template paths. The
amendment records their narrow staging applicability, preserves production
policy and notes the typed-adapter limitation. Shared-environment impact,
monitoring coverage and actual deployment/grant effects are still
operator-reported rather than independently established. This is retrospective
review, not a claim that the prior gate was satisfied before staging execution.

### SE-2 — Partial: candidate digest supplied, immutable deployment binding absent

The operator reports this ACR digest for the staging tag:

`sha256:8f7a000de935d560737c736a66c247df35d90b1a291f48154318f2bb3d9824fb`

The reviewer confirmed no tracked differences from `4224eaa` through `be1f2c0`
in `src/`, `Dockerfile`, `pyproject.toml`, `uv.lock`, `.dockerignore` or `docker/`.
This supports source continuity but does not prove build context, dependencies,
or which digest the tested revision ran. A current tag lookup needs a link to
the tested staging revision/build record; the reviewer did not query ACR/Azure.

The local input file has all three expected model and pricing map entries. Only
structural names/membership were inspected and reported, without exposing any
credential values. An initial display filter omitted names with decimal points;
a direct membership check corrected that reviewer error. There is no finding
that this file is missing the Zen or Haiku entries.

That file is configuration input, not a deployment receipt or a secret-version
map. Health/readiness and usable credit groups do not establish immutable secret
selection. Seven root secret URLs are versionless; only initial remaining has
an optional version. The root image expression is registry/repository plus a tag,
so the stated intention to promote by digest still needs an exact supported
update procedure and drift protection, or a separately reviewed template change.
No unsupported digest-in-tag workaround is approved here. Retain the requirement
for an actual production baseline/delta, coherent selected secret versions,
tested revision-to-digest binding and safe retained rollback bundle.

### SE-3 — Major: Proposed production seeds and reserves violate account continuity

- **File/Module:** Supplied release packet; [release contract](index.md#release-and-state-contract),
  [credit operations](../../operations/shared-resource-credit.md),
  `src/foundry_router/credit.py` and the app-wide reserve configuration.
- **The Issue:** The packet treats Zen as the only affected account and proposes
  USD 0.05 / 5% production reserves. The plan adds Zen to the existing app, whose
  memory state includes all retained Azure accounts. A restart reinitializes
  those accounts too. Reserve settings apply to the whole app, not just Zen.
- **Why Static Analysis Missed It:** This depends on the rollout's account
  ownership and the financial meaning of otherwise valid configuration values.
- **Impact:** Old Azure startup seeds could restore spent credit. Lowering the
  flat reserve could expose more credit on existing accounts. Sharing the Zen
  account between independently funded staging/production ledgers could also
  duplicate usable credit.
- **Recommended Fix:** Retain the baseline-plus-Zen target. Prepare current,
  conservative, per-account cycle/allowance/remaining seeds for all retained
  groups after draining writers; establish a disjoint staging allocation or
  controlled handoff. Preserve production reserve policy unless a separate
  reviewed amendment explicitly assesses every affected account. Never invent a
  higher balance to meet the reserve. Fresh authoritative account inputs and
  conservative local estimates remain distinct.
- **Disposition:** Open. The proposed seed/policy packet is not approved.

The reported Zen staging debit is exactly USD 0.000063 at the configured prices;
its small size is no reason to discard it. USD 9.50 of available credit is
spendable headroom, not a guard limiting spend to the USD 0.01 harness allowance.
The harness limits the two prescribed checks; it does not impose that allowance
on later production clients. OpenRouter need not be added to production, but its
exclusion does not remove the retained Azure accounts from the restart boundary.

The reviewer retains the existing-app target from the accepted plan and does not
invent human owners or appoint an unattended review session as on-call. The
operator/approver and monitoring/rollback owner must accept named responsibility
and an actual maintenance/intake-halt procedure before execution. No live action
or production approval follows from this packet review.

Verification added: both Bicep builds and root lint completed with existing
warnings, compiled contract assertions passed, 25 credit tests passed, and
configuration map membership was checked without displaying secret values.
No runtime/template implementation changes were made by the reviewer.
