# Phase 01 Exit Criteria

## Gate Checklist
- [ ] `pyproject.toml` defines all dependencies with pinned versions
- [ ] `src/foundry_router/config/` loads and validates all settings from `docs/configuration/index.md`
- [ ] Startup fails fast with actionable error messages for invalid configuration
- [ ] `ClientAuth` dependency returns 401 for missing/invalid client credentials on `/openai/v1/*`
- [ ] `AdminAuth` dependency returns 401 for missing/invalid admin credentials on `/admin/status`
- [ ] Client and admin authentication use separate credential sets
- [ ] `AllowedBackendClient` rejects requests to non-configured hostnames
- [ ] `AllowedBackendClient` strips sensitive headers before forwarding
- [ ] Structured JSON logs include correlation ID on every request
- [ ] Log redaction removes: Authorization headers, API keys, backend credentials, prompts, model outputs
- [ ] Redaction verified by automated test (log capture + pattern scan)
- [ ] `/health/live` returns 200 OK immediately
- [ ] `/health/ready` returns 200 only when configuration is valid and at least one backend configured
- [ ] All unit tests pass (`pytest tests/unit/`)
- [ ] All integration tests pass (`pytest tests/integration/`)
- [ ] Test coverage ≥ 80% for `src/foundry_router/` (measured by `pytest --cov`)
- [ ] Ruff reports no errors (`ruff check .`)
- [ ] Mypy reports no errors in strict mode (`mypy src/`)
- [ ] Docker image builds (`docker build -t foundry-router:test .`)
- [ ] Docker image runs and `/health/live` responds within 5 seconds
- [ ] CI pipeline (`.github/workflows/ci.yml`) passes on clean checkout
- [ ] No secrets in `.env.example`, Dockerfile, or any committed file
- [ ] Documentation updated: `docs/configuration/index.md` reflects implemented settings; `docs/configuration/security.md` reflects implemented auth/redaction

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Owner | | Pending | |
| Reviewer | | Pending | |
| Approver | | Pending | |