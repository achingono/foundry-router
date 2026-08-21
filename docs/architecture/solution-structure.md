# Solution Structure

## Current Repository

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
└── LICENSE
```

No `src/`, `app/`, `tests/`, `infra/`, `.github/workflows/`, `Dockerfile`, or package manifest currently exists.

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
