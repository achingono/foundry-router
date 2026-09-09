# Architecture

## Objective

The target system is a small asynchronous HTTP proxy hosted on Azure Container Apps. It receives an OpenAI-compatible request, selects a configured backend, forwards the request without changing the logical model name, streams or returns the upstream response, and records health, quota, usage, and estimated cost state.

```text
Client -> OpenAI-compatible API -> Foundry Router -> configured Foundry backends
                                      |                 A / B / ...
                                      +-> cost reconciliation and telemetry
```

## Boundaries

- **API adapter (`api/`)**: Owns endpoint routing (`/openai/v1/*`, `/health/*`, `/admin/*`), request validation, authentication, protocol translation, and streaming response packaging.
- **Forwarding (`forwarding/`)**: Owns outbound HTTP transport, retry loops, bounded pre-output waiting, streaming chunk pass-through, and SSE terminal usage extraction with bounded buffers.
- **Backend client (`backends/`)**: Owns outbound connection pool lifecycle (`httpx.Limits`), keep-alive tuning, HTTP/2 multiplexing, and safe header allow-listing.
- **Routing & Scheduling (`routing/`)**: Owns candidate selection, composite scoring (ADR-006), deterministic tie-breaking, failover coordination, and explainable decision logging.
- **Health tracking (`health/`)**: Owns ephemeral health states (`ACTIVE`, `QUOTA_COOLDOWN`, `ERROR_COOLDOWN`, `DISABLED`), cooldown duration calculation, and snapshotting.
- **Credit subsystem (`credit/` & `reconciliation/`)**: Owns cycle calculations, conservative token/cost estimation, atomic reservation lifecycle (`try...finally`), safe-capacity validation, and periodic billing reconciliation.
- **State Store Abstraction (`state/`)**: Owns `CreditStore`/`HealthStore` protocols, in-memory stores, and injected-client Azure Table Storage adapters (`AzureTableHealthStore`, `AzureTableCreditStore`) with same-partition ETag transactions. Redis remains an optional later hot-state optimization, not the authoritative store.
- **Telemetry (`logging/` & `metrics/`)**: Owns structured redacted logging, Prometheus `/metrics` (single-process; multi-process aggregation Planned), correlation IDs, and live admin diagnostics.
- **Infrastructure (`infra/`)**: Owns Bicep templates (`infra/main.bicep`), Azure Container Apps, Key Vault secrets, managed identity RBAC, and deployment automation. **Implemented**.

Keep these responsibilities separate. In particular, estimated local cost is not authoritative Azure cost, and model quota is not subscription credit.

## Deployment Shape

The initial target is Azure Container Apps Consumption with 0.25 vCPU, 0.5 GiB memory, and zero minimum replicas. Deployments default to `max_replicas: 1` and may increase to `2` after verifying the Phase 06 Azure Table Storage adapter (now **Implemented** via `src/foundry_router/state/table.py` and verified by `tests/unit/test_state.py`). Scale-to-zero must remain possible. Single-process deployments use in-memory credit and health state. Multi-replica or multi-worker deployments use Azure Table Storage for authoritative credit balances and reservations with ETag-based same-partition transactions. Health and cooldown snapshots are timestamped and eventually consistent. Redis may be added later as a cache, but it does not replace the Azure Table Storage source of truth.

## Technology Direction

The preferred stack is Python 3.12+, FastAPI, asynchronous `httpx` (with HTTP/2 and connection limits), Pydantic settings, Docker, Azure Container Apps, Bicep IaC, GitHub Actions, pytest, Ruff, and mypy. All are **Implemented** except multi-worker metrics aggregation, which remains **Planned**.
