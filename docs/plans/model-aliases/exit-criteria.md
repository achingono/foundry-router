# Model Alias Exit Criteria

## Plan Gate

- [x] Baseline/docs/source/tests inspected and templates copied into a new plan folder.
- [x] Observed review name and user-requested approve name explicitly distinguished.
- [x] Independent review complete and findings addressed.
- [x] Relative links, whitespace and final secret/status claims checked.

## Code Gate

- [x] Empty configuration preserves behavior; arbitrary explicit aliases resolve exactly once.
- [x] Bounds, types, duplicate keys, whitespace/control characters, collisions, self references,
  chains/cycles, missing targets and alias price overrides fail validation predictably.
- [x] Both Codex names and unrelated custom aliases work only when configured; unknown names
  retain 404 with no reservation/egress; targets always identify canonical pools.
- [x] Responses and embeddings use canonical routing/accounting and selected physical deployment
  mappings; every non-model request field is identical to the caller's parsed value.
- [x] JSON/SSE response bodies are unchanged; usage settlement uses canonical prices even when
  provider response model differs, streaming fails, or mapping changes for a later request.
- [x] Aliased/direct concurrent requests share target capacity with distinct server request IDs;
  no duplicated prices, accounts, quotas, balances or finalization.
- [x] Health, retry/failover, missing-pricing/credit, free/metered policy, cancellation and cleanup
  match direct-target behavior; aliases cannot introduce broader backend eligibility.
- [x] Authenticated `/models` includes aliases once; admin mapping is separate; readiness remains
  canonical; requested/resolved logs are redacted and metrics count once under canonical identity.
- [x] Optional Bicep configuration propagates through root and typed paths with empty defaults;
  no new resources/deployments; valid/invalid map examples and rendered env checks pass.
- [ ] Focused/full tests, at least 80% coverage, lint/format/type, required CI/Azurite, Docker
  smoke/build and applicable Bicep/template checks pass with actual results recorded.
  (Local: 468 passed, 89.29% coverage, ruff/mypy clean, Bicep builds pass.
  Subsequent ACR: 482 passed, 90.38% coverage, Azurite and Docker/image smoke passed.
  GitHub CI remains separately unpassed; see production rollout evidence.)
- [x] Conditional Sonar scan and independent deep review completed; actionable findings addressed.
  (Sonar script absent; deep-review themes applied with no Critical/Major findings.)
- [x] Canonical docs/traceability and operations updated; relative links and secret/status diff pass.

## Separate Live Gates

- [x] Actual target/configuration revalidated and finite validation limits applied.
- [x] Six direct/aliased normal and streaming inference cases passed with canonical usage metrics and catalog/admin identities.
- [x] Actual Codex approval client produced expected synthetic allow, deny and injected-error outcomes with built-in policy preserved.
- [x] Parameter/schema/model-equivalence limitations are explicit; no fabricated approval or replay of a denied real action.
- [x] Production retained memory/one and preserved ingress unchanged under explicit user direction; sensitive content was not retained.

See [production rollout evidence](../model-aliases-production/evidence.md) for exact
scope and initial harness failures. The unfenced memory handoff does not establish
exact credit continuity, and unrelated live traffic limits total-debit attribution.
The earlier failed push was not retried.

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Plan author | Codex | Prepared | Documentation only |
| Independent reviewer | `review_model_alias_plan` session | Reviewed | No Critical/Major findings; evidence-attribution suggestion addressed |
| Rollout approver | Project maintainer | Pending | Existing approval mechanisms continue to apply |
