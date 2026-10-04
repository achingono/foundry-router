# Solution Structure

## Current Repository (Phase 10 template and Phase 11 code implemented; deployed multi-replica Partially implemented pending Azure verification)

```text
foundry-router/
├── AGENTS.md
├── README.md
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── configuration/
│   ├── decisions/
│   ├── development/
│   ├── features/
│   ├── getting-started/
│   ├── operations/
│   ├── plans/
│   └── templates/
├── src/foundry_router/
│   ├── api/
│   ├── auth/
│   ├── backends/
│   ├── config/
│   ├── forwarding/
│   ├── health/
│   ├── logging/
│   ├── metrics/
│   ├── reconciliation/
│   ├── routing/
│   ├── credit.py
│   └── main.py
├── tests/
│   ├── unit/
│   └── integration/
├── .github/workflows/ci.yml
├── infra/
│   ├── main.bicep
│   ├── types/                 # Shared sealed configuration and reference contracts
│   └── modules/               # Identity, observability, scoped grants, conditional Storage
├── Dockerfile
└── pyproject.toml
```

Configuration, authentication, health checks, model listing, backend allow-listing, streaming/non-streaming forwarding, health cooldowns, credit-aware scheduling, Phase 05 modular decomposition, Phase 06 distributed state adapters, Phase 07 IaC, Phase 08 credit-integrity hardening, Phase 10 existing-resource Bicep support, and Phase 11 conditional Storage provisioning/client wiring/Azurite tests are implemented in code. Deployed multi-replica shared state remains Partially implemented pending Azure validation and a two-replica deployment. Multi-worker metrics aggregation remains Planned.

## Target Structure

Typed identity, observability, managed environment and router modules are **Implemented**, along with conditional Storage and scoped access modules. The root retains registry/vault resources and orchestrates module dependencies through typed configs and non-secret refs. Registry/vault extraction is **Design target**; [incremental extraction evidence](../plans/bicep-module-extraction/evidence.md) and [container module evidence](../plans/bicep-container-modules/evidence.md) record synthetic redeployment verification.

The modular implementation decomposes `src/foundry_router/` and adds infrastructure:

```text
foundry-router/
├── src/foundry_router/
│   ├── api/                  # FastAPI routers (openai, admin, health)
│   ├── auth/                 # API key verification & constant-time HMAC
│   ├── backends/             # Restricted HTTP client, limits, HTTP/2
│   ├── config/               # Pydantic settings & validation
│   ├── credit/               # Cycle math, reservations, estimates, scoring
│   ├── forwarding/           # Transport execution, retries, SSE parser
│   ├── health/               # Ephemeral cooldown state tracking
│   ├── logging/              # Redacted structured JSON logging
│   ├── metrics/              # Prometheus telemetry (single-process; multi-process Planned)
│   ├── reconciliation/       # Background billing cost reconciliation
│   ├── state/                # State protocols & Azure Table Storage adapters
│   └── main.py               # Lightweight lifespan & application entrypoint (graceful shutdown)
├── tests/
│   ├── unit/                 # Domain-specific unit test suites
│   ├── integration/          # End-to-end proxy and concurrency tests
│   └── fixtures/             # Mock upstream responses and SSE streams
├── infra/
│   ├── main.bicep            # Azure Container Apps environment & app
│   └── modules/              # Key Vault, Log Analytics, Storage modules
├── .github/workflows/
├── Dockerfile
└── pyproject.toml
```

Feature behavior remains strictly local to its owning boundary.
