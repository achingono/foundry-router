# Operations and Deployment

## Status: Implemented (IaC and synthetic Table verification); production cut-over Partially implemented

IaC is **Implemented** in `infra/main.bicep` and typed resource modules; CI/CD is defined in `.github/workflows/ci.yml` and `deploy.yml`. Azure template validation, one/two-replica synthetic Table and existing-account cross-RG runtime verification passed. Production cut-over remains **Partially implemented** pending reconciled starting balances and real traffic gates. Production remains `stateBackend: memory` with `maxReplicas: 1`.

## Initial Container App

Existing-account cross-RG synthetic Table runtime is **Implemented** and verified: table-scoped managed identity, idempotent redeployment, checked parent-setting preservation and restart persistence passed. See [cross-RG evidence](../plans/table-existing-cross-rg/evidence.md). Real inference/provider traffic and production cut-over remain unverified; production stays memory/one.

Two-replica synthetic Table verification is **Implemented** in the isolated test app: replica-targeted managed-identity reservation checks, shared app diagnostics and individual container restart persistence passed. Production remains memory-backed with one replica until cut-over requirements are fulfilled. This evidence does not cover real inference, provider quota admission traffic or metrics aggregation. See [two-replica evidence](../plans/table-two-replica/evidence.md).

Target Consumption settings are 0.25 vCPU, 0.5 GiB memory, and minimum replicas 0. `stateBackend` defaults to `memory`; `table` mode uses the configured HTTPS endpoint and table names with a user-assigned managed identity. Table-mode readiness requires every configured backend balance row. Startup sync retries failed initialization when routing calls sync again; storage failures fail closed. Scale-to-zero startup latency is expected. Connection-pool/keep-alive/HTTP/2 tuning and graceful shutdown draining are implemented. Do not add always-on infrastructure, API Management, Front Door, Kubernetes, Redis, SQL, or other services without a concrete requirement.

Production cut-over requires reconciled starting balances, deployment in table mode with one replica, a green readiness check, and draining all memory-backed revisions before raising the replica count. In-memory state is not migrated. Rollback is to `memory` with one replica; retain Table data.

Memory-mode Azure validation and a single-replica synthetic baseline deployment are **Implemented** and verified in the [validation evidence](../plans/memory-mode-validation/evidence.md). The synthetic baseline covers health, authentication, model discovery, admin and metrics, not inference. New-workspace logging bootstrap requires `configureConsoleLogsPlan=false` until ingestion creates the console table, followed by `true`. The current Classic console table uses Analytics with 30-day retention; Basic/DCR migration remains **Planned**. See the [infrastructure deployment guide](../../infra/README.md) for tenant checks and partial-deployment recovery.

## Reconciliation

One-replica synthetic Table runtime verification is **Implemented**: token-only managed-identity readiness, independent adapter reservation/settlement/reconciliation/cooldown checks and balance persistence across app restart passed. Two-replica synthetic checks also passed as recorded above. The Azure extra includes aiohttp and the Table data-role ID is corrected. Production remains memory-backed with one replica; real inference and remaining cut-over gates are pending. See [Table runtime evidence](../plans/table-runtime-validation/evidence.md).

The Bicep typing foundation, identity/observability and environment/router modules are **Implemented**; the public flat parameter interface remains compatible. Use Bicep 0.47.16 or newer (minimum verified version). Direct internal module callers supply sealed config objects and preserve access-grant dependencies. See [typing evidence](../plans/bicep-typing/evidence.md), [module extraction evidence](../plans/bicep-module-extraction/evidence.md), [container module evidence](../plans/bicep-container-modules/evidence.md) and the infrastructure guide.

Reconcile authoritative Azure usage/cost data every 5–15 minutes, not on every request. Expose `last_cost_reconciliation` and `cost_data_age`. If unavailable, continue with labeled local estimates, mark the state stale, and optionally route more conservatively. Never treat stale estimates as authoritative.

## Failure Handling

All new infrastructure resource families now have typed module owners; the root preserves existing-resource lookups and the flat deployment interface. Registry/vault combinations are template-validated, with the synthetic existing/existing memory path redeployed and smoke-tested. New-resource runtime convergence, real inference and Table runtime remain separate verification gates; see [registry/vault evidence](../plans/bicep-registry-vault/evidence.md).

The opt-in `infra/typed.bicep` interface is **Implemented** and synthetic memory redeployment verified. CI retains `main.bicep`. Typed registry/vault/state choices reject inactive branch fields; password remains separate and secure. Both entry points retain the same bootstrap and cut-over requirements; see [public interface evidence](../plans/bicep-public-interface/evidence.md).

Fail over an unavailable backend, cooldown 429 and repeated 5xx failures, return a clear error when all backends are unavailable or protected, clamp negative usable credit to zero, reject unknown models and malformed requests without outbound calls, and never intentionally cross a safety reserve. Operational priority is safety, availability, quota efficiency, minimizing cycle-end waste, then balancing.
