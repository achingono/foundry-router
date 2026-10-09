# Architecture

## Objective

The target system is a small asynchronous HTTP proxy hosted on Azure Container Apps. It receives an OpenAI-compatible request, selects a configured backend, forwards the request without changing the logical model name, streams or returns the upstream response, and records health, quota, usage, and estimated cost state.

```text
Client -> OpenAI-compatible API -> Foundry Router -> configured Foundry backends
                                      |                 A / B / ...
                                      +-> cost reconciliation and telemetry
```

## Boundaries

- **API adapter (`api/`)**: Owns endpoint routing (`/openai/v1/*`, `/health/*`, `/admin/*`), request validation, authentication, protocol translation (`api/adapters/`: typed provider protocol, Azure pass-through, shared OpenAI-compatible Responses/embeddings translation with per-request stream decoders and Google validation hooks), and streaming response packaging. The generic translation classes are **Implemented**; the configurable text/embedding provider is **Implemented** with mocked upstream verification. Live compatibility remains unverified.
- **Forwarding (`forwarding/`)**: Owns outbound HTTP transport, retry loops, bounded pre-output waiting, Azure streaming chunk pass-through and Google Responses SSE translation with prefetch-validated commit, incremental bounded reads, absolute reservation deadlines, and billable-failure settlement with bounded buffers.
- **Backend client (`backends/`)**: Owns outbound connection pool lifecycle (`httpx.Limits`), keep-alive tuning, HTTP/2 multiplexing, provider URL/header enforcement (Google `Authorization: Bearer`, double-suffix-tolerant compat paths, credential query rejection), and safe header allow-listing.
- **Routing & Scheduling (`routing/`)**: Owns candidate selection, composite scoring (ADR-006), deterministic tie-breaking, failover coordination, and explainable decision logging.
- **Health tracking (`health/`)**: Owns ephemeral health states (`ACTIVE`, `QUOTA_COOLDOWN`, `ERROR_COOLDOWN`, `DISABLED`), cooldown duration calculation, and snapshotting.
- **Credit subsystem (`credit/` & `reconciliation/`)**: Owns cycle calculations, conservative token/cost estimation, atomic reservation lifecycle (`try...finally`), safe-capacity validation, and periodic billing reconciliation.
- **State Store Abstraction (`state/`)**: Owns `CreditStore`/`HealthStore` protocols, in-memory stores, and injected-client Azure Table Storage adapters (`AzureTableHealthStore`, `AzureTableCreditStore`) with same-partition ETag transactions. Redis remains an optional later hot-state optimization, not the authoritative store.
- **Telemetry (`logging/` & `metrics/`)**: Owns structured redacted logging, Prometheus `/metrics` (single-process; multi-process aggregation Planned), correlation IDs, and live admin diagnostics.
- **Infrastructure (`infra/`)**: Owns Bicep templates (`infra/main.bicep`), Azure Container Apps, Key Vault secrets, managed identity RBAC, and deployment automation. **Implemented**.

Keep these responsibilities separate. In particular, estimated local cost is not authoritative Azure cost, and model quota is not subscription credit.

The configurable `openai_compatible` provider is **Implemented with mocked verification**:
`compatible_text.py` owns independent bounded text capability hooks, the backend client owns
exact-root/Bearer egress, and forwarding shares the bounded translated attempt/SSE lifecycle
with Google while selecting the actual configured provider. Google native/media logic remains
profile-bound. No additional infrastructure or universal upstream capability is implied.

Shared-resource credit is **Implemented**: `credit_groups.py` owns the validated canonical account
namespace and one-pass backend alias resolution used by settings and credit stores. Memory/Table
balances, locks/caches and reservations use groups; captured ownership governs settlement. Health
continues to use deployment backend IDs. Quota groups remain independent. See
[migration](../operations/shared-resource-credit.md) and [evidence](../plans/shared-resource-credit/evidence.md).

Logical model aliases are **Implemented** with mocked verification:
`config/model_aliases.py` owns explicit one-hop alias-to-canonical-pool validation and
resolution at the API boundary. Routing, credit, and telemetry keep canonical
accounting while preserving requested/resolved identity for diagnostics; backend
deployment substitution is unchanged. Live inference and approval-client validation
remain separately gated.

The approved recovery amendment adds retained/durable settlement intent and conservative expiry,
fresh balance/reservation ETags, metering-aware serialized local ownership, bounded uncertain request
tracking and independently protected cleanup (`cleanup.py`). This does not create a distributed
cross-partition identity protocol; requests retain server-owned unique IDs and drained rollout rules.

## Deployment Shape

The initial target is Azure Container Apps Consumption with 0.25 vCPU, 0.5 GiB memory, and zero minimum replicas. Production remains `max_replicas: 1` until the Phase 11 Azure validation and two-replica deployment gates pass. Table adapters, an identity-only Table client, startup wiring, readiness checks and Azurite tests are implemented in code, but deployed multi-replica shared state is still **Partially implemented**. Single-process deployments use in-memory credit and health state; table mode uses Azure Table Storage for authoritative credit balances and reservations with ETag-based same-partition transactions. Health and cooldown snapshots are timestamped and eventually consistent. Redis may be added later as a cache, but it does not replace the Azure Table Storage source of truth.

## Technology Direction

The preferred stack is Python 3.12+, FastAPI, asynchronous `httpx` (with HTTP/2 and connection limits), Pydantic settings, Docker, Azure Container Apps, Bicep IaC, GitHub Actions, pytest, Ruff, and mypy. All are **Implemented** except multi-worker metrics aggregation, which remains **Planned**.

Google feature helpers remain inside `api/adapters/`: bounded schema validation, ordered tool
history and bounded inline image intake (PNG, opt-in baseline JPEG/static VP8L). Default-off configuration profiles own declared combinations;
credit owns estimates and routing owns eligibility/reservations. Immutable request-local tool/
format context flows to translation and decoders. No conversation cache or native surface exists.
See [feature implementation](../plans/google-ai-studio-tools-multimodal/implementation/index.md).

Opt-in Table quota accounting is **Implemented** locally and independent of credit/health
storage. One bounded atomic group row admits full configured limits across workers;
per-attempt ownership prevents failover from erasing earlier provider consumption. Real
Azurite concurrency/persistence passed; deployed provider admission and clock guarantees
remain unverified. Production remains memory/one.
