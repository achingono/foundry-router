# Independent Zen/OpenRouter live-verification plan review

Date: 2026-10-11.

Scope: all seven original plan documents, relevant canonical API/configuration
and operations documentation, Zen/OpenRouter implementation evidence, forwarding
and admin code, provider integration tests, and existing Google verification
harnesses. The original review was performed in this session at the user's
request before editing the plan. The user then requested revisions and this
record. Finding dispositions were checked by the same reviewer; this is not a
claim of a second independent model or review session.

## Original findings and disposition

### PR-1 — Major: Record dispatch intent before sending each request

- **Location:** [Activities](activities.md), originally step 4.
- **Issue:** Stage outcomes were recorded after execution, without a durable
  dispatch ledger or restart contract. A crash after upstream acceptance could
  leave neither an outcome nor a halt record and allow repeated generation.
- **Required correction:** Fixed case IDs, exclusive execution, durable intent
  before egress, validated per-case results and refusal to replay uncertain
  dispatches. Require non-streaming success before the streaming case.
- **Disposition:** Addressed at planning level in the contract, activities,
  inputs, exit criteria and risks R3/R4. Five IDs bind to a fixed manifest;
  intent consumes a conservative slot before egress. Missing/corrupt/mismatched
  state and failed writes block progress. Persisted passes are skipped; uncertain
  or failed cases stop the run. Offline crash/resume and concurrency tests remain
  required before execution.

### PR-2 — Major: Define independent upstream evidence capture

- **Location:** [Contract](index.md), item 3, and [activities](activities.md),
  originally step 5.
- **Issue:** Public responses/admin diagnostics cannot establish provider status
  or independently verify usage mapping. Upstream authentication failures become
  public 502; public usage and settlement could agree while sharing a mapping
  defect. Admin status has no per-request upstream usage record.
- **Required correction:** A bounded, redacted observer before translation,
  independent usage parsing, and comparisons with public results and per-request
  credit deltas. Existing Google tooling is a precedent, not a ready Zen/OpenRouter
  runner.
- **Disposition:** Addressed at planning level in activities and exit criteria.
  The planned harness observes provider status/usage independently, verifies SSE
  completion and embeddings results, and reconciles unrounded canonical
  credit-group deltas. It has explicit time/byte bounds and redaction checks.
  Harness implementation and review remain pending.

### PR-3 — Major: Narrow pre-dispatch credential guarantees

- **Location:** [Contract](index.md), originally item 2.
- **Issue:** The plan promised rejection of any wrong key before dispatch.
  Local readiness cannot establish the validity of a populated upstream key.
- **Required correction:** Limit local refusal to detectable configuration,
  retrieval and client/admin authentication failures. Count upstream 401/403 as
  dispatched attempts and halt without cycling credentials.
- **Disposition:** Addressed in the contract, activities, exit criteria and
  risks R1/R8. Provider authentication remains unverified until an actual request;
  no additional authentication probe is included in the budget.

### PR-4 — Suggestion: Align the dispatch cap with the case matrix

- **Location:** [Contract](index.md), originally item 1.
- **Issue:** Two Responses pairs plus one embeddings call total five requests,
  while the plan allowed six without defining the extra case.
- **Disposition:** Addressed throughout the plan: five fixed cases, no sixth
  probe or retry slot. Embeddings uses two short inputs in one request so order
  can be checked without adding a dispatch.

These are contextual planning/verification findings, not static-analysis findings.
No SonarQube scan or implementation deep review was performed in this review.

## Revised-plan disposition

All three Major findings and the Suggestion are addressed at the planning level;
no unresolved Critical or Major plan findings remain from this review. The
revised plan is cleared for verification-harness implementation. This clearance
is not live-execution readiness: harness implementation, offline tests, applicable
repository verification, implementation review and operator inputs remain pending
in the [exit criteria](exit-criteria.md). No upstream compatibility, billing or
production readiness is established.

## Verification scope

- Checked relative Markdown links in all eight plan documents and whitespace
  with `git diff --check`; reviewed the final diff for unsupported claims/secrets.
- No runtime code, infrastructure or production configuration changed; no live
  requests sent and no credentials retrieved.
- Runtime tests, coverage, lint/type checks and Docker build were not run for
  this documentation-only revision. Harness implementation must satisfy its
  separate verification gates before live use.
