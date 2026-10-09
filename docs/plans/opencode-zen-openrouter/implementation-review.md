# Zen/OpenRouter implementation review

Contextual (non-static-analysis) review of the implementation diff
`25fda32..HEAD` against the [revised contract](index.md), performed by the
implementing session after the full test suite, Ruff/mypy, Docker build/smoke,
link and secret checks. No Critical or Major findings; one Suggestion recorded
below. Static-analysis scan was not run: `scripts/quality/sonarqube-scan.sh`
does not exist (conditional gate).

## Findings

- **File/Module:** `src/foundry_router/forwarding/__init__.py`
  (`_enter_google_stream`, `_handle_google_error_status`,
  `_shielded_google_cancel_cleanup`, `_fallback_estimate_cost`)
- **The Issue:** The Zen single-shot paths reuse helpers whose names and
  docstrings say Google. Behavior is provider-parameterized (adapter lookup via
  `_provider_of`, pre-output failover gated on `provider == "google_ai_studio"`),
  so this is naming debt only, not a policy leak.
- **Why Static Analysis Missed It:** Name-to-policy correspondence is a
  contextual judgment; linters verify references, not naming intent.
- **Impact:** Future readers may assume Zen inherits Google-specific semantics
  (e.g. quota-group cooldown scope, pre-output failover) without reading the
  guards. No runtime impact: unit and integration tests pin single-shot dispatch,
  429-only failover eligibility, and conservative settlement for both providers.
- **Recommended Fix:** Suggestion only. If these helpers gain a third caller,
  rename to provider-neutral names (`_enter_backend_stream`,
  `_handle_provider_error_status`) in a separate mechanical commit with the
  oracle suites green. Not done here to keep the change surface minimal.

## Verified properties

- Zen and OpenRouter provider keys never fall through to Azure/Google/generic
  dispatch: config literals, backend URL/auth branches, adapter registry, and
  forwarding policy branches are all keyed on the actual configured provider.
- Zen never sends the Chat dialect; OpenRouter never bypasses bounded
  translation (pinned by transport and integration assertions on upstream bodies).
- Unsupported/foreign fields are rejected before Zen/OpenRouter quota/credit
  admission; mixed-pool and operation-filtering behavior is pinned by
  integration tests.
- `retry_attempts > 1` still yields one dispatch per backend for both providers;
  only pre-output 429 is failover-eligible, with both quota attempts counted.
- Ambiguous dispatched failures and cancellation retain known usage or the full
  estimate; confirmed pre-dispatch failures release without charge.
- Existing Azure/Google/generic oracles and suites pass unchanged.
