# Configuration

## Status: Implemented (Google AI Studio quota-aware routing is single-process and the Responses/embeddings adapter is implemented with mocked verification; distributed quota accounting and real Google inference remain Planned)

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

## Shared Resource Credit (Implemented)

Set `credit_group` on each deployment backend belonging to the same resource credit account.
Omitted or null membership defaults to the backend ID. Any number of deployments and model pools
can share an account; the intended production topology is twelve deployment backends in six model
pools with two credit groups. Health remains backend-owned and provider quota remains `quota_group`-owned.

The existing `FOUNDRY_BACKEND_CYCLE_START_DAY_JSON`,
`FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON`,
`FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON` and
`FOUNDRY_RECONCILIATION_OVERRIDES_USD_JSON` names remain compatible. Their keys must be canonical
credit-group IDs. Provide each account's cycle and estimates once; duplicated backend entries are
rejected. Group IDs reject blank values, surrounding whitespace, Table-forbidden/control characters
and UTF-16 encodings exceeding 1,024 bytes. A group cannot overlap a backend alias mapped elsewhere
or combine metered and non-metered backends. Missing values fail readiness and credit admission.

See [migration and operations](../operations/shared-resource-credit.md) before regrouping existing state.
Incomplete Table group initialization/config merge raises a typed failure and blocks routing;
failed Settings are not cached and can be retried unchanged after storage recovery.

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
per-credit-group configuration for readiness.

Each backend declares the operations it serves via `supported_operations`. Azure backends default
to `["responses", "embeddings"]`; Google backends default to `["responses"]` and must explicitly
declare `["embeddings"]` to serve embeddings (existing Google embeddings configurations must add
the declaration; there is no automatic model discovery). Empty, duplicated, or unknown operations
are rejected at config load.

Synthetic environment-loaded examples (placeholders only; never real keys, endpoints, or model IDs
beyond the documented compat root):

```bash
FOUNDRY_BACKENDS_JSON='{
  "gemini-text-a": {
    "provider": "google_ai_studio",
    "endpoint": "https://generativelanguage.googleapis.com",
    "credential": "${GEMINI_TEXT_A_KEY}",
    "deployment": "gemini-2.5-flash",
    "quota_group": "text-project",
    "credit_metered": false,
    "supported_operations": ["responses"]
  },
  "gemini-emb-a": {
    "provider": "google_ai_studio",
    "endpoint": "https://generativelanguage.googleapis.com",
    "credential": "${GEMINI_EMB_A_KEY}",
    "deployment": "gemini-embedding-001",
    "quota_group": "emb-project",
    "credit_metered": false,
    "supported_operations": ["embeddings"]
  }
}'
FOUNDRY_MODELS_JSON='{
  "gemini-text": {"backends": {"gemini-text-a": 1.0}},
  "gemini-embeddings": {"backends": {"gemini-emb-a": 1.0}}
}'
FOUNDRY_QUOTA_GROUP_RATE_LIMITS_JSON='{"text-project": {"rpm": 15, "tpm": 1000000, "rpd": 1500}}'
```

Paid (metered) Google pools keep `credit_metered: true` with explicit pricing and complete
per-credit-group cycle configuration; free-tier pools use `credit_metered: false` with zero
pricing. Non-metered opt-out affects dollar credit only; it never bypasses quota admission.
Paid balances and prices remain local operator estimates with no Google billing synchronization.

## Core Settings

The implementation validates client authentication, reconciliation interval, minimum credit reserve in dollars and percent, retry attempts and maximum delay, logging level, pricing, per-backend cycle start day, backend API version, and whether protected backends may be emergency fallbacks. It also validates optional per-backend local estimate and reconciliation inputs:

- `FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON`
- `FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON`
- `FOUNDRY_RECONCILIATION_OVERRIDES_USD_JSON` (optional mock/adapter input for authoritative remaining values)

It also validates two request-intake and reservation-lifecycle bounds introduced in Phase 08:

- `FOUNDRY_MAX_REQUEST_BODY_BYTES` (default 2,097,152 bytes / 2 MiB): maximum accepted request body size, enforced before JSON parsing for `/openai/v1/responses` and `/openai/v1/embeddings`.
- `FOUNDRY_RESERVATION_MAX_AGE_SECONDS` (default 900 seconds): maximum reservation age before conservative settlement. Valid retained settlement intent wins; otherwise the full reserved estimate is charged, including legacy/pre-egress rows. Confirmed explicit releases charge zero.

The optional distributed state backend is `memory` by default. When `FOUNDRY_STATE_BACKEND=table`, configure `FOUNDRY_TABLE_ENDPOINT`, `FOUNDRY_TABLE_HEALTH_NAME`, and `FOUNDRY_TABLE_CREDIT_NAME`; the endpoint must be HTTPS and contain no credential or query string. `FOUNDRY_TABLE_REQUEST_TIMEOUT_SECONDS` bounds Table SDK connect/read timeouts. `FOUNDRY_RATE_LIMIT_REPLICA_SHARE` is set by Bicep from `maxReplicas` and divides configured provider quota limits per replica; readiness names any group/dimension whose effective share is zero. Table settings are ignored in memory mode. Table-mode wiring and tests are implemented, but a two-replica Azure deployment and production cut-over remain unverified.

`GET /health/ready` reports whether every unique routable metered credit group has complete credit configuration and every configured model has pricing, surfacing incomplete configuration without failing config load outright. Non-metered backends are excluded only from dollar-credit completeness checks. Table probes require one balance row per routable metered group and still check health-table reachability for non-metered topology.

Pricing values and local credit balances are estimates; zero is valid for an uncharged dimension. Missing local credit estimates make a backend ineligible for credit-aware routing rather than defaulting to unlimited capacity. Reconciliation is Partially implemented through a periodic background loop that can apply externally supplied remaining-credit snapshots while preserving local fail-safe behavior.

## Authoritative Data

Keep these sources separate:

- Authoritative configuration.
- Authoritative Azure usage and cost data.
- Locally estimated usage and cost.
- Ephemeral health, cooldown, and inflight reservation state.

Local estimates must be labeled as estimates and must never be presented as exact balances.
