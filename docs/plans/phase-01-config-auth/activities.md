# Phase 01 Activities

## Step-By-Step Activities

1. **Scaffold Python project structure**
   - Create `pyproject.toml` with: Python 3.12+, FastAPI, httpx, pydantic, pydantic-settings, python-dotenv, structlog, pytest, pytest-asyncio, httpx-mock, ruff, mypy
   - Create `src/foundry_router/` package with submodules: `config`, `auth`, `logging`, `main`
   - Create `tests/` with `unit/`, `integration/`, `fixtures/`
   - Create `.github/workflows/ci.yml`
   - Create `Dockerfile` (multi-stage, non-root user)
   - Create `.dockerignore`, `.gitignore`, `.env.example`

2. **Implement configuration module (`src/foundry_router/config/`)**
   - Define `Settings` class using `pydantic-settings.BaseSettings`
   - Model all settings from `docs/configuration/index.md`:
     - `backends`: dict of backend configs (endpoint, credential, optional: region; forwarding requires deployment)
     - `models`: dict of model configs with backend pools and weights
     - `client_auth`: API key or JWT validation config
     - `admin_auth`: separate auth config for `/admin/status`
     - `reconciliation_interval_minutes`: 5-15
     - `min_credit_reserve_usd` and `min_credit_reserve_percent`
     - `retry_attempts`, `retry_max_delay_seconds`
     - `log_level`
     - `pricing`: per-model input/output token prices
     - `backend_cycle_start_day`: per-backend day of month (1-28)
     - `protected_emergency_fallback`: bool
   - Add field validators for: positive values, valid URLs, weight sums, cycle day range
   - Implement startup validation that raises clear errors for missing/invalid config
   - Unit tests: valid config, missing required fields, invalid URLs, negative values, weight normalization

3. **Implement logging module (`src/foundry_router/logging/`)**
   - Configure `structlog` for JSON output with correlation ID (request ID)
   - Define log schema: request_id, timestamp, level, logger, event, model, backend, endpoint_type, status, latency_ms, tokens_in, tokens_out, estimated_cost_usd, retry_count, streaming, routing_state, routing_score
   - Create redaction processor: removes `authorization`, `api-key`, `x-api-key`, backend credentials, prompts, completions from log records
   - Unit tests: JSON format, correlation ID propagation, redaction of secrets, non-redaction of safe fields

4. **Implement authentication module (`src/foundry_router/auth/`)**
   - `ClientAuth` dependency: validates `Authorization: Bearer <key>` or `api-key` header against configured client keys
   - `AdminAuth` dependency: separate validation for `/admin/status` (different key set)
   - Return 401 with WWW-Authenticate header on failure
   - Unit tests: valid key, invalid key, missing header, admin vs client key separation

5. **Implement backend allow-list HTTP client (`src/foundry_router/backends/`)**
   - Create `AllowedBackendClient` wrapping `httpx.AsyncClient`
   - On initialization, extract allowed hostnames from `Settings.backends`
   - Intercept requests: reject if target host not in allow-list (raise `SecurityError`)
   - Forward only safe headers (strip `authorization`, `api-key`, `cookie`, custom sensitive headers)
   - Unit tests: allowed backend succeeds, blocked backend rejected, header stripping

6. **Implement main application (`src/foundry_router/main.py`)**
   - Create FastAPI app with lifespan for startup/shutdown
   - Startup: load settings, validate, initialize logging, initialize allowed backend client
   - Health endpoints: `/health/live` (always 200), `/health/ready` (checks config valid, at least one backend configured)
   - Apply `ClientAuth` dependency to `/openai/v1/*` routes (stub routes for now)
   - Apply `AdminAuth` dependency to `/admin/status`
   - Global exception handler: structured error responses, no stack traces in production
   - Unit tests: health endpoints, auth enforcement, error format

7. **Create CI/CD pipeline (`.github/workflows/ci.yml`)**
   - Jobs: lint (ruff), type-check (mypy), unit tests (pytest), integration tests (pytest), docker build
   - Run on PR and main branch
   - Cache pip dependencies
   - Fail on any job failure

8. **Create integration test fixtures (`tests/fixtures/`)**
   - Mock Foundry backend server (FastAPI) that echoes requests, supports streaming
   - Test configuration files for various scenarios

9. **Write integration tests (`tests/integration/`)**
   - Full request flow with mocked backend: auth → validation → forward → response
   - Auth failure returns 401
   - Unknown model returns 404
   - Non-allow-listed backend rejected
   - Logs contain correlation ID and no secrets

## Review Focus
- Configuration validation catches all invalid inputs at startup
- Authentication is enforced on all public endpoints
- No secrets appear in logs (tested explicitly)
- Outbound requests only go to configured backends
- Code follows project conventions (async, type hints, structured logging)
- Test coverage ≥ 80% for implemented modules
- Docker image builds and runs health endpoints
