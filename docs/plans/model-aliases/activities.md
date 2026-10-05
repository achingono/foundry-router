# Model Alias Activities

## Step-By-Step Activities

### A1 — Validate the alias namespace

Implement the Settings field and one-hop resolver in [Alias contract](alias-contract.md).
Default to `{}` and preserve existing canonical pool/pricing validation. Reject duplicate keys,
invalid/oversized entries, collisions, chains/cycles and noncanonical targets. Reject alias-specific
prices. Add focused config/resolver tests, including both requested Codex names and unrelated
custom names; production names must never appear as built-in defaults.

### A2 — Resolve at API ingress and preserve request identity (depends on A1)

Use the helper in Responses and embeddings before membership checks/admission. Pass a canonical
request copy and identity context into existing routing/forwarding. Keep original nested content
unchanged. Carry the same canonical name through initial selection, failover, stream closures,
usage extraction, settlement and metrics. Do not put requested-name metadata into provider JSON.

Test alias → canonical pool → different backend deployment IDs with the existing Azure Responses
and embeddings URL/body rules. Direct requests and empty alias configuration must keep current
behavior. Google tests cover only existing transport/model substitution; complete Google schema
translation still belongs to the separate adapter plan.

### A3 — Catalog and diagnostics (depends on A2)

Include configured aliases exactly once in authenticated `/models`; retain canonical ordering and
append aliases deterministically. Expose targets only in admin mapping. Keep readiness based on
canonical pool/account completeness. Add requested/resolved/alias context to bounded routing logs
and keep metric `model` canonical with one observation per outcome. Use existing logging-volume
and credential-redaction tests; do not add arbitrary user-supplied labels or duplicate cost series.

### A4 — Regression and accounting tests (depends on A2–A3)

- Both `codex-auto-review` and `codex-auto-approve`, direct target and several custom names;
  unknown names, case mismatch, omitted alias map and removed aliases.
- Missing target fails config; missing target price/credit retains readiness and no-egress
  failure. Alias price overrides rejected; non-metered targets inherit zero pricing only by
  existing metering policy.
- Normal Responses and embeddings forward all non-model fields unchanged. Synthetic reviewer
  instructions, tools, reasoning and structured-output fields must survive exact comparison;
  provider 400/errors are not repaired or converted to approval success.
- SSE bytes (including returned model and fragmented usage events) remain identical. Actual
  and fallback estimated charges use canonical prices through success, failure and cancellation.
- Multiple aliases plus direct traffic concurrently share existing credit/quota capacity, use
  distinct server reservation IDs and clean up exactly once; no duplicate account/group state.
- 429/5xx cooldown, bounded failover and no post-output retry match direct-target behavior;
  different deployment names on retry never overwrite the original request/context.
- Freeze resolution/settings for in-flight requests: changing the alias map for a later request
  cannot reprice or retarget an earlier stream. Exercise drained rollout/retarget/removal semantics.
- Catalog/admin auth, log identity fields, canonical metrics, redaction and arbitrary-backend
  allow-list enforcement pass. Unknown-model tests assert no reservation or provider egress.

### A5 — Configuration delivery, docs and quality gates (depends on A4)

Wire optional `modelAliases` through `infra/main.bicep`, `infra/typed.bicep` and the container
configuration type/module into the environment; default empty, no new resource. Add parameter/
render checks for both entry points and empty/custom maps. Update `.env.example`, infra examples
and operations so later deployments preserve alias configuration rather than losing an ad hoc edit.

Update canonical API/config/security, architecture, routing, observability, requirements traceability
and the docs hub. Document response-model passthrough, explicit aliases versus hidden visibility,
no specialized-model equivalence guarantee, target-price inheritance and rollout/rollback.

Run new resolver tests plus focused config/main/backend/stream/metrics/integration tests first, then:

```bash
.venv/bin/python -m pytest tests/unit/ tests/integration/ -m "not docker and not azurite" --cov=src/foundry_router --cov-report=term-missing --cov-report=xml --cov-fail-under=80
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/
```

Complete configured Azurite/combined coverage, Docker build/image smoke and Bicep build/lint/
template validation gates. Record unavailable local prerequisites and obtain required CI evidence
before declaring completion. Run `scripts/quality/sonarqube-scan.sh` if present (absent at baseline),
resolve Blocker/Critical/Major findings, and run independent implementation review using the
[deep-review prompt](../../../.agents/prompts/deep-review.prompt.md). Validate relative links and
final secret/status claims. No runtime test or build is claimed by drafting this plan.

### A6 — Optional operational and approval-client verification (after code gates)

Reverify target readiness and current deployment configuration using operator-supplied inputs.
Apply a bounded isolated test configuration with the observed review alias, confirm authenticated
catalog/admin output and run normal/streaming synthetic Responses plus canonical settlement checks.
Verify the actual approval client/version and its response-model acceptance separately, with
synthetic expected allow/deny/error cases; HTTP 200 alone does not close that gate.

If a 400/tool/schema incompatibility follows successful alias resolution, record it and leave
reviewer compatibility unverified. Do not change prompts, drop fields, return fake approvals or
automatically retry blocked actions. Record only case IDs, configured names, result assertions,
usage and redacted diagnostics; no real review context, prompts, outputs or credentials.

Production configuration/rollout remains a separate operator step with memory/one preserved.
Remove/retarget aliases through validated configuration and normal drain/restart to roll back.
Existing backend/credit/quota state is not reset. Retain code, inference and reviewer-validation
evidence as separate gates.

## Review Focus
- Resolution occurs before admission and never changes during a request.
- Requested, canonical and physical identities are never confused in settlement or logs.
- Aliases inherit all target policy without creating capacity or bypassing future continuation rules.
- Non-model fields, provider errors and SSE bytes retain existing semantics.
