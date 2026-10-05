# Model Alias Exit Criteria

## Plan Gate

- [x] Baseline/docs/source/tests inspected and templates copied into a new plan folder.
- [x] Observed review name and user-requested approve name explicitly distinguished.
- [x] Independent review complete and findings addressed.
- [x] Relative links, whitespace and final secret/status claims checked.

## Code Gate

- [ ] Empty configuration preserves behavior; arbitrary explicit aliases resolve exactly once.
- [ ] Bounds, types, duplicate keys, whitespace/control characters, collisions, self references,
  chains/cycles, missing targets and alias price overrides fail validation predictably.
- [ ] Both Codex names and unrelated custom aliases work only when configured; unknown names
  retain 404 with no reservation/egress; targets always identify canonical pools.
- [ ] Responses and embeddings use canonical routing/accounting and selected physical deployment
  mappings; every non-model request field is identical to the caller's parsed value.
- [ ] JSON/SSE response bodies are unchanged; usage settlement uses canonical prices even when
  provider response model differs, streaming fails, or mapping changes for a later request.
- [ ] Aliased/direct concurrent requests share target capacity with distinct server request IDs;
  no duplicated prices, accounts, quotas, balances or finalization.
- [ ] Health, retry/failover, missing-pricing/credit, free/metered policy, cancellation and cleanup
  match direct-target behavior; aliases cannot introduce broader backend eligibility.
- [ ] Authenticated `/models` includes aliases once; admin mapping is separate; readiness remains
  canonical; requested/resolved logs are redacted and metrics count once under canonical identity.
- [ ] Optional Bicep configuration propagates through root and typed paths with empty defaults;
  no new resources/deployments; valid/invalid map examples and rendered env checks pass.
- [ ] Focused/full tests, at least 80% coverage, lint/format/type, required CI/Azurite, Docker
  smoke/build and applicable Bicep/template checks pass with actual results recorded.
- [ ] Conditional Sonar scan and independent deep review completed; actionable findings addressed.
- [ ] Canonical docs/traceability and operations updated; relative links and secret/status diff pass.

## Separate Live Gates

- [ ] Operator revalidates the actual target/configuration and supplies finite test limits.
- [ ] Bounded aliased normal/streaming inference returns provider outcomes and correct canonical
  usage/settlement; catalog/admin identities and optional custom alias behavior verified.
- [ ] Actual approval-client version accepts response-model semantics and gives expected results
  for synthetic allow, deny and error cases with original reviewer instructions preserved.
- [ ] Any parameter/schema/model-equivalence limitations remain explicit; no fake/fail-open
  approvals and no blocked operational action retried as an automatic consequence.
- [ ] Rollout/rollback follows existing memory/one and drain rules; sensitive content is not retained.

Code completion alone may be reported as **Implemented** with mocked verification. Live inference
and approval-review compatibility remain **Planned** until their own gates pass. The planning task
does not close the earlier push failure.

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Plan author | Codex | Prepared | Documentation only |
| Independent reviewer | `review_model_alias_plan` session | Reviewed | No Critical/Major findings; evidence-attribution suggestion addressed |
| Rollout approver | Project maintainer | Pending | Existing approval mechanisms continue to apply |
