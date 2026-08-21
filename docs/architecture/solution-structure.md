# Solution Structure

## Current Repository (Partially implemented)

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
│   ├── auth/
│   ├── backends/
│   ├── config/
│   ├── logging/
│   ├── credit.py
│   └── main.py
├── tests/
│   ├── unit/
│   └── integration/
├── .github/workflows/ci.yml
├── Dockerfile
└── pyproject.toml
```

Configuration, authentication, health checks, model listing, backend allow-listing, streaming/non-streaming forwarding, health cooldowns, and credit-aware scheduling are implemented. Decomposition into domain modules, distributed state store adapters, metrics, and `infra/` IaC definitions are Planned for Phases 05–07.

## Target Structure

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
│   ├── metrics/              # Prometheus / OpenTelemetry telemetry
│   ├── reconciliation/       # Background billing cost reconciliation
│   ├── state/                # State protocols & Redis distributed store
│   └── main.py               # Lightweight lifespan & application entrypoint
├── tests/
│   ├── unit/                 # Domain-specific unit test suites
│   ├── integration/          # End-to-end proxy and concurrency tests
│   └── fixtures/             # Mock upstream responses and SSE streams
├── infra/
│   ├── main.bicep            # Azure Container Apps environment & app
│   └── modules/              # Key Vault, Log Analytics, Redis modules
├── .github/workflows/
├── Dockerfile
└── pyproject.toml
```

Feature behavior remains strictly local to its owning boundary.
