# Operations and Deployment

## Status: Implemented (Bicep IaC, connection-pool tuning, graceful shutdown, CI/CD + smoke tests; multi-replica gating via Table Storage verified)

IaC is **Implemented** in `infra/main.bicep` (resource group scope, Container Apps environment + app, Key Vault, Log Analytics, system-assigned identity, parameterized deployment for either subscription – no hard-coded IDs). CI/CD is implemented in `.github/workflows/ci.yml` and `deploy.yml` (lint/typecheck/test/coverage 80% + docker build/health + Bicep validate + staging/prod deploy + smoke tests via `scripts/operations/smoke-test.sh`).

## Initial Container App

Target Consumption settings are 0.25 vCPU, 0.5 GiB memory, and minimum replicas 0. With the Phase 06 Azure Table Storage adapter now verified (`src/foundry_router/state/table.py`), `max_replicas` may increase to 2; otherwise remain 1. Scale-to-zero startup latency is expected. Connection-pool/keep-alive/HTTP/2 tuning (`FOUNDRY_HTTP_MAX_CONNECTIONS`, `FOUNDRY_HTTP_MAX_KEEPALIVE_CONNECTIONS`, `FOUNDRY_HTTP_KEEPALIVE_EXPIRY_SECONDS`, `FOUNDRY_HTTP2_ENABLED` → `httpx.Limits` in `src/foundry_router/backends/__init__.py:28`) and graceful shutdown draining (`FOUNDRY_GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS` → `src/foundry_router/main.py:57,121`) are implemented. Do not add always-on infrastructure, API Management, Front Door, Kubernetes, Redis, SQL, or other services without a concrete requirement.

## Reconciliation

Reconcile authoritative Azure usage/cost data every 5–15 minutes, not on every request. Expose `last_cost_reconciliation` and `cost_data_age`. If unavailable, continue with labeled local estimates, mark the state stale, and optionally route more conservatively. Never treat stale estimates as authoritative.

## Failure Handling

Fail over an unavailable backend, cooldown 429 and repeated 5xx failures, return a clear error when all backends are unavailable or protected, clamp negative usable credit to zero, reject unknown models and malformed requests without outbound calls, and never intentionally cross a safety reserve. Operational priority is safety, availability, quota efficiency, minimizing cycle-end waste, then balancing.
