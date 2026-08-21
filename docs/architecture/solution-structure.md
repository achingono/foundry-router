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
├── tests/
├── .github/workflows/ci.yml
├── Dockerfile
└── pyproject.toml
```

`infra/` and the health-aware routing and credit subsystems do not yet exist. Responses and embeddings forwarding is implemented in the API/backend boundaries; retries, failover, and scheduling remain Planned.

## Target Structure

The eventual implementation may use this shape:

```text
app/{api,routing,credit,backends}/
tests/{unit,integration,fixtures}/
infra/{modules,parameters}/
.github/workflows/
Dockerfile
pyproject.toml
```

The exact names may change, but feature behavior should remain local to its owning boundary. Add a structure decision before introducing a new cross-cutting subsystem.
