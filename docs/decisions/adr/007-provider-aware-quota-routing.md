# ADR-007: Provider-Aware Quota Routing

## Status
Proposed

## Context
The router supports multiple provider backends in a logical model pool. Gemini API keys can
provide independent credentials, but Google documents the Gemini RPM, input TPM, and RPD limits
as project-scoped, with RPD resetting at midnight Pacific Time. Treating each key as an independent
quota would overstate available capacity. Free-tier backends also do not necessarily have a dollar
credit balance, so dollar-credit completeness must remain separate from request-rate accounting.

Google's current documentation confirms the OpenAI-compatible base URL
`https://generativelanguage.googleapis.com/v1beta/openai/`, API-key authentication, the
`x-goog-api-key` REST header, per-project limits, model/tier-specific limits, and midnight-Pacific
RPD reset:

- [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai)
- [Use API keys to access APIs](https://docs.cloud.google.com/docs/authentication/api-keys-use)
- [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Manage API keys](https://docs.cloud.google.com/docs/authentication/api-keys)

## Decision

1. Model each Google AI Studio key as a backend with `provider: "google_ai_studio"`. Keep the
   Google compatibility base path and credential handling in the allow-listed backend client.
   Client-supplied Google auth headers are stripped; backend IDs, never key strings, identify
   candidates and metric labels.
2. Use `quota_group` as the operator-configured Google Cloud project identifier. If omitted, the
   backend ID is the group. Keys in one group share counters and cooldown; only distinct groups
   provide independent project quota. Automatic project lookup is not part of runtime routing.
3. Configure per-group `{rpm, tpm, rpd}` through
   `FOUNDRY_QUOTA_GROUP_RATE_LIMITS_JSON`. Values are operator inputs taken from the current AI
   Studio rate-limit page, not code defaults. Reject unknown groups and non-positive or non-integer
   limits. A group with no configured limits has no proactive quota accounting.
4. Track RPM and input TPM over a monotonic trailing 60-second window. Google documents usage
   within a minute but does not specify rolling versus fixed-minute windows; the rolling window is
   the conservative implementation assumption. Track RPD as a project-day counter that resets at
   midnight in `America/Los_Angeles`, including daylight-saving transitions.
5. Reserve estimated request count and input tokens atomically before dispatch. Reconcile input
   tokens from non-streaming usage or a terminal streaming usage event; transfer or release an
   outstanding reservation on failover or abandonment. Use the existing bounded reservation age
   for cleanup.
6. Feed projected remaining quota into the existing ADR-006 score's 0.2 quota-health component.
   For each configured dimension, compute the remaining fraction after the estimated request;
   use the minimum and clamp it to `[0.0, 1.0]`. Skip a candidate that cannot fit the estimate,
   except for the existing single-candidate protected emergency fallback. Preserve deterministic
   score, weight, and backend-ID ordering.
7. On proactive exhaustion or a pre-output 429, put every backend in the group into
   `QUOTA_COOLDOWN` until the earliest relevant minute-window or Pacific-midnight reset. Google
   retries without a usable `Retry-After` use bounded full jitter. The no-retry-after-stream-output
   contract is unchanged.
8. Add `credit_metered: false` for a backend that is not charged in dollars. Such backends bypass
   dollar-credit assessment/reservation and are excluded from credit-readiness completeness. A
   logical model pool must be homogeneous in credit-metering mode because pricing is model-scoped.
   An all-non-metered model receives zero pricing regardless of configured price values; metered
   pools retain existing pricing and credit requirements.
9. Keep the rate-limit store in-process and single-replica for this phase. Distributed quota
   accounting and multi-worker metrics aggregation remain **Planned**.

## Consequences

- Same-project keys no longer appear to add independent throughput and receive group-wide cooldown.
- Selection remains explainable and deterministic, with the quota contribution visible in routing
  logs and admin diagnostics.
- Estimates can differ from Google's internal token accounting; reactive 429 handling remains the
  backstop, and values must be tuned from authenticated AI Studio data.
- Multiple replicas do not share this in-memory quota state; operators must not treat it as a
  distributed quota guarantee.

## Verification References

- Configuration and quota group validation: `tests/unit/test_config.py`
- Rate windows, reservations, reconciliation, reaping, and Pacific/DST reset: `tests/unit/test_ratelimit.py`
- Headroom ranking, group cooldown, free-tier routing, and API finalization: `tests/unit/test_main.py`
- Safe budget and cooldown metrics: `tests/unit/test_metrics.py`