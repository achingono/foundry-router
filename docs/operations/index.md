# Operations and Deployment

## Status: Implemented (Bicep IaC, connection-pool tuning, graceful shutdown, CI/CD + smoke tests; multi-replica Azure deployment verification pending)

IaC is **Implemented** in `infra/main.bicep` (resource group scope, Container Apps environment + app, Key Vault, Log Analytics, pre-created user-assigned runtime identity, conditional Table Storage, and parameterized deployment – no hard-coded IDs). CI/CD is defined in `.github/workflows/ci.yml` and `deploy.yml`; Azure validation and environment deployment checks still require operator credentials. Table adapter, client, startup wiring, readiness checks and Azurite coverage are implemented in code, but deployed multi-replica shared state remains **Partially implemented** until Azure validation and a two-replica deployment pass. Production remains `stateBackend: memory` with `maxReplicas: 1`.

## Initial Container App

Target Consumption settings are 0.25 vCPU, 0.5 GiB memory, and minimum replicas 0. `stateBackend` defaults to `memory`; `table` mode uses the configured HTTPS endpoint and table names with a user-assigned managed identity. Table-mode readiness requires every configured backend balance row. Startup sync retries failed initialization when routing calls sync again; storage failures fail closed. Scale-to-zero startup latency is expected. Connection-pool/keep-alive/HTTP/2 tuning and graceful shutdown draining are implemented. Do not add always-on infrastructure, API Management, Front Door, Kubernetes, Redis, SQL, or other services without a concrete requirement.

Production cut-over requires reconciled starting balances, deployment in table mode with one replica, a green readiness check, and draining all memory-backed revisions before raising the replica count. In-memory state is not migrated. Rollback is to `memory` with one replica; retain Table data.

Memory-mode Azure validation and a single-replica synthetic baseline deployment are **Implemented** and verified in the [validation evidence](../plans/memory-mode-validation/evidence.md). The synthetic baseline covers health, authentication, model discovery, admin and metrics, not inference. New-workspace logging bootstrap requires `configureConsoleLogsPlan=false` until ingestion creates the console table, followed by `true`. The current Classic console table uses Analytics with 30-day retention; Basic/DCR migration remains **Planned**. See the [infrastructure deployment guide](../../infra/README.md) for tenant checks and partial-deployment recovery.

## Reconciliation

The Bicep typing foundation and identity/observability modules are **Implemented**; the public flat parameter interface remains compatible. Use Bicep 0.47.16 or newer (minimum verified version). Direct internal module callers supply sealed config objects. See [typing evidence](../plans/bicep-typing/evidence.md), [module extraction evidence](../plans/bicep-module-extraction/evidence.md) and the infrastructure guide.

Reconcile authoritative Azure usage/cost data every 5–15 minutes, not on every request. Expose `last_cost_reconciliation` and `cost_data_age`. If unavailable, continue with labeled local estimates, mark the state stale, and optionally route more conservatively. Never treat stale estimates as authoritative.

## Failure Handling

Fail over an unavailable backend, cooldown 429 and repeated 5xx failures, return a clear error when all backends are unavailable or protected, clamp negative usable credit to zero, reject unknown models and malformed requests without outbound calls, and never intentionally cross a safety reserve. Operational priority is safety, availability, quota efficiency, minimizing cycle-end waste, then balancing.
