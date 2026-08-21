# Configuration

## Status: Partially implemented

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

## Core Settings

The implementation validates client authentication, reconciliation interval, minimum credit reserve in dollars and percent, retry attempts and maximum delay, logging level, pricing, per-backend cycle start day, backend API version, and whether protected backends may be emergency fallbacks. Phase 04 also validates optional per-backend local estimate inputs:

- `FOUNDRY_BACKEND_CYCLE_ALLOWANCE_USD_JSON`
- `FOUNDRY_BACKEND_INITIAL_ESTIMATED_REMAINING_USD_JSON`

Pricing values and local credit balances are estimates; zero is valid for an uncharged dimension. Missing local credit estimates make a backend ineligible for credit-aware routing rather than defaulting to unlimited capacity. Authoritative reconciliation remains Planned.

## Authoritative Data

Keep these sources separate:

- Authoritative configuration.
- Authoritative Azure usage and cost data.
- Locally estimated usage and cost.
- Ephemeral health, cooldown, and inflight reservation state.

Local estimates must be labeled as estimates and must never be presented as exact balances.
