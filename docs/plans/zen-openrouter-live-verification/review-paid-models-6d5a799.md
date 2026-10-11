# Independent review of paid-models commit 6d5a799

Date: 2026-10-11.
Reviewed commit: `6d5a799719b40c4deb22d71516a4e426737c5954`.

The reviewing assistant independently reviewed the completed implementation in
this session at the user's explicit request, before making the documentation edits. Scope: all eleven
changed files, the paid-models amendment, existing run/manifest/ledger validation,
transport observation and settlement integration, related harness tests, and
canonical configuration/security/routing requirements. This is a review of the
specified commit, not a new live execution or a retrospective approval of Runs
A/B. Documented operator model/price choices were treated as the intended scope;
this review did not retrieve credentials or independently verify provider prices
or billing.

## Disposition

**Changes required before paid-model live execution.** One Major finding and one
Suggestion remain open. No Critical findings were identified. Prior harness
review clearances remain scoped to their reviewed revisions; they do not clear
this new amendment's model/price authorization boundary.

### PM-1 — Major: Paid run identities do not bind approved models and prices

- **File/Module:** [New run allowlist](../../../scripts/quality/zen_openrouter_live_budget.py),
  lines 52–54 at the reviewed commit, interacting with `validate_manifest`
  (lines 204–234), stage CLI manifest loading, and the transport observer.
- **The Issue:** The amendment authorizes three exact model/price pairs, but the
  new entries bind only a run ID to case names. Existing validation accepts any
  nonblank active model and any positive finite prices. The CLI accepts an
  arbitrary manifest path, and both router configuration and the observer's
  expected deployment are derived from that same manifest. The fingerprint
  prevents changing a run after results exist; it does not enforce the reviewed
  model/price choices before the first request. Tests assert the committed
  manifests' contents but do not reject changed copies at execution time.
- **Why Static Analysis Missed It:** The types and local comparisons are valid;
  the defect is the missing relationship between reviewed authorization and
  first-run configuration. No static scan was run as part of this review.
- **Impact:** A mistaken or substituted manifest can consume either paid run's
  budget on a different model and record settlement at unapproved prices. The
  OpenAI and Anthropic run IDs can even target the same model. Canonical files
  still prevent replay within each run, but do not constrain model selection to
  the amendment's approved scope.
- **Recommended Fix:** Bind each paid run to an immutable reviewed model/price
  specification (or validated canonical manifest) before ledger initialization
  and egress. Compare the active model, inactive fields, prices and allowed case
  scope against it. Keep the existing resume fingerprint and ledger checks.
  Add negative execution tests changing each model and each price independently;
  assert refusal with zero transport calls and no consumed dispatch slot.
- **Offline reproduction:** For each of the three committed paid manifests, a
  temporary copy substituted `unapproved-model` (Zen) or `unapproved/model`
  (OpenRouter), and input/output prices `2.0`/`3.0`. `validate_manifest` accepted
  all three. `execute_stage` with temporary canonical run files and a recording
  fake transport dispatched both cases to the substituted model and returned
  two passes for each run. Six fake dispatches total; no live network traffic.
- **Status:** Open; no implementation fix made during this review.

### PM-2 — Suggestion: Distinguish list-price estimates from provider spend

- **File/Module:** [Paid-models amendment](amendment-paid-models.md), lines 16–29
  at the reviewed commit, and its committed price manifests.
- **The Issue:** The amendment calls the values real list prices and states
  that total real spend is a fraction of a cent, without recording price sources,
  an observation date, or a provider billing measurement. These fixtures and the
  harness establish configured local estimates, not actual charges. This review
  found no evidence that the numeric rates are wrong; their provenance and the
  spend wording are the concern.
- **Why Static Analysis Missed It:** This is a documentation/evidence distinction,
  not a code type or arithmetic error.
- **Impact:** Readers can mistake an estimated verification cost for a verified
  bill or a guaranteed spend ceiling, contrary to the plan's billing non-claims.
- **Recommended Fix:** Cite provider/model pricing sources with the date checked.
  Describe any amount as an estimated local cost at the selected rates and
  stated token assumptions; retain the explicit unverified provider-billing gate.
- **Status:** Open; no provider pricing lookup or billing verification performed.

## Verification and limits

- All 103 focused harness checks passed through the repository virtual
  environment (`tests/unit/test_zen_openrouter_live_budget.py`,
  `tests/unit/test_zen_openrouter_live_runtime.py`, and
  `tests/unit/test_zen_openrouter_live_stage.py`).
- Additional temporary, offline mutation probes confirmed PM-1 for all three
  new run IDs. Existing live ledgers/results and historical captures were not
  read, modified, recreated or reset.
- Reviewed canonical filename isolation, shared stage locking, inherited
  reserve-before-egress/halt behavior and real-rate mocked settlement tests.
  Those checks do not address first-dispatch model/price authorization.
- `scripts/quality/sonarqube-scan.sh` is absent. This review applies the contextual
  categories in the repository deep-review prompt without claiming a preceding
  SonarQube scan. Full-suite coverage, lint/type checks and Docker build were not
  rerun for this review-only documentation change.
- Relative links in the review and plan were checked, along with whitespace and
  the final documentation diff. No runtime code, tests, configuration, credentials
  or production resources were changed; no live requests were sent.
