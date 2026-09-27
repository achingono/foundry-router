# Configuration

## Status: Partially implemented (Google AI Studio quota-aware routing is single-process; distributed quota accounting remains Planned)

Configuration is externalized through validated environment variables and dotenv values. Secrets must come from environment variables, Azure Container Apps secrets, or managed identity where supported. They must never be committed to source, Git history, images, logs, or diagnostic responses. Retry/cooldown/failover settings are runtime behavior, and Phase 04 local credit estimation settings are runtime-enforced.

## Backend and Model Pools

The configuration must support an arbitrary number of backends and an independent backend pool per model. A backend should identify subscription, project, region, endpoint, and deployment even if the first release uses only two subscriptions. Forwarding-capable backends require a deployment identifier.

```yaml
backends:
  sub_a:
    endpoint: ${FOUNDRY_A_ENDPOINT}
    credential: ${FOUNDRY_A_CREDENTIAL}
models:
  gpt-5.4:
    backends:
      sub_a: {weight: 1}
```

The initial logical model set is `gpt-5.6-luna`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5.3-codex`, `gpt-5.2-chat`, and `text-embedding-3-large`.

## Google AI Studio Keys

Each Google AI Studio API key is configured as a separate backend with
`provider: "google_ai_studio"`, the compatibility endpoint, its Gemini model name, and its own
credential. Set `quota_group` to the Google Cloud project ID when multiple keys belong to one
project; those keys share RPM, input-TPM, RPD accounting, and cooldown state. When omitted, the
backend ID is used as the group. Only distinct projects add independent project quota.

`FOUNDRY_QUOTA_GROUP_RATE_LIMITS_JSON` maps configured quota-group IDs to active limits. Obtain
the values for each model and tier from the [AI Studio Rate Limits page](https://aistudio.google.com/rate-limit);
there is no universal limit triplet, and the values below are illustrative only:

```json
{"project-a": {"rpm": 15, "tpm": 1000000, "rpd": 1500}}
```

Groups with no configured limits are not tracked by the rate-limit store. Configured groups must
be declared by at least one backend. RPM and input TPM use a monotonic trailing-60-second window;
RPD resets at midnight Pacific Time with daylight-saving rules.

Set `credit_metered: false` on free-tier backends to opt out of dollar-credit assessment. A model
pool must be homogeneous: it cannot mix metered and non-metered backends because pricing and cost
are configured per logical model. An all-non-metered model always receives zero pricing,
regardless of any pricing entry. Metered pools still require explicit pricing and complete
per-backend credit configuration for readiness.

## Core Settings

The implementation validates client authentication, reconciliation interval, minimum credit reserve in dollars and percent, retry attempts and maximum delay, logging level, pricing, per-backend cycle start day, backend API version, and whether protected backends may be emergency fallbacks. It also validates optional per-backend local estimate and reconciliation inputs:

- `FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON`
- `FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON`
- `FOUNDRY_RECONCILIATION_OVERRIDES_USD_JSON` (optional mock/adapter input for authoritative remaining values)

It also validates two request-intake and reservation-lifecycle bounds introduced in Phase 08:

- `FOUNDRY_MAX_REQUEST_BODY_BYTES` (default 2,097,152 bytes / 2 MiB): maximum accepted request body size, enforced before JSON parsing for `/openai/v1/responses` and `/openai/v1/embeddings`.
- `FOUNDRY_RESERVATION_MAX_AGE_SECONDS` (default 900 seconds): maximum age of an inflight credit reservation before the bounded reaper reclaims it without charging the backend.

`GET /health/ready` reports whether every metered backend referenced by a model pool has complete credit configuration and every configured model has pricing, surfacing incomplete configuration without failing config load outright. Non-metered backends are excluded only from dollar-credit completeness checks.

Pricing values and local credit balances are estimates; zero is valid for an uncharged dimension. Missing local credit estimates make a backend ineligible for credit-aware routing rather than defaulting to unlimited capacity. Reconciliation is Partially implemented through a periodic background loop that can apply externally supplied remaining-credit snapshots while preserving local fail-safe behavior.

## Authoritative Data

Keep these sources separate:

- Authoritative configuration.
- Authoritative Azure usage and cost data.
- Locally estimated usage and cost.
- Ephemeral health, cooldown, and inflight reservation state.

Local estimates must be labeled as estimates and must never be presented as exact balances.
