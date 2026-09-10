# Phase 09 Activities

Implement the workstreams in order. W1–W2 establish the provider and multi-key model; W3–W4 add
proactive rate-limit accounting and quota-aware selection (the core of the request); W5–W6 handle
reactive limits and free-tier economics; W7–W8 cover observability, documentation, and
verification. Each workstream lands as its own commit(s) with tests. Do not weaken the
streaming/SSE contract or the "never retry or fail over after meaningful streaming output begins"
rule while editing forwarding. Never log API keys, credentials, prompts, or model outputs.

Before writing code, copy nothing else from templates; follow the required change workflow in
`AGENTS.md` (plan review by a second model/session before implementation).

## W1 — Provider-aware backend configuration and client
1. Add a `provider` field to `BackendConfig` in `src/foundry_router/config/__init__.py`, a
   `Literal["azure_foundry", "google_ai_studio"]` defaulting to `"azure_foundry"` so existing
   configurations are unchanged. Relax provider-specific validation: for `google_ai_studio`, the
   `deployment`/`api_version` Azure fields are not required, but a Gemini model identifier and the
   Google endpoint must be present and HTTPS.
2. In `src/foundry_router/backends/__init__.py`, branch `_backend_url` and `_backend_headers` on
   the backend's provider. For `google_ai_studio`, build the request against the Google
   OpenAI-compatibility base path (confirmed URL recorded in the ADR) and set the Google auth
   header (`x-goog-api-key`) from the backend credential instead of the Azure `api-key` header.
   Keep `_validate_url` allow-listing intact for the Google host.
3. Ensure `_sanitize_headers` also strips the Google auth header name from any client-supplied
   headers so a caller cannot inject or observe it, mirroring the existing `api-key` handling.
4. Add unit tests in `tests/unit/test_backends.py` and `tests/unit/test_config.py` for: a Google
   backend builds the compatibility URL and Google auth header; an Azure backend is unchanged; a
   Google backend with a non-HTTPS or off-host endpoint is rejected.

## W2 — Multiple API keys as pool backends
5. Confirm (and test) that `ModelBackendPool` already supports an arbitrary number of backend
   entries for one model; represent each Google API key as its own backend ID (for example
   `gemini-flash-key-1`, `gemini-flash-key-2`, ...) mapped into the same model pool. Do not add any
   two-key or A/B special case.
6. Add an optional `quota_group` identifier to `BackendConfig` (defaulting to the backend ID) that
   names the Google Cloud project a key belongs to. Rate-limit accounting (W3) keys off the quota
   group, so two keys that set the same `quota_group` share one budget and cool down together, while
   distinct values are independent. For the target one-key-per-project deployment the field may be
   omitted (each key becomes its own group) or set to the project ID for clearer observability;
   validate that any per-quota-group rate-limit config references a group that at least one backend
   declares.
7. Investigate (best-effort, optional) deriving the project from the key via the Cloud API Keys API
   (`apikeys.googleapis.com`) when separately authorized credentials are supplied; if pursued, use
   it only to default or cross-check the configured `quota_group`, never as a hard dependency, and
   never log the key. AI Studio `AIza…` keys do not embed a decodable project, so explicit
   configuration remains the source of truth. Record the outcome in the ADR.
8. Document the configuration pattern (one backend per key, shared endpoint, distinct credential,
   `quota_group` set to the project so same-project keys are grouped) in
   `docs/configuration/index.md` and the getting-started example, using placeholder keys only.
9. Add an integration test in `tests/integration/test_full_flow.py` (or a new sibling) proving a
   model backed by three synthetic Google keys with distinct `quota_group` values routes across them
   under the scoring rules, not round-robin, and that two keys sharing a `quota_group` share a
   budget and cool down together, using the mock backend.

## W3 — Rate-limit state boundary (proactive quota accounting)
10. Add a rate-limit state boundary alongside the health store. Define a `RateLimitStore` Protocol
    and an `InMemoryRateLimitStore` (single-replica) under `src/foundry_router/state/` or a new
    `src/foundry_router/ratelimit/` module, consistent with ADR-005. Track, per **quota group**
    (project): requests in the trailing 60 seconds (RPM), **input** tokens in the trailing 60
    seconds (TPM), and requests in the current quota day (RPD). Use a monotonic trailing-60-second
    window for the per-minute dimensions (Google documents only "within a minute"; a rolling window
    is the prudent assumption) and a fixed daily boundary for RPD.
11. Compute the RPD reset at **midnight Pacific Time** (07:00 UTC during PDT, 08:00 UTC during PST),
    honouring the daylight-saving transition rather than assuming a fixed UTC offset; RPD is a fixed
    daily quota, not a rolling 24-hour window.
12. Expose async methods to (a) snapshot remaining budget for a set of backends resolved to their
    quota groups, (b) reserve/record a request's request-count and estimated input-token usage
    before dispatch, and (c) finalize actual input-token usage after the response/stream completes
    (reconciling the pre-dispatch estimate with the usage reported by the terminal usage event).
    Use the existing estimated-token path from `estimate_request_cost` for the pre-dispatch
    estimate; reuse the streaming usage extractor for finalization.
13. Add per-quota-group free-tier limits to configuration via a new JSON settings field (for
    example `FOUNDRY_QUOTA_GROUP_RATE_LIMITS_JSON` mapping quota-group ID to `{rpm, tpm, rpd}`),
    parsed and bounded-validated in `parse_json_fields` with the same "references unknown group"
    and finite/positive checks used by existing per-backend maps. Groups without limits have no
    rate-limit accounting (Azure backends stay unaffected). Values are model/tier-specific and must
    come from the authenticated AI Studio Rate Limits page; do not bake a universal triplet into
    code.
14. When a per-minute or per-day budget is exhausted, feed the existing health store so every key
    in that quota group enters `QUOTA_COOLDOWN` until the window resets (reuse
    `set_backend_cooldown`), so cooldown exhaustion responses and `Retry-After` remain consistent.
    Keep the reset time bounded and computed from the window (trailing-60s for RPM/TPM,
    midnight-Pacific for RPD), not from unbounded background work.
15. Add unit tests for trailing-60-second rollover (RPM and input TPM), RPD reset across a
    midnight-Pacific boundary including a DST transition, reservation vs finalization
    reconciliation, same-group budget sharing, exhaustion → cooldown, and reset → active.

## W4 — Quota-aware scoring (highest chance of success)
16. Add a rate-limit health signal to the scoring path so selection prefers the key most likely to
    succeed. Extend `score_credit_assessment` (or add a composed scorer in `routing/__init__.py`)
    with a bounded `0.0–1.0` quota-health term derived from the remaining RPM/input-TPM/RPD headroom
    of the key's quota group relative to the estimated request cost, consistent with the ADR-006
    "Quota Health" component. A key whose group has little remaining budget for this request scores
    low; a key with ample headroom scores high.
17. In `select_candidate_backend`, snapshot rate-limit budgets for the ranked candidates alongside
    health snapshots, filter out keys with zero remaining headroom for the request (unless it is the
    only candidate and protected emergency fallback applies, mirroring the existing cooldown
    fallback), compute the composite score, and select the highest. Preserve the existing weighted
    tie-break and the single-failover flow. Record the quota-health inputs in the existing
    `routing_decision` structured log so decisions stay explainable (never log the key itself).
18. Reserve the request against the selected key's rate-limit budget at the same point the credit
    reservation is taken, using the server-owned request key from Phase 08 (never a client value),
    so a failover releases the first key's rate-limit reservation just as it releases credit.
19. Add unit tests proving: among otherwise-equal keys the one with the most remaining budget is
    chosen; a key near its RPM/TPM/RPD limit is deprioritised or skipped; selection is deterministic
    for identical inputs; and a failover releases the first key's rate-limit reservation.

## W5 — Reactive limit handling and daily reset
20. Confirm Google `429` responses (including `RESOURCE_EXHAUSTED`) flow through the existing
    `parse_retry_after` + `set_backend_cooldown` path and set `QUOTA_COOLDOWN` for the whole quota
    group; when no usable `Retry-After` is present, apply exponential backoff with jitter (Google's
    recommendation) bounded by `retry_max_delay_seconds`. Add handling for the RPD daily reset so a
    key returns to `ACTIVE` at the midnight-Pacific boundary rather than only after a fixed
    cooldown. Keep `parse_retry_after` hardened (Phase 08 F5) behaviour.
21. Ensure the "never retry or fail over after meaningful streaming output begins" rule is
    unchanged; a 429 mid-stream must not trigger failover.
22. Add tests for a Google-style `429 RESOURCE_EXHAUSTED` with and without `Retry-After` (asserting
    backoff-with-jitter bounds in the latter), and for RPD reset returning a key to service at the
    midnight-Pacific boundary.

## W6 — Free-tier credit and pricing handling
23. Define how a free-tier backend opts out of dollar-credit accounting so the Phase 08 readiness
    completeness checks (`backend_credit_config_complete`, `model_pricing_complete`) do not flag it.
    Choose one and record it in the risk register and traceability: either (a) a per-backend
    `credit_metered: false` flag that excludes the backend from the credit-config completeness
    check and treats credit assessment as always-usable, or (b) require zero-pricing plus zero/
    unlimited allowance entries for free backends. Prefer (a) to keep quota and credit cleanly
    separate.
24. Ensure cost estimation returns a zero (not "unavailable") cost for free models so routing does
    not fail closed on missing pricing for those models, while non-free models keep current
    behaviour.
25. Add tests: a free Google model with no dollar-credit config is routable and passes readiness;
    an Azure model with missing credit config still fails readiness as before.

## W7 — Observability and documentation
26. Surface per-key remaining RPM/input-TPM/RPD and current cooldown in `/admin/status`
    (`src/foundry_router/api/routes/admin.py`) using the same locked-snapshot pattern as reservation
    counts; identify keys and quota groups by ID only, never by credential.
27. Add rate-limit metrics (for example remaining-budget gauges and rate-limit-cooldown counters) in
    `src/foundry_router/metrics/`, consistent with the existing single-process Prometheus approach.
28. Write a new ADR `docs/decisions/adr/007-provider-aware-quota-routing.md` (next free ADR number;
    confirm at implementation time) covering the provider discriminator, the quota-group rate-limit
    state boundary, the quota-health scoring term, and the free-tier credit opt-out, and link it
    from `docs/decisions/index.md`.
29. Update `docs/features/routing.md` (quota-aware, multi-key, non-round-robin selection),
    `docs/configuration/index.md` (Google provider, quota groups, rate-limit config, free-tier
    credit opt-out), `docs/configuration/security.md` (key handling and redaction), and
    `docs/operations/observability.md` (new admin/status fields and metrics). Use only verified
    behaviour and the four status labels.
30. Update `docs/decisions/requirements-traceability.md` to map the new provider, quota-group
    rate-limit tracking, and quota-aware selection requirements to their modules and tests.

## W8 — Verification
31. Run focused tests per workstream, then the full suite via
    `.venv/bin/python -m pytest -m "not docker" -q`, then coverage
    (`--cov=src/foundry_router`, maintain >= 80% for implemented code), then
    `.venv/bin/ruff check src/ tests/`, `.venv/bin/ruff format --check src/ tests/`, and
    `.venv/bin/mypy src/`.
32. Run `scripts/quality/sonarqube-scan.sh` and the deep-review prompt if they exist and resolve
    `Blocker`/`Critical`/`Major` findings; note as N/A if absent (they are not present as of Phase
    08).
33. Attempt a Docker build where the CLI is available; otherwise record as N/A in evidence.
34. Validate relative documentation links and review the final diff for secrets, hard-coded
    identifiers, and unsupported present-tense claims.
35. Record all evidence in [Evidence](evidence.md).

## Review Focus
- Selection is genuinely quota-aware (highest estimated success probability), not round-robin, and
  remains deterministic and explainable via `routing_decision` logs.
- Rate-limit accounting is correct across trailing-60-second (RPM/input-TPM) and midnight-Pacific
  (RPD) window boundaries, is scoped to the quota group so same-project keys share a budget, and
  reconciles estimated vs actual input-token usage; reservations release on failover and on client
  disconnect (reuse the Phase 08 reaper pattern where applicable).
- Quota and credit stay separate; free-tier backends are routable without weakening the Phase 08
  readiness completeness guarantees for metered backends.
- No API key, credential, prompt, or output appears in logs, errors, admin output, metrics labels,
  or docs; the Google auth header is stripped from client-supplied headers.
- Streaming/SSE boundaries and the no-retry-after-output rule are unchanged.
- The Google OpenAI-compatibility base URL and auth header are verified against current Google
  documentation and are configuration-driven, not hard-coded guesses.
