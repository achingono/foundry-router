# Independent review: proposed OpenRouter roster

Date: 2026-10-12.
Reviewed commit: `57bee77f3d919e090150d362a72991d6309dfb09`.
Scope: both changed documents, existing production/streaming restrictions,
reserve defaults, model/operation configuration and immutable validation harness.

## Disposition

**Changes required; roster amendment gate not cleared.** Three Major planning
findings remain. Local design/configuration preparation may continue, but this
record does not clear vault writes, staging rollout, paid validation or OpenRouter
production. The existing Zen-first contract stays in force. Group-reserve
implementation clearance and original staging outcomes are not reopened.

The five candidates are operator-reported catalog entries, not independently
qualified router backends. Listing in a catalog does not establish account/provider
availability, compatibility of translated responses, acceptable data-use terms or
streaming behavior. This review neither declares any proposed ID invalid nor
confirms it exists.

## OR-1 — Major: Non-streaming production restriction has no enforcement

- **File/Module:** Roster amendment configuration contract;
  `src/foundry_router/config/__init__.py` (`BackendConfig.supported_operations`),
  `src/foundry_router/api/routes/openai.py:309` and the existing rollout decision.
- **The Issue:** The draft adds five OpenRouter production pools while saying
  streaming remains excluded with no code/configuration enforcement design.
  `responses` includes both modes; a caller-supplied `stream: true` selects the
  stream path. Single-backend pools and client guidance do not disable it.
  “Mocked-only” also misstates the prior evidence: earlier router streams were
  tried live and failed acceptance; separate direct-provider results did not
  qualify router streaming or prove the cause of those failures.
- **Why Static Analysis Missed It:** The gap is between the operational promise
  and allowed API behavior, not a syntactic configuration error.
- **Impact:** Any authorized caller able to select a new pool could reach an
  unqualified stream path in production, despite a non-stream-only validation run.
- **Required Revision:** Keep candidates staging-only, or design and independently
  review a restriction enforced before routing/provider admission (including
  alias resolution), with zero-dispatch negative tests and unchanged Azure/Zen
  streaming. Alternatively qualify streaming under a separate bounded protocol
  and explicitly revise the operating policy. A roster/config-only amendment
  cannot establish a production non-streaming restriction.
- **Disposition:** Open. Do not silently reinterpret the existing exclusion as
  permission for unrestricted OpenRouter production.

## OR-2 — Major: Proposed shared account has no usable production headroom

- **File/Module:** Roster “no reserve-map change” and runway statements;
  group-reserve amendment and `src/foundry_router/credit.py` reserve calculation.
- **The Issue:** The reviewed intended production override targets Zen only.
  An absent `or-shared` entry inherits USD 10 / 5%. With the reported USD 4.83
  remaining estimate, usable headroom is zero under the USD 10 flat reserve,
  regardless of whether the percentage reserve is even larger. Staging's
  lower global settings do not prove production readiness.
- **Why Static Analysis Missed It:** All values can be valid while their combined
  admission policy makes every positive-cost request ineligible.
- **Impact:** Five configured production pools can remain protected and reject
  inference. Copying the staging-wide reserve to work around this would alter
  retained accounts and violate the reviewed group-specific policy boundary.
- **Required Revision:** Specify an independently reviewed `or-shared` group
  policy and fresh conservative balance/allowance/cycle inputs, or establish real
  headroom under the retained defaults. Do not invent or increase a seed to clear
  the reserve. Confirm all deployments use the same actual billed account,
  define independent quota ownership, and reserve a disjoint staging allocation
  or perform a controlled handoff. Fresh seeds still cover every retained account.
- **Disposition:** Open. The draft's balance and request-count runway are not
  current authoritative funds or a reviewed production allocation.

## OR-3 — Major: A new identity alone does not define executable validation

- **File/Module:** Roster acceptance;
  `scripts/quality/staging_validation.py` fixed run/spec/file maps and production
  prerequisite; existing six-case and group-reserve execution gates.
- **The Issue:** The harness permits only the old four staging/two Zen production
  cases. It does not accept these five IDs or an arbitrary new run string. The
  roster gives no replacement immutable specs, exact call matrix/budget,
  production canary contract or predicate tying promotion to new-release staging
  evidence. Previous passes predate the group-reserve image and these deployments.
- **Why Static Analysis Missed It:** This is evidence/authorization continuity
  across a release and expanded roster, not schema correctness of the old runner.
- **Impact:** Renaming files or supplying a new identity either refuses execution
  or encourages an unreviewed harness change; trusting the old staging predicate
  would qualify untested production models or a different release.
- **Required Revision:** Prepare a concrete execution amendment and reviewed
  harness/manifests before configuration rollout/dispatch. Bind exact retained
  and added topology, model IDs/prices, modes, release/configuration scope,
  maximum calls, input/output assumptions, time/byte/frame limits, allowance,
  durable files, reservation/no-replay behavior and stop rules. Define production
  checks/approval separately and consume the new accepted staging evidence.
  Integrate the still-pending shared-instance reserve-policy validation; neither
  reuse old slots nor add Azure inference or diagnostic probes implicitly.
- **Disposition:** Open. No new live allowance is established by this review.

## OR-4 — Suggestion / evidence prerequisite: Separate sources from qualification

The draft names a public catalog endpoint/date but retains no excerpt or exact
capture time. Volume, speed, quality and “open” claims cite only a session date;
those facts are not established by catalog membership. Preserve a bounded public
excerpt of the five entries with raw pricing units, capture time and source;
verify relevant request/cache/reasoning charges, parameter support and account/
provider retention/training terms. Link distinct sources for any rationale kept.
Clarify whether the claimed 5.5% fee applies to funding, requests or another
charge before applying it to cost/runway calculations. No inference capability
or privacy property follows solely from paid status or the absence of `:free`.

The reviewer attempted a credential-free bounded GET of the public catalog.
The restricted environment failed DNS resolution. The escalated read was **not
executed**: automatic approval review failed because its own API deployment
returned HTTP 404. The tool explicitly called this a review-service failure,
not a determination that the catalog request was unsafe. No alternate route or
paid request was used. A public evidence excerpt was requested from the operator;
independent catalog verification remains unavailable for this review.

## Provisional arithmetic (not verified prices or a spending authorization)

| Candidate | Draft USD/M input / output | 2,000 input / 1,000 output USD | 512 input / 128 output USD |
| --- | --- | --- | --- |
| Luna | 0.10 / 0.50 | 0.00070000 | 0.00011520 |
| Haiku 5.5 | 0.10 / 0.50 | 0.00070000 | 0.00011520 |
| DeepSeek V4.1 Flash | 0.15 / 0.60 | 0.00090000 | 0.00015360 |
| MiMo V2.6 Flash | 0.14 / 0.28 | 0.00056000 | 0.00010752 |
| Muse Spark 1.3 Contributor | 0.10 / 0.20 | 0.00040000 | 0.00007680 |

Five hypothetical staging calls at the prior token assumptions total USD
0.00056832 using only the listed input/output prices. The arithmetic does not
include unverified fees/other token categories or allocate a new budget. Wallet
balance divided by nominal request cost is not admission headroom or guaranteed
request runway; reserve policy, other writers and actual token use also matter.

## Verification and limits

Inspected the plan, group reserve and model/operation boundaries, actual stream
selection path and fixed harness specs; recomputed pricing arithmetic with
Decimal. No tests were needed or run for this documentation-only review. No
credential files, private account data or historical ledgers were read. No
configuration writes, deployments or paid inference occurred. Documentation
links/anchors, whitespace and final diff were checked. No production approval.

## Evidence follow-up: efd13ab

Date: 2026-10-12.
Reviewed commit: `efd13ab452cc7d84bb20cd169333e283e644f4c7`.
Scope: both changed files (the narrowly scoped gitignore exception and public
catalog excerpt), supplied source links and independent decimal reconciliation.

**Retained-catalog/source-location gap addressed; OR-1/OR-2/OR-3 remain open.**
This follow-up supersedes OR-4's statement that no excerpt/time or source links
were supplied. It does not independently authenticate the remote API response,
qualify inference, verify account/provider policy or clear any staging write.
No new model/price contradiction was found in the supplied artifact.

### Artifact checks

[Catalog excerpt](catalog-openrouter-excerpt-2026-10-12.json), operator-recorded
capture `2026-10-12T13:48:27Z` from
[OpenRouter models API](https://openrouter.ai/api/v1/models).
SHA-256 of reviewed committed bytes:
`7a22189e702f8594b6ee05f4d3c1d3a04d70a6cc21c499dba5ea105865533f2b`.

The working file exactly matched `git show efd13ab:<path>`. Checked duplicate-key
absence, expected metadata/row fields, exactly five unique expected IDs, positive
integer context lengths and finite positive decimal prompt/completion prices.
Multiplying every per-token rate by 1,000,000 exactly reproduces the amendment's
five USD/M price pairs. The 512-input/128-output five-case input/output estimate
remains **USD 0.00056832**. No artifact bytes were changed.

This is a selected operator-supplied excerpt, not the full API response. It omits
other possible pricing fields, supported parameters/provider routing and account
policy. Omitted charges or restrictions must not be inferred absent. Context
lengths are recorded catalog values, not tested router or provider limits.

### Supplied sources and their scope

The following URLs and claim descriptions were supplied by the operator. They
are now retained for audit; this reviewer did not fetch or validate their contents.

| Subject | Supplied sources | Scope / limitation |
| --- | --- | --- |
| IDs, pricing and context | [API](https://openrouter.ai/api/v1/models), [catalog UI](https://openrouter.ai/models) | Captured subset checked locally as above; recheck at execution time |
| Weekly volume | [OpenRouter rankings](https://openrouter.ai/rankings), [TeamDay article](https://www.teamday.ai/blog/top-ai-models-openrouter-2026) | Operator attributes DeepSeek 25.6T, MiMo 9.63T, Luna 6.18T, Muse 1.43T and Haiku 1.09T to a Sept 28–Oct 4 window / Oct 5 check, with Haiku described as new-week; do not combine differing windows or infer quality from volume |
| Haiku speed | [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models), [17nas mirror](https://17nas.com/llm-leaderboard.php?lang=en-US) | Operator reports 240 tokens/s in an Oct 12 snapshot; methodology, provider, sample and comparability not reviewed |
| Funding fee | [OpenRouter pricing](https://openrouter.ai/pricing), [Tokenplan comparison](https://tokenplan.vip/en/openrouter-token-plan/openrouter-pricing-comparison) | Operator clarifies 5.5% with USD 0.80 minimum is a top-up fee; current primary-source terms and applicability not independently checked |
| Inference markup | [Ofox article](https://ofox.ai/blog/openrouter-pricing-hidden-markup-breakdown-2026/) | Operator cites pass-through pricing; a secondary article is not account-specific billing evidence |
| Benchmark cross-checks | [Arena](https://arena.ai/leaderboard), [Rank.ai](https://www.rank.ai/llm-leaderboard) | Source locations supplied; exact model/version, task and score evidence not reviewed |

The fee clarification removes the ambiguity between funding and per-token pricing.
Do not multiply configured input/output rates by 1.055 on that basis or subtract
a funding fee again from an already credited wallet balance. Funding cost, local
usage debit and actual account balance remain distinct. The claimed 5,000-request
runway is not restored: usable headroom and shared allocation still fail OR-2's
current production contract, and token/fee assumptions do not guarantee usage.

### Disposition and verification limits

The catalog retention/units/source-location portion of OR-4 is satisfied. Optional
volume/speed/quality rationale remains outside acceptance until its evidence is
actually assessed; it is not needed to implement the router contract. Current
paid-model/provider terms, other charge categories and day-of provenance remain
execution inputs, not new findings against this artifact.

OR-1 (enforced non-streaming), OR-2 (shared-account reserve/allocation) and OR-3
(bounded new-release harness/manifests/promotion) are unchanged. Roster review and
staging-write gates remain uncleared. No network read was retried after the prior
automatic-review service failure, and no bypass was attempted. Only local artifact
and arithmetic checks were run; no code tests, secrets, account reads, paid calls
or configuration changes. Documentation links/anchors and whitespace checked.
