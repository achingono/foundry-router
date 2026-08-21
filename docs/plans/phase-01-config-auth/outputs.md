# Phase 01 Outputs

## Mandatory Outputs

| Output | Description | Format |
| --- | --- | --- |
| `pyproject.toml` | Project metadata, dependencies, tool config (ruff, mypy, pytest) | TOML |
| `src/foundry_router/config/__init__.py` | Settings model, validation, loading | Python |
| `src/foundry_router/logging/__init__.py` | Structured JSON logging, redaction processor | Python |
| `src/foundry_router/auth/__init__.py` | ClientAuth, AdminAuth dependencies | Python |
| `src/foundry_router/backends/__init__.py` | AllowedBackendClient with allow-list enforcement | Python |
| `src/foundry_router/main.py` | FastAPI app, lifespan, health endpoints, routing stubs | Python |
| `tests/unit/test_config.py` | Configuration validation tests | Python |
| `tests/unit/test_logging.py` | Logging format and redaction tests | Python |
| `tests/unit/test_auth.py` | Authentication tests | Python |
| `tests/unit/test_backends.py` | Allow-list enforcement tests | Python |
| `tests/unit/test_main.py` | Health endpoints, error handling tests | Python |
| `tests/integration/test_full_flow.py` | End-to-end flow with mocked backend | Python |
| `tests/fixtures/mock_backend.py` | Mock Foundry backend test server | Python |
| `.github/workflows/ci.yml` | CI pipeline: lint, type-check, test, docker build | YAML |
| `Dockerfile` | Multi-stage build, non-root, health check | Dockerfile |
| `.env.example` | Documented environment variable template | Shell |
| `.dockerignore` | Exclude tests, docs, git, local env from image | Text |
| `.gitignore` | Exclude __pycache__, .env, dist, .pytest_cache, etc. | Text |

## Optional Outputs
- `Makefile` or `justfile` for common development commands
- `scripts/dev.sh` for local development with mocked backends

## Output Quality Checklist
- [ ] All mandatory outputs produced
- [ ] All outputs reviewed before gate
- [ ] Evidence log updated with output references
- [ ] Type hints on all public functions/classes
- [ ] Docstrings on all public modules/classes/functions
- [ ] Ruff passes with no errors
- [ ] Mypy passes with strict mode (or documented exceptions)
- [ ] Pytest coverage ≥ 80% for `src/foundry_router/`
- [ ] Docker image builds successfully
- [ ] CI pipeline passes on clean checkout