# Google AI Studio Adapter Activities

## Step-By-Step Activities

### W1 — Confirm and freeze the compatibility contract

Confirm the vendor references in [Inputs](inputs.md), including authentication on the specific
compatibility surface. Retain existing `x-goog-api-key` behavior only if that surface supports
it; otherwise inject the documented backend credential header in `backends/` and update tests.
Never pass client authentication through. Record verification date, supported operations,
model capabilities and synthetic success/error/SSE fixtures. Review any contract changes.

**Deliverable:** agreed [adapter contract](adapter-contract.md), strict provider fixtures, and
a scoped ADR extending ADR-007. No live requests are needed for the mocked implementation.

### W2 — Add the adapter boundary and operation eligibility (depends on W1)

- Add a small typed adapter protocol and provider implementations under the proposed
  `src/foundry_router/api/adapters/`. Keep transformation pure except for per-request stream
  state; no HTTP clients, stores, retries, credentials or global conversation state in adapters.
- Resolve the adapter from the selected backend provider for every attempt. Retain the
  immutable public request so failover never feeds one provider's transformed body to another.
- Add `supported_operations` to `BackendConfig`: default existing Azure entries to Responses
  and embeddings; default Google entries to Responses. Google embeddings entries explicitly
  declare embeddings. Reject empty, duplicated or unknown operations. Document migration for
  existing Google embeddings configurations and return clear operation-not-supported errors.
- Filter candidates by operation and request features before cost/quota reservation and apply
  the same filter during failover. Preserve valid Azure requests with features Google rejects.
  Health/readiness and model diagnostics must expose usable configured capabilities without
  claiming provider availability has been probed.
- Keep URL construction, selected-backend origin/path validation, credential injection and
  connection pooling in `AllowedBackendClient`. Limit provider operations to trusted mappings.

**Deliverable:** typed adapters and capability tests; Azure URL, body and SSE behavior remains
covered by existing regressions.

### W3 — Translate non-streaming responses and embeddings (depends on W2)

- Implement request/response mapping, explicit rejection and sanitized error translation in
  [Adapter contract](adapter-contract.md). Do not require callers to send Chat Completions
  `messages` to the public Responses route.
- Validate Google success envelopes before returning success. Normalize usage independently
  of output conversion, so a malformed output cannot discard known billable usage.
- Read Google non-streaming/error bodies through incrementally bounded transport, counting
  decoded bytes; a post-read length check on buffered `.content` is insufficient. Test chunked
  responses without length headers and compressed expansion beyond the limit.
- Recompute response headers for transformed bodies; preserve only the existing safe headers.
- Pass `rate_limit_store` through embeddings selection, failover and finalization in
  `api/routes/openai.py`, matching Responses ownership and cleanup behavior.
- Update conservative estimation in `credit.py` to cover instructions and supported history
  as well as input. Enforce the reserved output bound upstream even when the caller omits it;
  choose a validated provider-supported token-limit field in W1.

**Deliverable:** strict mocked end-to-end text Responses and embeddings, including usage,
unsupported-field rejection before egress, operation filtering and quota admission.

### W4 — Translate streaming with bounded state (depends on W3)

Implement incremental Google SSE decoding and Responses encoding according to the contract.
Forwarding retains retry and cleanup ownership. Prefetch a validated translatable provider
event under the existing pre-output deadline before returning a downstream stream; do not emit
synthetic lifecycle events on an unvalidated upstream connection. Latch the retry prohibition
at the first downstream event, including lifecycle events.

Add explicit bounds for provider events, assembled output and pending stream state. Reuse
existing time/size limits where suitable; validate and document any new setting. Handle split
UTF-8, LF/CRLF, multiline data, keepalives, multiple events per chunk, usage-only final chunks,
malformed data, truncation, read timeout, cancellation and stream-close failures. Preserve
bounded independent credit/quota/metrics/transport cleanup from `cleanup.py`.
Use an absolute deadline established at initial reservation creation and retained across
retry/failover; test retry delays, prefetch and slow downstream backpressure against the
remaining lifetime with cleanup headroom before reservation expiry.

**Deliverable:** Responses SSE contract fixtures and failure/cancellation tests with exactly
one terminal outcome and no second provider dispatch after downstream delivery begins.

### W5 — Verify retries, reservations and information boundaries (depends on W3–W4)

- Exercise three or more keys, shared-project keys and distinct-project groups; quota
  exhaustion, 429 with/without/invalid `Retry-After`, 5xx, auth errors and all-backend failure.
- Count provider attempts conservatively: an attempt that may have reached Google must retain
  estimated quota consumption even if another key is selected. Retry within one backend also
  needs quota admission. Release estimates only for confirmed pre-dispatch abandonment;
  reconcile known usage without double-counting. Reuse or minimally extend `ratelimit.py`.
- Keep credit reservations server-owned and settlement idempotent across retries/failover.
  Distinguish upstream rejection from successful generation followed by translation failure;
  the latter charges actual known usage or the reservation estimate. A settlement failure
  must not permit another dispatch. For Google, do not retry/fail over after ambiguous dispatch
  (partial write, response timeout/read failure, truncated 200 stream); settle usage/estimate
  and retain consumed quota. Only confirmed pre-dispatch failures and confirmed non-generation
  rejections may retry. Do not infer non-generation from a 5xx status alone. Never retry
  semantic schema/safety failures as transport outages; preserve Azure's existing policy.
- Put Google 401/403 failures into backend-local bounded `ERROR_COOLDOWN` without retrying
  the same request; later requests can select healthy keys. Test repeated selection and
  cooldown expiry, with no authentication failure propagated to sibling project keys.
- Verify logical model IDs in Google public results and telemetry; inspect logs, errors,
  admin/status and metrics for synthetic credential, prompt and output markers.
- Test metered Google configurations using local estimates and non-metered configurations
  using zero pricing. Preserve homogeneous metering and independent credit/quota groups.

**Deliverable:** focused safety/integration tests and evidence of reservation cleanup and
conservative accounting, including protocol failures before and after stream commitment.

### W6 — Complete documentation and implementation quality gates (depends on W5)

Update API support tables and real Responses SSE examples, architecture/structure, configuration
and security, routing, observability, operations, README/docs hub and requirements traceability.
Replace broad Google compatibility claims with the implemented subset and evidence scope;
preserve historical Phase 09 evidence. Add synthetic, environment-loaded backend examples using
placeholders, with explicit operations, project groups and free/paid metering notes.

Run focused tests first, then the configured full verification gates:

```bash
.venv/bin/python -m pytest tests/unit/test_backends.py tests/unit/test_config.py tests/unit/test_forwarding_stream.py tests/unit/test_ratelimit.py tests/integration/test_full_flow.py -q
.venv/bin/python -m pytest tests/unit/ tests/integration/ -m "not docker and not azurite" --cov=src/foundry_router --cov-report=term-missing --cov-report=xml --cov-fail-under=80
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/
```

Also include all new adapter tests in the focused run. Run the Azurite suite and combined
coverage gate as configured in CI, Docker build and image health smoke test when the required
services/tools are available. Record unavailable gates explicitly and obtain CI results before
claiming code verification complete. Run `scripts/quality/sonarqube-scan.sh` if present and
resolve all Blocker/Critical/Major findings. It is absent at the planning baseline.

Run the independent [deep-review prompt](../../../.agents/prompts/deep-review.prompt.md),
address findings, check relative Markdown links, and review the final diff for secrets and
unsupported status claims. Maintain at least 80% overall implemented-code coverage.

**Deliverable:** completed code-verification evidence, reviewed docs and a release candidate.

### W7 — Perform opt-in real Google validation (depends on W6 and operator inputs)

Use an isolated memory-backed, one-worker, one-replica test configuration with supplied
credentials and explicit request/token/spend ceilings. Exercise non-streaming text, streamed
text, embeddings on a separately configured embedding model, stateless text history and usage
settlement. Verify the configured header/path/model, logical aliases and cleanup through
redacted assertions. Do not deliberately exhaust provider quota; mocked failure cases remain
separate evidence unless authorized real failure traffic has been tested.

Record client/model versions, date, operation, result, usage counts and redacted diagnostics;
do not retain prompt/output bodies or credentials. Remove test configuration/credentials through
the normal secret lifecycle. Production onboarding remains a separate operator action and must
preserve the repository's memory/one production restriction.

**Deliverable:** live evidence for the exact tested subset, or an explicit **Planned** gate if
operator inputs are unavailable. Code tests alone never close this gate.

## Review Focus

- Provider-specific validation must not regress Azure or bypass admission during failover.
- No unsupported Responses field may disappear silently; no partial output may be retried.
- SSE correctness, bounded memory and billable-failure handling must be reviewed together.
- Provider quota attempts, credit reservations and normalized usage have distinct ownership.
- The plan and evidence must distinguish implemented transport from unverified real inference.
